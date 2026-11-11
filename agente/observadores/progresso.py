"""Indicador de progresso no terminal (ConcreteObserver)."""

from __future__ import annotations

import sys

from ..nucleo.eventos import Evento, ObservadorConversa, TipoEvento


class IndicadorProgresso(ObservadorConversa):
    """Mostra qual agente está trabalhando, pois uma resposta pode levar minutos.

    Escreve em stderr para não misturar com a resposta em stdout: quem redireciona a
    saída da CLI (ex.: script de cenários) recebe só o texto do tutor.
    """

    NOMES = {"tutor": "Tutor do conceito", "exemplificador": "Exemplificador",
             "inquiridor": "Inquiridor", "guardiao": "Guardião"}

    def atualizar(self, evento: Evento) -> None:
        if evento.tipo is TipoEvento.AGENTE_INICIADO:
            agentes = " → ".join(self.NOMES.get(a, a) for a in evento.dados["agentes"])
            print(f"  [{evento.dados['intencao']}] consultando: {agentes} ...", file=sys.stderr, flush=True)
        elif evento.tipo is TipoEvento.TURNO_CONCLUIDO:
            print(f"  (respondido em {evento.dados['segundos']:.0f}s)", file=sys.stderr, flush=True)
