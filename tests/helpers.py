import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from selfservice.github import GitHubError  # noqa: E402

CAT = {
    "siglas": {
        "crt": {"produtos": {"credito": {"times": ["pagamentos"]}, "debito": {"times": ["contas"]}}},
        "emp": {"produtos": {"consignado": {"times": ["credito-pf"]}}},
    },
    "golden_paths": {
        "java-spring": {"nome": "Java / Spring Boot", "template": "platform-java-boilerplate",
                        "primeiro_passo": "Comece pelo contrato em `api/openapi.yaml`."},
        "go": {"nome": "Go", "template": "platform-go-boilerplate"},
    },
}


class FakeGitHub:
    """Registra as chamadas; `existentes` são os paths que respondem 200."""

    def __init__(self, existentes=(), papeis=None, rulesets=(), arquivos=None):
        self.org, self.token = "acme", "t"
        self.existentes, self.papeis, self.rulesets = set(existentes), papeis or {}, list(rulesets)
        self.arquivos = dict(arquivos or {})  # "repos/x/y/contents/<path>" -> texto
        self.chamadas, self.corpos = [], {}

    def exists(self, path):
        return path in self.existentes or path.split("?")[0] in self.existentes

    def team_role(self, team, user):
        return self.papeis.get((team, user))

    def gh(self, *args, **kwargs):
        self.chamadas.append(("gh",) + args)
        if args[:2] == ("repo", "create"):
            self.existentes |= {f"repos/{args[2]}", f"repos/{args[2]}/commits"}

    def api(self, path, method="GET", body=None):
        self.chamadas.append(("api", method, path))
        if body is not None:
            self.corpos[path] = body
        if method == "GET" and "/contents/" in path:
            chave = path.split("?")[0]
            if chave not in self.arquivos:
                raise GitHubError("404 Not Found")
            return {"content": base64.b64encode(self.arquivos[chave].encode()).decode(), "sha": "sha-antigo"}
        if method == "GET" and path.endswith("/git/ref/heads/main"):
            return {"object": {"sha": "sha-main"}}
        return [{"name": n} for n in self.rulesets] if path.endswith("/rulesets") and method == "GET" else None
