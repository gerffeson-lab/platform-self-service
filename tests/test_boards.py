import io
import json
import unittest
import urllib.error

from helpers import CAT  # noqa: F401  (ajusta o sys.path)

from selfservice.boards import Boards, BoardsError
from selfservice.operacoes import novo_servico as op


def resposta(status=200, corpo=None):
    def urlopen(req, timeout):
        urlopen.req = req
        if status != 200:
            raise urllib.error.HTTPError(req.full_url, status, "erro", {}, io.BytesIO(b"{}"))
        return io.BytesIO(json.dumps(corpo).encode())
    return urlopen


class BoardsTest(unittest.TestCase):
    def test_consulta_na_org_sem_projeto_com_pat(self):
        urlopen = resposta(corpo={"fields": {"System.State": "Active"}})
        self.assertEqual(Boards("acme", "pat", urlopen).work_item(7), {"System.State": "Active"})
        self.assertTrue(urlopen.req.full_url.startswith("https://dev.azure.com/acme/_apis/wit/workitems/7?"))
        self.assertEqual(urlopen.req.get_header("Authorization"), "Basic OnBhdA==")  # base64(":pat")

    def test_inexistente_vira_none(self):
        self.assertIsNone(Boards("acme", "pat", resposta(404)).work_item(7))

    def test_token_invalido_e_erro_de_infra(self):
        with self.assertRaises(BoardsError):
            Boards("acme", "pat", resposta(401)).work_item(7)


class FakeBoards:
    def __init__(self, itens):
        self.itens = itens

    def work_item(self, numero):
        return self.itens.get(numero)


class ChecarWorkItemTest(unittest.TestCase):
    def checar(self, itens, work_item="AB#12"):
        from helpers import FakeGitHub
        gh = FakeGitHub({"orgs/acme/teams/pagamentos", "repos/acme/platform-java-boilerplate"})
        pedido = {"time": "pagamentos", "nome": "crt-credito-autorizador", "template": "platform-java-boilerplate",
                  "golden_path": "java-spring", "work_item": work_item}
        return op.checar(pedido, gh, FakeBoards(itens))

    def test_aberto_passa(self):
        self.assertEqual(self.checar({12: {"System.State": "Active", "System.Title": "Autorizador"}}), [])

    def test_inexistente(self):
        self.assertIn("não existe no Azure Boards", self.checar({})[0])

    def test_encerrado(self):
        erros = self.checar({12: {"System.State": "Closed", "System.Title": "Antigo"}})
        self.assertIn("está `Closed`", erros[0])

    def test_sem_boards_configurado_so_o_formato(self):
        from helpers import FakeGitHub
        gh = FakeGitHub({"orgs/acme/teams/pagamentos", "repos/acme/platform-java-boilerplate"})
        self.assertEqual(op.checar({"work_item": "AB#12"}, gh), [])


if __name__ == "__main__":
    unittest.main()
