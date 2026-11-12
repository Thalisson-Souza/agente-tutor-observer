"""Classifica a mensagem do estudante em uma intenção e escolhe o agente que vai responder.

Usa expressões regulares, não o LLM: classificar com o modelo custaria mais uma chamada
(mesmo prompts curtos levaram 30 a 40 s no 7b em CPU), e regras fixas dão sempre o mesmo
resultado para a mesma frase, o que permite testá-las sem o modelo.

Limitação: só reconhece as formulações previstas em REGRAS. Uma paráfrase não coberta
cai em "conceito"; por isso os prompts dos agentes repetem as regras anti-alucinação.
"""

from __future__ import annotations

import dataclasses
import re
import unicodedata

from ..nucleo.intencoes import Intencao as I
from ..nucleo.intencoes import NomeAgente as A
from ..nucleo.intencoes import NomeTarefa as T
from ..nucleo.intencoes import Rota

# Primeira palavra dos nomes de padrões reais (GoF e alguns muito citados), em minúsculas.
# Só a primeira palavra porque padrao_desconhecido() captura uma palavra só:
# "padrão Factory Method" -> "factory". Um "padrão <Nome>" fora daqui é tratado como inventado.
PADROES_CONHECIDOS = {
    "observer", "observador", "factory", "abstract", "builder", "prototype", "singleton",
    "adapter", "bridge", "composite", "decorator", "facade", "flyweight", "proxy",
    "chain", "command", "interpreter", "iterator", "mediator", "memento", "state",
    "strategy", "template", "visitor", "mvc", "publish", "pub", "dependents", "gof",
}

# Qual agente atende cada intenção e que trechos da base ele recebe. O texto da orientação
# (que o modelo lê) fica em agentes/prompts/rotas.yaml, junto com os outros prompts.
ROTAS: dict[I, Rota] = {r.intencao: r for r in [
    Rota(I.CONCEITO, A.TUTOR, T.ESPECIALISTA, ("conceito", "participantes", "consequencias")),
    Rota(I.SELECAO, A.TUTOR, T.ESPECIALISTA, ("conceito", "selecao")),
    Rota(I.FECHAMENTO, A.TUTOR, T.ESPECIALISTA, ("fechamento", "consequencias")),
    # Exemplo e uso incorreto sem Guardião: em 11/11 ele aprovou um exemplo de erro falso no C4
    # e somava ~3 min. A correção veio de ancorar o código na base (seção uso_incorreto).
    Rota(I.EXEMPLO, A.EXEMPLIFICADOR, T.ESPECIALISTA, ("participantes", "exemplo")),
    Rota(I.USO_INCORRETO, A.EXEMPLIFICADOR, T.ESPECIALISTA, ("uso_incorreto",)),
    Rota(I.CONFUSAO, A.INQUIRIDOR, T.ESPECIALISTA, ("confusao", "conceito")),
    Rota(I.EXERCICIO, A.INQUIRIDOR, T.ESPECIALISTA, ("participantes", "selecao"), bloquear_solucao=True),
    # Sem Guardião desde a iteração 10: no caso E1.2 ele levou ~7 min e a falha real (uma
    # afirmação do aluno sem avaliação) vinha da orientação, agora mais específica.
    Rota(I.RESPOSTA_EXERCICIO, A.INQUIRIDOR, T.ESPECIALISTA, ("participantes", "consequencias", "uso_incorreto"),
         bloquear_solucao=True),
    # Sem revisão do Guardião: no teste ele manteve a solução completa e dobrou as chamadas ao modelo.
    # Quem garante a regra aqui é bloquear_solucao, aplicado depois do modelo.
    Rota(I.SOLUCAO_PRONTA, A.INQUIRIDOR, T.ESPECIALISTA, ("participantes", "fechamento"), bloquear_solucao=True),
    Rota(I.INVENTADO, A.GUARDIAO, T.RECUSA, ()),
    # Outro padrão do GoF sem menção ao Observer: o Tutor recusa e, no máximo, cita a relação
    # que a base registra (seção confusao). Antes caía em "conceito" e o modelo explicava o
    # outro padrão (caso E2, iteração 9).
    Rota(I.FORA_ESCOPO, A.TUTOR, T.ESPECIALISTA, ("confusao",)),
    # Afirmação para confirmar vai ao Inquiridor (diagnóstico de concepções erradas): na rota
    # conceito o Tutor corrigia e emendava a aula inteira (caso E4, iteração 10).
    Rota(I.CONFIRMACAO, A.INQUIRIDOR, T.ESPECIALISTA, ("conceito", "participantes", "consequencias", "confusao")),
]}

# A primeira regra que casar vence, e a ordem é proposital: os pedidos de risco vêm antes, e
# as palavras genéricas ("exemplo", "código") ficam por último. Ex.: "dê um exemplo de uso
# equivocado" é uso_incorreto, e "me entregue o código pronto" é solucao_pronta, não exemplo.
# As expressões são aplicadas ao texto normalizado (minúsculo e sem acento): "código" -> "codigo".
REGRAS: list[tuple[I, list[str]]] = [
    (I.INVENTADO, [r"\binvent", r"\bcri(e|ar) um (novo )?padrao", r"\bpadrao chamado\b"]),
    (I.SOLUCAO_PRONTA, [r"codigo (completo|pronto|inteiro)", r"solucao (completa|pronta|inteira)",
                        r"\bpronto\b.*\bcodigo|\bcodigo\b.*\bpronto", r"\b(faca|faz|resolva|resolve) (pra|para) mim",
                        r"\bme (entregue|entrega|de|da) .*\b(solucao|projeto|sistema)"]),
    (I.EXERCICIO, [r"\bexercicio", r"\bpraticar\b", r"\bme (teste|testa)\b", r"\bdesafio", r"\bquiz"]),
    (I.CONFUSAO, [r"confund", r"\bdiferenca", r"\bversus\b", r"\bvs\.?\b", r"\bcompar", r"\bmediator\b",
                  r"pub/?sub", r"publish"]),
    (I.USO_INCORRETO, [r"\berrad", r"\bincorret", r"\bequivocad", r"\bmal (usado|aplicado)", r"anti-?padr",
                       r"\barmadilha", r"\bcuidado"]),
    (I.FECHAMENTO, [r"\blembrar\b", r"\bresum", r"checklist", r"\bfechamento", r"antes de usar"]),
    (I.SELECAO, [r"quando (usar|utilizar|evitar|aplicar|nao usar)", r"melhor escolha", r"\bevitad", r"\bevitar\b",
                 r"\bsituac"]),
    (I.CONFIRMACAO, [r"\b(ne|certo|correto|nao e|nao eh|confere)\s*\?\s*$", r"^e verdade que\b",
                      r"^(estou|to|tou) certo\b", r"\bisso esta (certo|correto)\b"]),
    (I.EXEMPLO, [r"\bexemplo", r"\bcodigo\b", r"\bjava\b", r"\bimplement", r"\bmostr"]),
]

# Outros padrões do GoF, para a rota fora_escopo. Nome normalizado -> nome para exibir.
OUTROS_PADROES = {
    "factory method": "Factory Method", "abstract factory": "Abstract Factory", "builder": "Builder",
    "prototype": "Prototype", "singleton": "Singleton", "adapter": "Adapter", "bridge": "Bridge",
    "composite": "Composite", "decorator": "Decorator", "facade": "Facade", "flyweight": "Flyweight",
    "proxy": "Proxy", "chain of responsibility": "Chain of Responsibility", "command": "Command",
    "interpreter": "Interpreter", "iterator": "Iterator", "mediator": "Mediator", "memento": "Memento",
    "state": "State", "strategy": "Strategy", "template method": "Template Method", "visitor": "Visitor",
}


def outro_padrao(texto_normalizado: str) -> str | None:
    """Nome do outro padrão citado, se a mensagem não mencionar o Observer.
    "Qual a diferença entre Observer e Mediator?" cita o Observer: é confusao, não fora_escopo."""
    if re.search(r"\bobserv(er|ador)", texto_normalizado):
        return None
    for nome, exibir in OUTROS_PADROES.items():
        if re.search(rf"\b{nome}\b", texto_normalizado):
            return exibir
    return None


# Pedidos que valem mesmo no meio de um exercício: o aluno pode tentar obter a resposta pronta.
PRIORITARIAS = (I.INVENTADO, I.SOLUCAO_PRONTA)

# Início típico de um pedido novo. Com exercício pendente, uma mensagem que não começa assim
# (nem termina em "?") é lida como resposta, mesmo contendo "código" ou "diferença".
INICIO_DE_PEDIDO = re.compile(
    r"^(o que|como|por ?que|qual|quais|quando|onde|explique|me explique|mostre|me mostre|de um|"
    r"quero|gostaria|pode|poderia|agora|outro|outra|proximo|proxima)\b")


def normalizar(texto: str) -> str:
    return _sem_acento(texto).lower().strip()


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def padrao_desconhecido(texto: str) -> str | None:
    """Retorna o nome se a mensagem citar 'padrão <Nome>' que não é um padrão conhecido.

    Exige inicial maiúscula para não confundir com texto comum ("o padrão de projeto",
    "o padrão é..."). Limitação: um nome inventado escrito em minúsculas não é detectado.
    """
    # Usa _sem_acento e não normalizar(): a maiúscula inicial é o que identifica um nome.
    for m in re.finditer(r"\b[Pp]adr(?:ao|oes)\s+(?:de projeto\s+)?(?:chamado\s+)?([A-Z][\w-]*)", _sem_acento(texto)):
        nome = m.group(1)
        if nome.lower() not in PADROES_CONHECIDOS:
            return nome
    return None


def parece_pedido_novo(texto_normalizado: str) -> bool:
    return texto_normalizado.endswith("?") or bool(INICIO_DE_PEDIDO.match(texto_normalizado))


def _primeira_regra(t: str, intencoes: tuple[I, ...] | None = None) -> I | None:
    for intencao, padroes in REGRAS:
        if intencoes is not None and intencao not in intencoes:
            continue
        if any(re.search(p, t) for p in padroes):
            return intencao
    return None


def classificar(texto: str, exercicio_pendente: bool = False) -> Rota:
    """Escolhe a rota da mensagem.

    Com exercício pendente e mensagem que não parece pedido novo, só as intenções
    PRIORITARIAS são verificadas; o resto é resposta ao exercício. Outro padrão do GoF
    citado sem o Observer vai para fora_escopo. Sem palavra-chave, a mensagem é tratada
    como pergunta conceitual (a orientação de conceito cobre fora do tema e afirmação errada).
    """
    nome = padrao_desconhecido(texto)
    if nome:
        return dataclasses.replace(ROTAS[I.INVENTADO], detalhe=nome)
    t = normalizar(texto)
    if exercicio_pendente and not parece_pedido_novo(t):
        return ROTAS[_primeira_regra(t, PRIORITARIAS) or I.RESPOSTA_EXERCICIO]
    prioritaria = _primeira_regra(t, PRIORITARIAS)
    if prioritaria:
        return ROTAS[prioritaria]
    outro = outro_padrao(t)
    if outro:
        return dataclasses.replace(ROTAS[I.FORA_ESCOPO], detalhe=outro)
    return ROTAS[_primeira_regra(t) or I.CONCEITO]
