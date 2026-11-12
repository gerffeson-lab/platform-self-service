"""Valida um pedido de novo serviço (Issue Form ou workflow_dispatch) contra as regras e o
catálogo. Não acessa a rede: as checagens que dependem do GitHub (time existe, quem pediu é
maintainer, repositório já existe) ficam no workflow.

Uso: validate_request.py <catalogo.yaml>
Saída: chave=valor para o $GITHUB_OUTPUT (só valores que passaram no formato, para uso
seguro em chamadas de API). Erros em Markdown, um por linha, no arquivo $ERRORS_FILE."""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402

# Rótulos do Issue Form -> chave interna
FORM_LABELS = {
    "Nome do serviço": "nome",
    "Produto": "produto",
    "Time responsável": "time",
    "Work item no Azure Boards": "work_item",
    "Descrição": "descricao",
}

NAME_RE = r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$"
WORK_ITEM_RE = r"^AB#[0-9]+$"


def parse_issue_form(body: str) -> dict:
    """Issue Forms chegam como blocos '### Rótulo' seguidos do valor."""
    fields = {}
    for match in re.finditer(r"^###\s+(.+?)\s*$\n(.*?)(?=^###\s|\Z)", body, re.S | re.M):
        label, value = match.group(1).strip(), match.group(2).strip()
        if label in FORM_LABELS:
            fields[FORM_LABELS[label]] = "" if value == "_No response_" else value
    return fields


def validate(fields: dict, cat: dict) -> tuple[dict, list[str]]:
    """Devolve (valores seguros, erros)."""
    nome = fields.get("nome", "")
    produto = fields.get("produto", "")
    time = fields.get("time", "")
    work_item = fields.get("work_item", "")
    produtos = cat.get("produtos", {})
    regras = cat.get("regras", {})
    errors, safe = [], {}

    if produto not in produtos:
        errors.append(f"Produto `{produto or '(vazio)'}` não está no catálogo. "
                      "O onboarding de produto novo é um PR em `catalogo/produtos.yaml`.")
    else:
        safe["produto"] = produto
        safe["system"] = produtos[produto].get("system", produto)
        times = produtos[produto].get("times", [])
        if time not in times:
            errors.append(f"O time `{time or '(vazio)'}` não pertence ao produto `{produto}` "
                          f"(times do produto: {', '.join(f'`{t}`' for t in times)}).")

    if re.fullmatch(catalog.TEAM_RE, time):
        safe["time"] = time

    if not (3 <= len(nome) <= 40 and re.fullmatch(NAME_RE, nome)):
        errors.append("Nome do serviço inválido: use 3 a 40 caracteres, minúsculas, números e hífen, "
                      "começando com letra e sem hífen no fim ou repetido.")
    else:
        reservado = next((p for p in regras.get("prefixos_reservados", []) if nome.startswith(p)), None)
        if reservado:
            errors.append(f"O prefixo `{reservado}` é reservado para a plataforma.")
        elif regras.get("prefixo_produto", True) and produto in produtos and not nome.startswith(f"{produto}-"):
            errors.append(f"O nome deve começar com o produto: `{produto}-<nome>` (ex.: `{produto}-autorizador`).")
        else:
            safe["nome"] = nome

    if re.fullmatch(WORK_ITEM_RE, work_item):
        safe["work_item"] = work_item
    else:
        errors.append("Work item inválido: use o formato `AB#<número>` do Azure Boards.")

    # descrição em uma linha, sem caracteres que quebrem o $GITHUB_OUTPUT
    safe["descricao"] = " ".join(fields.get("descricao", "").split())[:200]
    return safe, errors


def main() -> int:
    cat = catalog.load(sys.argv[1])
    if os.environ.get("EVENT_NAME") == "issues":
        fields = parse_issue_form(os.environ.get("ISSUE_BODY", ""))
    else:
        fields = {k: os.environ.get(f"IN_{k.upper()}", "") for k in
                  ("nome", "produto", "time", "work_item", "descricao")}
    fields = {k: v.strip() for k, v in fields.items()}

    safe, errors = validate(fields, cat)
    with open(os.environ["ERRORS_FILE"], "a", encoding="utf-8") as f:
        for err in errors:
            f.write(f"- {err}\n")
    for key in ("nome", "produto", "time", "work_item", "system", "descricao"):
        print(f"{key}={safe.get(key, '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
