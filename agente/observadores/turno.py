"""Coleta, a cada pergunta, quem respondeu, em quanto tempo e o veredito (ConcreteObserver).

Base das interfaces: o chat com Rich (painel_rich.py) e o web (interface/web.py) mostram
esses dados junto da resposta.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..nucleo.eventos import Evento, ObservadorConversa, TipoEvento

NOMES = {"tutor": "Tutor", "exemplificador": "Exemplificador",
         "inquiridor": "Inquiridor", "guardiao": "Guardião"}

VEREDITOS = {"aprovado": "revisado pelo Guardião", "corrigido": "corrigido pelo Guardião",
             "codigo_removido": "código removido pela trava"}


@dataclass
class Turno:
    agentes: list[str] = field(default_factory=list)
    veredito: str | None = None
    segundos: float | None = None
    modelo: str | None = None

    def detalhes(self) -> str:
        """Ex.: "qwen2.5:7b · 200 s · revisado pelo Guardião"."""
        partes = [self.modelo or "", f"{self.segundos:.0f} s" if self.segundos is not None else "",
                  VEREDITOS.get(self.veredito or "", "")]
        return " · ".join(p for p in partes if p)

    def rodape(self) -> str:
        """Ex.: "Exemplificador → Guardião · qwen2.5:7b · 200 s"."""
        return " · ".join(p for p in (" → ".join(self.agentes), self.detalhes()) if p)


class ColetorTurno(ObservadorConversa):
    def __init__(self) -> None:
        self.turno = Turno()

    def novo_turno(self) -> None:
        """Chamado pela interface antes de cada pergunta: se a resposta voltar sem chamar o
        modelo (ex.: Ollama fora do ar), não sobram dados da pergunta anterior."""
        self.turno = Turno()

    def atualizar(self, evento: Evento) -> None:
        d = evento.dados
        if evento.tipo is TipoEvento.AGENTE_INICIADO:
            self.turno.agentes = [NOMES.get(a, a) for a in d["agentes"]]
        elif evento.tipo is TipoEvento.REVISAO:
            self.turno.veredito = d["veredito"]
        elif evento.tipo is TipoEvento.TURNO_CONCLUIDO:
            self.turno.segundos = d["segundos"]
            self.turno.modelo = d.get("modelo")
