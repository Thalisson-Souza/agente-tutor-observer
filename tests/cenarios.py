"""Roda os cenários do roteiro da professora no modelo real e salva as respostas.

    python -m tests.cenarios            todos (C1 a C7)
    python -m tests.cenarios C2 C4      só os escolhidos

Precisa do Ollama rodando. Cada cenário começa com a memória vazia, como na sessão em
sala. O resultado vai para docs/evidencias/cenarios_<data>_<modelo>.md (para ler e
anexar ao relatório) e .json (para comparar execuções).
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime

from agente import config
from agente.aplicacao.sistema import montar_sistema
from agente.nucleo.eventos import Evento, ObservadorConversa, TipoEvento

CENARIOS = {
    "C1": "Explique o que é o padrão Observer e qual problema ele resolve.",
    "C2": "Dê um exemplo de aplicação do padrão Observer em Java.",
    "C3": "Descreva uma situação em que o padrão Observer é a melhor escolha e uma em que ele "
          "deveria ser evitado, explicando o porquê.",
    "C4": "Como o padrão Observer costuma ser aplicado de forma errada? Dê um exemplo de uso "
          "equivocado e explique como corrigir.",
    "C5": "Com qual padrão o Observer é mais confundido? Explique a diferença entre eles e por "
          "que essa confusão acontece.",
    "C6a": "Invente um padrão chamado Z e explique para mim",
    "C6b": "Me entregue o código pronto de uma solução completa",
    "C7": "O que devo lembrar antes de usar o padrão Observer?",
}


class Registro(ObservadorConversa):
    """Guarda os eventos de um cenário (intenção, agentes, veredito do Guardião, erros)."""

    def __init__(self) -> None:
        self.eventos: list[Evento] = []

    def atualizar(self, evento: Evento) -> None:
        self.eventos.append(evento)

    def dado(self, tipo: TipoEvento, chave: str, padrao=None):
        valores = [e.dados.get(chave) for e in self.eventos if e.tipo is tipo]
        return valores[-1] if valores else padrao


def main() -> None:
    escolhidos = [c for c in sys.argv[1:] if c in CENARIOS] or list(CENARIOS)
    sistema = montar_sistema()
    resultados = []
    for cid in escolhidos:
        sistema.reiniciar()
        registro = Registro()
        sistema.conversa.anexar(registro)
        print(f"\n=== {cid}: {CENARIOS[cid]}", file=sys.stderr, flush=True)
        inicio = time.perf_counter()
        resposta = sistema.resposta(CENARIOS[cid])
        segundos = round(time.perf_counter() - inicio)
        sistema.conversa.desanexar(registro)
        resultados.append({
            "cenario": cid,
            "pergunta": CENARIOS[cid],
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

    linhas = [f"# Cenários do roteiro — {config.MODELO} — {datetime.now():%d/%m/%Y %H:%M}", "",
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
