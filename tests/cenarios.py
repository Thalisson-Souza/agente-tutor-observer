"""Roda cenários no modelo real e salva as respostas.

    python -m tests.cenarios              roteiro da professora (C1 a C7)
    python -m tests.cenarios extras       casos-limite (E1 a E4)
    python -m tests.cenarios dialogos     respostas do aluno à pergunta do tutor (D1 a D8)
    python -m tests.cenarios C2 E1 D2     só os escolhidos

Precisa do Ollama rodando. Cada cenário começa com a memória vazia, como na sessão em
sala; um cenário com várias mensagens (ex.: E1) as envia em sequência, na mesma
conversa. Os diálogos começam com um turno anterior escrito à mão (`contexto`), para a
pergunta do tutor ser sempre a mesma e o teste ser comparável entre execuções.

Cada cenário pode ter verificações automáticas (intenção esperada, expressões que devem ou
não aparecer). Elas não substituem a leitura: só apontam regressões óbvias ao ajustar prompts. O resultado vai para docs/evidencias/cenarios_<data>_<modelo>.md (para ler e
anexar ao relatório) e .json (para comparar execuções).
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime

from agente import config
from agente.aplicacao.sistema import montar_sistema
from agente.interface.roteiro import PERGUNTAS
from agente.nucleo.eventos import Evento, ObservadorConversa, TipoEvento

@dataclass(frozen=True)
class Cenario:
    mensagens: list[str]
    # Turno anterior inventado (pergunta do aluno, resposta do tutor) posto na memória antes
    # da primeira mensagem, sem chamar o modelo.
    contexto: tuple[str, str] | None = None
    intencao: str | None = None          # intenção esperada da ÚLTIMA mensagem
    deve: tuple[str, ...] = ()           # regex (sem diferenciar maiúsculas) que devem aparecer
    nao_deve: tuple[str, ...] = ()       # regex que não podem aparecer


INTENCOES_ROTEIRO = {"C1": "conceito", "C2": "exemplo", "C3": "selecao", "C4": "uso_incorreto",
                     "C5": "confusao", "C6a": "inventado", "C6b": "solucao_pronta", "C7": "fechamento"}
ROTEIRO: dict[str, Cenario] = {cid: Cenario([p], intencao=INTENCOES_ROTEIRO.get(cid))
                               for cid, p in PERGUNTAS.items()}

# Casos-limite que as outras duplas podem tentar além do roteiro.
EXTRAS: dict[str, Cenario] = {
    # Ciclo exercício -> resposta errada -> diagnóstico: exercita memória e feedback.
    "E1": Cenario(["Quero praticar com um exercício sobre o Observer.",
                   "Acho que a estação é o observador e os painéis são o Subject, e a estação "
                   "chama cada painel direto pelo nome da classe."], intencao="resposta_exercicio"),
    "E2": Cenario(["Me explique o padrão Strategy."], intencao="fora_escopo"),
    "E3": Cenario(["Qual é a capital da França?"], intencao="conceito", nao_deve=(r"\bparis\b",)),
    "E4": Cenario(["O Observer é um padrão criacional, né?"], intencao="confirmacao",
                  deve=(r"comportamental",)),
}


def _turno(pergunta_tutor: str) -> tuple[str, str]:
    """Turno anterior padrão: uma explicação curta terminando com a pergunta do tutor."""
    return ("O que é o Observer?",
            "O Observer define uma dependência um-para-muitos: quando o subject muda de estado, "
            "todos os observadores são notificados e atualizados.\n\n" + pergunta_tutor)


# Mesma classe chamada de Subject e de ConcreteSubject (ou Observer e ConcreteObserver) na
# explicação do exemplo: Subject e Observer são as interfaces (testes D6/D7, 13/11).
PAPEL_REPETIDO = (r"(?<!Concrete)Subject\W{0,4}\(`?(\w+)`?\)[\s\S]*ConcreteSubject\W{0,4}\(`?\1`?\)",
                  r"(?<!Concrete)Observer\W{0,4}\(`?(\w+)`?\)[\s\S]*ConcreteObserver\W{0,4}\(`?\1`?\)")

# Os quatro papéis do GoF têm de ser nomeados no exemplo (no C2 de 13/11, 18:26, nenhum foi).
PAPEIS = (r"(?<!Concrete)Subject", r"(?<!Concrete)Observer\b", r"ConcreteSubject", r"ConcreteObserver")


# Respostas do aluno à pergunta com que o tutor terminou o turno (iteração 15). Cobrem o
# diagnóstico de erros da rubrica: resposta certa, errada, parcial, "não sei", aceitar
# convite, e pedidos novos que não podem ser lidos como resposta.
DIALOGOS: dict[str, Cenario] = {
    "D1": Cenario(["o ConcreteSubject"], _turno(
        "Qual participante armazena o estado de interesse e notifica os observadores quando ele muda?"),
        intencao="resposta_pergunta", deve=(r"acert|corret|\bcerto",), nao_deve=(r"parcial|em parte|errou",)),
    # Confusão clássica: Update é do Observer; quem notifica é o Notify, do Subject.
    "D2": Cenario(["o update"], _turno(
        "Qual operação do Subject é chamada para notificar os observadores quando o estado muda?"),
        intencao="resposta_pergunta", deve=(r"\bnotify\b", r"err|incorret|n[ãa]o (está|esta) cert|n[ãa]o do subject"),
        nao_deve=(r"(resposta|você) est[áa] corret", r"^\W*corret", r"em parte|parcial")),
    "D3": Cenario(["anexar e desanexar"], _turno(
        "Quais são as três operações que o Subject oferece aos observadores?"),
        intencao="resposta_pergunta", deve=(r"\bnotify\b|notific", r"parte|parcial|falt|incomplet")),
    "D4": Cenario(["sim, eles se comunicam entre si"], _turno(
        "No Observer, um observador conhece os outros observadores?"),
        intencao="resposta_pergunta", deve=(r"err|incorret|n[ãa]o (conhec|sabe)",)),
    "D5": Cenario(["não sei"], _turno(
        "No modelo push, quem decide quais dados vão na notificação: o subject ou o observador?"),
        intencao="nao_sei", deve=(r"\bsubject\b",), nao_deve=(r"acertou|errou|qual (é )?a sua resposta",)),
    "D6": Cenario(["sim"], _turno("Quer ver um exemplo em Java?"), intencao="exemplo",
                  deve=(r"```java", *PAPEIS), nao_deve=PAPEL_REPETIDO),
    # Pedidos novos com pergunta pendente: têm de seguir a rota normal.
    "D7": Cenario(["Dê um exemplo em Java do Observer."], _turno("Quer saber mais sobre os participantes?"),
                  intencao="exemplo", deve=PAPEIS, nao_deve=PAPEL_REPETIDO),
    "D8": Cenario(["me dá o código pronto"], _turno("Quem seria o subject no seu sistema?"),
                  intencao="solucao_pronta"),
}

ROTEIRO["C2"] = Cenario(ROTEIRO["C2"].mensagens, intencao="exemplo", deve=PAPEIS, nao_deve=PAPEL_REPETIDO)

CENARIOS: dict[str, Cenario] = {**ROTEIRO, **EXTRAS, **DIALOGOS}
GRUPOS = {"extras": EXTRAS, "dialogos": DIALOGOS}


def verificar(cenario: Cenario, intencao: str | None, resposta: str) -> list[str]:
    """Falhas das verificações automáticas da última mensagem; lista vazia = passou."""
    falhas = []
    if cenario.intencao and intencao != cenario.intencao:
        falhas.append(f"intenção {intencao}, esperada {cenario.intencao}")
    falhas += [f"faltou /{p}/" for p in cenario.deve if not re.search(p, resposta, re.I | re.M)]
    falhas += [f"apareceu /{p}/" for p in cenario.nao_deve if re.search(p, resposta, re.I | re.M)]
    return falhas


class Registro(ObservadorConversa):
    """Guarda os eventos de um turno (intenção, agentes, veredito do Guardião, erros)."""

    def __init__(self) -> None:
        self.eventos: list[Evento] = []

    def atualizar(self, evento: Evento) -> None:
        self.eventos.append(evento)

    def dado(self, tipo: TipoEvento, chave: str, padrao=None):
        valores = [e.dados.get(chave) for e in self.eventos if e.tipo is tipo]
        return valores[-1] if valores else padrao


def escolher(argumentos: list[str]) -> list[str]:
    ids = [c for a in argumentos for c in (GRUPOS[a] if a in GRUPOS else [a]) if c in CENARIOS]
    return ids or list(ROTEIRO)


def main() -> None:
    sistema = montar_sistema()
    resultados = []
    for cid in escolher(sys.argv[1:]):
        sistema.reiniciar()
        cenario = CENARIOS[cid]
        if cenario.contexto:
            estudante, tutor = cenario.contexto
            sistema.memoria.atualizar(Evento(TipoEvento.TURNO_CONCLUIDO, {
                "pergunta": estudante, "resposta": tutor, "intencao": "conceito"}))
        for n, pergunta in enumerate(cenario.mensagens, start=1):
            registro = Registro()
            sistema.conversa.anexar(registro)
            print(f"\n=== {cid} ({n}): {pergunta}", file=sys.stderr, flush=True)
            inicio = time.perf_counter()
            resposta = sistema.resposta(pergunta)
            segundos = round(time.perf_counter() - inicio)
            sistema.conversa.desanexar(registro)
            resultados.append({
                "cenario": cid if len(cenario.mensagens) == 1 else f"{cid}.{n}",
                "pergunta": pergunta,
                "intencao": registro.dado(TipoEvento.PERGUNTA_RECEBIDA, "intencao"),
                "agentes": registro.dado(TipoEvento.AGENTE_INICIADO, "agentes", []),
                "vereditos": [e.dados["veredito"] for e in registro.eventos if e.tipo is TipoEvento.REVISAO],
                "erro": registro.dado(TipoEvento.ERRO, "erro"),
                "segundos": segundos,
                "resposta": resposta,
            })
        ultimo = resultados[-1]
        ultimo["falhas"] = verificar(cenario, ultimo["intencao"], ultimo["resposta"])
        print("    verificação: " + ("ok" if not ultimo["falhas"] else "; ".join(ultimo["falhas"])),
              file=sys.stderr, flush=True)

    pasta = config.RAIZ / "docs" / "evidencias"
    pasta.mkdir(parents=True, exist_ok=True)
    # Nome montado como texto: com Path.with_suffix, o ponto de "qwen2.5" virava extensão.
    nome = f"cenarios_{datetime.now():%Y-%m-%d_%H%M}_{config.MODELO.replace(':', '-')}"
    json_, md = pasta / f"{nome}.json", pasta / f"{nome}.md"
    json_.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    linhas = [f"# Cenários — {config.MODELO} — {datetime.now():%d/%m/%Y %H:%M}", "",
              "| Cenário | Intenção | Agentes | Revisão | Tempo | Verificação automática |",
              "|---|---|---|---|---|---|"]
    for r in resultados:
        checagem = "—" if "falhas" not in r else ("ok" if not r["falhas"] else "; ".join(r["falhas"]))
        linhas.append(f"| {r['cenario']} | {r['intencao']} | {' → '.join(r['agentes'])} | "
                      f"{', '.join(r['vereditos']) or '—'} | {r['segundos']} s | {checagem} |")
    for r in resultados:
        linhas += ["", f"## {r['cenario']}", ""]
        cid = r["cenario"].split(".")[0]
        if CENARIOS[cid].contexto and r["cenario"] in (cid, f"{cid}.1"):
            linhas += [f"**Pergunta anterior do tutor (contexto fixo):** "
                       f"{CENARIOS[cid].contexto[1].splitlines()[-1]}", ""]
        linhas += [f"**Pergunta:** {r['pergunta']}", ""]
        if r["erro"]:
            linhas += [f"**Erro registrado:** `{r['erro']}`", ""]
        linhas.append(r["resposta"])
    md.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"\nSalvo em {md} e {json_.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
