"""Acesso ao GitHub pelo `gh` (presente nos runners), com o token passado explicitamente.

Dois clientes no fluxo: o da GitHub App da plataforma (org: times, repositórios) e o do
GITHUB_TOKEN do workflow (só comentar e rotular as issues deste repositório)."""

import json
import os
import subprocess


class GitHubError(RuntimeError):
    pass


class GitHub:
    def __init__(self, token: str, org: str, run=subprocess.run):
        self.token, self.org, self._run = token, org, run

    def gh(self, *args: str, stdin: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
        env = {**os.environ, "GH_TOKEN": self.token}
        proc = self._run(["gh", *args], env=env, input=stdin, capture_output=True, text=True)
        if check and proc.returncode != 0:
            raise GitHubError(f"gh {' '.join(args[:3])}: {proc.stderr.strip()[:500]}")
        return proc

    def api(self, path: str, method: str = "GET", body=None):
        args = ["api", "-X", method, path]
        if body is not None:
            args += ["--input", "-"]
        out = self.gh(*args, stdin=None if body is None else json.dumps(body)).stdout
        return json.loads(out) if out.strip() else None

    def exists(self, path: str) -> bool:
        return self.gh("api", path, "--silent", check=False).returncode == 0

    def team_role(self, team: str, user: str) -> str | None:
        """Papel ativo do usuário no time (member | maintainer) ou None."""
        proc = self.gh("api", f"orgs/{self.org}/teams/{team}/memberships/{user}", check=False)
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout)
        return data.get("role") if data.get("state") == "active" else None

    # issues (no repositório do self-service)
    def comment(self, repo: str, number: str, body: str) -> None:
        self.gh("issue", "comment", number, "--repo", repo, "--body-file", "-", stdin=body)

    def labels(self, repo: str, number: str, add: str = "", remove: str = "") -> None:
        args = ["issue", "edit", number, "--repo", repo]
        if add:
            args += ["--add-label", add]
        if remove:
            args += ["--remove-label", remove]
        self.gh(*args, check=not remove)  # remover label ausente não é erro

    def close(self, repo: str, number: str, reason: str) -> None:
        self.gh("issue", "close", number, "--repo", repo, "--reason", reason)
