"""Ponto de entrada padronizado.

    python -m agente "pergunta aqui"     responde uma vez e encerra
    python -m agente                     abre o chat no terminal (com memória e Rich)
    python -m agente --simples           chat em texto puro, sem Rich
    python -m agente --web               chat no navegador (opcional: requirements-web.txt)
    python -m agente --sessao s1 "..."   pergunta única, mas lembrando da sessão 's1'
"""

import argparse
import sys

from . import config
from .aplicacao.sistema import SistemaTutor, montar_sistema
from .nucleo.erros import ErroDeConfiguracao


def conversar_simples(sistema: SistemaTutor) -> None:
    print("Sistema pedagógico: padrão Observer.")
    print("Digite 'sair' para encerrar e 'nova' para começar uma nova conversa.")
    while True:
        try:
            pergunta = input("\nVocê: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        comando = pergunta.strip().lower()
        if comando in ("sair", "exit", "quit"):
            return
        if comando == "nova":
            sistema.reiniciar()
            print("Sistema: conversa reiniciada.")
            continue
        print(f"\nSistema: {sistema.resposta(pergunta)}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m agente", description="Tutor multiagente do padrão Observer")
    parser.add_argument("pergunta", nargs="*", help="pergunta (sem pergunta abre o modo conversa)")
    parser.add_argument("--sessao", help="nome de uma sessão para guardar a memória entre execuções")
    parser.add_argument("--simples", action="store_true", help="chat em texto puro, sem a interface Rich")
    parser.add_argument("--web", action="store_true", help="chat no navegador (precisa do requirements-web.txt)")
    args = parser.parse_args()

    if args.web:
        try:
            from .interface.web import iniciar
        except ModuleNotFoundError as erro:
            if erro.name != "gradio":
                raise
            sys.exit("A interface web precisa do Gradio: pip install -r requirements-web.txt")
        try:
            iniciar()
        except ErroDeConfiguracao as erro:
            sys.exit(f"Erro de configuração dos prompts: {erro}")
        return

    # Rich só no chat interativo num terminal de verdade: com a saída redirecionada
    # (scripts, arquivo) ou com --simples, o texto sai puro.
    usar_rich = not args.pergunta and not args.simples and sys.stdout.isatty()

    arquivo = config.RAIZ / ".sessoes" / f"{args.sessao}.json" if args.sessao else None
    try:
        sistema = montar_sistema(arquivo_sessao=arquivo, mostrar_progresso=not usar_rich)
    except ErroDeConfiguracao as erro:
        sys.exit(f"Erro de configuração dos prompts: {erro}")

    if args.pergunta:
        print(sistema.resposta(" ".join(args.pergunta)))
    elif usar_rich:
        from .agentes.orquestrador import OrquestradorCrewAI
        from .interface.terminal import conversar
        conversar(sistema, criar_orquestrador=OrquestradorCrewAI)
    else:
        conversar_simples(sistema)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # Ctrl+C durante uma resposta: sai sem traceback
        sys.exit(130)          # 130 = código de saída convencional para interrupção por Ctrl+C
