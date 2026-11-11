"""Carrega a base de conhecimento do Observer, separada por seções '## [id]'."""

import re
from functools import lru_cache
from pathlib import Path

ARQUIVO = Path(__file__).with_name("observer.md")


@lru_cache(maxsize=1)
def secoes() -> dict[str, str]:
    texto = ARQUIVO.read_text(encoding="utf-8")
    partes = re.split(r"^## \[(\w+)\]\s*$", texto, flags=re.MULTILINE)
    # partes = [cabeçalho, id1, conteúdo1, id2, conteúdo2, ...]
    return {partes[i]: partes[i + 1].strip() for i in range(1, len(partes), 2)}


def trecho(ids: tuple[str, ...]) -> str:
    base = secoes()
    return "\n\n".join(base[i] for i in ids if i in base) or "(sem trecho específico)"
