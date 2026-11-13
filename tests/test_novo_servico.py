import os
import stat
import tempfile
import unittest
from pathlib import Path

from helpers import CAT, FakeGitHub

from selfservice.operacoes import novo_servico as op

OK = {"sigla": "crt", "produto": "credito", "aplicacao": "autorizador", "time": "pagamentos",
      "golden-path": "java-spring", "work-item": "AB#12"}
PEDIDO = {"sigla": "crt", "produto": "credito", "aplicacao": "autorizador", "nome": "crt-credito-autorizador",
          "time": "pagamentos", "golden_path": "java-spring", "template": "platform-java-boilerplate",
          "work_item": "AB#12", "descricao": ""}
CFG = {"visibilidade": "private", "server_url": "https://github.com"}
REPO = "repos/acme/crt-credito-autorizador"


def erros(**override):
    return op.validar({**OK, **override}, CAT)[1]


class ValidarTest(unittest.TestCase):
    def test_pedido_valido_monta_o_nome(self):
        pedido, errs = op.validar(OK, CAT)
        self.assertEqual(errs, [])
        self.assertEqual(pedido, PEDIDO)

    def test_sigla_fora_do_catalogo(self):
        self.assertIn("A sigla `seg` não está no catálogo", erros(sigla="seg")[0])

    def test_produto_de_outra_sigla(self):
        errs = erros(produto="consignado")
        self.assertIn("não pertence à sigla `crt`", errs[0])
        self.assertIn("`credito`, `debito`", errs[0])

    def test_time_de_outro_produto(self):
        self.assertIn("não pertence", erros(time="contas")[0])

    def test_aplicacao_mal_formada_nao_e_repassada(self):
        pedido, errs = op.validar({**OK, "aplicacao": "Autorizador--X"}, CAT)
        self.assertIn("Nome da aplicação inválido", errs[0])
        self.assertNotIn("nome", pedido)

    def test_nao_repete_sigla_ou_produto(self):
        self.assertIn("Não repita", erros(aplicacao="credito-autorizador")[0])
        self.assertIn("Não repita", erros(aplicacao="crt-autorizador")[0])

    def test_golden_path_escolhe_o_template(self):
        pedido, errs = op.validar({**OK, "golden-path": "go"}, CAT)
        self.assertEqual(errs, [])
        self.assertEqual(pedido["template"], "platform-go-boilerplate")

    def test_golden_path_fora_do_catalogo(self):
        pedido, errs = op.validar({**OK, "golden-path": "cobol"}, CAT)
        self.assertIn("Golden path `cobol`", errs[0])
        self.assertNotIn("template", pedido)

    def test_work_item(self):
        self.assertIn("Work item inválido", erros(**{"work-item": "123"})[0])

    def test_descricao_em_uma_linha(self):
        self.assertEqual(op.validar({**OK, "descricao": "a\n\nb  c"}, CAT)[0]["descricao"], "a b c")


class GitHubRulesTest(unittest.TestCase):
    BASE = {"orgs/acme/teams/pagamentos", "repos/acme/platform-java-boilerplate"}

    def test_valido(self):
        self.assertEqual(op.checar(PEDIDO, FakeGitHub(self.BASE)), [])

    def test_repo_existente(self):
        self.assertIn("já existe", op.checar(PEDIDO, FakeGitHub(self.BASE | {REPO}))[0])

    def test_template_inexistente(self):
        self.assertIn("template", op.checar(PEDIDO, FakeGitHub({"orgs/acme/teams/pagamentos"}))[0])

    def test_time_inexistente_nao_vira_nao_autorizado(self):
        gh = FakeGitHub({"repos/acme/platform-java-boilerplate"})
        self.assertIn("não existe", op.checar(PEDIDO, gh)[0])
        self.assertEqual(op.autorizar(PEDIDO, gh, "dev"), [])

    def test_so_maintainer_pede(self):
        gh = FakeGitHub({"orgs/acme/teams/pagamentos"}, papeis={("pagamentos", "tl"): "maintainer",
                                                                ("pagamentos", "dev"): "member"})
        self.assertEqual(op.autorizar(PEDIDO, gh, "tl"), [])
        self.assertIn("não é maintainer", op.autorizar(PEDIDO, gh, "dev")[0])


class ExecutarTest(unittest.TestCase):
    def test_cria_do_zero_a_partir_do_template_do_golden_path(self):
        gh, publicados = FakeGitHub(), []
        msg = op.executar(PEDIDO, gh, CFG, publicar=lambda g, repo, p: publicados.append(repo), cat=CAT)
        self.assertIn(("gh", "repo", "create", "acme/crt-credito-autorizador", "--private",
                       "--template", "acme/platform-java-boilerplate"), [c[:7] for c in gh.chamadas])
        self.assertIn(("api", "PATCH", f"{REPO}/properties/values"), gh.chamadas)
        self.assertIn(("api", "POST", f"{REPO}/rulesets"), gh.chamadas)
        self.assertEqual(publicados, ["acme/crt-credito-autorizador"])
        self.assertIn("@acme/pagamentos", msg)
        self.assertIn("Java / Spring Boot", msg)
        self.assertIn("api/openapi.yaml", msg)

    def test_custom_properties_incluem_o_golden_path(self):
        gh = FakeGitHub()
        op.executar(PEDIDO, gh, CFG, publicar=lambda *a: None, cat=CAT)
        props = {p["property_name"]: p["value"] for p in gh.corpos[f"{REPO}/properties/values"]["properties"]}
        self.assertEqual(props, {"sigla": "crt", "produto": "credito", "time": "pagamentos",
                                 "golden-path": "java-spring"})

    def test_reexecucao_retoma_sem_duplicar(self):
        gh, publicados = FakeGitHub({REPO, f"{REPO}/branches/develop"}, rulesets=["gitflow"]), []
        op.executar(PEDIDO, gh, CFG, publicar=lambda g, r, p: publicados.append(r), cat=CAT)
        self.assertEqual(publicados, [])
        self.assertNotIn("create", [c[2] for c in gh.chamadas if c[0] == "gh"])
        self.assertNotIn(("api", "POST", f"{REPO}/rulesets"), gh.chamadas)


class PersonalizarTest(unittest.TestCase):
    def repo(self, script=None, executavel=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        if script is not None:
            path = Path(tmp.name, ".golden-path", "personalizar")
            path.parent.mkdir()
            path.write_text(script)
            if executavel:
                path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return tmp.name

    def test_roda_o_script_do_template_sem_token_e_apaga_golden_path(self):
        work = self.repo("#!/bin/sh\nenv > ambiente.txt\n")
        os.environ["GH_TOKEN"] = "segredo"
        self.addCleanup(os.environ.pop, "GH_TOKEN")
        op.personalizar(work, {**PEDIDO, "descricao": "Autoriza compras"}, "acme")
        ambiente = Path(work, "ambiente.txt").read_text()
        self.assertIn("GP_NOME=crt-credito-autorizador", ambiente)
        self.assertIn("GP_DESCRICAO=Autoriza compras", ambiente)
        self.assertNotIn("segredo", ambiente)
        self.assertFalse(Path(work, ".golden-path").exists())

    def test_template_sem_script_segue_sem_personalizar(self):
        op.personalizar(self.repo(), PEDIDO, "acme")

    def test_script_que_falha_interrompe(self):
        with self.assertRaisesRegex(RuntimeError, "falhou: deu ruim"):
            op.personalizar(self.repo("#!/bin/sh\necho deu ruim >&2\nexit 3\n"), PEDIDO, "acme")

    def test_script_nao_executavel(self):
        with self.assertRaisesRegex(RuntimeError, "não é executável"):
            op.personalizar(self.repo("#!/bin/sh\n", executavel=False), PEDIDO, "acme")


if __name__ == "__main__":
    unittest.main()
