"""Cria os agentes e as tarefas do CrewAI a partir dos prompts em prompts/*.yaml.

Os prompts ficam em YAML, fora do código, porque o relatório exige o texto integral de cada
um: o arquivo é a fonte única, sem cópia que possa ficar desatualizada.
"""

from __future__ import annotations

from pathlib import Path

from enum import Enum

import yaml

from .. import config  # noqa: F401  tem que vir antes do crewai (ver telemetria em config.py)
from ..nucleo.erros import ErroDeConfiguracao
from ..nucleo.intencoes import Intencao, NomeAgente, NomeTarefa

from crewai import LLM, Agent, Task  # noqa: E402

PASTA_PROMPTS = Path(__file__).with_name("prompts")
CAMPOS_AGENTE = ("role", "goal", "backstory")
CAMPOS_TAREFA = ("description", "expected_output")
CAMPOS_ROTA = ("orientacao",)


def _carregar(arquivo: Path, chaves: type[Enum], campos: tuple[str, ...]) -> dict:
    """Lê o YAML e exige uma entrada por valor do Enum, com todos os campos preenchidos."""
    try:
        dados = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as erro:
        raise ErroDeConfiguracao(f"não foi possível ler {arquivo.name}: {erro}") from erro
    for chave in chaves:
        if chave.value not in dados:
            raise ErroDeConfiguracao(f"{arquivo.name}: falta a entrada '{chave.value}'")
        faltando = [c for c in campos if not str(dados[chave.value].get(c, "")).strip()]
        if faltando:
            raise ErroDeConfiguracao(f"{arquivo.name}: '{chave.value}' sem {', '.join(faltando)}")
    return dados


class FabricaAgentes:
    def __init__(self, llm: LLM, pasta: Path = PASTA_PROMPTS) -> None:
        prompts = _carregar(pasta / "agentes.yaml", NomeAgente, CAMPOS_AGENTE)
        self._tarefas = _carregar(pasta / "tarefas.yaml", NomeTarefa, CAMPOS_TAREFA)
        self._rotas = _carregar(pasta / "rotas.yaml", Intencao, CAMPOS_ROTA)
        # Um único LLM é compartilhado (injetado) por todos os agentes: o Ollama mantém um só
        # modelo carregado na RAM. allow_delegation=False impede um agente de acionar outro
        # por conta própria, o que geraria chamadas extras; max_iter=3 limita as tentativas
        # internas do agente, e cada uma é uma chamada lenta ao modelo.
        self._agentes = {
            nome: Agent(role=prompts[nome.value]["role"].strip(), goal=prompts[nome.value]["goal"].strip(),
                        backstory=prompts[nome.value]["backstory"], llm=llm,
                        allow_delegation=False, verbose=False, max_iter=3)
            for nome in NomeAgente
        }

    def agente(self, nome: NomeAgente) -> Agent:
        return self._agentes[nome]

    def orientacao(self, intencao: Intencao, detalhe: str = "") -> str:
        # replace e não str.format: o texto pode ganhar chaves (ex.: código Java) sem quebrar.
        texto = self._rotas[intencao.value]["orientacao"].strip()
        return texto.replace("{detalhe}", detalhe or "nenhum nome citado")

    def tarefa(self, nome: NomeTarefa, agente: NomeAgente, contexto: list[Task] | None = None) -> Task:
        """Cria uma Task nova a cada turno: o CrewAI guarda a saída na própria Task."""
        t = self._tarefas[nome.value]
        extra = {"context": contexto} if contexto else {}
        return Task(description=t["description"], expected_output=t["expected_output"].strip(),
                    agent=self._agentes[agente], **extra)
