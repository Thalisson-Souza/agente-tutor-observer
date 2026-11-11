# Tutor Observer

Sistema multiagente que ensina o padrão de projeto Observer (GoF) a estudantes iniciantes.
Trabalho final de ELC1070 – Análise e Projeto de Sistemas Orientados a Objetos (UFSM).

Roda inteiramente na sua máquina: o [CrewAI](https://www.crewai.com/) coordena os agentes e o
[Ollama](https://ollama.com/) executa um modelo aberto local. Depois de instalado, funciona sem
chave de API e sem internet, de graça.

## Como funciona

Cada pergunta passa por um roteador, que identifica a intenção (explicar o conceito, dar exemplo,
propor exercício, comparar padrões...) e escolhe um agente:

| Agente | O que faz |
|---|---|
| Tutor | Explica o conceito em camadas: analogia, definição, participantes, consequências |
| Exemplificador | Mostra exemplos curtos em Java e casos de uso incorreto com a correção |
| Inquiridor | Propõe exercícios, avalia as respostas e compara o Observer com padrões parecidos |
| Guardião | Revisa as respostas de maior risco e recusa pedidos sobre padrões inventados |

Os fatos sobre o Observer vêm de uma base de conhecimento fixa (`agente/conhecimento/observer.md`).
Quem pede o código pronto recebe um roteiro de passos para escrever a solução por conta própria.
O sistema lembra os últimos turnos da conversa.

## Requisitos

- Python 3.10 a 3.13 (o CrewAI ainda não funciona no 3.14).
- [Ollama](https://ollama.com/download) instalado.
- 16 GB de RAM para o modelo `qwen2.5:7b` (padrão). Com 8 GB, use o `qwen2.5:3b`.

## Instalação

```bash
git clone https://github.com/Thalisson-Souza/agente-tutor-observer.git
cd agente-tutor-observer
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Se o Python do sistema for o 3.14, o [`uv`](https://docs.astral.sh/uv/) cria o ambiente com o
3.12 sem mexer no resto da máquina:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

Baixe o modelo (só esta etapa precisa de internet):

```bash
ollama pull qwen2.5:7b
```

Confira se o Ollama está rodando:

```bash
curl http://localhost:11434
```

A resposta deve ser `Ollama is running`. Se não for, rode `ollama serve`.

## Uso

Uma pergunta, responde e encerra:

```bash
python -m agente "Explique o que é o padrão Observer e qual problema ele resolve."
```

Conversa no terminal, com memória entre as perguntas (`nova` reinicia, `sair` encerra):

```bash
python -m agente
```

Pergunta única lembrando de uma conversa anterior:

```bash
python -m agente --sessao aula1 "Agora me dê um exemplo em Java"
```

No modelo 7b em CPU, uma resposta leva em torno de 1 a 2 minutos, e as que passam pela revisão
do Guardião levam mais. O terminal mostra qual agente está trabalhando.

### Configuração

Por variáveis de ambiente, sem mexer no código:

| Variável | Padrão | Efeito |
|---|---|---|
| `TUTOR_MODELO` | `qwen2.5:7b` | Modelo do Ollama. `qwen2.5:3b` é cerca de 2x mais rápido, mas erra mais. |
| `TUTOR_OLLAMA_URL` | `http://localhost:11434` | Endereço do Ollama |
| `TUTOR_GUARDIAO` | `1` | `0` desliga a revisão do Guardião |
| `TUTOR_REVISAR_TUDO` | desligado | `1` faz o Guardião revisar todas as respostas |
| `TUTOR_HISTORICO` | `3` | Quantos turnos anteriores entram no prompt |

Exemplo: `TUTOR_MODELO=qwen2.5:3b python -m agente "O que é Observer?"`

## Testes

Os testes de unidade não usam o Ollama e rodam em menos de um segundo:

```bash
python -m unittest -v
```

## Estrutura

```
agente/
├── __main__.py      linha de comando
├── config.py        configuração
├── nucleo/          intenções, rotas, eventos e erros
├── regras/          roteador e salvaguardas (Python puro)
├── agentes/         CrewAI: fábrica, orquestrador e prompts (YAML)
├── aplicacao/       fachada do tutor
├── observadores/    memória, log e progresso (padrão Observer)
└── conhecimento/    base de conhecimento do Observer
sdd/                 requisitos, design, tarefas e histórico de iterações
tests/               testes de unidade
```

Os prompts completos dos agentes estão em `agente/agentes/prompts/`. As decisões de projeto e o
histórico de testes estão em `sdd/`.

## Limitações conhecidas

- É lento em CPU: o 7b lê o prompt a cerca de 13 tokens/s nesta máquina de teste (i5-1235U).
- O roteador usa palavras-chave. Uma pergunta formulada de um jeito não previsto é tratada como
  pergunta conceitual.
- A proteção contra "código pronto" só reconhece código entre blocos de três crases.
- Os logs das conversas ficam em `logs/conversa.jsonl` (não versionado).
