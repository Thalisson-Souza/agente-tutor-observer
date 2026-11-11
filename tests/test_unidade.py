"""Testes que rodam sem o Ollama (segundos). Rodar com: python -m unittest -v

O SistemaTutor recebe um OrquestradorFalso, então memória, roteamento, eventos e
tratamento de erros são testados sem chamar o modelo.
"""

import tempfile
import unittest
from pathlib import Path

from agente.nucleo.erros import ErroDeConfiguracao, FalhaModelo
from agente.nucleo.eventos import Conversa, ObservadorConversa, TipoEvento
from agente.nucleo.intencoes import Intencao, NomeAgente, Resultado
from agente.observadores import Memoria
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

    def test_toda_intencao_tem_rota(self):
        self.assertEqual(set(ROTAS), set(Intencao))


class TestDecisaoDeRevisao(unittest.TestCase):
    def test_so_especialista_de_rota_marcada_e_revisado(self):
        self.assertTrue(ROTAS[Intencao.EXEMPLO].com_revisao(guardiao_ligado=True))
        self.assertFalse(ROTAS[Intencao.CONCEITO].com_revisao(guardiao_ligado=True))
        self.assertTrue(ROTAS[Intencao.CONCEITO].com_revisao(guardiao_ligado=True, revisar_tudo=True))
        self.assertFalse(ROTAS[Intencao.EXEMPLO].com_revisao(guardiao_ligado=False))

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
    def __init__(self, texto="resposta", erro=None, problema=None):
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


if __name__ == "__main__":
    unittest.main()
