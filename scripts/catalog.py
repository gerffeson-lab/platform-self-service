"""Leitura do catálogo de produtos (catalogo/produtos.yaml)."""

import json
import re
import subprocess

SLUG_RE = r"^[a-z][a-z0-9-]{1,29}$"
TEAM_RE = r"^[a-z0-9][a-z0-9-]{0,49}$"


def load(path: str) -> dict:
    """Lê o YAML com PyYAML ou, se não houver, com o yq (presente nos runners)."""
    try:
        import yaml  # noqa: PLC0415

        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        out = subprocess.run(["yq", "-o=json", path], check=True, capture_output=True, text=True)
        return json.loads(out.stdout or "{}")


def check(catalog: dict) -> list[str]:
    """Erros de estrutura do catálogo."""
    errors = []
    produtos = catalog.get("produtos")
    if not isinstance(produtos, dict) or not produtos:
        return ["`produtos` precisa ser um mapa com ao menos um produto."]
    for nome, dados in produtos.items():
        if not re.fullmatch(SLUG_RE, str(nome)):
            errors.append(f"Produto `{nome}`: nome inválido (minúsculas, números e hífen).")
        if not isinstance(dados, dict):
            errors.append(f"Produto `{nome}`: precisa ser um mapa.")
            continue
        times = dados.get("times")
        if not isinstance(times, list) or not times:
            errors.append(f"Produto `{nome}`: `times` precisa ter ao menos um time.")
            continue
        for time in times:
            if not re.fullmatch(TEAM_RE, str(time)):
                errors.append(f"Produto `{nome}`: time `{time}` inválido (slug do time no GitHub).")
    return errors


def all_teams(catalog: dict) -> list[str]:
    return sorted({t for p in catalog.get("produtos", {}).values() for t in p.get("times", [])})
