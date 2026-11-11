"""Configuração do sistema. Roda só com o Ollama local: sem chave de API nem serviço pago.

Variáveis de ambiente (opcionais):
    TUTOR_MODELO        modelo do Ollama (padrão: qwen2.5:7b; mais rápido: qwen2.5:3b)
    TUTOR_OLLAMA_URL    endereço do Ollama (padrão: http://localhost:11434)
    TUTOR_GUARDIAO      0 desliga a revisão do Guardião (a recusa de padrão inventado continua)
    TUTOR_REVISAR_TUDO  1 faz o Guardião revisar todas as intenções, não só as de risco
    TUTOR_HISTORICO     quantos turnos anteriores entram no prompt (padrão: 3)
"""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent  # pasta do repositório (logs/, .sessoes/)

# Precisa rodar antes de qualquer `import crewai` (por isso os módulos de agentes/ importam config antes):
# o CrewAI lê estas variáveis na importação e, sem elas, tenta enviar telemetria pela internet.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

MODELO = os.getenv("TUTOR_MODELO", "qwen2.5:7b")
OLLAMA_URL = os.getenv("TUTOR_OLLAMA_URL", "http://localhost:11434")
USAR_GUARDIAO = os.getenv("TUTOR_GUARDIAO", "1") != "0"
REVISAR_TUDO = os.getenv("TUTOR_REVISAR_TUDO") == "1"  # quais rotas revisam: Rota.revisar
try:
    TURNOS_HISTORICO = max(0, int(os.getenv("TUTOR_HISTORICO", "3")))
except ValueError:  # valor inválido não pode derrubar a CLI na importação
    TURNOS_HISTORICO = 3

MAX_TENTATIVAS_EXERCICIO = 3   # depois disso o exercício deixa de estar pendente

TEMPERATURA = 0.3          # baixa para favorecer respostas fiéis à base de conhecimento
TIMEOUT_SEGUNDOS = 400     # por chamada ao modelo; folgado porque o 7b em CPU leva minutos
# Informa ao CrewAI o tamanho da janela para ele controlar o histórico enviado. Não altera o
# Ollama, que usa 4096 por padrão (confirmado com `ollama ps`).
JANELA_CONTEXTO = 4096
MAX_CARACTERES_ENTRADA = 2000  # entradas maiores são cortadas para caber na janela
