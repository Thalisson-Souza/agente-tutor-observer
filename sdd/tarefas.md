# Tarefas

Backlog do projeto. Atualizar a cada mudança, junto com [iteracoes.md](iteracoes.md).
Cada tarefa aponta para o requisito ou cenário de [requisitos.md](requisitos.md) que atende.

## A fazer (em ordem)

| # | Tarefa | Atende | Notas |
|---|---|---|---|
| T1 | Script `tests/cenarios.py`: roda C1–C7 no modelo e salva respostas e tempos em `docs/evidencias/` | R3, R4, C1–C7 | evidência para o relatório e roteiro da demo |
| T2 | Rodar C2, C3, C4 e C7 no 7b e corrigir o que falhar | R3, C2–C4, C7 | |
| T3 | Medir e reduzir o tempo das rotas com Guardião (exemplo, uso_incorreto, resposta_exercicio) | R3 | única medida com revisão: 366–433 s |
| T4 | Ajustar orientação do `solucao_pronta`: saiu "Quando notificar o Subject?" (é o Subject que notifica) | C6b | redação |
| T5 | `requirements.txt` (`uv pip freeze`) e README | R8 | |
| T6 | Testar com a rede desligada | R7 | |
| T7 | Template do caderno de evidências para a sessão em sala | entregável 6 | |
| T8 | Opcional: Gradio | R9 | |
| T9 | Opcional: acelerar com Vulkan na Iris Xe | R3 (tempo) | exige configurar o serviço do Ollama com sudo |

## Melhorias anotadas, não priorizadas

- `nucleo/intencoes.py` guarda também Rota, nomes de agentes/tarefas e Resultado; o nome não diz tudo.
- A lógica de `conhecimento/` está no `__init__.py`.
- Testes num único arquivo; poderiam espelhar as camadas.
- `SistemaTutor` lê `config` global (dependência escondida; testes não variam as opções).
- `montar_sistema()` (composition root) está em `aplicacao/`.

## Feito

| Quando | O que | Iteração |
|---|---|---|
| 10/11 | Ambiente: `uv`, Python 3.12, CrewAI, Ollama, benchmark 3b × 7b | 0 |
| 10/11 | Primeira versão multiagente (roteador, 4 agentes, base de conhecimento, memória, CLI) | 1 |
| 10/11 | Code review: bugs B1–B4 corrigidos (resposta de exercício desviada; exercício sempre pendente; falha de observador silenciosa; nome de agente sem validação) | 2 |
| 10/11 | Refatoração: fábrica, orquestrador isolado, fachada com injeção, Enums, 26 testes sem Ollama; melhorias M1–M7 (aviso do CrewAI, checagem do modelo, entrada cortada com aviso, código fora do histórico, config inválida, CLI, mensagens de erro) | 2 |
| 10/11 | C6b corrigido: salvaguarda em código + prompt reescrito | 3 |
| 10/11 | Pacotes por camada | 4 |
| 10/11 | Orientações para `rotas.yaml`, `Resultado` no núcleo, decisão de revisão única | 5 |
| 10/11 | Pasta `sdd/` (requisitos, design, tarefas, iterações) | 6 |
