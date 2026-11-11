"""Exceções do sistema. Ficam fora do orquestrador para a fachada tratá-las sem importar o CrewAI."""


class FalhaModelo(Exception):
    """Falha do modelo local, com mensagem já pronta para mostrar ao estudante."""


class ErroDeConfiguracao(Exception):
    """Prompts ausentes ou incompletos. Detectado na inicialização, antes da primeira pergunta."""
