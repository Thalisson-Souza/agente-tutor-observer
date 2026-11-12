"""Roda cenários no modelo real e salva as respostas.

    python -m tests.cenarios              roteiro da professora (C1 a C7)
    python -m tests.cenarios extras       casos-limite (E1 a E4)
    python -m tests.cenarios C2 E1        só os escolhidos

Precisa do Ollama rodando. Cada cenário começa com a memória vazia, como na sessão em
sala; um cenário com várias mensagens (ex.: E1) as envia em sequência, na mesma
conversa. O resultado vai para docs/evidencias/cenarios_<data>_<modelo>.md (para ler e
anexar ao relatório) e .json (para comparar execuções).
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime

from agente import config
from agente.aplicacao.sistema import montar_sistema
from agente.interface.roteiro import PERGUNTAS
from agente.nucleo.eventos import Evento, ObservadorConversa, TipoEvento

ROTEIRO: dict[str, list[str]] = {cid: [pergunta] for cid, pergunta in PERGUNTAS.items()}

# Casos-limite que as outras duplas podem tentar além do roteiro.
EXTRAS: dict[str, list[str]] = {
    # Ciclo exercício -> resposta errada -> diagnóstico: exercita memória e feedback.
    "E1": ["Quero praticar com um exercício sobre o Observer.",
           "Acho que a estação é o observador e os painéis são o Subject, e a estação "
           "chama cada painel direto pelo nome da classe."],
    "E2": ["Me explique o padrão Strategy."],
    "E3": ["Qual é a capital da França?"],
    "E4": ["O Observer é um padrão criacional, né?"],
}

CENARIOS = {**ROTEIRO, **EXTRAS}


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
    if "extras" in argumentos:
        return list(EXTRAS)
    return [c for c in argumentos if c in CENARIOS] or list(ROTEIRO)


def main() -> None:
    sistema = montar_sistema()
    resultados = []
    for cid in escolher(sys.argv[1:]):
        sistema.reiniciar()
        for n, pergunta in enumerate(CENARIOS[cid], start=1):
            registro = Registro()
            sistema.conversa.anexar(registro)
            print(f"\n=== {cid} ({n}): {pergunta}", file=sys.stderr, flush=True)
            inicio = time.perf_counter()
            resposta = sistema.resposta(pergunta)
            segundos = round(time.perf_counter() - inicio)
            sistema.conversa.desanexar(registro)
            resultados.append({
                "cenario": cid if len(CENARIOS[cid]) == 1 else f"{cid}.{n}",
                "pergunta": pergunta,
                "intencao": registro.dado(TipoEvento.PERGUNTA_RECEBIDA, "intencao"),
                "agentes": registro.dado(TipoEvento.AGENTE_INICIADO, "agentes", []),
                "vereditos": [e.dados["veredito"] for e in registro.eventos if e.tipo is TipoEvento.REVISAO],
                "erro": registro.dado(TipoEvento.ERRO, "erro"),
                "segundos": segundos,
                "resposta": resposta,
            })

    pasta = config.RAIZ / "docs" / "evidencias"
    pasta.mkdir(parents=True, exist_ok=True)
    # Nome montado como texto: com Path.with_suffix, o ponto de "qwen2.5" virava extensão.
    nome = f"cenarios_{datetime.now():%Y-%m-%d_%H%M}_{config.MODELO.replace(':', '-')}"
    json_, md = pasta / f"{nome}.json", pasta / f"{nome}.md"
    json_.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    linhas = [f"# Cenários — {config.MODELO} — {datetime.now():%d/%m/%Y %H:%M}", "",
              "| Cenário | Intenção | Agentes | Revisão | Tempo |", "|---|---|---|---|---|"]
    for r in resultados:
        linhas.append(f"| {r['cenario']} | {r['intencao']} | {' → '.join(r['agentes'])} | "
                      f"{', '.join(r['vereditos']) or '—'} | {r['segundos']} s |")
    for r in resultados:
        linhas += ["", f"## {r['cenario']}", "", f"**Pergunta:** {r['pergunta']}", ""]
        if r["erro"]:
            linhas += [f"**Erro registrado:** `{r['erro']}`", ""]
        linhas.append(r["resposta"])
    md.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"\nSalvo em {md} e {json_.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
