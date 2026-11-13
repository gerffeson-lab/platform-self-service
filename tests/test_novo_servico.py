import unittest

from helpers import CAT, FakeGitHub

from selfservice.operacoes import novo_servico as op

OK = {"sigla-produto": "crt-credito", "aplicacao": "autorizador", "time": "pagamentos", "work-item": "AB#12"}
PEDIDO = {"sigla": "crt", "produto": "credito", "aplicacao": "autorizador", "nome": "crt-credito-autorizador",
          "time": "pagamentos", "work_item": "AB#12", "descricao": ""}
CFG = {"visibilidade": "private", "template": "acme/platform-java-boilerplate", "server_url": "https://github.com"}


def erros(**override):
    return op.validar({**OK, **override}, CAT)[1]


class ValidarTest(unittest.TestCase):
    def test_pedido_valido_monta_o_nome(self):
        pedido, errs = op.validar(OK, CAT)
        self.assertEqual(errs, [])
        self.assertEqual(pedido, PEDIDO)

    def test_produto_fora_do_catalogo(self):
        self.assertIn("não está no catálogo", erros(**{"sigla-produto": "seg-vida"})[0])

    def test_time_de_outro_produto(self):
        self.assertIn("não pertence", erros(time="contas")[0])

    def test_aplicacao_mal_formada_nao_e_repassada(self):
        pedido, errs = op.validar({**OK, "aplicacao": "Autorizador--X"}, CAT)
        self.assertIn("Nome da aplicação inválido", errs[0])
        self.assertNotIn("nome", pedido)

    def test_nao_repete_sigla_ou_produto(self):
        self.assertIn("Não repita", erros(aplicacao="credito-autorizador")[0])

    def test_work_item(self):
        self.assertIn("Work item inválido", erros(**{"work-item": "123"})[0])

    def test_descricao_em_uma_linha(self):
        self.assertEqual(op.validar({**OK, "descricao": "a\n\nb  c"}, CAT)[0]["descricao"], "a b c")


class GitHubRulesTest(unittest.TestCase):
    def test_repo_existente(self):
        gh = FakeGitHub({"orgs/acme/teams/pagamentos", "repos/acme/crt-credito-autorizador"})
        self.assertIn("já existe", op.checar(PEDIDO, gh)[0])

    def test_time_inexistente_nao_vira_nao_autorizado(self):
        gh = FakeGitHub()
        self.assertIn("não existe", op.checar(PEDIDO, gh)[0])
        self.assertEqual(op.autorizar(PEDIDO, gh, "dev"), [])

    def test_so_maintainer_pede(self):
        gh = FakeGitHub({"orgs/acme/teams/pagamentos"}, papeis={("pagamentos", "tl"): "maintainer",
                                                                ("pagamentos", "dev"): "member"})
        self.assertEqual(op.autorizar(PEDIDO, gh, "tl"), [])
        self.assertIn("não é maintainer", op.autorizar(PEDIDO, gh, "dev")[0])


class ExecutarTest(unittest.TestCase):
    def test_cria_do_zero(self):
        gh, publicados = FakeGitHub(), []
        msg = op.executar(PEDIDO, gh, CFG, publicar=lambda g, repo, p: publicados.append(repo))
        self.assertIn(("gh", "repo", "create", "acme/crt-credito-autorizador", "--private"), [c[:5] for c in gh.chamadas])
        self.assertIn(("api", "PATCH", "repos/acme/crt-credito-autorizador/properties/values"), gh.chamadas)
        self.assertIn(("api", "POST", "repos/acme/crt-credito-autorizador/rulesets"), gh.chamadas)
        self.assertEqual(publicados, ["acme/crt-credito-autorizador"])
        self.assertIn("@acme/pagamentos", msg)

    def test_reexecucao_retoma_sem_duplicar(self):
        repo = "repos/acme/crt-credito-autorizador"
        gh, publicados = FakeGitHub({repo, f"{repo}/branches/develop"}, rulesets=["gitflow"]), []
        op.executar(PEDIDO, gh, CFG, publicar=lambda g, r, p: publicados.append(r))
        self.assertEqual(publicados, [])
        self.assertNotIn("create", [c[2] for c in gh.chamadas if c[0] == "gh"])
        self.assertNotIn(("api", "POST", f"{repo}/rulesets"), gh.chamadas)


if __name__ == "__main__":
    unittest.main()
