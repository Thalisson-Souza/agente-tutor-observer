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
├── interface/       roteiro.py (perguntas do roteiro), terminal.py (chat com Rich), web.py (Gradio)
├── observadores/    memoria.py, log_arquivo.py, progresso.py, turno.py, painel_rich.py (ConcreteObservers)
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
| Tutor | Explica o conceito em camadas (analogia, definição, participantes, consequências); responde direto em seleção e fechamento; recusa outros padrões e temas | conceito, seleção, fechamento, fora do escopo |
| Exemplificador | Exemplos Java curtos com o papel de cada classe; uso incorreto e correção | exemplo, uso incorreto |
| Inquiridor | Método socrático: exercícios, avaliação da resposta, comparação com padrões confundidos, confirmação de afirmações | confusão, exercício, resposta ao exercício, solução pronta, confirmação |
| Guardião | Recusa padrão inventado; revisa rascunhos só com `TUTOR_REVISAR_TUDO=1` | padrão inventado |

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
| exemplo, uso_incorreto | Exemplificador | não (D13) | não |
| confusao | Inquiridor | não | não |
| exercicio | Inquiridor | não | sim |
| resposta_exercicio | Inquiridor | sim | sim |
| solucao_pronta | Inquiridor | não | sim |
| confirmacao | Inquiridor | não | não |
| fora_escopo | Tutor | não | não |
| inventado | Guardião (recusa) | — | não |

## Interface de terminal

`interface/` é um adaptador de entrada, como a CLI: usa só a fachada `SistemaTutor` e não
conhece CrewAI nem os agentes.

- `python -m agente` num terminal abre o chat com Rich; com `--simples`, ou com a saída
  redirecionada, usa o laço de texto puro. `python -m agente "pergunta"` não muda.
- Comandos: `/1` a `/7` (cenários do roteiro; `/6` é o padrão inventado e `/6b` o código
  pronto), `/nova`, `/ajuda`, `/sair`. Texto sem barra é pergunta.
- `observadores/painel_rich.py` (ConcreteObserver) liga e desliga a animação de status em
  `AGENTE_INICIADO` / `TURNO_CONCLUIDO` / `ERRO` e guarda agentes, veredito e tempo para o
  painel da resposta. A animação do Rich se atualiza sozinha enquanto a chamada ao modelo
  bloqueia, então não há threads no código do projeto.
- As perguntas do roteiro ficam em `interface/roteiro.py` e são reaproveitadas por
  `tests/cenarios.py`.

## Interface web

`interface/web.py` é mais um adaptador de entrada: usa só a fachada `SistemaTutor`, como o chat
com Rich. Aberta com `python -m agente --web`.

- **Dependência opcional:** o Gradio 6.31.0 fica em `requirements-web.txt`, fora do
  `requirements.txt`. Para os dois arquivos serem instaláveis juntos, o `pillow` do
  `requirements.txt` desceu de 13.0.0 para 12.3.0 (o Gradio 6 exige `pillow<13`; quem usa
  o pillow é o `pdfplumber`, dependência do CrewAI que o tutor não usa). `web.py` só é importado com `--web`; sem o Gradio instalado, a CLI e o
  Rich continuam funcionando e `--web` avisa como instalar.
- **Offline e sem custo:** `GRADIO_ANALYTICS_ENABLED=False` definido antes do import,
  `launch(share=False, server_name="127.0.0.1")`, tema com fontes do sistema (sem Google
  Fonts). Verificar com a rede desligada (junto com T6).
- **Memória por aba:** um `SistemaTutor` por sessão do navegador (`gr.State`), criado com o
  mesmo orquestrador; assim o modelo carregado e os agentes são compartilhados e só a
  `Memoria` é separada. O histórico que o Gradio mostra é só visual; quem lembra é a `Memoria`.
- **Tela:** barra lateral com as perguntas de `interface/roteiro.py` agrupadas (Entender,
  Código, Limites do tutor), "Praticar" e "Nova conversa"; chat à direita; cada resposta termina com uma linha discreta "Agente · tempo · veredito",
  vinda do mesmo tipo de observador do Rich (`TURNO_CONCLUIDO`, `REVISAO`).
- **Fila:** uma pergunta por vez (`concurrency_limit=1`), porque o modelo na CPU não atende
  duas ao mesmo tempo sem dobrar o tempo de ambas.
- **Testes:** a montagem da resposta (texto + linha do agente) fica numa função pura,
  testada sem navegador e sem modelo; a tela é conferida à mão.

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
`conhecimento/observer.md`, baseado no GoF (conferida com o livro na D20), é a única fonte de fatos permitida nos prompts. Só as seções da intenção entram, para reduzir o tempo de leitura.
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

**D13 — Guardião só na avaliação de resposta de exercício** (11/11)
No roteiro, o Guardião aprovou um exemplo de erro conceitualmente falso no C4 e somava ~3 min por resposta. Exemplo e uso incorreto passaram a ser ancorados em código da base de conhecimento, e o Guardião ficou só em `resposta_exercicio`. Efeito colateral observado: sem revisão, o C2 inventou uma regra; resolvido restringindo a orientação.

**D14 — Interface de terminal com Rich** (11/11)
O Rich já vem como dependência do CrewAI (nada novo no `requirements.txt`), resolve o principal problema do chat atual (Markdown e código aparecendo crus) e cabe em ~1 h. A interface vira mais um observador da conversa, sem mudar o núcleo.
*Descartados:* Textual (também instalado; tela de aplicativo, mas exige rodar o modelo numa thread e atualizar a tela com segurança, 2 a 4 h); Gradio (dependência grande, desligar telemetria e fontes externas para funcionar offline).

**D18 — Tema Minimal guardado no repositório** (11/11)
O tema da comunidade "Minimal" (Taithrah, Apache 2.0) foi copiado para `interface/tema/minimal.json` em vez de carregado do Hugging Face a cada abertura, que exigiria internet. O JSON trazia prontos os endereços do Google Fonts; `carregar_tema()` os remove e usa a Source Sans 3 que vem no Gradio e a Ubuntu Mono do sistema. Verificado no navegador: nenhum pedido a endereço externo.

**D15 — Interface web com Gradio, como opcional** (11/11)
A professora usou o Gradio no tutorial e sugeriu botões de exemplo para os avaliadores; no navegador, colegas que não usam terminal testam com mais facilidade. Fica opcional (`requirements-web.txt`) porque é uma dependência grande e precisa de configuração para funcionar offline; o Rich (D14) continua sendo a interface que não depende de nada novo.

**D16 — Guardião só para recusar padrão inventado** (11/11)
Na avaliação de exercício (E1.2) o Guardião levou ~7 min e a falha real era a orientação, que deixava uma afirmação do aluno sem avaliação. Com a orientação afirmação por afirmação, o Inquiridor sozinho cobriu os 3 erros em 206 s. Nenhuma rota é revisada por padrão; `TUTOR_REVISAR_TUDO=1` liga a revisão em todas.

**D17 — Rotas `fora_escopo` e `confirmacao`** (11/11)
Mensagens sem palavra-chave caíam em "conceito" e o Tutor dava a aula inteira, mesmo quando o pedido era outro padrão (E2) ou a confirmação de uma afirmação (E4). Instrução dentro da rota conceito não bastou para o E4: o prompt do Tutor manda explicar em camadas. Rotas próprias resolvem sem mexer no prompt do agente, e a confirmação vai ao Inquiridor, cujo papel é diagnosticar concepções erradas.

**D19 — Troca de modelo durante a conversa** (11/11)
O orquestrador recebe o modelo por parâmetro (antes lia o `config` global) e a fachada ganhou `usar_orquestrador()`. As interfaces criam um orquestrador por modelo na primeira escolha e o reaproveitam; a memória continua ao trocar. Cada resposta registra o modelo que de fato respondeu (rodapé e log). O 7b fica como padrão; o 3b é opção explícita de "mais rápido, erra mais" e ainda não rodou o roteiro completo.

**D20 — Base de conhecimento ancorada no livro da disciplina** (11/11)
Cada fato do GoF traz a página da edição da Bookman (bibliografia básica), com nossas palavras e os termos da tradução; o que é prática fora do livro é marcado [prática]. Assim o tutor pode indicar "veja o livro da disciplina, p. X" (sugerido no enunciado) e a dupla pode justificar de onde vem cada afirmação. A conferência corrigiu um erro (referência do ConcreteObserver ao subject, p. 276).

## Verificado e descartado

- Chaves `{}` em backstory ou em código Java não quebram a interpolação de `inputs` do CrewAI (10/11).
