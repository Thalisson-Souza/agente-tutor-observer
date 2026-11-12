"""Chat de terminal com Rich: respostas em Markdown, agente ativo e atalhos do roteiro."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .. import config
from ..aplicacao.sistema import Orquestrador, SistemaTutor
from ..observadores.painel_rich import PainelRich
from .roteiro import ATALHOS, PERGUNTAS


@dataclass(frozen=True)
class Comando:
    acao: str           # "pergunta", "modelo", "nova", "ajuda", "sair" ou "invalido"
    texto: str = ""     # a pergunta, o nome do modelo ou o comando desconhecido


def interpretar(entrada: str) -> Comando:
    """Traduz o que foi digitado. Texto sem barra é pergunta; /1 a /7 viram a pergunta
    do roteiro. Separado da tela para ser testado sem terminal nem modelo."""
    texto = entrada.strip()
    if not texto.startswith("/"):
        return Comando("pergunta", texto)
    nome = texto[1:].strip().lower()
    if nome in ATALHOS:
        return Comando("pergunta", PERGUNTAS[ATALHOS[nome]])
    if nome in ("sair", "exit", "quit"):
        return Comando("sair")
    if nome in ("nova", "ajuda"):
        return Comando(nome)
    if nome.startswith("modelo"):
        # "/modelo 3b" ou "/modelo qwen2.5:3b"; sem argumento, mostra o atual
        pedido = nome[len("modelo"):].strip()
        escolhido = next((m for m in config.MODELOS if pedido and (m == pedido or m.endswith(":" + pedido))), "")
        return Comando("modelo", escolhido) if escolhido or not pedido else Comando("invalido", texto)
    return Comando("invalido", texto)


def _ajuda() -> Table:
    tabela = Table(show_header=False, box=None, padding=(0, 2))
    for atalho, cid in ATALHOS.items():
        tabela.add_row(f"[bold]/{atalho}[/]", f"{cid}: {PERGUNTAS[cid]}")
    for modelo, descricao in config.MODELOS.items():
        tabela.add_row(f"[bold]/modelo {modelo.split(':')[-1]}[/]", f"usa o {modelo} ({descricao})")
    tabela.add_row("[bold]/nova[/]", "começa uma conversa nova (apaga a memória)")
    tabela.add_row("[bold]/sair[/]", "encerra")
    return tabela


def conversar(sistema: SistemaTutor, console: Console | None = None,
              criar_orquestrador: Callable[[str], Orquestrador] | None = None) -> None:
    """`criar_orquestrador(modelo)` habilita o /modelo; cada modelo é criado uma vez."""
    console = console or Console()
    orquestradores = {sistema.orquestrador.modelo: sistema.orquestrador}
    painel = PainelRich(console)
    sistema.conversa.anexar(painel)

    console.print(Panel("Pergunte sobre o padrão Observer ou use os atalhos do roteiro.\n"
                        f"[dim]modelo {sistema.orquestrador.modelo} · /ajuda mostra os comandos · /sair encerra · "
                        "cada resposta leva de 1 a 4 minutos[/]",
                        title="Tutor Observer", border_style="cyan"))
    while True:
        try:
            entrada = console.input("\n[bold green]Você:[/] ")
        except (EOFError, KeyboardInterrupt):
            console.print()
            return
        comando = interpretar(entrada)
        if comando.acao == "sair":
            return
        if comando.acao == "nova":
            sistema.reiniciar()
            console.print("[dim]Conversa reiniciada.[/]")
            continue
        if comando.acao == "ajuda":
            console.print(_ajuda())
            continue
        if comando.acao == "modelo":
            if comando.texto and criar_orquestrador:
                if comando.texto not in orquestradores:
                    orquestradores[comando.texto] = criar_orquestrador(comando.texto)
                sistema.usar_orquestrador(orquestradores[comando.texto])
            console.print(f"[dim]Modelo: {sistema.orquestrador.modelo} (a conversa continua).[/]")
            continue
        if comando.acao == "invalido":
            console.print(f"[yellow]Comando desconhecido: {comando.texto}. Use /ajuda.[/]")
            continue
        if entrada.strip().startswith("/"):
            console.print(f"[dim]Pergunta: {comando.texto}[/]")

        painel.novo_turno()
        try:
            resposta = sistema.resposta(comando.texto)
        except KeyboardInterrupt:  # Ctrl+C no meio da resposta: volta ao prompt
            painel.parar()
            console.print("[yellow]Resposta interrompida.[/]")
            continue

        turno = painel.turno
        console.print(Panel(Markdown(resposta, code_theme="monokai"),
                            title=" → ".join(turno.agentes) or "Sistema",
                            subtitle=turno.detalhes(), border_style="blue"))
