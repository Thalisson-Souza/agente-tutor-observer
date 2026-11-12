"""Animação de status no chat com Rich (ConcreteObserver).

Herda de ColetorTurno os dados do painel (agentes, tempo, veredito) e acrescenta a animação
"X trabalhando... N s" enquanto o modelo responde.
"""

from __future__ import annotations

import time

from rich.console import Console
from rich.status import Status
from rich.text import Text

from ..nucleo.eventos import Evento, TipoEvento
from .turno import ColetorTurno


class _Cronometro:
    """Texto da animação. O Rich chama __rich__ a cada atualização da tela, então o tempo
    corre sozinho enquanto a chamada ao modelo bloqueia, sem thread no nosso código."""

    def __init__(self, agentes: list[str]) -> None:
        self.rotulo = " → ".join(agentes)
        self.inicio = time.monotonic()

    def __rich__(self) -> Text:
        return Text(f"{self.rotulo} trabalhando... {time.monotonic() - self.inicio:.0f} s", style="cyan")


class PainelRich(ColetorTurno):
    def __init__(self, console: Console) -> None:
        super().__init__()
        self.console = console
        self._status: Status | None = None

    def atualizar(self, evento: Evento) -> None:
        super().atualizar(evento)
        if evento.tipo is TipoEvento.AGENTE_INICIADO:
            self.parar()
            self._status = self.console.status(_Cronometro(self.turno.agentes), spinner="dots")
            self._status.start()
        elif evento.tipo in (TipoEvento.TURNO_CONCLUIDO, TipoEvento.ERRO):
            self.parar()

    def parar(self) -> None:
        """Também chamado pelo chat se a resposta for interrompida (Ctrl+C), para a animação
        não continuar rodando por cima do terminal."""
        if self._status is not None:
            self._status.stop()
            self._status = None
