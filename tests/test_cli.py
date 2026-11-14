import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import ROOT  # noqa: F401  (ajusta o sys.path)

import cli
from selfservice.operacoes import novo_servico


class FakeIssues:
    def __init__(self, state="open", labels=("novo-servico",)):
        self.atual = {"state": state, "labels": list(labels), "title": "x"}
        self.titulos = []

    def issue(self, repo, number):
        return self.atual

    def title(self, repo, number, title):
        self.titulos.append(title)


def rodar(fake, env, funcao, *args):
    base = {"EVENT_NAME": "issues", "GITHUB_REPOSITORY": "acme/platform-self-service", "ISSUE_NUMBER": "7"}
    with mock.patch.object(cli, "ENV", {**base, **env}), mock.patch.object(cli, "issues", lambda: fake), \
            redirect_stdout(io.StringIO()) as out:
        funcao(*args)
    return out.getvalue()


class OperacaoTest(unittest.TestCase):
    def test_issue_aberta_com_a_label_da_operacao(self):
        self.assertIn("operacao=novo-servico", rodar(FakeIssues(), {}, cli.cmd_operacao))

    def test_usa_o_estado_atual_e_nao_o_do_evento(self):
        # edição feita durante a criação: quando roda, a issue já foi concluída
        saida = rodar(FakeIssues("closed", ("novo-servico", "concluido")), {}, cli.cmd_operacao)
        self.assertIn("operacao=\n", saida)

    def test_concluida_mas_reaberta_nao_roda(self):
        self.assertIn("operacao=\n", rodar(FakeIssues("open", ("novo-servico", "concluido")), {}, cli.cmd_operacao))


class TituloTest(unittest.TestCase):
    PEDIDO = {"nome": "crt-credito-autorizador"}

    def test_completa_o_titulo_com_o_nome_do_repositorio(self):
        fake = FakeIssues()
        rodar(fake, {"ISSUE_TITLE": "[novo-servico]"}, cli.atualizar_titulo, novo_servico, self.PEDIDO)
        self.assertEqual(fake.titulos, ["[novo-servico] crt-credito-autorizador"])

    def test_titulo_ja_certo_nao_edita(self):
        fake = FakeIssues()
        rodar(fake, {"ISSUE_TITLE": "[novo-servico] crt-credito-autorizador"}, cli.atualizar_titulo,
              novo_servico, self.PEDIDO)
        self.assertEqual(fake.titulos, [])

    def test_sem_nome_valido_nao_edita(self):
        fake = FakeIssues()
        rodar(fake, {"ISSUE_TITLE": "[novo-servico]"}, cli.atualizar_titulo, novo_servico, {})
        self.assertEqual(fake.titulos, [])


if __name__ == "__main__":
    unittest.main()
