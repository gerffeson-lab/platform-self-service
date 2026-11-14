import base64
import unittest

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

    def test_work_item_que_o_github_virou_link(self):
        campo = "[AB#12](https://dev.azure.com/acme/25f7c38e/_workitems/edit/12)"
        pedido, errs = op.validar({**OK, "work-item": campo}, CAT)
        self.assertEqual(errs, [])
        self.assertEqual(pedido["work_item"], "AB#12")

    def test_link_com_outro_texto_nao_passa(self):
        self.assertIn("Work item inválido", erros(**{"work-item": "[AB#12](https://x) e AB#13"})[0])

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
    TEMPLATE = {f"{REPO}/contents/.github/CODEOWNERS": "* @acme/plataforma\n"}

    def test_cria_do_zero_a_partir_do_template_do_golden_path(self):
        gh = FakeGitHub(arquivos=self.TEMPLATE)
        msg = op.executar(PEDIDO, gh, CFG, cat=CAT)
        self.assertIn(("gh", "repo", "create", "acme/crt-credito-autorizador", "--private",
                       "--template", "acme/platform-java-boilerplate"), [c[:7] for c in gh.chamadas])
        self.assertIn(("api", "PATCH", f"{REPO}/properties/values"), gh.chamadas)
        self.assertIn(("api", "POST", f"{REPO}/rulesets"), gh.chamadas)
        self.assertIn("@acme/pagamentos", msg)
        self.assertIn("Java / Spring Boot", msg)
        self.assertIn("api/openapi.yaml", msg)

    def test_time_vira_dono_num_commit_com_o_work_item(self):
        gh = FakeGitHub(arquivos=self.TEMPLATE)
        op.executar(PEDIDO, gh, CFG, cat=CAT)
        corpo = gh.corpos[f"{REPO}/contents/.github/CODEOWNERS"]
        self.assertEqual(base64.b64decode(corpo["content"]).decode(), "* @acme/pagamentos\n")
        self.assertEqual(corpo["sha"], "sha-antigo")
        self.assertIn("AB#12", corpo["message"])

    def test_template_sem_codeowners_cria_o_arquivo(self):
        gh = FakeGitHub()
        op.executar(PEDIDO, gh, CFG, cat=CAT)
        self.assertNotIn("sha", gh.corpos[f"{REPO}/contents/.github/CODEOWNERS"])

    def test_develop_nasce_da_main(self):
        gh = FakeGitHub(arquivos=self.TEMPLATE)
        op.executar(PEDIDO, gh, CFG, cat=CAT)
        self.assertEqual(gh.corpos[f"{REPO}/git/refs"], {"ref": "refs/heads/develop", "sha": "sha-main"})
        # a develop sai depois do CODEOWNERS, então já nasce com o time dono
        ordem = [c[2] for c in gh.chamadas if c[0] == "api"]
        self.assertLess(ordem.index(f"{REPO}/contents/.github/CODEOWNERS"), ordem.index(f"{REPO}/git/refs"))

    def test_custom_properties_incluem_o_golden_path(self):
        gh = FakeGitHub(arquivos=self.TEMPLATE)
        op.executar(PEDIDO, gh, CFG, cat=CAT)
        props = {p["property_name"]: p["value"] for p in gh.corpos[f"{REPO}/properties/values"]["properties"]}
        self.assertEqual(props, {"sigla": "crt", "produto": "credito", "time": "pagamentos",
                                 "golden-path": "java-spring"})

    def test_reexecucao_retoma_sem_duplicar(self):
        gh = FakeGitHub({REPO, f"{REPO}/branches/develop"}, rulesets=["gitflow"],
                        arquivos={f"{REPO}/contents/.github/CODEOWNERS": "* @acme/pagamentos\n"})
        op.executar(PEDIDO, gh, CFG, cat=CAT)
        self.assertNotIn("create", [c[2] for c in gh.chamadas if c[0] == "gh"])
        self.assertNotIn(("api", "PUT", f"{REPO}/contents/.github/CODEOWNERS"), gh.chamadas)
        self.assertNotIn(("api", "POST", f"{REPO}/git/refs"), gh.chamadas)
        self.assertNotIn(("api", "POST", f"{REPO}/rulesets"), gh.chamadas)


if __name__ == "__main__":
    unittest.main()
