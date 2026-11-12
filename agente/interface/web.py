"""Chat no navegador com Gradio (opcional): python -m agente --web

Abre só em 127.0.0.1, sem link público e sem estatísticas de uso, para funcionar sem
internet. Cada aba do navegador tem seu próprio SistemaTutor (memória separada), todos com
o mesmo orquestrador por modelo, que é quem mantém o modelo e os agentes. O seletor de
modelo troca o orquestrador da aba sem apagar a memória da conversa.

Layout: barra lateral com o roteiro da professora agrupado por tema, "Praticar" e "Nova
conversa"; chat à direita. Tema "Minimal" (interface/tema/), guardado no repositório.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Antes de importar o Gradio: com isso ele não envia estatísticas de uso pela internet.
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr  # noqa: E402
from gradio.themes.utils.fonts import Font, LocalFont  # noqa: E402

from .. import config  # noqa: E402
from ..aplicacao.sistema import Orquestrador, SistemaTutor, montar_sistema  # noqa: E402
from ..observadores.turno import ColetorTurno  # noqa: E402
from .roteiro import PERGUNTAS  # noqa: E402

TEMA = Path(__file__).with_name("tema") / "minimal.json"

# Roteiro agrupado por tema na barra lateral: (título do grupo, [(cenário, rótulo)]).
GRUPOS = [
    ("Entender", [("C1", "C1 · Conceito"), ("C3", "C3 · Quando usar"),
                  ("C5", "C5 · Confusões"), ("C7", "C7 · O que lembrar")]),
    ("Código", [("C2", "C2 · Exemplo em Java"), ("C4", "C4 · Uso incorreto")]),
    ("Limites do tutor", [("C6a", "C6 · Invente um padrão"), ("C6b", "C6 · Código pronto")]),
]
PRATICAR = "Quero praticar com um exercício sobre o Observer."

COMO_FUNCIONA = """\
Cada pergunta vai para **um agente**, escolhido pelo tipo de pergunta:

- **Tutor**: explica o conceito e recusa assuntos fora do Observer.
- **Exemplificador**: exemplos em Java e usos incorretos.
- **Inquiridor**: exercícios, correção das suas respostas e comparação com padrões parecidos.
- **Guardião**: recusa padrões inventados.

Os fatos vêm de uma base de conhecimento fixa do Observer (catálogo GoF). Pedidos de código
pronto recebem um roteiro de passos, não a solução.
"""

# Ajustes de layout sobre o tema: barra lateral estreita com botões alinhados à esquerda,
# chat ocupando a altura da janela e cabeçalho numa linha só.
CSS = """
.cabecalho { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.cabecalho h2 { margin: 0; }
.cabecalho p { margin: 2px 0 0; opacity: .75; }
.selo { font-family: var(--font-mono); font-size: .8rem; padding: 4px 12px; border-radius: 999px;
        border: 1px solid var(--border-color-primary); white-space: nowrap; }
#barra { max-width: 280px; gap: 6px; max-height: calc(100vh - 110px); overflow-y: auto; overflow-x: hidden; }
#barra .grupo { margin: 12px 0 0; font-size: .7rem; letter-spacing: .08em; text-transform: uppercase;
                opacity: .65; }
#barra .titulo { font-weight: 600; }
.roteiro { justify-content: flex-start !important; text-align: left !important; }
"""

# Uma fila só para todas as entradas: o modelo na CPU responde uma pergunta por vez, e duas
# ao mesmo tempo dobrariam o tempo das duas.
FILA = dict(concurrency_limit=1, concurrency_id="modelo")

QUADROS = "⏳⌛"  # alternam a cada segundo: mostra que a página não travou


def aguardando(agentes: list[str], segundos: float) -> str:
    """Mensagem de espera atualizada a cada segundo. Função pura, testável."""
    quem = " → ".join(agentes) or "Preparando a resposta"
    return (f"{QUADROS[int(segundos) % len(QUADROS)]} **{quem}** trabalhando… {segundos:.0f} s\n\n"
            "<sub>O modelo local leva de 1 a 4 minutos. Os botões voltam quando a resposta chegar.</sub>")


def com_rodape(texto: str, turno) -> str:
    """Resposta + linha discreta com agente, tempo e veredito. Função pura, testável."""
    rodape = turno.rodape()
    return f"{texto}\n\n<sub>{rodape}</sub>" if rodape else texto


def carregar_tema() -> gr.themes.ThemeClass:
    """Tema Minimal do repositório, com as fontes trocadas por versões locais.

    O JSON original aponta para o Google Fonts; sem internet o navegador cairia na fonte
    padrão. Source Sans 3 (nome atual da Source Sans Pro) vem embutida no Gradio; a Ubuntu
    Mono é a do sistema, com fontes de reserva para máquinas que não a tenham.
    """
    tema = gr.Theme.load(str(TEMA))
    texto = LocalFont("Source Sans 3", weights=(400, 600))
    tema._font = [texto, "ui-sans-serif", "system-ui", "sans-serif"]
    tema._font_mono = [Font("Ubuntu Mono"), "ui-monospace", "Consolas", "monospace"]
    tema.font = "'Source Sans 3', ui-sans-serif, system-ui, sans-serif"
    tema.font_mono = "'Ubuntu Mono', ui-monospace, Consolas, monospace"
    # O JSON já traz prontos os endereços do Google Fonts (_stylesheets) e as regras de fonte
    # (_font_css), e o Gradio usa essas listas direto: trocar só _font não bastava.
    tema._stylesheets = []
    tema._font_css = [texto.stylesheet()["css"]]
    return tema


def criar_app(criar_orquestrador: Callable[[str], Orquestrador]) -> gr.Blocks:
    """`criar_orquestrador(modelo)` é chamado uma vez por modelo; as abas compartilham o
    mesmo orquestrador de cada modelo."""
    orquestradores: dict[str, Orquestrador] = {}
    trava = threading.Lock()  # duas abas escolhendo o mesmo modelo ao mesmo tempo

    def orquestrador(modelo: str) -> Orquestrador:
        with trava:
            if modelo not in orquestradores:
                orquestradores[modelo] = criar_orquestrador(modelo)
            return orquestradores[modelo]

    def nova_sessao(modelo: str) -> tuple[SistemaTutor, ColetorTurno]:
        sistema = montar_sistema(mostrar_progresso=False, orquestrador=orquestrador(modelo))
        coletor = ColetorTurno()
        sistema.conversa.anexar(coletor)
        return sistema, coletor

    def responder(pergunta: str, historico: list, sessao, modelo: str):
        pergunta = (pergunta or "").strip()
        if not pergunta:
            yield historico, "", sessao
            return
        if sessao is None:
            sessao = nova_sessao(modelo)
        sistema, coletor = sessao
        historico = historico + [{"role": "user", "content": pergunta}]
        # A resposta roda numa thread para a mensagem de espera ser atualizada a cada segundo
        # com o agente ativo (vindo do coletor) e o tempo. Sem isso a tela ficava parada por
        # minutos e o usuário clicava de novo, enfileirando outra pergunta.
        coletor.novo_turno()
        inicio = time.monotonic()
        with ThreadPoolExecutor(max_workers=1) as executor:
            futuro = executor.submit(sistema.resposta, pergunta)
            while not futuro.done():
                espera = aguardando(coletor.turno.agentes, time.monotonic() - inicio)
                yield historico + [{"role": "assistant", "content": espera}], "", sessao
                time.sleep(1)
            texto = futuro.result()
        historico = historico + [{"role": "assistant", "content": com_rodape(texto, coletor.turno)}]
        yield historico, "", sessao

    def trocar_modelo(modelo: str, sessao):
        if sessao is not None:
            sessao[0].usar_orquestrador(orquestrador(modelo))
        return sessao

    def reiniciar(sessao):
        if sessao is not None:
            sessao[0].reiniciar()
        return [], sessao

    with gr.Blocks(title="Tutor Observer", analytics_enabled=False) as app:
        gr.HTML("<div class='cabecalho'><div><h2>Tutor Observer</h2>"
                "<p>Aprenda o padrão de projeto Observer com 4 agentes de IA.</p></div>"
                "<span class='selo'>modelo local · sem internet</span></div>")
        sessao = gr.State(None)
        botoes: list[tuple[gr.Button, str]] = []

        with gr.Row(equal_height=False):
            with gr.Column(scale=0, min_width=240, elem_id="barra"):
                gr.HTML("<div class='titulo'>Roteiro da professora</div>")
                for titulo, itens in GRUPOS:
                    gr.HTML(f"<div class='grupo'>{titulo}</div>")
                    for cid, rotulo in itens:
                        botoes.append((gr.Button(rotulo, size="sm", elem_classes="roteiro"), PERGUNTAS[cid]))
                gr.HTML("<div class='grupo'>Modelo</div>")
                seletor = gr.Radio([(f"{m} · {d}", m) for m, d in config.MODELOS.items()],
                                   value=config.MODELO, show_label=False, container=False)
                gr.HTML("<div class='grupo'>Prática</div>")
                praticar = gr.Button("▶ Praticar", variant="primary", size="sm")
                botoes.append((praticar, PRATICAR))
                nova = gr.Button("↺ Nova conversa", variant="secondary", size="sm")
                with gr.Accordion("Como funciona", open=False):
                    gr.Markdown(COMO_FUNCIONA)

            with gr.Column(scale=1):
                # Altura acompanha a janela: em monitor grande não sobra espaço vazio embaixo,
                # em tela pequena não passa da dobra.
                chat = gr.Chatbot(height="calc(100vh - 200px)", min_height=380, show_label=False,
                                  layout="panel", group_consecutive_messages=False,
                                  placeholder="Escolha uma pergunta do roteiro ou escreva a sua.")
                with gr.Row():
                    caixa = gr.Textbox(placeholder="Pergunte sobre o padrão Observer", show_label=False,
                                       scale=5, container=False)
                    enviar = gr.Button("Enviar", variant="primary", scale=1, min_width=90)

        # Enquanto uma resposta é gerada, caixa e botões ficam travados: um segundo clique
        # entraria na fila e rodaria depois, sem o usuário querer.
        entradas = [caixa, enviar, nova, seletor, *(b for b, _ in botoes)]

        def travar():
            return [gr.update(interactive=False)] * len(entradas)

        def liberar():
            return [gr.update(interactive=True)] * len(entradas)

        def ligar(evento, pergunta):
            (evento(travar, None, entradas, queue=False)
             .then(responder, [pergunta, chat, sessao, seletor], [chat, caixa, sessao], **FILA)
             .then(liberar, None, entradas, queue=False))

        ligar(caixa.submit, caixa)
        ligar(enviar.click, caixa)
        for botao, pergunta in botoes:
            ligar(botao.click, gr.State(pergunta))
        nova.click(reiniciar, [sessao], [chat, sessao])
        seletor.change(trocar_modelo, [seletor, sessao], [sessao])
    return app


def lancar(app: gr.Blocks, porta: int = 7860, abrir_navegador: bool = True) -> None:
    """Sobe o servidor só nesta máquina, sem link público, sem renderização no servidor
    (que usaria Node) e sem o rodapé de propaganda do Gradio."""
    app.queue().launch(server_name="127.0.0.1", server_port=porta, share=False,
                       inbrowser=abrir_navegador, theme=carregar_tema(), css=CSS,
                       ssr_mode=False, footer_links=[])


def iniciar() -> None:
    from ..agentes.orquestrador import OrquestradorCrewAI

    lancar(criar_app(OrquestradorCrewAI))
