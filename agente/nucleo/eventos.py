"""O próprio sistema usa o padrão Observer para divulgar o que acontece na conversa.

- Conversa é o Subject (ConcreteSubject): mantém a lista de observadores e os notifica.
- ObservadorConversa é a interface Observer.
- Memória, log em arquivo e indicador de progresso são ConcreteObservers (pacote observadores/).

Assim, a fachada do tutor (aplicacao/sistema.py) não conhece quem reage aos eventos: adicionar
um novo observador (ex.: métricas de tempo) não exige mudar o núcleo.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)


class TipoEvento(str, Enum):
    PERGUNTA_RECEBIDA = "pergunta_recebida"   # dados: pergunta, intencao
    AGENTE_INICIADO = "agente_iniciado"       # dados: intencao, agentes
    REVISAO = "revisao"                       # dados: veredito, revisao
    TURNO_CONCLUIDO = "turno_concluido"       # dados: pergunta, resposta, intencao, segundos, modelo
    ERRO = "erro"                             # dados: pergunta, erro


@dataclass(frozen=True)
class Evento:
    tipo: TipoEvento
    dados: dict[str, Any] = field(default_factory=dict)


class ObservadorConversa(ABC):      # Observer
    @abstractmethod
    def atualizar(self, evento: Evento) -> None: ...


class Conversa:                     # Subject / ConcreteSubject
    def __init__(self) -> None:
        self._observadores: list[ObservadorConversa] = []

    def anexar(self, observador: ObservadorConversa) -> None:
        if observador not in self._observadores:
            self._observadores.append(observador)

    def desanexar(self, observador: ObservadorConversa) -> None:
        if observador in self._observadores:
            self._observadores.remove(observador)

    def notificar(self, tipo: TipoEvento, **dados: Any) -> None:
        evento = Evento(tipo, dados)
        # Itera sobre uma cópia: se um observador se desanexar dentro de atualizar(), a lista
        # original muda e a iteração pularia elementos (armadilha clássica do Observer).
        for observador in list(self._observadores):
            try:
                observador.atualizar(evento)
            except Exception:
                # Um observador com defeito não pode impedir a resposta ao estudante nem a
                # notificação dos demais, mas a falha precisa aparecer (ex.: memória quebrada).
                log.warning("observador %s falhou ao tratar %s", type(observador).__name__,
                            evento.tipo.value, exc_info=True)
