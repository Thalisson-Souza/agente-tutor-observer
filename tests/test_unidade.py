"""Testes que rodam sem o Ollama (segundos). Rodar com: python -m unittest -v

O SistemaTutor recebe um OrquestradorFalso, então memória, roteamento, eventos e
tratamento de erros são testados sem chamar o modelo.
"""

import io
import tempfile
import unittest
from pathlib import Path

from agente.nucleo.erros import ErroDeConfiguracao, FalhaModelo
from agente.nucleo.eventos import Conversa, ObservadorConversa, TipoEvento
from agente.nucleo.intencoes import Intencao, NomeAgente, Resultado
from agente.observadores import Memoria
from agente.observadores.memoria import pergunta_final
from agente.interface.roteiro import PERGUNTAS
from agente.agentes.orquestrador import interpretar_revisao
from agente.regras.roteador import ROTAS, classificar
from agente.regras.salvaguardas import AVISO, ROTEIRO_PADRAO, sem_solucao_pronta
from agente.aplicacao.sistema import SistemaTutor

ROTEIRO = {  # os 7 cenários do roteiro da professora, com X = Observer
    "Explique o que é o padrão Observer e qual problema ele resolve.": Intencao.CONCEITO,
    "Dê um exemplo de aplicação do padrão Observer em Java.": Intencao.EXEMPLO,
    "Descreva uma situação em que o padrão Observer é a melhor escolha e uma em que ele deveria ser evitado, explicando o porquê.": Intencao.SELECAO,
    "Como o padrão Observer costuma ser aplicado de forma errada? Dê um exemplo de uso equivocado e explique como corrigir.": Intencao.USO_INCORRETO,
    "Com qual padrão o Observer é mais confundido? Explique a diferença entre eles e por que essa confusão acontece.": Intencao.CONFUSAO,
    "Invente um padrão chamado Z e explique para mim": Intencao.INVENTADO,
    "Me entregue o código pronto de uma solução completa": Intencao.SOLUCAO_PRONTA,
    "O que devo lembrar antes de usar o padrão Observer?": Intencao.FECHAMENTO,
}


class TestRoteador(unittest.TestCase):
    def test_roteiro_da_professora(self):
        for pergunta, esperada in ROTEIRO.items():
            with self.subTest(pergunta=pergunta):
                self.assertEqual(classificar(pergunta).intencao, esperada)

    def test_padrao_desconhecido_com_nome(self):
        rota = classificar("Me explique o Padrão Zorblax")
        self.assertEqual(rota.intencao, Intencao.INVENTADO)
        self.assertEqual(rota.detalhe, "Zorblax")

    def test_padrao_real_nao_e_inventado(self):
        self.assertNotEqual(classificar("Qual a diferença do padrão Mediator?").intencao, Intencao.INVENTADO)

    def test_resposta_ao_exercicio_com_palavras_chave(self):  # bug B1
        for resposta in ["o código ficaria: class Painel implements Observer",
                         "acho que a diferença é que o painel é o observador",
                         "o Subject é a estação, os observadores são os painéis"]:
            with self.subTest(resposta=resposta):
                self.assertEqual(classificar(resposta, exercicio_pendente=True).intencao,
                                 Intencao.RESPOSTA_EXERCICIO)

    def test_pergunta_nova_sai_do_exercicio(self):  # bug B2
        self.assertEqual(classificar("o que é um Subject?", exercicio_pendente=True).intencao, Intencao.CONCEITO)
        self.assertEqual(classificar("quero outro exercício", exercicio_pendente=True).intencao, Intencao.EXERCICIO)

    def test_pedido_de_resposta_pronta_no_meio_do_exercicio(self):
        self.assertEqual(classificar("me dá o código pronto", exercicio_pendente=True).intencao,
                         Intencao.SOLUCAO_PRONTA)

    def test_outro_padrao_vai_para_fora_do_escopo(self):  # caso E2
        rota = classificar("Me explique o padrão Strategy.")
        self.assertEqual((rota.intencao, rota.detalhe), (Intencao.FORA_ESCOPO, "Strategy"))
        # citando o Observer, é comparação; pedindo código pronto, a trava vem antes
        self.assertEqual(classificar("Qual a diferença entre Observer e Mediator?").intencao, Intencao.CONFUSAO)
        self.assertEqual(classificar("Me entregue o código pronto do Singleton").intencao, Intencao.SOLUCAO_PRONTA)

    def test_afirmacao_para_confirmar_vai_ao_inquiridor(self):  # caso E4
        for frase in ["O Observer é um padrão criacional, né?",
                      "É verdade que o Subject conhece as classes concretas?",
                      "O observador guarda referência ao sujeito, certo?"]:
            with self.subTest(frase=frase):
                self.assertEqual(classificar(frase).intencao, Intencao.CONFIRMACAO)
        self.assertEqual(classificar("Me dê um exemplo, ok?").intencao, Intencao.EXEMPLO)

    def test_secoes_das_rotas_existem_na_base(self):
        from agente.conhecimento import secoes

        for rota in ROTAS.values():
            for secao in rota.secoes:
                self.assertIn(secao, secoes(), f"{rota.intencao.value} usa a seção '{secao}'")

    def test_toda_intencao_tem_rota(self):
        self.assertEqual(set(ROTAS), set(Intencao))


class TestDecisaoDeRevisao(unittest.TestCase):
    def test_revisao_so_com_revisar_tudo(self):  # D16: nenhuma rota é revisada por padrão
        for rota in ROTAS.values():
            self.assertFalse(rota.com_revisao(guardiao_ligado=True), rota.intencao)
        self.assertTrue(ROTAS[Intencao.CONCEITO].com_revisao(guardiao_ligado=True, revisar_tudo=True))
        self.assertFalse(ROTAS[Intencao.CONCEITO].com_revisao(guardiao_ligado=False, revisar_tudo=True))

    def test_recusa_nunca_e_revisada(self):
        inventado = ROTAS[Intencao.INVENTADO]
        self.assertFalse(inventado.com_revisao(guardiao_ligado=True, revisar_tudo=True))
        self.assertEqual(inventado.agentes(False), [NomeAgente.GUARDIAO])


class TestRevisao(unittest.TestCase):
    RASCUNHO = "rascunho do especialista"

    def test_aprovado_com_markdown(self):
        self.assertEqual(interpretar_revisao(self.RASCUNHO, "**APROVADO**"), (self.RASCUNHO, "aprovado"))

    def test_corrigido(self):
        correcao = "Texto corrigido e completo para o estudante, com mais de quarenta caracteres."
        self.assertEqual(interpretar_revisao(self.RASCUNHO, "CORRIGIDO: " + correcao), (correcao, "corrigido"))

    def test_corrigido_vazio_mantem_rascunho(self):
        self.assertEqual(interpretar_revisao(self.RASCUNHO, "CORRIGIDO:")[0], self.RASCUNHO)

    def test_saida_inesperada_mantem_rascunho(self):
        self.assertEqual(interpretar_revisao(self.RASCUNHO, "Acho que está bom."),
                         (self.RASCUNHO, "saida_inesperada"))


class Quebrado(ObservadorConversa):
    def atualizar(self, evento):
        raise KeyError("defeito")


class Gravador(ObservadorConversa):
    def __init__(self):
        self.eventos = []

    def atualizar(self, evento):
        self.eventos.append(evento.tipo)


class TestConversa(unittest.TestCase):
    def test_observador_quebrado_e_registrado_e_nao_impede_os_outros(self):  # bug B3
        conversa, gravador = Conversa(), Gravador()
        conversa.anexar(Quebrado())
        conversa.anexar(gravador)
        with self.assertLogs("agente.nucleo.eventos", level="WARNING"):
            conversa.notificar(TipoEvento.ERRO)
        self.assertEqual(gravador.eventos, [TipoEvento.ERRO])

    def test_desanexar_durante_notificacao(self):
        conversa = Conversa()

        class SaiSozinho(ObservadorConversa):
            def atualizar(self, evento):
                conversa.desanexar(self)

        gravador = Gravador()
        conversa.anexar(SaiSozinho())
        conversa.anexar(gravador)
        conversa.notificar(TipoEvento.ERRO)
        self.assertEqual(gravador.eventos, [TipoEvento.ERRO])  # não foi pulado


class OrquestradorFalso:
    def __init__(self, texto="resposta", erro=None, problema=None, modelo="falso:1b"):
        self.modelo = modelo
        self.texto, self.erro, self.problema = texto, erro, problema
        self.chamadas = []

    def verificar(self):
        return self.problema

    def executar(self, rota, entradas, com_revisao):
        self.chamadas.append((rota, entradas, com_revisao))
        if self.erro:
            raise self.erro
        return Resultado(self.texto)


def novo_sistema(**kw):
    orq = OrquestradorFalso(**kw)
    return SistemaTutor(orq, Memoria()), orq


class TestSistema(unittest.TestCase):
    def test_entrada_vazia_nao_chama_o_modelo(self):
        sistema, orq = novo_sistema()
        self.assertIn("não digitou", sistema.resposta("   "))
        self.assertEqual(orq.chamadas, [])

    def test_ollama_indisponivel(self):
        sistema, orq = novo_sistema(problema="Ollama fora do ar")
        self.assertEqual(sistema.resposta("O que é Observer?"), "Ollama fora do ar")
        self.assertEqual(orq.chamadas, [])

    def test_falha_do_modelo_mostra_mensagem_e_nao_vai_para_memoria(self):
        sistema, _ = novo_sistema(erro=FalhaModelo("modelo demorou"))
        self.assertEqual(sistema.resposta("O que é Observer?"), "modelo demorou")
        self.assertEqual(sistema.memoria.turnos, [])

    def test_defeito_interno_nao_derruba(self):
        sistema, _ = novo_sistema(erro=KeyError("x"))
        self.assertIn("problema interno", sistema.resposta("O que é Observer?"))

    def test_saida_vazia(self):
        sistema, _ = novo_sistema(texto="")
        self.assertIn("vazia", sistema.resposta("O que é Observer?"))

    def test_entrada_longa_e_cortada_com_aviso(self):
        sistema, orq = novo_sistema()
        self.assertIn("cortada", sistema.resposta("a" * 5000))
        self.assertEqual(len(orq.chamadas[0][1]["pergunta"]), 2000)

    def test_memoria_entra_no_prompt_seguinte(self):
        sistema, orq = novo_sistema(texto="O Observer define dependência um-para-muitos.")
        sistema.resposta("O que é Observer?")
        sistema.resposta("Dê um exemplo em Java")
        self.assertIn("um-para-muitos", orq.chamadas[1][1]["historico"])

    def test_ciclo_de_exercicio(self):
        sistema, orq = novo_sistema()
        sistema.resposta("quero praticar")
        sistema.resposta("o código ficaria: class Painel implements Observer")
        self.assertEqual(orq.chamadas[1][0].intencao, Intencao.RESPOSTA_EXERCICIO)

    def test_exercicio_deixa_de_estar_pendente_apos_tentativas(self):  # bug B2
        sistema, _ = novo_sistema()
        sistema.resposta("quero praticar")
        for _ in range(3):
            sistema.resposta("o Subject é a estação")
        self.assertFalse(sistema.memoria.exercicio_pendente)

    def test_troca_de_modelo_mantem_a_memoria(self):
        sistema, _ = novo_sistema(texto="O Observer define dependência um-para-muitos.")
        sistema.resposta("O que é Observer?")
        outro = OrquestradorFalso(modelo="falso:2b")
        sistema.usar_orquestrador(outro)
        sistema.resposta("Dê um exemplo em Java")
        self.assertIn("um-para-muitos", outro.chamadas[0][1]["historico"])
        self.assertEqual(sistema.memoria.turnos[-1]["intencao"], "exemplo")

    def test_inventado_vai_ao_guardiao_sem_revisao(self):
        sistema, orq = novo_sistema()
        sistema.resposta("Invente um padrão chamado Z")
        rota, _, com_revisao = orq.chamadas[0]
        self.assertEqual(rota.agentes(com_revisao), [NomeAgente.GUARDIAO])


class TestMemoria(unittest.TestCase):
    def test_codigo_antigo_e_omitido_do_historico(self):  # M4
        m = Memoria()
        m.turnos = [{"estudante": "ex", "tutor": "Veja:\n```java\nclass A {}\n```\nFim.", "intencao": "exemplo"}]
        texto = m.como_texto()
        self.assertIn("[código omitido]", texto)
        self.assertNotIn("class A", texto)

    def test_sessao_persiste_e_arquivo_corrompido_nao_quebra(self):
        with tempfile.TemporaryDirectory() as d:
            arquivo = Path(d) / "s.json"
            sistema = SistemaTutor(OrquestradorFalso(), Memoria(arquivo=arquivo))
            sistema.resposta("O que é Observer?")
            self.assertEqual(len(Memoria(arquivo=arquivo).turnos), 1)
            arquivo.write_text("{quebrado", encoding="utf-8")
            self.assertEqual(Memoria(arquivo=arquivo).turnos, [])


class TestPerguntaDoTutor(unittest.TestCase):
    """Bug relatado em 13/11: responder à pergunta final do tutor dava resposta sem relação."""

    PERGUNTA = "O Observer liga objetos.\n\nNo exemplo da planilha, quem seria o subject?"

    def test_pergunta_final_e_extraida(self):
        self.assertEqual(pergunta_final(self.PERGUNTA), "No exemplo da planilha, quem seria o subject?")
        self.assertEqual(pergunta_final("Texto.\n**Quer ver um exemplo?**"), "Quer ver um exemplo?")
        self.assertEqual(pergunta_final("Resposta sem pergunta."), "")

    def test_respostas_curtas_vao_ao_inquiridor(self):
        for resposta in ["acho que seria no push", "um exemplo seria um botão de interface",
                         "o gráfico seria o observador e a planilha o subject"]:
            with self.subTest(resposta=resposta):
                rota = classificar(resposta, pergunta_tutor="Quem seria o subject?")
                self.assertEqual(rota.intencao, Intencao.RESPOSTA_PERGUNTA)
                self.assertEqual(rota.agente, NomeAgente.INQUIRIDOR)

    def test_aceite_segue_o_convite_do_tutor(self):
        self.assertEqual(classificar("sim", pergunta_tutor="Quer ver um exemplo em Java?").intencao, Intencao.EXEMPLO)
        self.assertEqual(classificar("bora!", pergunta_tutor="Quer tentar um exercício?").intencao, Intencao.EXERCICIO)
        self.assertEqual(classificar("sim", pergunta_tutor="Quer saber mais sobre os participantes?").intencao,
                         Intencao.RESPOSTA_PERGUNTA)
        self.assertEqual(classificar("sim, eles se comunicam", pergunta_tutor="Um observador conhece os outros?")
                         .intencao, Intencao.RESPOSTA_PERGUNTA)

    def test_nao_sei_tem_rota_propria(self):
        self.assertEqual(classificar("não sei", pergunta_tutor="Push ou pull?").intencao, Intencao.NAO_SEI)

    def test_pedido_novo_continua_roteado_normalmente(self):
        self.assertEqual(classificar("Dê um exemplo em Java", pergunta_tutor="Quem seria o subject?").intencao, Intencao.EXEMPLO)
        self.assertEqual(classificar("o que é um Subject?", pergunta_tutor="Quem seria o subject?").intencao, Intencao.CONCEITO)
        self.assertEqual(classificar("me dá o código pronto", pergunta_tutor="Quem seria o subject?").intencao,
                         Intencao.SOLUCAO_PRONTA)

    def test_roteiro_da_professora_nao_e_desviado(self):
        for cid, texto in PERGUNTAS.items():
            with self.subTest(cenario=cid):
                self.assertEqual(classificar(texto, pergunta_tutor="Quem seria o subject?"), classificar(texto))

    def test_cenarios_de_dialogo_tem_a_rota_esperada(self):
        from tests.cenarios import DIALOGOS
        for cid, c in DIALOGOS.items():
            with self.subTest(cenario=cid):
                pergunta = c.contexto[1].splitlines()[-1]
                self.assertEqual(classificar(c.mensagens[-1], pergunta_tutor=pergunta).intencao.value, c.intencao)

    def test_pergunta_sobrevive_ao_corte_do_historico(self):
        sistema, orq = novo_sistema(texto="Explicação longa. " * 60 + "\nQuem seria o subject?")
        sistema.resposta("O que é Observer?")
        sistema.resposta("a planilha")
        rota, entradas, _ = orq.chamadas[1]
        self.assertEqual(rota.intencao, Intencao.RESPOSTA_PERGUNTA)
        self.assertIn("O tutor terminou perguntando: Quem seria o subject?", entradas["historico"])

    def test_sem_pergunta_final_nada_muda(self):
        sistema, orq = novo_sistema(texto="Resposta sem pergunta.")
        sistema.resposta("O que é Observer?")
        sistema.resposta("a planilha")
        self.assertEqual(orq.chamadas[1][0].intencao, Intencao.CONCEITO)


DADOS = Path(__file__).with_name("dados")


class TestSalvaguarda(unittest.TestCase):
    def test_resposta_real_que_falhou_no_6b_perde_toda_implementacao(self):
        # Saída real do qwen2.5:7b em 10/11 (iteração 2 do log): dizia que não entregaria e entregava.
        original = (DADOS / "resposta_6b_falhou.txt").read_text(encoding="utf-8")
        texto, alterado = sem_solucao_pronta(original)
        self.assertTrue(alterado)
        for trecho_de_solucao in ("observers.add", "public static void main", "System.out.println"):
            self.assertNotIn(trecho_de_solucao, texto)
        self.assertIn("interface Observer", texto)  # assinatura curta de interface é permitida

    def test_interface_sem_corpo_e_mantida(self):
        texto = "Comece por aqui:\n```java\ninterface Observer {\n    void atualizar(double t);\n}\n```\nE agora?"
        self.assertEqual(sem_solucao_pronta(texto), (texto, False))

    def test_metodo_implementado_e_removido(self):
        texto = "Veja " * 80 + "\n```java\nclass A {\n  void f() { x(); }\n}\n```"
        novo, alterado = sem_solucao_pronta(texto)
        self.assertTrue(alterado)
        self.assertIn(AVISO, novo)

    def test_sobrou_pouco_texto_usa_roteiro_padrao(self):
        texto = "Aqui está:\n```java\nclass A {\n  void f() { x(); }\n}\n```"
        self.assertEqual(sem_solucao_pronta(texto), (ROTEIRO_PADRAO, True))

    def test_sistema_aplica_salvaguarda_so_nas_rotas_marcadas(self):
        codigo = "Pronto:\n```java\nclass A {\n  void f() { x(); }\n}\n```"
        sistema, _ = novo_sistema(texto=codigo)
        self.assertEqual(sistema.resposta("Me entregue o código pronto de uma solução completa"), ROTEIRO_PADRAO)
        sistema, _ = novo_sistema(texto=codigo)
        self.assertEqual(sistema.resposta("Dê um exemplo de aplicação do padrão Observer em Java."), codigo)


class TestFabrica(unittest.TestCase):
    def test_prompts_validos_e_prompt_incompleto_falha_na_inicializacao(self):  # bug B4
        from crewai import LLM
        from agente.agentes.fabrica_agentes import PASTA_PROMPTS, FabricaAgentes

        llm = LLM(model="ollama/qwen2.5:3b", base_url="http://localhost:11434")
        FabricaAgentes(llm)  # os YAML reais carregam sem erro
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            (pasta / "agentes.yaml").write_text("tutor:\n  role: r\n  goal: g\n  backstory: b\n", encoding="utf-8")
            for nome in ("tarefas.yaml", "rotas.yaml"):
                (pasta / nome).write_text((PASTA_PROMPTS / nome).read_text(encoding="utf-8"), encoding="utf-8")
            with self.assertRaisesRegex(ErroDeConfiguracao, "exemplificador"):
                FabricaAgentes(llm, pasta)

    def test_rotas_yaml_cobre_todas_as_intencoes_e_preenche_detalhe(self):
        from crewai import LLM
        from agente.agentes.fabrica_agentes import FabricaAgentes

        fabrica = FabricaAgentes(LLM(model="ollama/qwen2.5:3b", base_url="http://localhost:11434"))
        for intencao in Intencao:
            self.assertTrue(fabrica.orientacao(intencao))
        self.assertIn("Zorblax", fabrica.orientacao(Intencao.INVENTADO, "Zorblax"))
        self.assertNotIn("{detalhe}", fabrica.orientacao(Intencao.INVENTADO))


class TestInterfaceTerminal(unittest.TestCase):
    def test_comandos(self):
        from agente.interface.roteiro import PERGUNTAS
        from agente.interface.terminal import Comando, interpretar

        self.assertEqual(interpretar("O que é Observer?").texto, "O que é Observer?")
        self.assertEqual(interpretar("/3").texto, PERGUNTAS["C3"])
        self.assertEqual(interpretar("/6").texto, PERGUNTAS["C6a"])
        self.assertEqual(interpretar("/6b").texto, PERGUNTAS["C6b"])
        self.assertEqual(interpretar(" /SAIR ").acao, "sair")
        self.assertEqual(interpretar("/nova").acao, "nova")
        self.assertEqual(interpretar("/9").acao, "invalido")
        self.assertEqual(interpretar("/modelo 3b"), Comando("modelo", "qwen2.5:3b"))
        self.assertEqual(interpretar("/modelo qwen2.5:7b"), Comando("modelo", "qwen2.5:7b"))
        self.assertEqual(interpretar("/modelo").acao, "modelo")
        self.assertEqual(interpretar("/modelo 70b").acao, "invalido")

    def test_conversa_mostra_agente_tempo_e_veredito(self):
        from rich.console import Console
        from agente.interface import terminal
        from agente.nucleo.eventos import TipoEvento

        class OrquestradorComEventos(OrquestradorFalso):
            def executar(self, rota, entradas, com_revisao):
                return Resultado("## Título\n\n```java\nclass A {}\n```", "aprovado", "APROVADO")

        sistema = SistemaTutor(OrquestradorComEventos(), Memoria())
        console = Console(record=True, force_terminal=True, width=100, file=io.StringIO())
        entradas = iter(["/1", "/sair"])
        console.input = lambda *a, **k: next(entradas)
        terminal.conversar(sistema, console)
        tela = console.export_text()
        self.assertIn("Tutor", tela)                      # agente no título do painel
        self.assertIn("revisado pelo Guardião", tela)     # veredito no rodapé
        self.assertIn("class A", tela)                    # código renderizado
        self.assertNotIn("```", tela)                     # Markdown não aparece cru


try:
    import gradio  # noqa: F401
    TEM_GRADIO = True
except ModuleNotFoundError:
    TEM_GRADIO = False


@unittest.skipUnless(TEM_GRADIO, "Gradio não instalado (requirements-web.txt)")
class TestInterfaceWeb(unittest.TestCase):
    def test_rodape_com_agente_tempo_e_veredito(self):
        from agente.interface.web import com_rodape
        from agente.observadores.turno import Turno

        turno = Turno(["Inquiridor", "Guardião"], "aprovado", 95.4)
        self.assertEqual(com_rodape("Resposta", turno),
                         "Resposta\n\n<sub>Inquiridor → Guardião · 95 s · revisado pelo Guardião</sub>")
        self.assertEqual(com_rodape("Ollama fora do ar", Turno()), "Ollama fora do ar")

    def test_mensagem_de_espera_mostra_agente_e_tempo(self):
        from agente.interface.web import aguardando

        self.assertIn("**Inquiridor → Guardião** trabalhando… 42 s", aguardando(["Inquiridor", "Guardião"], 42.3))
        self.assertIn("Preparando a resposta", aguardando([], 0))

    def test_tela_monta_sem_erro(self):
        from agente.interface.web import criar_app

        self.assertIsNotNone(criar_app(lambda modelo: OrquestradorFalso(modelo=modelo)))


if __name__ == "__main__":
    unittest.main()
