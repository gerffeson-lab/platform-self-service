"""Catálogo da plataforma (catalogo/*.yaml).

- siglas.yaml:        siglas -> produtos -> times
- golden-paths.yaml:  golden paths -> repositório template"""

import json
import re
import subprocess
from pathlib import Path

SIGLA_RE = r"[a-z][a-z0-9]{1,4}"
PRODUTO_RE = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
TEAM_RE = r"[a-z0-9][a-z0-9-]{0,49}"
GOLDEN_PATH_RE = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
REPO_RE = r"[A-Za-z0-9._-]{1,100}"


def load(path: str) -> dict:
    """Lê um YAML com PyYAML ou, se não houver, com o yq (presente nos runners)."""
    try:
        import yaml  # noqa: PLC0415

        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        out = subprocess.run(["yq", "-o=json", path], check=True, capture_output=True, text=True)
        return json.loads(out.stdout or "{}")


def carregar(diretorio) -> dict:
    """Junta os arquivos do catálogo; cada um traz suas chaves de topo (siglas, golden_paths)."""
    cat = {}
    for path in sorted(Path(diretorio).glob("*.yaml")):
        dados = load(str(path))
        repetidas = set(cat) & set(dados)
        if repetidas:
            raise ValueError(f"{path.name}: chave(s) {', '.join(sorted(repetidas))} já definida(s) em outro arquivo.")
        cat.update(dados)
    return cat


def check(cat: dict) -> list[str]:
    """Erros de estrutura do catálogo."""
    return _check_siglas(cat) + _check_golden_paths(cat)


def _check_siglas(cat: dict) -> list[str]:
    siglas = cat.get("siglas")
    if not isinstance(siglas, dict) or not siglas:
        return ["`siglas` precisa ser um mapa com ao menos uma sigla."]
    errors = []
    for sigla, dados in siglas.items():
        if not re.fullmatch(SIGLA_RE, str(sigla)):
            errors.append(f"Sigla `{sigla}`: use 2 a 5 caracteres, minúsculas e números, começando com letra.")
        produtos_ = dados.get("produtos") if isinstance(dados, dict) else None
        if not isinstance(produtos_, dict) or not produtos_:
            errors.append(f"Sigla `{sigla}`: `produtos` precisa ter ao menos um produto.")
            continue
        for produto, pdados in produtos_.items():
            onde = f"Produto `{sigla}-{produto}`"
            if not (re.fullmatch(PRODUTO_RE, str(produto)) and len(str(produto)) <= 20):
                errors.append(f"{onde}: nome inválido (até 20 caracteres, minúsculas, números e hífen).")
            times = pdados.get("times") if isinstance(pdados, dict) else None
            if not isinstance(times, list) or not times:
                errors.append(f"{onde}: `times` precisa ter ao menos um time.")
                continue
            errors += [f"{onde}: time `{t}` inválido (slug do time no GitHub)."
                       for t in times if not re.fullmatch(TEAM_RE, str(t))]
    return errors


def _check_golden_paths(cat: dict) -> list[str]:
    gps = cat.get("golden_paths")
    if not isinstance(gps, dict) or not gps:
        return ["`golden_paths` precisa ser um mapa com ao menos um golden path."]
    errors = []
    for gp, dados in gps.items():
        onde = f"Golden path `{gp}`"
        if not re.fullmatch(GOLDEN_PATH_RE, str(gp)):
            errors.append(f"{onde}: id inválido (minúsculas, números e hífen).")
        if not isinstance(dados, dict):
            errors.append(f"{onde}: precisa ser um mapa com `nome` e `template`.")
            continue
        if not isinstance(dados.get("nome"), str) or not dados["nome"].strip():
            errors.append(f"{onde}: `nome` é obrigatório.")
        if not re.fullmatch(REPO_RE, str(dados.get("template", ""))):
            errors.append(f"{onde}: `template` precisa ser o nome de um repositório da org.")
    return errors


def siglas(cat: dict) -> list[str]:
    return sorted(cat.get("siglas", {}))


def produtos(cat: dict) -> dict:
    """{"crt-credito": {"sigla": "crt", "produto": "credito", "times": [...]}}"""
    return {
        f"{sigla}-{produto}": {"sigla": sigla, "produto": produto, "times": list(p.get("times", []))}
        for sigla, s in cat.get("siglas", {}).items()
        for produto, p in s.get("produtos", {}).items()
    }


def nomes_produtos(cat: dict) -> list[str]:
    """Nomes de produto de todas as siglas (um mesmo nome pode existir em mais de uma sigla)."""
    return sorted({p["produto"] for p in produtos(cat).values()})


def all_teams(cat: dict) -> list[str]:
    return sorted({t for p in produtos(cat).values() for t in p["times"]})


def golden_paths(cat: dict) -> dict:
    return dict(cat.get("golden_paths", {}))
