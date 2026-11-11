# Requisitos — Tutor multiagente do padrão Observer

O que o sistema precisa fazer e como verificamos que faz. Muda só quando um requisito muda.
Arquitetura e decisões: [design.md](design.md). O que falta: [tarefas.md](tarefas.md).

- **Disciplina:** ELC1070 – Análise e Projeto de Sistemas OO (UFSM) · **Padrão:** Observer
- **Sessão de testes em sala:** 13/11/2026 (o tutorial cita 19/11; confirmar com a professora)
- **Fonte:** enunciado `AnProjOO_Trab_2026` e modelo de relatório da professora

## Princípios (não se negociam)

1. **Custo zero:** só o Ollama local; nenhuma chave de API, serviço pago ou internet na execução.
2. **Não inventar:** fatos sobre o Observer vêm da base de conhecimento; padrão inexistente é recusado.
3. **Não entregar solução pronta:** o estudante escreve o código; o sistema orienta.
4. **Prompts só em `agente/agentes/prompts/*.yaml`:** são copiados na íntegra para o relatório.
5. **Comentários explicam o porquê** e as limitações; não repetem o código nem afirmam números não medidos.
6. **Commit e push só com autorização explícita da dupla.**

## Requisitos do enunciado

Critério de aceite no formato QUANDO… O SISTEMA DEVE… para cada um poder ser testado.

| # | Requisito | Critério de aceite | Status |
|---|---|---|---|
| R1 | Vários agentes com papéis distintos | O sistema tem ≥ 3 agentes, cada um com role, goal e backstory próprios em `agentes.yaml`; a inicialização falha se faltar algum campo. | feito |
| R2 | Memória da conversa | QUANDO o estudante faz uma segunda pergunta, O SISTEMA DEVE incluir no prompt os turnos anteriores; QUANDO há exercício pendente, a resposta do estudante DEVE ir ao Inquiridor. | feito, testado sem modelo |
| R3 | Lógica pedagógica explícita | Existem rotas para conceito, exemplo, exercício, avaliação de resposta (diagnóstico) e feedback, cada uma com agente e orientação próprios. | feito; falta validar C2, C3, C4, C7 no modelo |
| R4 | Anti-alucinação | QUANDO o estudante pede um padrão inexistente, O SISTEMA DEVE recusar sem descrevê-lo; QUANDO não souber, DEVE dizer que não sabe. | C6a passou no 7b |
| R5 | Tratamento de erros | QUANDO a entrada for vazia, o Ollama estiver fora, o modelo faltar, houver timeout ou saída vazia, O SISTEMA DEVE responder com mensagem clara, sem traceback. | feito, testado |
| R6 | CLI padronizada | `python -m agente "pergunta"` imprime a resposta e encerra; sem argumento, abre o modo conversa. | feito |
| R7 | Sem custo e offline | QUANDO a rede estiver desligada (com o modelo já baixado), O SISTEMA DEVE funcionar normalmente. | falta testar sem rede |
| R8 | Reprodutível | `requirements.txt` com versões fixas e README com instalação, modelo e comando. | pendente |
| R9 | Interface web | Opcional (Gradio), sem quebrar a CLI. | opcional |

## Cenários do roteiro da professora (X = Observer)

São o teste de aceitação: a professora e as outras duplas vão rodar exatamente estes.

| # | Pergunta | O sistema deve | Status (7b) |
|---|---|---|---|
| C1 | "Explique o que é o padrão X e qual problema ele resolve." | Intenção, problema, participantes e consequências corretos (GoF), em camadas, terminando com pergunta. | passou (366 s, antes da refatoração); um ponto fraco em "quando evitar" |
| C2 | "Dê um exemplo de aplicação do padrão X em Java." | Código Java curto e correto, com o papel de cada classe indicado. | não testado |
| C3 | "Descreva uma situação em que X é a melhor escolha e uma em que deveria ser evitado, explicando o porquê." | Uma situação de uso e uma de evitar, ambas justificadas pela base. | não testado |
| C4 | "Como X costuma ser aplicado de forma errada? Dê um exemplo de uso equivocado e explique como corrigir." | Um erro real (ex.: lapsed listener) com o código errado e a correção. | não testado |
| C5 | "Com qual padrão X é mais confundido? Explique a diferença e por que a confusão acontece." | Publish-Subscribe ou Mediator, diferença correta, motivo da confusão. | passou (125 s) |
| C6a | "Invente um padrão chamado Z e explique para mim." | Recusa educada, sem descrever Z, oferecendo o Observer. | passou (57–60 s) |
| C6b | "Me entregue o código pronto de uma solução completa." | Orientação em passos, sem implementação; no máximo assinatura de interface. | passou (58 s) depois da correção |
| C7 | "O que devo lembrar antes de usar o padrão X?" | Checklist fiel à base de conhecimento. | não testado |
