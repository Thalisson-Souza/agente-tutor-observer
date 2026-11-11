# Design — Tutor multiagente do padrão Observer

Como o sistema atende aos [requisitos](requisitos.md) e por quê. Base das seções 2 (agentes)
e 3 (justificativa de design) do relatório. Medições citadas estão em [iteracoes.md](iteracoes.md).

- **Stack:** Python 3.12 (venv via `uv`), CrewAI 1.15.39, Ollama com `qwen2.5:7b` (plano B `qwen2.5:3b`)
- **Máquina de referência:** Dell Inspiron 15, i5-1235U, 16 GB DDR4, Iris Xe sem uso pelo Ollama (inferência em CPU), Linux

## Arquitetura

Camadas no estilo Ports and Adapters (hexagonal): as dependências apontam para dentro e o
framework de agentes fica isolado num adaptador.

```
agente/
├── __main__.py      CLI: python -m agente (precisa ficar na raiz do pacote)
├── config.py        configuração por variáveis de ambiente; RAIZ do repositório
├── nucleo/          intencoes.py (Enums, Rota, Resultado), eventos.py (Subject/Observer), erros.py
├── regras/          roteador.py (classificar → Rota), salvaguardas.py (remove solução pronta)
├── agentes/         fabrica_agentes.py, orquestrador.py, prompts/{agentes,tarefas,rotas}.yaml
├── aplicacao/       sistema.py: SistemaTutor (fachada), porta Orquestrador, montar_sistema()
├── observadores/    memoria.py, log_arquivo.py, progresso.py (ConcreteObservers)
└── conhecimento/    observer.md + carregador por seções
tests/test_unidade.py   OrquestradorFalso; roda sem Ollama
```

**Regra de dependência:** `nucleo` não importa nada do projeto; `regras` e `observadores` só usam
`nucleo`; `aplicacao` usa todos menos o CrewAI (recebe o orquestrador pela porta `Orquestrador`);
só `agentes/` importa `crewai`.

**Simplificações conscientes** (não seguem a forma "pura" da arquitetura):
- `montar_sistema()`, que liga as peças reais (composition root), está em `aplicacao/`.
- `SistemaTutor` depende da classe concreta `Memoria`, não de uma porta.
- `SistemaTutor` lê `config` e `conhecimento` diretamente.

## Agentes

| Agente | Papel | Atende |
|---|---|---|
| Tutor | Explica o conceito em camadas (analogia → definição → participantes → consequências) | conceito, seleção, fechamento |
| Exemplificador | Exemplos Java curtos com o papel de cada classe; uso incorreto e correção | exemplo, uso incorreto |
| Inquiridor | Método socrático: exercícios, avaliação da resposta, comparação com padrões confundidos | confusão, exercício, resposta ao exercício, solução pronta |
| Guardião | Revisa rascunhos contra a base (APROVADO/CORRIGIDO); recusa padrão inventado | revisão nas rotas de risco; padrão inventado |

Prompts integrais: `agente/agentes/prompts/agentes.yaml` (persona), `tarefas.yaml` (molde da
mensagem) e `rotas.yaml` (orientação por intenção).

## Fluxo de um turno

1. `SistemaTutor.resposta()` valida a entrada e consulta `Orquestrador.verificar()` (Ollama e modelo).
2. `regras/roteador.classificar()` devolve a `Rota`: intenção, agente, seções da base, flags.
3. `Rota.com_revisao()` decide se o Guardião revisa.
4. O orquestrador monta uma Crew sequencial (especialista, ou especialista → Guardião) com
   pergunta, histórico, trechos da base e orientação.
5. Nas rotas com `bloquear_solucao`, `regras/salvaguardas.py` remove código de implementação.
6. `Conversa.notificar()` avisa memória, log e indicador de progresso.

| Intenção | Agente | Guardião revisa? | Salvaguarda de código |
|---|---|---|---|
| conceito, selecao, fechamento | Tutor | não (sim com `TUTOR_REVISAR_TUDO=1`) | não |
| exemplo, uso_incorreto | Exemplificador | sim | não |
| confusao | Inquiridor | não | não |
| exercicio | Inquiridor | não | sim |
| resposta_exercicio | Inquiridor | sim | sim |
| solucao_pronta | Inquiridor | não | sim |
| inventado | Guardião (recusa) | — | não |

## Decisões

Cada decisão: o que, por que, alternativa descartada. Data entre parênteses.

**D1 — `qwen2.5:7b` como modelo principal, `3b` como plano B** (10/11)
O 3b errou a definição do Observer no primeiro teste; o 7b acertou. Custo: 4,9 tok/s de geração contra 10,5 do 3b. Trocável por `TUTOR_MODELO`.

**D2 — Roteador por expressões regulares, sem LLM** (10/11)
Classificar com o modelo seria mais uma chamada (prompts curtos levaram 30–40 s), e regras fixas são testáveis sem o modelo. Limitação: paráfrases não previstas caem em "conceito"; por isso os prompts repetem as regras anti-alucinação.
*Descartado:* agente roteador no CrewAI (hierarchical process).

**D3 — Um especialista por pergunta, não os 4 agentes em sequência** (10/11)
O 7b lê o prompt a ~13,5 tok/s; cada agente lê ~1300 tokens, ~100 s só de leitura. Quatro agentes em fila passariam de 5 min por pergunta.

**D4 — Base de conhecimento fixa, injetada por seções** (10/11)
`conhecimento/observer.md`, baseado no GoF, é a única fonte de fatos permitida nos prompts. Só as seções da intenção entram, para reduzir o tempo de leitura.
*Descartado:* deixar o modelo responder só com o que "sabe" (alucinação) ou RAG com embeddings (mais complexidade sem ganho para um padrão só).

**D5 — Guardião só nas rotas de risco** (10/11)
Conceito com Guardião levou 366 s; confusão sem Guardião, 125 s. Revisam-se as rotas com código e avaliação do aluno, onde o erro é mais provável.

**D6 — Salvaguarda em código contra solução pronta** (10/11)
No C6b o 7b escreveu que não entregaria a solução e a entregou, e o Guardião manteve. A regra em Python (`salvaguardas.py`) vale independentemente do modelo. Na rota `solucao_pronta` o Guardião foi retirado: piorou a resposta e dobrava as chamadas.
Limitação: só detecta código entre ```.

**D7 — Memória própria em vez da memória nativa do CrewAI** (10/11)
Turnos recentes e estado do exercício, guardados por um observador; opcionalmente em JSON (`--sessao`). A memória nativa usa embeddings, o que exigiria configurar um modelo de embeddings local e aumentaria o risco de dependência externa (não testado).
Só turnos concluídos entram no histórico; código de respostas antigas é omitido para economizar tokens.

**D8 — O próprio sistema usa Observer** (10/11)
`Conversa` (Subject) notifica memória, log e progresso (ConcreteObservers). A fachada não sabe quem reage aos eventos. A cópia da lista em `notificar()` evita a armadilha de desanexar durante a notificação.

**D9 — CrewAI isolado atrás de uma porta, orquestrador injetado** (10/11)
Permite 34 testes de unidade em ~0,1 s com um `OrquestradorFalso`. Antes da refatoração nada era testável sem o Ollama.

**D10 — Prompts em YAML, incluindo a orientação por intenção** (10/11)
O relatório exige o texto integral; o YAML é a fonte única. Validados na inicialização: prompt faltando falha antes da primeira pergunta.

**D11 — Parâmetros do LLM** (10/11)
Temperatura 0,3 (fidelidade à base); timeout de 400 s por chamada; `context_window_size=4096` (informa o CrewAI; o Ollama já usa 4096). `num_ctx` foi tentado e quebrou a chamada, pois o CrewAI 1.15 usa a API compatível com OpenAI do Ollama.

**D12 — Telemetria do CrewAI desligada** (10/11)
`OTEL_SDK_DISABLED`, `CREWAI_DISABLE_TELEMETRY` e `CREWAI_TRACING_ENABLED` definidos antes de importar o CrewAI, para a execução não depender de internet.

## Verificado e descartado

- Chaves `{}` em backstory ou em código Java não quebram a interpolação de `inputs` do CrewAI (10/11).
