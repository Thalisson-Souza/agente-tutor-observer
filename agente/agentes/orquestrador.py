"""Executa uma Rota com o CrewAI e o Ollama. É o único módulo que conversa com o modelo.

O resto do sistema depende só do contrato Orquestrador (aplicacao/sistema.py), então os testes
trocam esta classe por uma falsa e rodam sem o Ollama.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from .. import config  # tem que vir antes do crewai (ver comentário da telemetria em config.py)
from ..nucleo.erros import FalhaModelo
from ..nucleo.intencoes import NomeAgente, NomeTarefa, Resultado, Rota

from crewai import LLM, Crew, Process  # noqa: E402

from .fabrica_agentes import FabricaAgentes  # noqa: E402  (também importa crewai)

# O CrewAI avisa a cada chamada que estimou os tokens (o Ollama não informa a contagem).
# É inofensivo e poluía a saída da CLI na demo.
logging.getLogger("crewai.llms.base_llm").setLevel(logging.ERROR)


def interpretar_revisao(rascunho: str, revisao: str) -> tuple[str, str]:
    """Devolve (texto final, veredito). Na dúvida, fica com o rascunho do especialista.

    Modelos pequenos nem sempre seguem o formato: podem pôr markdown antes do veredito
    ("**APROVADO**") ou escrever "CORRIGIDO:" sem texto depois. Por isso se removem
    `*`, `#` e espaços do início, e uma correção com menos de 40 caracteres é descartada.
    """
    cabeca = revisao.lstrip("*# ").upper()
    if cabeca.startswith("APROVADO"):
        return rascunho, "aprovado"
    if cabeca.startswith("CORRIGIDO"):
        corrigido = revisao.split(":", 1)[1].strip(" *\n") if ":" in revisao else ""
        if len(corrigido) > 40:
            return corrigido, "corrigido"
        return rascunho, "corrigido_vazio"
    return rascunho, "saida_inesperada"


class OrquestradorCrewAI:
    def __init__(self, modelo: str = config.MODELO) -> None:
        # Recebido por parâmetro (e não lido do config) para as interfaces poderem ter um
        # orquestrador por modelo e trocar entre eles sem reiniciar o programa.
        self.modelo = modelo
        llm = LLM(
            model=f"ollama/{modelo}",
            base_url=config.OLLAMA_URL,
            temperature=config.TEMPERATURA,
            timeout=config.TIMEOUT_SEGUNDOS,
            context_window_size=config.JANELA_CONTEXTO,
        )
        self.fabrica = FabricaAgentes(llm)

    def verificar(self) -> str | None:
        """Devolve uma mensagem de erro se o Ollama ou o modelo não estiverem disponíveis.

        Leva no máximo 3 s; sem isso o problema só apareceria depois do timeout do modelo.
        """
        try:
            with urllib.request.urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=3) as r:
                modelos = {m["name"] for m in json.load(r).get("models", [])}
        except (urllib.error.URLError, OSError, ValueError):
            return (f"Não consegui falar com o modelo local em {config.OLLAMA_URL}. "
                    "Verifique se o Ollama está rodando (`ollama serve`) e tente de novo.")
        if self.modelo not in modelos and f"{self.modelo}:latest" not in modelos:
            return f"O modelo '{self.modelo}' não está instalado no Ollama. Rode: ollama pull {self.modelo}"
        return None

    def executar(self, rota: Rota, entradas: dict[str, str], com_revisao: bool) -> Resultado:
        try:
            return self._executar(rota, entradas, com_revisao)
        except Exception as erro:  # CrewAI/LiteLLM não têm um tipo de erro único para falhas do modelo
            raise FalhaModelo(self._mensagem(erro)) from erro

    def _executar(self, rota: Rota, entradas: dict[str, str], com_revisao: bool) -> Resultado:
        f = self.fabrica
        entradas = {**entradas, "orientacao": f.orientacao(rota.intencao, rota.detalhe)}
        principal = f.tarefa(rota.tarefa, rota.agente)
        tarefas = [principal]
        if com_revisao:  # decidido uma única vez, por Rota.com_revisao(), na aplicação
            # O rascunho chega ao Guardião pelo context da tarefa de revisão.
            tarefas.append(f.tarefa(NomeTarefa.REVISAO, NomeAgente.GUARDIAO, contexto=[principal]))

        agentes = [f.agente(n) for n in rota.agentes(com_revisao)]
        saida = Crew(agents=agentes, tasks=tarefas, process=Process.sequential, verbose=False).kickoff(inputs=entradas)

        rascunho = saida.tasks_output[0].raw.strip()
        if not com_revisao:
            return Resultado(rascunho)
        revisao = saida.tasks_output[1].raw.strip()
        texto, veredito = interpretar_revisao(rascunho, revisao)
        return Resultado(texto, veredito, revisao[:300])

    def _mensagem(self, erro: Exception) -> str:
        # Classifica pelo texto porque o tipo da exceção varia com a versão do CrewAI/LiteLLM.
        # Texto não reconhecido cai na mensagem genérica.
        msg = str(erro).lower()
        if "timeout" in msg or "timed out" in msg:
            return ("O modelo local demorou demais para responder. Tente uma pergunta mais curta "
                    "ou use TUTOR_MODELO=qwen2.5:3b.")
        if "model" in msg and "not found" in msg:
            return f"O modelo '{self.modelo}' não está instalado. Rode: ollama pull {self.modelo}"
        return "Tive um problema ao gerar a resposta com o modelo local. Tente de novo ou reformule a pergunta."
