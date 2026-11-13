"""Catálogo da plataforma (catalogo/siglas.yaml): siglas -> produtos -> times."""

import json
import re
import subprocess

SIGLA_RE = r"[a-z][a-z0-9]{1,4}"
PRODUTO_RE = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
TEAM_RE = r"[a-z0-9][a-z0-9-]{0,49}"


def load(path: str) -> dict:
    """Lê o YAML com PyYAML ou, se não houver, com o yq (presente nos runners)."""
    try:
        import yaml  # noqa: PLC0415

        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        out = subprocess.run(["yq", "-o=json", path], check=True, capture_output=True, text=True)
        return json.loads(out.stdout or "{}")


def check(cat: dict) -> list[str]:
    """Erros de estrutura do catálogo."""
    siglas = cat.get("siglas")
    if not isinstance(siglas, dict) or not siglas:
        return ["`siglas` precisa ser um mapa com ao menos uma sigla."]
    errors = []
    for sigla, dados in siglas.items():
        if not re.fullmatch(SIGLA_RE, str(sigla)):
            errors.append(f"Sigla `{sigla}`: use 2 a 5 caracteres, minúsculas e números, começando com letra.")
        produtos = dados.get("produtos") if isinstance(dados, dict) else None
        if not isinstance(produtos, dict) or not produtos:
            errors.append(f"Sigla `{sigla}`: `produtos` precisa ter ao menos um produto.")
            continue
        for produto, pdados in produtos.items():
            onde = f"Produto `{sigla}-{produto}`"
            if not (re.fullmatch(PRODUTO_RE, str(produto)) and len(str(produto)) <= 20):
                errors.append(f"{onde}: nome inválido (até 20 caracteres, minúsculas, números e hífen).")
            times = pdados.get("times") if isinstance(pdados, dict) else None
            if not isinstance(times, list) or not times:
                errors.append(f"{onde}: `times` precisa ter ao menos um time.")
                continue
            errors += [f"{onde}: time `{t}` inválido (slug do time no GitHub)."
                       for t in times if not re.fullmatch(TEAM_RE, str(t))]
    if not errors:
        chaves = [f"{s}-{p}" for s, d in siglas.items() for p in d["produtos"]]
        errors += [f"`{c}` aparece mais de uma vez (sigla + produto precisa ser único)."
                   for c in sorted({c for c in chaves if chaves.count(c) > 1})]
    return errors


def produtos(cat: dict) -> dict:
    """{"crt-credito": {"sigla": "crt", "produto": "credito", "times": [...]}}"""
    return {
        f"{sigla}-{produto}": {"sigla": sigla, "produto": produto, "times": list(p.get("times", []))}
        for sigla, s in cat.get("siglas", {}).items()
        for produto, p in s.get("produtos", {}).items()
    }


def all_teams(cat: dict) -> list[str]:
    return sorted({t for p in produtos(cat).values() for t in p["times"]})
