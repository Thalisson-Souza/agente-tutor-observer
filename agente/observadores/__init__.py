"""ConcreteObservers da conversa: reagem aos eventos de nucleo/eventos.py.

Cada um em seu arquivo; para adicionar outro (ex.: métricas de tempo), basta criar a classe
e anexá-la em aplicacao/sistema.py:montar_sistema(), sem mudar o resto do sistema.
"""

from .log_arquivo import LogArquivo
from .memoria import Memoria
from .progresso import IndicadorProgresso

__all__ = ["IndicadorProgresso", "LogArquivo", "Memoria"]
