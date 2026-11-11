"""Memória da conversa (ConcreteObserver)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..nucleo.eventos import Evento, ObservadorConversa, TipoEvento
from ..nucleo.intencoes import Intencao

BLOCO_DE_CODIGO = re.compile(r"```.*?(```|$)", re.DOTALL)


class Memoria(ObservadorConversa):
    """Memória de curto prazo da conversa: turnos recentes e estado pedagógico.

    Só reage a TURNO_CONCLUIDO, que traz a resposta final entregue (já corrigida
    pelo Guardião, quando houve revisão). Turnos com erro ou saída vazia não geram
    esse evento, então não entram no histórico nem realimentam o modelo.
    Com `arquivo`, persiste em JSON para a CLI lembrar a conversa entre execuções (--sessao).
    """

    def __init__(self, max_turnos: int = 3, arquivo: Path | None = None, max_tentativas: int = 3) -> None:
        self.max_turnos = max_turnos         # quantos turnos vão para o prompt
        self.max_tentativas = max_tentativas
        self.arquivo = arquivo
        self.turnos: list[dict[str, str]] = []
        self.vistos: list[str] = []          # intenções já trabalhadas, para o agente não repetir
        # Respostas já avaliadas no exercício atual; -1 = nenhum exercício pendente.
        # Com exercício pendente, o roteador lê mensagens sem cara de pedido como resposta.
        self.tentativas = -1
        self._carregar()

    @property
    def exercicio_pendente(self) -> bool:
        return 0 <= self.tentativas < self.max_tentativas

    def atualizar(self, evento: Evento) -> None:
        if evento.tipo is not TipoEvento.TURNO_CONCLUIDO:
            return
        d = evento.dados
        intencao = Intencao(d["intencao"])
        self.turnos.append({"estudante": d["pergunta"], "tutor": d["resposta"], "intencao": intencao.value})
        self.turnos = self.turnos[-20:]  # limita o arquivo de sessão; o prompt usa só max_turnos
        if intencao is Intencao.EXERCICIO:
            self.tentativas = 0
        elif intencao is Intencao.RESPOSTA_EXERCICIO:
            self.tentativas += 1
        else:
            self.tentativas = -1         # o estudante mudou de assunto
        if intencao.value not in self.vistos:
            self.vistos.append(intencao.value)
        self._salvar()

    def como_texto(self, limite_resposta: int = 500) -> str:
        """Histórico para o prompt. Cada token a mais custa tempo de leitura no modelo local,
        então o código das respostas antigas é omitido e o texto cortado em `limite_resposta`
        caracteres. Omitir o código evita que o corte deixe um bloco pela metade."""
        recentes = self.turnos[-self.max_turnos:] if self.max_turnos else []
        if not recentes:
            return "(primeira mensagem da conversa)"
        linhas = []
        for t in recentes:
            resposta = BLOCO_DE_CODIGO.sub("[código omitido]", t["tutor"])
            if len(resposta) > limite_resposta:
                resposta = resposta[:limite_resposta] + " [...]"
            linhas.append(f"Estudante: {t['estudante']}\nTutor: {resposta}")
        if self.vistos:
            linhas.append("Temas já trabalhados: " + ", ".join(self.vistos))
        return "\n\n".join(linhas)

    def limpar(self) -> None:
        self.turnos.clear()
        self.vistos.clear()
        self.tentativas = -1
        self._salvar()

    def _carregar(self) -> None:
        if self.arquivo and self.arquivo.exists():
            try:
                dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
                self.turnos = dados.get("turnos", [])
                self.vistos = dados.get("vistos", [])
                self.tentativas = int(dados.get("tentativas", -1))
            except (json.JSONDecodeError, OSError, ValueError, AttributeError):
                pass  # arquivo corrompido ou ilegível: começa uma conversa nova

    def _salvar(self) -> None:
        if not self.arquivo:
            return
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        dados = {"turnos": self.turnos, "vistos": self.vistos, "tentativas": self.tentativas}
        self.arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
