"""Fachada do tutor: coordena um turno da conversa sem conhecer o CrewAI.

Fluxo de um turno:
    1. valida a entrada (vazia, longa demais);
    2. confere se o Ollama e o modelo estão disponíveis;
    3. o roteador classifica a intenção e escolhe UM agente especialista;
    4. o orquestrador executa a rota: só o especialista, ou especialista -> Guardião
       nas rotas de risco (Rota.revisar); padrão inventado vai direto ao Guardião;
    5. nas rotas com Rota.bloquear_solucao, remove código de implementação (regras/salvaguardas.py);
    6. notifica os observadores (memória, log, progresso).

O orquestrador é recebido pelo construtor (injeção de dependência): montar_sistema()
liga o real, e os testes passam um falso que responde sem o modelo.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol

from .. import config
from ..conhecimento import trecho
from ..nucleo.erros import FalhaModelo
from ..nucleo.eventos import Conversa, TipoEvento
from ..nucleo.intencoes import Resultado, Rota
from ..observadores import IndicadorProgresso, LogArquivo, Memoria
from ..regras.roteador import classificar
from ..regras.salvaguardas import sem_solucao_pronta

class Orquestrador(Protocol):
    """Porta para o modelo. Implementada por agentes/orquestrador.py e, nos testes, por um falso."""

    modelo: str  # nome do modelo no Ollama, registrado em cada resposta

    def verificar(self) -> str | None:
        """Mensagem para o estudante se o modelo estiver indisponível; None se estiver ok."""

    def executar(self, rota: Rota, entradas: dict[str, str], com_revisao: bool) -> Resultado:
        """Executa a rota. Falhas do modelo saem como FalhaModelo."""


class SistemaTutor:
    def __init__(self, orquestrador: Orquestrador, memoria: Memoria, conversa: Conversa | None = None) -> None:
        self.orquestrador = orquestrador
        self.memoria = memoria
        self.conversa = conversa or Conversa()
        self.conversa.anexar(memoria)

    def resposta(self, pergunta: str) -> str:
        pergunta = (pergunta or "").strip()
        if not pergunta:
            return "Você não digitou nada. Pergunte algo sobre o padrão Observer, por exemplo: \"O que é o Observer?\""
        aviso = ""
        if len(pergunta) > config.MAX_CARACTERES_ENTRADA:
            pergunta = pergunta[: config.MAX_CARACTERES_ENTRADA]
            aviso = f"(Sua mensagem foi cortada em {config.MAX_CARACTERES_ENTRADA} caracteres.)\n\n"

        problema = self.orquestrador.verificar()
        if problema:
            return problema

        rota = classificar(pergunta, self.memoria.exercicio_pendente)
        com_revisao = rota.com_revisao(config.USAR_GUARDIAO, config.REVISAR_TUDO)
        intencao = rota.intencao.value
        self.conversa.notificar(TipoEvento.PERGUNTA_RECEBIDA, pergunta=pergunta, intencao=intencao)
        self.conversa.notificar(TipoEvento.AGENTE_INICIADO, intencao=intencao,
                                agentes=[a.value for a in rota.agentes(com_revisao)])
        entradas = {
            "pergunta": pergunta,
            "historico": self.memoria.como_texto(),
            "conhecimento": trecho(rota.secoes),
        }

        inicio = time.perf_counter()
        try:
            resultado = self.orquestrador.executar(rota, entradas, com_revisao)
        except FalhaModelo as erro:  # já traz a mensagem para o estudante
            self.conversa.notificar(TipoEvento.ERRO, pergunta=pergunta, erro=repr(erro.__cause__ or erro))
            return aviso + str(erro)
        except Exception as erro:    # defeito do próprio sistema: registra e não derruba a conversa
            self.conversa.notificar(TipoEvento.ERRO, pergunta=pergunta, erro=repr(erro))
            return aviso + "Tive um problema interno ao gerar a resposta. Tente de novo ou reformule a pergunta."

        if resultado.veredito:
            self.conversa.notificar(TipoEvento.REVISAO, veredito=resultado.veredito, revisao=resultado.revisao_bruta)
        texto = resultado.texto
        if rota.bloquear_solucao:
            texto, alterado = sem_solucao_pronta(texto)
            if alterado:
                self.conversa.notificar(TipoEvento.REVISAO, veredito="codigo_removido",
                                        revisao=resultado.texto[:300])
        if not texto:
            self.conversa.notificar(TipoEvento.ERRO, pergunta=pergunta, erro="saida_vazia")
            return aviso + "O modelo devolveu uma resposta vazia. Pode reformular a pergunta?"

        self.conversa.notificar(TipoEvento.TURNO_CONCLUIDO, pergunta=pergunta, resposta=texto,
                                intencao=intencao, segundos=time.perf_counter() - inicio, modelo=self.orquestrador.modelo)
        return aviso + texto

    def usar_orquestrador(self, orquestrador: Orquestrador) -> None:
        """Troca o modelo no meio da conversa. A memória continua: o novo modelo recebe o
        mesmo histórico."""
        self.orquestrador = orquestrador

    def reiniciar(self) -> None:
        self.memoria.limpar()


def montar_sistema(arquivo_sessao: Path | None = None, mostrar_progresso: bool = True,
                   orquestrador: Orquestrador | None = None) -> SistemaTutor:
    """Liga as peças reais. Importa o orquestrador aqui para que os testes da fachada
    não precisem carregar o CrewAI.

    `orquestrador` permite reaproveitar um já criado: a interface web monta um SistemaTutor
    por aba do navegador, todos com o mesmo orquestrador e memórias separadas."""
    if orquestrador is None:
        from ..agentes.orquestrador import OrquestradorCrewAI
        orquestrador = OrquestradorCrewAI()

    conversa = Conversa()
    conversa.anexar(LogArquivo(config.RAIZ / "logs" / "conversa.jsonl"))
    if mostrar_progresso:
        conversa.anexar(IndicadorProgresso())
    memoria = Memoria(config.TURNOS_HISTORICO, arquivo_sessao, config.MAX_TENTATIVAS_EXERCICIO)
    return SistemaTutor(orquestrador, memoria, conversa)
