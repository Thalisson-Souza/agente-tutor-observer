"""Verificações em Python aplicadas à resposta final, depois do modelo.

Existem porque instrução no prompt não bastou: no teste do cenário 6b ("me entregue o
código pronto"), o 7b escreveu que não entregaria a solução e a entregou em seguida, e o
Guardião manteve o código (sdd/iteracoes.md, iteração 2). Uma regra em código vale
sempre, independentemente do modelo.
"""

from __future__ import annotations

import re

BLOCO = re.compile(r"```[^\n]*\n(.*?)(?:```|\Z)", re.DOTALL)
# ")" seguido de "{" é o corpo de um método ou construtor; uma interface só tem assinaturas
# terminadas em ";". Também pega "throws X {".
CORPO_DE_METODO = re.compile(r"\)\s*(throws\s+[\w.,\s]+)?\{")
MAX_LINHAS_ASSINATURA = 8      # uma interface Observer/Subject cabe com folga

AVISO = "[código removido: esta parte é para você escrever]"

# Resposta usada quando, sem o código, sobra pouco texto útil. Escrita à mão a partir da
# base de conhecimento, então não depende do modelo.
ROTEIRO_PADRAO = """Não vou te entregar a solução pronta: escrever o código é o que fixa o padrão. Mas vamos construir juntos, passo a passo.

1. **Identifique os papéis.** No seu problema, qual objeto muda de estado (Subject) e quais objetos precisam reagir a essa mudança (Observers)?
2. **Escreva a interface Observer** com um único método de atualização. Ele vai receber os dados da mudança (modelo push) ou o próprio sujeito (modelo pull)?
3. **Escreva o Subject** com três responsabilidades: anexar, desanexar e notificar observadores. Que estrutura guarda a lista de observadores?
4. **No ConcreteSubject**, decida em que momento chamar notificar(): só depois de o estado estar consistente.
5. **Implemente um ConcreteObserver** e teste: anexe dois observadores, mude o estado e veja os dois reagirem. Depois desanexe um e repita.

Por qual passo você quer começar? Me mostre sua tentativa da interface Observer que eu te ajudo a revisar."""


def _e_implementacao(codigo: str) -> bool:
    linhas = [l for l in codigo.strip().splitlines() if l.strip()]
    return len(linhas) > MAX_LINHAS_ASSINATURA or bool(CORPO_DE_METODO.search(codigo))


def sem_solucao_pronta(texto: str) -> tuple[str, bool]:
    """Remove blocos de código com implementação, mantendo assinaturas curtas de interface.

    Devolve (texto, alterado). Se, sem o código, sobrar pouco texto, usa ROTEIRO_PADRAO.
    Limitação: só vê código entre ``` (o formato que os prompts pedem); código solto no
    texto passa.
    """
    alterado = False

    def trocar(m: re.Match) -> str:
        nonlocal alterado
        if _e_implementacao(m.group(1)):
            alterado = True
            return AVISO
        return m.group(0)

    novo = BLOCO.sub(trocar, texto)
    if not alterado:
        return texto, False
    # Texto do modelo que sobra fora dos avisos; abaixo disso a resposta não guia ninguém.
    restante = re.sub(re.escape(AVISO), "", novo)
    if len(restante.strip()) < 300:
        return ROTEIRO_PADRAO, True
    return novo, True
