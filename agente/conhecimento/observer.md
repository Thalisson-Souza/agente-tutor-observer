# Base de conhecimento — padrão Observer

Fonte principal: GAMMA, HELM, JOHNSON e VLISSIDES. Padrões de Projeto: Soluções Reutilizáveis
de Software Orientado a Objetos. Bookman, 2005 (bibliografia básica da disciplina), capítulo 5,
Observer, p. 274–283. Os fatos do livro trazem a página entre parênteses, com nossas palavras.
Itens marcados [prática] são conhecimento usual de programação, fora do livro.
Termos como na tradução: subject (assunto), observador (observer); as operações ficam em
inglês: Attach, Detach, Notify, Update, GetState, SetState.
Cada seção começa com "## [id]". O sistema injeta no prompt apenas as seções da pergunta.

## [conceito]
- Classificação: padrão comportamental de objetos (p. 274).
- Intenção: definir uma dependência um-para-muitos entre objetos, de modo que, quando um objeto muda de estado, todos os seus dependentes são notificados e atualizados automaticamente (p. 274).
- Também conhecido como: Dependents, Publish-Subscribe (p. 274). O livro diz que esse tipo de interação também é chamado de publish-subscribe: o subject publica notificações sem saber quem são seus observadores (p. 275).
- Problema (motivação): manter a consistência entre objetos relacionados sem acoplá-los fortemente, o que reduziria a reutilização. Exemplo do livro: uma planilha e um gráfico de barras mostram os mesmos dados; um não conhece o outro, mas quando o usuário muda a planilha o gráfico reflete na hora, e vice-versa. Pode haver qualquer número de visões dos mesmos dados (p. 274–275).
- Uso conhecido mais famoso: o MVC do Smalltalk, em que Model é o subject e View é a base dos observadores (p. 283).
- Analogia [prática]: assinatura de um jornal: quem assina recebe as novidades e pode cancelar a qualquer momento.

## [participantes]
- Subject: conhece os seus observadores (qualquer número) e fornece uma interface para acrescentá-los e removê-los (Attach, Detach) (p. 276).
- Quem faz o quê: Notify é operação do Subject e é o que notifica; Update é operação do Observer e é chamada por Notify, uma vez para cada observador. Confundir os dois é erro comum (p. 275–276).
- Observer: define uma interface de atualização (Update) para os objetos que devem ser notificados de mudanças no subject (p. 276).
- ConcreteSubject: armazena o estado de interesse dos ConcreteObservers e envia uma notificação aos observadores quando esse estado muda (p. 276).
- ConcreteObserver: mantém uma referência para um ConcreteSubject, guarda o estado que deve ficar consistente com o do subject e implementa Update para manter essa consistência (p. 276).
- Colaborações: o ConcreteSubject notifica os observadores sempre que uma mudança puder deixá-los inconsistentes; depois de notificado, o ConcreteObserver pode consultar o subject (GetState) para se atualizar. Notify nem sempre é chamado pelo subject: pode ser chamado por um observador ou por outro objeto (p. 276).
- Estrutura: Subject (Attach, Detach, Notify) com uma lista de Observer (Update); ConcreteSubject (GetState, SetState, subjectState) estende Subject; ConcreteObserver (Update, observerState) implementa Observer e referencia o ConcreteSubject. Notify percorre a lista chamando Update de cada observador (p. 275).

## [consequencias]
- Subject e observadores variam e são reutilizados de forma independente, e dá para acrescentar observadores sem modificar o subject nem os outros observadores (p. 276).
- Acoplamento abstrato entre Subject e Observer: o subject só sabe que tem uma lista de objetos com a interface Observer, sem conhecer suas classes concretas. Por isso podem ficar em camadas diferentes do sistema: um subject de nível baixo avisa um observador de nível alto sem quebrar as camadas (p. 277).
- Suporte a comunicação broadcast: a notificação não especifica o receptor e vai para todos os inscritos; observadores entram e saem a qualquer momento, e cada um decide se trata ou ignora a notificação (p. 277).
- Atualizações inesperadas: como um observador não sabe dos outros, uma operação aparentemente inofensiva no subject pode causar uma cascata de atualizações; dependências mal definidas geram atualizações espúrias difíceis de achar. Piora porque o protocolo simples de Update não diz o que mudou (p. 277).

## [implementacao]
Questões de implementação discutidas no livro (p. 277–280):
1. Mapear subjects para observadores: o mais simples é o subject guardar as referências; com muitos subjects e poucos observadores, uma tabela hash economiza memória em troca de acesso mais lento (p. 277).
2. Observar mais de um subject: Update recebe o subject como parâmetro, para o observador saber quem notificou (p. 277–278).
3. Quem dispara a atualização: (a) as operações que mudam o estado do subject chamam Notify: o cliente não precisa lembrar, mas várias mudanças seguidas geram várias atualizações; (b) o cliente chama Notify no momento certo: evita atualizações intermediárias, mas o cliente pode esquecer (p. 278).
4. Referências pendentes: ao ser apagado, o subject deve avisar os observadores para que não fiquem apontando para ele (p. 278).
5. Estado consistente antes de notificar: os observadores consultam o subject durante a atualização, então Notify só pode ser chamado com o estado completo. Uma forma de garantir é fazer Notify a última operação de um Template Method na classe Subject. Documente quais operações disparam notificação (p. 278).
6. Modelos push e pull: no push o subject manda detalhes da mudança, queiram ou não os observadores, o que supõe que ele conhece suas necessidades e os deixa menos reutilizáveis; no pull ele manda a notificação mínima e cada observador busca o que precisa, o que pode ser ineficiente (p. 279).
7. Interesses específicos: o observador se registra só para certos eventos (aspectos), e o subject avisa apenas os interessados (p. 279).
8. ChangeManager: para dependências complexas, um objeto mapeia subjects a observadores, define a estratégia de atualização e atualiza os dependentes. O SimpleChangeManager atualiza todos sempre; o DAGChangeManager evita atualização repetida quando um observador observa vários subjects. O ChangeManager é uma instância do Mediator e pode ser Singleton (p. 279–280).
9. Em linguagens sem herança múltipla (como Smalltalk) as interfaces de Subject e Observer costumam ficar numa única classe (p. 280).

## [selecao]
Quando usar, segundo o livro (p. 275):
- uma abstração tem dois aspectos, um dependente do outro, e separá-los em objetos permite variar e reutilizar cada um;
- uma mudança em um objeto exige mudar outros, e não se sabe quantos;
- um objeto deve notificar outros sem fazer suposições sobre quem eles são, ou seja, sem acoplamento forte.
O livro não lista quando evitar; os critérios abaixo saem das consequências e da prática:
- há um único dependente fixo e conhecido: uma chamada direta é mais simples [prática];
- uma mudança pode disparar cascatas de atualização custosas ou difíceis de rastrear (consequência "atualizações inesperadas", p. 277);
- a ordem das notificações ou garantias transacionais importam [prática: o padrão não define ordem];
- atualizações muito frequentes com muitos observadores ficam caras; considere agrupar notificações ou deixar o cliente disparar Notify (p. 278).
Exemplos reais [prática]: listeners de interface gráfica, MVC, eventos de domínio, PropertyChangeListener em Java.

## [uso_incorreto]
Erros que contrariam o livro:
- Notificar com o subject em estado inconsistente, por exemplo chamando Notify no meio de uma alteração ou numa subclasse antes de terminar a mudança. Correção: Notify por último, de preferência num Template Method (p. 278).
- Apagar o subject sem avisar os observadores, deixando referências pendentes (p. 278).
- Subject que conhece as classes concretas dos observadores, o que quebra o acoplamento abstrato. Correção: depender só da interface Observer (p. 277).
- Cliente que esquece de chamar Notify quando essa responsabilidade é dele (p. 278).
Erros comuns de implementação [prática, fora do livro]:
- Lapsed listener (vazamento de memória): observador nunca desanexado (Detach); o subject mantém a referência e impede a coleta de lixo. Correção: desanexar no fim do ciclo de vida, ou usar referências fracas.
- Modificar a lista de observadores durante a notificação (ex.: observador faz Detach dentro de Update), causando ConcurrentModificationException. Correção: iterar sobre uma cópia da lista.
- Observador que altera o subject dentro de Update, gerando notificações recursivas. Correção: não alterar o subject em Update ou usar guarda contra reentrância.
- Trabalho pesado ou bloqueante dentro de Update, travando o subject.
- Depender da ordem de notificação dos observadores.

Exemplo em Java [prática] do erro de desanexar durante a notificação. O problema só existe porque
o Detach acontece DENTRO de atualizar(), enquanto o for do subject percorre a lista; um Detach
feito fora da notificação (ex.: no main, depois de notificar) é correto e não causa erro.

```java
// ERRADO: o observador se desanexa enquanto o subject percorre a lista
class AlertaUnico implements Observador {
    private final Estacao estacao;
    AlertaUnico(Estacao e) { this.estacao = e; }
    public void atualizar(double t) {
        System.out.println("Alerta: " + t);
        estacao.desanexar(this);   // altera a lista no meio do for abaixo
    }
}

class Estacao {
    private final List<Observador> observadores = new ArrayList<>();
    public void desanexar(Observador o) { observadores.remove(o); }
    public void notificar(double t) {
        // lança ConcurrentModificationException (ou pula observadores sem avisar)
        for (Observador o : observadores) o.atualizar(t);
    }
}

// CORREÇÃO: percorrer uma cópia; mudanças na lista original não afetam a iteração
public void notificar(double t) {
    for (Observador o : List.copyOf(observadores)) o.atualizar(t);
}
```

## [confusao]
- Mediator: o livro diz que Mediator e Observer "competem entre si". O Observer distribui a comunicação entre objetos subject e observer, que cooperam para manter a consistência; o Mediator a encapsula num objeto central. Observers e subjects são mais fáceis de reutilizar; o fluxo de comunicação do Mediator é mais fácil de entender, porque no Observer as ligações são feitas logo após a criação e ficam difíceis de ver depois (p. 319). Os dois se combinam: o ChangeManager é um Mediator entre subjects e observadores (p. 280, 283).
- Comparando formas de desacoplar emissor e receptor (Command, Observer, Mediator, Chain of Responsibility), o livro diz que o Observer é o melhor quando há dependência de dados entre os objetos; o Command liga um emissor a um receptor; na Chain of Responsibility a solicitação passa por uma cadeia até alguém tratar, enquanto no Observer todos os inscritos são notificados (p. 319–321).
- Publish-Subscribe: o livro usa o nome como sinônimo do Observer (p. 274–275), por isso a confusão é comum. Hoje "Publish-Subscribe" costuma designar a arquitetura com intermediário (barramento, broker, fila), em que publicadores e assinantes não se conhecem e a entrega muitas vezes é assíncrona; no Observer clássico o subject mantém a lista de observadores e os chama diretamente [prática]. Quem conhece quem: no Observer o subject conhece os observadores (só pela interface) e o ConcreteObserver referencia o ConcreteSubject (p. 276); no Publish-Subscribe com broker nenhum dos lados conhece o outro [prática].
- Java [prática]: java.util.Observer e java.util.Observable foram depreciados no Java 9; hoje se usam interfaces próprias, PropertyChangeListener ou bibliotecas de eventos.

## [exemplo]
Exemplo do livro: ClockTimer (subject concreto que guarda a hora e notifica a cada segundo, por meio de Tick) com DigitalClock e AnalogClock como observadores; o Update recebe o subject e confere se é o seu relógio antes de redesenhar (p. 280–283). O livro usa C++.
Exemplo em Java [prática], com os mesmos papéis (modelo push):

```java
interface Observador { void atualizar(double temperatura); }

interface Sujeito {                                       // Subject
    void anexar(Observador o);                            // Attach
    void desanexar(Observador o);                         // Detach
    void notificar();                                     // Notify
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
2. Push ou pull? Defina o que vai na notificação (p. 279).
3. Quem chama Notify e quando? Só com o estado consistente (p. 278).
4. Como e quando os observadores serão desanexados (evitar vazamento de memória)?
5. O código não pode depender da ordem de notificação.
6. Cuidado com cascatas e com observadores que alteram o subject (p. 277).
7. Update deve ser leve.
