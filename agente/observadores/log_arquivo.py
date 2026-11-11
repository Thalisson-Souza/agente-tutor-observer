"""Log de eventos em arquivo (ConcreteObserver)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..nucleo.eventos import Evento, ObservadorConversa


class LogArquivo(ObservadorConversa):
    """Registra todos os eventos em JSONL (evidência para o relatório e depuração)."""

    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)

    def atualizar(self, evento: Evento) -> None:
        registro = {"quando": datetime.now().isoformat(timespec="seconds"), "tipo": evento.tipo.value,
                    **evento.dados}
        with self.arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
