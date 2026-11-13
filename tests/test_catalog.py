import unittest

from helpers import CAT, ROOT

from selfservice import catalog


class CatalogTest(unittest.TestCase):
    def test_catalogo_do_repo_e_valido(self):
        self.assertEqual(catalog.check(catalog.load(str(ROOT / "catalogo" / "siglas.yaml"))), [])

    def test_produtos_por_sigla(self):
        self.assertEqual(catalog.produtos(CAT)["crt-credito"],
                         {"sigla": "crt", "produto": "credito", "times": ["pagamentos"]})
        self.assertEqual(catalog.all_teams(CAT), ["contas", "pagamentos"])

    def test_sigla_invalida(self):
        erros = catalog.check({"siglas": {"CRT-1": {"produtos": {"x": {"times": ["t"]}}}}})
        self.assertIn("Sigla", erros[0])

    def test_produto_sem_times(self):
        self.assertIn("ao menos um time", catalog.check({"siglas": {"crt": {"produtos": {"x": {"times": []}}}}})[0])

    def test_sem_siglas(self):
        self.assertTrue(catalog.check({}))


if __name__ == "__main__":
    unittest.main()
