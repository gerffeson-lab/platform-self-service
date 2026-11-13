"""Operação novo-servico: cria o repositório <sigla>-<produto>-<aplicação> a partir do
boilerplate, com time dono, GitFlow, ruleset e custom properties."""

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from .. import catalog
from ..forms import Campo, Formulario
from ..personalizar import personalizar

ID = "novo-servico"
APLICACAO_RE = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
WORK_ITEM_RE = r"AB#[0-9]+"
NOME_MAX = 60
# custom properties da org gravadas no repositório (alvo de rulesets e políticas da org)
PROPRIEDADES = ("sigla", "produto", "time")
RULESET = Path(__file__).resolve().parents[3] / "rulesets" / "gitflow.json"


def formulario(cat: dict) -> Formulario:
    return Formulario(
        id=ID,
        nome="Novo serviço",
        descricao="Cria um serviço a partir do golden path (repositório, esteira e padrões prontos)",
        titulo="[novo-servico] ",
        intro="""
O pedido é validado assim que você envia. Se estiver tudo certo, o repositório é criado em
poucos minutos e o link aparece nesta issue; se não, o bot explica o que corrigir.

- **Quem pode pedir:** maintainers (tech leads) do time responsável.
- **Nome do repositório:** `<sigla>-<produto>-<aplicação>`, montado a partir dos campos abaixo.
- **Sigla ou produto que não aparece na lista:** é um PR em `catalogo/siglas.yaml`, revisado
  pela plataforma.
""",
        campos=(
            Campo("sigla-produto", "Sigla e produto", "dropdown",
                  descricao="Sistema (sigla) e produto do catálogo", opcoes=tuple(sorted(catalog.produtos(cat)))),
            Campo("aplicacao", "Nome da aplicação", "input",
                  descricao="Minúsculas, números e hífen. O repositório será <sigla>-<produto>-<aplicação>",
                  placeholder="autorizador"),
            Campo("time", "Time responsável", "dropdown",
                  descricao="Precisa ser um time do produto. Recebe acesso de escrita e vira CODEOWNER",
                  opcoes=tuple(catalog.all_teams(cat))),
            Campo("work-item", "Work item no Azure Boards", "input",
                  descricao="Formato AB#<número>", placeholder="AB#123"),
            Campo("descricao", "Descrição", "textarea",
                  descricao="O que o serviço faz, em uma ou duas frases", obrigatorio=False),
            Campo("confirmacao", "Confirmação", "checkboxes", opcoes=(
                "O serviço segue o golden path (Java/Spring, contrato OpenAPI primeiro, esteira da plataforma)",)),
        ),
    )


def validar(campos: dict, cat: dict) -> tuple[dict, list[str]]:
    """Regras que não dependem do GitHub. Devolve (pedido só com valores seguros, erros)."""
    produtos = catalog.produtos(cat)
    chave = campos.get("sigla-produto", "")
    aplicacao = campos.get("aplicacao", "")
    time_ = campos.get("time", "")
    work_item = campos.get("work-item", "")
    pedido, erros = {}, []

    produto = produtos.get(chave)
    if not produto:
        erros.append(f"`{chave or '(vazio)'}` não está no catálogo. Sigla ou produto novo é um PR em "
                     "`catalogo/siglas.yaml`.")
    else:
        pedido.update(sigla=produto["sigla"], produto=produto["produto"])
        if time_ not in produto["times"]:
            erros.append(f"O time `{time_ or '(vazio)'}` não pertence a `{chave}` "
                         f"(times: {', '.join(f'`{t}`' for t in produto['times'])}).")
    if re.fullmatch(catalog.TEAM_RE, time_):
        pedido["time"] = time_

    if not (2 <= len(aplicacao) <= 30 and re.fullmatch(APLICACAO_RE, aplicacao)):
        erros.append("Nome da aplicação inválido: 2 a 30 caracteres, minúsculas, números e hífen, começando "
                     "com letra e sem hífen no fim ou repetido.")
    elif produto:
        nome = f"{chave}-{aplicacao}"
        if aplicacao.startswith(f"{produto['sigla']}-") or aplicacao.startswith(f"{produto['produto']}-"):
            erros.append(f"Não repita a sigla ou o produto no nome da aplicação: o repositório já se chama "
                         f"`{chave}-<aplicação>`.")
        elif len(nome) > NOME_MAX:
            erros.append(f"`{nome}` passa de {NOME_MAX} caracteres; encurte o nome da aplicação.")
        else:
            pedido.update(aplicacao=aplicacao, nome=nome)

    if re.fullmatch(WORK_ITEM_RE, work_item):
        pedido["work_item"] = work_item
    else:
        erros.append("Work item inválido: use o formato `AB#<número>` do Azure Boards.")

    pedido["descricao"] = " ".join(campos.get("descricao", "").split())[:200]
    return pedido, erros


def checar(pedido: dict, gh) -> list[str]:
    """Regras que dependem do GitHub (com o token da App)."""
    erros = []
    if pedido.get("time") and not gh.exists(f"orgs/{gh.org}/teams/{pedido['time']}"):
        erros.append(f"O time `{pedido['time']}` não existe na organização.")
    if pedido.get("nome") and gh.exists(f"repos/{gh.org}/{pedido['nome']}"):
        erros.append(f"O repositório `{gh.org}/{pedido['nome']}` já existe.")
    return erros


def autorizar(pedido: dict, gh, solicitante: str) -> list[str]:
    """Só maintainers (tech leads) do time dono podem pedir."""
    time_ = pedido.get("time")
    if not time_ or not gh.exists(f"orgs/{gh.org}/teams/{time_}"):
        return []  # time inexistente já é erro em checar()
    if gh.team_role(time_, solicitante) == "maintainer":
        return []
    return [f"@{solicitante} não é maintainer do time `{pedido['time']}`. Só os maintainers (tech leads) "
            "do time podem pedir serviços para ele."]


def resumo(pedido: dict) -> str:
    return f"Criando `{pedido['nome']}` para o time `{pedido['time']}`."


def executar(pedido: dict, gh, cfg: dict, publicar=None) -> str:
    """Idempotente: o "Re-run failed jobs" retoma de onde parou."""
    org, nome = gh.org, pedido["nome"]
    repo = f"{org}/{nome}"

    if not gh.exists(f"repos/{repo}"):
        gh.gh("repo", "create", repo, f"--{cfg['visibilidade']}", "--template", cfg["template"],
              "--description", pedido["descricao"])
        _aguardar(lambda: gh.exists(f"repos/{repo}/commits?per_page=1"))

    gh.api(f"repos/{repo}/properties/values", "PATCH",
           {"properties": [{"property_name": p, "value": pedido[p]} for p in PROPRIEDADES]})

    if not gh.exists(f"repos/{repo}/branches/develop"):
        (publicar or _publicar)(gh, repo, pedido)

    gh.gh("repo", "edit", repo, "--default-branch", "develop", "--delete-branch-on-merge",
          "--add-topic", "golden-path", "--add-topic", f"sigla-{pedido['sigla']}",
          "--add-topic", f"produto-{pedido['produto']}")
    gh.api(f"orgs/{org}/teams/{pedido['time']}/repos/{repo}", "PUT", {"permission": "push"})

    ruleset = json.loads(RULESET.read_text(encoding="utf-8"))
    if ruleset["name"] not in {r["name"] for r in gh.api(f"repos/{repo}/rulesets") or []}:
        gh.api(f"repos/{repo}/rulesets", "POST", ruleset)

    return (f"🚀 Repositório criado: {cfg['server_url']}/{repo}\n\n"
            f"@{org}/{pedido['time']}, o serviço é de vocês:\n"
            "- Acesso de escrita e CODEOWNERS para o time.\n"
            "- Branch padrão `develop` (GitFlow); `main` e `develop` só recebem mudanças via PR.\n"
            "- A esteira já está ligada: abra um PR e acompanhe os gates.\n"
            "- Comece pelo contrato em `api/openapi.yaml`.")


def _aguardar(pronto, tentativas: int = 30, intervalo: float = 2) -> None:
    """A geração a partir do template é assíncrona."""
    for _ in range(tentativas):
        if pronto():
            return
        time.sleep(intervalo)
    raise TimeoutError("O repositório gerado do template não ficou pronto a tempo.")


def _publicar(gh, repo: str, pedido: dict) -> None:
    """Clona, personaliza e publica main e develop (commit com o AB# do pedido)."""
    env = {**os.environ, "GH_TOKEN": gh.token}
    with tempfile.TemporaryDirectory() as tmp:
        work = os.path.join(tmp, "repo")
        gh.gh("auth", "setup-git")
        gh.gh("repo", "clone", repo, work)
        personalizar(work, pedido["nome"], pedido["sigla"], gh.org, pedido["time"])

        def git(*args):
            subprocess.run(["git", "-C", work, "-c", "user.name=platform-bot",
                            "-c", "user.email=platform-bot@users.noreply.github.com", *args],
                           check=True, env=env)

        git("add", "-A")
        git("commit", "-m", f"chore: cria {pedido['nome']} a partir do platform-java-boilerplate",
            "-m", pedido["work_item"])
        git("push", "origin", "HEAD:main")
        git("push", "origin", "HEAD:refs/heads/develop")
