# Iterações (base para o mini-relatório)

Registro cronológico: o que mudou, como foi testado, o resultado. Uma entrada por iteração.

## 2026-11-10 — Iteração 0: ambiente
- Máquina: Dell Inspiron 15, Intel Core i5-1235U (12ª ger., 10 núcleos/12 threads), 16 GB DDR4, Intel Iris Xe (não usada pelo Ollama → inferência em CPU), Linux kernel 7.0.
- Python do sistema é 3.14 (incompatível com CrewAI) → venv com Python 3.12.16 criado via `uv`.
- CrewAI 1.15.39 (`crewai[litellm]`), Ollama com `qwen2.5:7b` e `qwen2.5:3b`.
- Benchmark (prompt de ~25 tokens, resposta de ~150 palavras sobre Observer):

| Modelo | Leitura do prompt | Geração | Tempo total |
|---|---|---|---|
| qwen2.5:3b | 42 tok/s | 10,5 tok/s | 29 s (265 tokens) |
| qwen2.5:7b | 16 tok/s | 4,9 tok/s | 43 s (163 tokens) |

- Observação: com 7b, um prompt de sistema de ~1500 tokens custaria ~90 s só de leitura. Conclusão: prompts enxutos e poucas chamadas LLM por turno.
- Teste `crewai.LLM(model='ollama/qwen2.5:7b').call(...)` OK, sem internet/API key.

## 2026-11-10 — Iteração 1: primeira versão multiagente
- Estrutura: roteador em Python (palavras-chave) → 1 especialista (Tutor, Exemplificador ou Inquiridor) → Guardião. Base de conhecimento `agente/conhecimento/observer.md` injetada por seção. Memória e log implementados como Observers da conversa (`agente/eventos.py`).
- Roteador testado nos 7 cenários do roteiro + padrão inventado ("Padrão Zorblax") + "quero praticar": 10/10 classificados corretamente.
- Erro 1: `num_ctx` no `LLM` quebrou a chamada (CrewAI 1.15 usa a API compatível com OpenAI do Ollama). O tratamento de erros devolveu mensagem amigável. Correção: trocar por `context_window_size=4096`.
- Teste conceitual com Tutor + Guardião (7b): resposta correta e bem estruturada, Guardião "APROVADO", mas **366 s**.
- Medição: leitura de prompt longo (1339 tokens) = 13,5 tok/s no 7b (~100 s) e 28,5 tok/s no 3b. O gargalo é a leitura do prompt, não a geração.
- Decisão: Guardião revisa só as intenções de maior risco (exemplo, uso incorreto, solução pronta, avaliação de resposta); `TUTOR_REVISAR_TUDO=1` liga para todas.
- Teste "confusão" (só Inquiridor): **125 s**, resposta correta (Pub/Sub com broker vs Observer síncrono, cita alias do GoF).

## 2026-11-10 — Iteração 2: code review e refatoração
- Code review encontrou 4 bugs confirmados por teste (B1–B4, ver tarefas.md): resposta de exercício desviada para outro agente; exercício sempre pendente; falha de observador silenciosa; nome de agente sem validação.
- Refatoração: `intencoes.py` (Enums + Rota com `revisar`), `fabrica_agentes.py` (YAML validado na inicialização), `orquestrador.py` (único módulo que usa CrewAI), `sistema.py` como fachada com o orquestrador injetado, `erros.py`.
- 26 testes de unidade sem o Ollama (`python -m unittest`), 0,1 s. Cobrem os bugs corrigidos e o roteiro.
- Cenário 6a (inventar padrão Z), real no 7b: recusa educada, cita que não está no GoF, oferece o Observer. 60 s. **Passou.**
- Cenário 6b (código pronto), real no 7b: **falhou.** Diz que não vai entregar e em seguida entrega a solução completa (interfaces, ConcreteSubject, ConcreteObserver e Main). O Guardião respondeu "CORRIGIDO" e o texto final também tinha o código completo. 433 s. Conclusão: a instrução "não entregue" no prompt não basta no 7b; precisa de verificação determinística.

## 2026-11-10 — Iteração 3: correção do cenário 6b (código pronto)
- Causa: instrução "NÃO entregue a solução" no prompt não foi obedecida pelo 7b, e o Guardião não barrou.
- Mudanças:
  1. `salvaguardas.py`: remove da resposta final blocos de código com implementação (método com corpo ou mais de 8 linhas), mantendo assinaturas curtas de interface. Se sobrar menos de 300 caracteres, usa um roteiro de 5 passos escrito à mão. Ligado pelas rotas com `bloquear_solucao` (solucao_pronta, exercicio, resposta_exercicio).
  2. Orientação da rota `solucao_pronta` reescrita com o formato exato esperado (frase gentil, 4–5 passos com perguntas, convite à tentativa).
  3. `solucao_pronta` sem Guardião: ele piorou a resposta no teste anterior e dobrava as chamadas.
- Teste de unidade com a resposta real que falhou (`tests/dados/resposta_6b_falhou.txt`): a salvaguarda remove ConcreteSubject, ConcreteObserver e Main e mantém as interfaces. 31 testes OK.
- Cenário 6b real no 7b: **passou**, em **58 s** (antes 433 s). Recusa gentil, 5 passos com perguntas, só a assinatura da interface Observer. Desta vez o prompt bastou e a salvaguarda não precisou agir.
- Observação de qualidade: o passo 4 diz "Quando notificar o Subject?", mas é o Subject que notifica. Ajustar a redação da orientação.

## 2026-11-10 — Iteração 4: pacotes por camada
- Arquivos soltos em `agente/` reorganizados em `nucleo/`, `regras/`, `agentes/`, `aplicacao/`, `observadores/` (estrutura em design.md). `memoria.py` dividido em memória, log e progresso.
- Sem mudança de comportamento: mesmos testes de unidade, imports ajustados.

## 2026-11-10 — Iteração 5: clareza da arquitetura
- Orientações por intenção (texto lido pelo modelo) movidas de `regras/roteador.py` para `agentes/prompts/rotas.yaml`, validado na inicialização como os outros YAML. A `Rota` passou a carregar só dados (`detalhe` = nome do padrão desconhecido).
- `Resultado` movido para `nucleo/intencoes.py`; porta `Orquestrador` com tipos e docstrings.
- Decisão "passa pelo Guardião?" unificada em `Rota.com_revisao()` (antes calculada no sistema e recalculada no orquestrador).
- Renomear `agentes/` para `crew/` foi testado e desfeito: a dupla achou `agentes/` mais claro.
- 34 testes OK.

## 2026-11-10 — Iteração 6: pasta de SDD
- `docs/SPEC.md` dividido em `sdd/requisitos.md` (princípios, R1–R9 e cenários C1–C7 com critério de aceite), `sdd/design.md` (arquitetura, agentes, fluxo e decisões D1–D12) e `sdd/tarefas.md` (backlog); este log foi movido de `docs/` para `sdd/iteracoes.md`.
- Escolhida a versão enxuta inspirada no Spec Kit/Kiro (requisitos → design → tarefas), sem constituição nem ADRs em arquivos separados: cada arquivo corresponde a uma seção do relatório.

## 2026-11-11 — Iteração 7: roteiro completo no 7b
- Script `tests/cenarios.py` roda C1–C7 com memória vazia em cada um e salva em `docs/evidencias/cenarios_2026-11-11_1912_qwen2.5-7b.{md,json}`. Total ~28 min.
- Roteamento: todos os 8 foram para a intenção esperada.

| Cenário | Tempo | Avaliação |
|---|---|---|
| C1 conceito | 292 s | Correto. Ponto fraco: "evitar quando o acoplamento é desejável" não vem da base. |
| C2 exemplo (+Guardião) | 386 s | Correto, domínio novo (estoque), papéis indicados. Lento. |
| C3 seleção | 177 s | Correto (uso: widgets do clima; evitar: dependente fixo). Repete a explicação do conceito antes de responder. |
| C4 uso incorreto (+Guardião) | 356 s | **Falhou.** Diz que `detach` chamado no `main`, fora da notificação, causa `ConcurrentModificationException`, o que é falso. Código com ~60 linhas (limite do prompt: 35). O Guardião aprovou. |
| C5 confusão | 166 s | Correto no essencial; afirma que "os observadores não precisam conhecer o sujeito", impreciso (no modelo pull o ConcreteObserver referencia o sujeito). |
| C6a inventado | 53 s | Passou. |
| C6b código pronto | 85 s | Passou; persiste "Quando notificar o Subject?" (T4). |
| C7 fechamento | 158 s | Parcial: 15 itens com repetições (9–10 repetem 6 e 5) e um item que mistura cascata com ordem. A base tem 7. |

- Conclusões: (1) o Guardião não pegou o erro conceitual do C4, então a revisão por LLM não é confiável para exemplos de código; (2) o 7b acerta quando copia a base e erra quando inventa o próprio exemplo de erro, então o C4 precisa de um exemplo de uso incorreto pronto na base; (3) mesmo sem Guardião, respostas longas levam 3–5 min, então limitar o tamanho também reduz o tempo.
- Bug no script: `Path.with_suffix` tratou ".5-7b" de "qwen2.5-7b" como extensão; corrigido e arquivos renomeados.

## 2026-11-11 — Iteração 8: correções do roteiro
- Mudanças: exemplo de código de uso incorreto na base (observador que se desanexa dentro de `atualizar()` e a correção com cópia da lista); orientações de seleção, fechamento e uso incorreto mais restritas (sem reexplicar o conceito, só itens da base, máx. 25 linhas); Tutor só explica em camadas quando a pergunta é sobre o conceito; base esclarece quem conhece quem (Observer × Pub/Sub); Guardião retirado de exemplo e uso incorreto (D13 em design.md).
- Reexecução (`docs/evidencias/cenarios_2026-11-11_1938_qwen2.5-7b.md`):

| Cenário | Antes | Depois | Avaliação |
|---|---|---|---|
| C1 | 292 s | 238 s | Correto; sem o "quando evitar" inventado |
| C2 | 386 s | 200 s | **Regressão:** sem o Guardião, inventou uma seção de uso incorreto falsa ("notify() deve receber o Observador") |
| C3 | 177 s | 106 s | Correto e direto, sem repetir o conceito |
| C4 | 356 s | 196 s | **Corrigido:** erro real (detach dentro de `atualizar()`) e correção certa |
| C5 | 166 s | 182 s | Correto; diz quem conhece quem |
| C6b | 85 s | 88 s | Correto; redação "em que momento o Subject deve notificar" |
| C7 | 158 s | 93 s | Correto: os 7 itens da base |

- Correção da regressão do C2: orientação do exemplo proíbe seção de uso incorreto e regras fora da base. C2 de novo (`cenarios_2026-11-11_1942_qwen2.5-7b.md`): correto, 4 papéis indicados, 216 s.
- Resultado: os 8 cenários passam; tempo por resposta entre 53 e 238 s (antes até 386 s).
- Lição: o que mais melhorou a correção foi dar ao modelo o exemplo certo na base, não a revisão por outro agente.
