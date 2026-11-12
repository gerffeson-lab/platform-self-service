"""Lê o pedido de novo serviço (Issue Form ou workflow_dispatch), valida e imprime
as saídas no formato chave=valor para o $GITHUB_OUTPUT."""

import os
import re
import sys

# Rótulos do Issue Form (.github/ISSUE_TEMPLATE/novo-servico.yml) -> chave interna
FORM_LABELS = {
    "Nome do serviço": "nome",
    "Produto": "produto",
    "Time responsável (slug do time no GitHub)": "time",
    "Work item no Azure Boards": "work_item",
    "Descrição": "descricao",
}

RULES = {
    "nome": (r"^[a-z][a-z0-9-]{2,39}$", "minúsculas, números e hífen, começando com letra (3 a 40 caracteres)"),
    "produto": (r"^[a-z][a-z0-9-]{1,29}$", "minúsculas, números e hífen (2 a 30 caracteres)"),
    "time": (r"^[a-z0-9][a-z0-9-]{0,49}$", "slug do time no GitHub (ex.: pagamentos)"),
    "work_item": (r"^AB#[0-9]+$", "formato AB#<número>"),
}


def parse_issue_form(body: str) -> dict:
    """Issue Forms chegam como blocos '### Rótulo' seguidos do valor."""
    fields = {}
    for match in re.finditer(r"^###\s+(.+?)\s*$\n(.*?)(?=^###\s|\Z)", body, re.S | re.M):
        label, value = match.group(1).strip(), match.group(2).strip()
        if label in FORM_LABELS:
            fields[FORM_LABELS[label]] = "" if value == "_No response_" else value
    return fields


def main() -> int:
    if os.environ.get("EVENT_NAME") == "issues":
        fields = parse_issue_form(os.environ.get("ISSUE_BODY", ""))
    else:
        fields = {
            "nome": os.environ.get("IN_NOME", ""),
            "produto": os.environ.get("IN_PRODUTO", ""),
            "time": os.environ.get("IN_TIME", ""),
            "work_item": os.environ.get("IN_WORK_ITEM", ""),
            "descricao": os.environ.get("IN_DESCRICAO", ""),
        }

    fields = {k: v.strip() for k, v in fields.items()}
    errors = []
    for key, (pattern, hint) in RULES.items():
        if not re.fullmatch(pattern, fields.get(key, "")):
            errors.append(f"Campo '{key}' inválido: {hint}.")
    if fields.get("nome", "").endswith("-") or "--" in fields.get("nome", ""):
        errors.append("Campo 'nome' não pode terminar com hífen nem ter hífens seguidos.")

    if errors:
        for err in errors:
            print(f"::error::{err}", file=sys.stderr)
        return 1

    # descrição em uma linha, sem caracteres que quebrem o $GITHUB_OUTPUT
    descricao = " ".join(fields.get("descricao", "").split())[:200]
    for key in ("nome", "produto", "time", "work_item"):
        print(f"{key}={fields[key]}")
    print(f"descricao={descricao}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
