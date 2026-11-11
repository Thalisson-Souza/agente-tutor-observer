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
