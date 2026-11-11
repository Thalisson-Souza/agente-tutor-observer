# Base de conhecimento — padrão Observer (GoF)

Fonte: GAMMA, HELM, JOHNSON, VLISSIDES. Design Patterns (1994), capítulo de padrões comportamentais.
Cada seção começa com "## [id]". O sistema injeta no prompt apenas as seções relevantes para a pergunta.

## [conceito]
- Classificação: padrão comportamental de objetos (GoF).
- Intenção: definir uma dependência um-para-muitos entre objetos, de modo que quando um objeto muda de estado, todos os seus dependentes são notificados e atualizados automaticamente.
- Também conhecido como (GoF): Dependents, Publish-Subscribe.
- Problema: manter consistência entre objetos relacionados sem acoplá-los fortemente. Ex.: uma planilha e vários gráficos que mostram os mesmos dados; quando os dados mudam, todas as visões precisam ser atualizadas, mas os dados não devem conhecer as classes concretas das visões.
- Analogia: assinatura de um canal ou jornal: quem assina recebe as novidades; pode cancelar a assinatura a qualquer momento.

## [participantes]
- Subject (Sujeito): conhece seus observadores (qualquer número); oferece interface para anexar e desanexar observadores (attach/detach).
- Observer (Observador): define uma interface de atualização (update) para objetos que devem ser notificados.
- ConcreteSubject (Sujeito concreto): armazena o estado de interesse; notifica seus observadores quando o estado muda (notify).
- ConcreteObserver (Observador concreto): mantém referência ao ConcreteSubject (quando usa modelo pull); guarda estado que deve ficar consistente com o do sujeito; implementa update.
- Colaboração: o ConcreteSubject chama notify() ao mudar; notify() chama update() de cada observador; o observador pode consultar o sujeito (getState) para se sincronizar.
- Estrutura (UML resumida): Subject 1 ---- * Observer; ConcreteSubject herda/implementa Subject; ConcreteObserver implementa Observer.

## [consequencias]
- Acoplamento abstrato entre Subject e Observer: o sujeito só conhece a interface Observer, não as classes concretas.
- Suporte a comunicação broadcast: a notificação vai a todos os inscritos; observadores podem ser adicionados ou removidos em tempo de execução.
- Atualizações inesperadas: uma mudança aparentemente simples pode disparar cascata de atualizações custosa e difícil de depurar, pois observadores não sabem uns dos outros.
- Questões de implementação (GoF): modelo push (sujeito envia os dados na notificação) versus pull (observador busca o que precisa); quem dispara a notificação (o próprio sujeito após cada mudança ou o cliente após um lote de mudanças); garantir que o sujeito esteja em estado consistente antes de notificar; referências pendentes quando um sujeito é destruído; observar mais de um sujeito (update recebe o sujeito como parâmetro); notificar apenas interesses específicos (aspectos); ChangeManager para relações complexas.
- Padrões relacionados (GoF): Mediator (o ChangeManager atua como mediador entre sujeitos e observadores); Singleton (o ChangeManager pode ser único).

## [selecao]
- Usar quando: uma mudança em um objeto exige mudar outros e não se sabe quantos são; um objeto deve notificar outros sem fazer suposições sobre quem eles são; uma abstração tem dois aspectos, um dependente do outro, e se quer variá-los e reutilizá-los independentemente.
- Exemplos reais: interfaces gráficas (listeners de botão), MVC (modelo notifica as views), eventos de domínio, PropertyChangeListener em Java.
- Evitar quando: há um único dependente fixo e conhecido (uma chamada direta é mais simples); a ordem das notificações ou garantias transacionais são essenciais; atualizações muito frequentes com muitos observadores causam custo alto (considerar agrupar notificações); cascatas de atualização tornariam o fluxo difícil de entender e depurar.

## [uso_incorreto]
- Lapsed listener (vazamento de memória): observador nunca é desanexado (detach); o sujeito mantém a referência e impede a coleta de lixo. Correção: desanexar no fim do ciclo de vida, ou usar referências fracas.
- Modificar a lista de observadores durante a notificação (ex.: observador faz detach dentro de update) e causar ConcurrentModificationException. Correção: iterar sobre uma cópia da lista.
- Observador que altera o sujeito dentro de update, gerando notificações recursivas ou laço infinito. Correção: evitar alterar o sujeito em update ou usar guarda contra reentrância.
- Notificar antes de o estado estar consistente (ex.: notify no meio da alteração). Correção: notificar só depois de concluir a mudança.
- Trabalho pesado ou bloqueante dentro de update, travando o sujeito. Correção: manter update leve ou delegar o trabalho.
- Depender da ordem de notificação dos observadores (o padrão não garante ordem).
- Sujeito que conhece classes concretas de observadores (quebra o acoplamento abstrato). Correção: depender só da interface Observer.

## [confusao]
- Publish-Subscribe com broker/canal de eventos: publicadores e assinantes não se conhecem, há um intermediário (barramento, fila) e muitas vezes a entrega é assíncrona. No Observer clássico, o sujeito mantém diretamente a lista de observadores e os chama de forma síncrona. O GoF cita "Publish-Subscribe" como outro nome do Observer, por isso a confusão é comum.
- Mediator: centraliza a comunicação complexa entre vários colegas (muitos-para-muitos), contendo lógica de coordenação. O Observer distribui notificação um-para-muitos sem lógica central. Podem ser combinados: um Mediator pode usar Observer para receber eventos dos colegas.
- Chain of Responsibility: a requisição passa por uma cadeia até um manipulador tratar; no Observer todos os observadores inscritos são notificados.
- Java: java.util.Observer e java.util.Observable foram depreciados no Java 9; hoje se usam interfaces próprias, PropertyChangeListener ou bibliotecas de eventos.

## [exemplo]
Exemplo canônico em Java (estação meteorológica, modelo push):

```java
interface Observador { void atualizar(double temperatura); }

interface Sujeito {
    void anexar(Observador o);
    void desanexar(Observador o);
    void notificar();
}

class EstacaoMeteorologica implements Sujeito {          // ConcreteSubject
    private final List<Observador> observadores = new ArrayList<>();
    private double temperatura;
    public void anexar(Observador o) { observadores.add(o); }
    public void desanexar(Observador o) { observadores.remove(o); }
    public void notificar() {
        for (Observador o : List.copyOf(observadores)) o.atualizar(temperatura);
    }
    public void setTemperatura(double t) { this.temperatura = t; notificar(); }
}

class PainelCelsius implements Observador {              // ConcreteObserver
    public void atualizar(double t) { System.out.println("Agora: " + t + " °C"); }
}
```

## [fechamento]
Checklist antes de usar o Observer:
1. Existe mesmo uma relação um-para-muitos que muda em tempo de execução? Se há um único dependente fixo, chame-o diretamente.
2. Push ou pull? Defina o que vai na notificação.
3. Quem chama notify e quando? Só com o estado consistente.
4. Como e quando os observadores serão desanexados (evitar vazamento de memória)?
5. O código não pode depender da ordem de notificação.
6. Cuidado com cascatas e com observadores que alteram o sujeito.
7. update deve ser leve.
