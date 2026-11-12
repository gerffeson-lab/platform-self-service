import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import catalog  # noqa: E402
from validate_request import parse_issue_form, validate  # noqa: E402

CAT = {
    "regras": {"prefixo_produto": True, "prefixos_reservados": ["platform-", "gitops-"]},
    "produtos": {"cartoes": {"system": "cartoes", "times": ["pagamentos"]}},
}
OK = {"nome": "cartoes-autorizador", "produto": "cartoes", "time": "pagamentos", "work_item": "AB#12"}


def erros(**override):
    return validate({**OK, **override}, CAT)[1]


class ValidateTest(unittest.TestCase):
    def test_pedido_valido(self):
        safe, errors = validate(OK, CAT)
        self.assertEqual(errors, [])
        self.assertEqual(safe["nome"], "cartoes-autorizador")
        self.assertEqual(safe["system"], "cartoes")

    def test_produto_fora_do_catalogo(self):
        self.assertIn("não está no catálogo", erros(produto="seguros")[0])

    def test_time_de_outro_produto(self):
        self.assertIn("não pertence ao produto", erros(time="sinistros")[0])

    def test_nome_sem_prefixo_do_produto(self):
        self.assertIn("deve começar com o produto", erros(nome="autorizador")[0])

    def test_prefixo_reservado(self):
        self.assertIn("reservado", erros(nome="platform-x")[0])

    def test_nome_mal_formado_nao_e_repassado(self):
        safe, errors = validate({**OK, "nome": "Cartoes--X"}, CAT)
        self.assertIn("Nome do serviço inválido", errors[0])
        self.assertNotIn("nome", safe)

    def test_work_item(self):
        self.assertIn("Work item inválido", erros(work_item="123")[0])

    def test_parse_issue_form(self):
        body = ("### Nome do serviço\n\ncartoes-autorizador\n\n### Produto\n\ncartoes\n\n"
                "### Time responsável\n\npagamentos\n\n### Work item no Azure Boards\n\nAB#1\n\n"
                "### Descrição\n\n_No response_\n\n### Confirmação\n\n- [X] segue o golden path\n")
        self.assertEqual(parse_issue_form(body), {**OK, "work_item": "AB#1", "descricao": ""})


class CatalogTest(unittest.TestCase):
    def test_catalogo_do_repo_e_valido(self):
        self.assertEqual(catalog.check(catalog.load(str(ROOT / "catalogo" / "produtos.yaml"))), [])

    def test_catalogo_sem_times(self):
        self.assertTrue(catalog.check({"produtos": {"cartoes": {"times": []}}}))


if __name__ == "__main__":
    unittest.main()
