"""Vocabulário do sistema: intenções, agentes, tarefas, a Rota que liga os três e o Resultado.

Não depende do CrewAI. Usar Enum em vez de strings soltas faz um erro de digitação
falhar na importação, e não no meio de uma conversa.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Intencao(str, Enum):
    CONCEITO = "conceito"
    SELECAO = "selecao"
    FECHAMENTO = "fechamento"
    EXEMPLO = "exemplo"
    USO_INCORRETO = "uso_incorreto"
    CONFUSAO = "confusao"
    EXERCICIO = "exercicio"
    RESPOSTA_EXERCICIO = "resposta_exercicio"
    SOLUCAO_PRONTA = "solucao_pronta"
    INVENTADO = "inventado"
    FORA_ESCOPO = "fora_escopo"     # outro padrão do GoF, sem relação pedida com o Observer
    CONFIRMACAO = "confirmacao"     # o estudante afirma algo e pede confirmação ("..., né?")
    RESPOSTA_PERGUNTA = "resposta_pergunta"  # resposta à pergunta que o tutor fez no fim do turno
    NAO_SEI = "nao_sei"             # "não sei" como resposta à pergunta do tutor


class NomeAgente(str, Enum):
    """Cada valor precisa ser uma chave de agentes/prompts/agentes.yaml (a fábrica valida)."""
    TUTOR = "tutor"
    EXEMPLIFICADOR = "exemplificador"
    INQUIRIDOR = "inquiridor"
    GUARDIAO = "guardiao"


class NomeTarefa(str, Enum):
    """Cada valor precisa ser uma chave de agentes/prompts/tarefas.yaml (a fábrica valida)."""
    ESPECIALISTA = "especialista"   # resposta ao estudante
    REVISAO = "revisao"             # Guardião revisa o rascunho do especialista
    RECUSA = "recusa"               # Guardião recusa padrão inventado


@dataclass(frozen=True)
class Rota:
    intencao: Intencao
    agente: NomeAgente
    tarefa: NomeTarefa
    secoes: tuple[str, ...]     # ids das seções "## [id]" de conhecimento/observer.md levadas ao prompt
    # Intenções de maior risco de erro (código, avaliação do aluno) passam pelo Guardião.
    # Nas demais a revisão custaria ~100 s a mais no 7b em CPU (ver sdd/iteracoes.md, iteração 1).
    revisar: bool = False
    # Rotas em que o estudante deve escrever o código: salvaguardas.sem_solucao_pronta()
    # remove implementações da resposta final, porque o modelo nem sempre obedece ao prompt.
    bloquear_solucao: bool = False
    # Dado extraído da mensagem pelo roteador: o nome do padrão desconhecido (inventado)
    # ou do outro padrão citado (fora_escopo).
    # O texto da orientação de cada intenção fica em agentes/prompts/rotas.yaml.
    detalhe: str = ""

    def com_revisao(self, guardiao_ligado: bool, revisar_tudo: bool = False) -> bool:
        """Única decisão sobre passar pelo Guardião. Só uma resposta de especialista tem
        o que revisar; a recusa de padrão inventado já é escrita pelo próprio Guardião."""
        if self.tarefa is not NomeTarefa.ESPECIALISTA or not guardiao_ligado:
            return False
        return self.revisar or revisar_tudo

    def agentes(self, com_revisao: bool) -> list[NomeAgente]:
        """Agentes que vão trabalhar nesta rota, na ordem."""
        return [self.agente, NomeAgente.GUARDIAO] if com_revisao else [self.agente]


@dataclass(frozen=True)
class Resultado:
    """O que o orquestrador devolve à aplicação (contrato da porta Orquestrador)."""
    texto: str
    veredito: str | None = None     # None quando não houve revisão do Guardião
    revisao_bruta: str = ""
