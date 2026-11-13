import tempfile
import unittest
from pathlib import Path

from helpers import CAT, ROOT

from selfservice import catalog


class CatalogTest(unittest.TestCase):
    def test_catalogo_do_repo_e_valido(self):
        cat = catalog.carregar(ROOT / "catalogo")
        self.assertEqual(catalog.check(cat), [])
        self.assertIn("java-spring", catalog.golden_paths(cat))

    def test_listas_do_formulario(self):
        self.assertEqual(catalog.siglas(CAT), ["crt", "emp"])
        self.assertEqual(catalog.nomes_produtos(CAT), ["consignado", "credito", "debito"])
        self.assertEqual(catalog.all_teams(CAT), ["contas", "credito-pf", "pagamentos"])
        self.assertEqual(catalog.produtos(CAT)["crt-credito"],
                         {"sigla": "crt", "produto": "credito", "times": ["pagamentos"]})

    def test_catalogo_de_teste_e_valido(self):
        self.assertEqual(catalog.check(CAT), [])

    def test_sigla_invalida(self):
        erros = catalog.check({**CAT, "siglas": {"CRT-1": {"produtos": {"x": {"times": ["t"]}}}}})
        self.assertIn("Sigla", erros[0])

    def test_produto_sem_times(self):
        erros = catalog.check({**CAT, "siglas": {"crt": {"produtos": {"x": {"times": []}}}}})
        self.assertIn("ao menos um time", erros[0])

    def test_golden_path_sem_template(self):
        erros = catalog.check({**CAT, "golden_paths": {"go": {"nome": "Go"}}})
        self.assertIn("`template`", erros[0])

    def test_sem_siglas_nem_golden_paths(self):
        self.assertEqual(len(catalog.check({})), 2)

    def test_chave_repetida_entre_arquivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.yaml").write_text("siglas: {}\n")
            Path(tmp, "b.yaml").write_text("siglas: {}\n")
            with self.assertRaises(ValueError):
                catalog.carregar(tmp)


if __name__ == "__main__":
    unittest.main()
