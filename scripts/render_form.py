"""Gera o Issue Form de novo serviço a partir do catálogo, para que as opções de produto e
time sejam sempre as do catálogo. Use --check na esteira para falhar se estiver desatualizado."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalogo" / "produtos.yaml"
FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "novo-servico.yml"

TEMPLATE = """\
# GERADO por scripts/render_form.py a partir de catalogo/produtos.yaml. Não edite à mão.
name: Novo serviço
description: Cria um serviço a partir do golden path (repositório, esteira e padrões prontos)
title: "[novo-servico] "
labels: [novo-servico]
body:
  - type: markdown
    attributes:
      value: |
        O pedido é validado assim que você envia. Se estiver tudo certo, o repositório é criado
        em poucos minutos e o link aparece nesta issue; se não, o bot explica o que corrigir.

        - **Quem pode pedir:** maintainers (tech leads) do time responsável.
        - **Produto que não aparece na lista:** o onboarding de produto é um PR em
          `catalogo/produtos.yaml`, revisado pela plataforma.
  - type: input
    id: nome
    attributes:
      label: Nome do serviço
      description: "Comece pelo produto: <produto>-<nome>. Minúsculas, números e hífen (ex.: cartoes-autorizador)"
      placeholder: cartoes-autorizador
    validations:
      required: true
  - type: dropdown
    id: produto
    attributes:
      label: Produto
      options:
{produtos}
    validations:
      required: true
  - type: dropdown
    id: time
    attributes:
      label: Time responsável
      description: Precisa ser um time do produto escolhido. Recebe acesso de escrita e vira CODEOWNER
      options:
{times}
    validations:
      required: true
  - type: input
    id: work-item
    attributes:
      label: Work item no Azure Boards
      description: "Formato AB#<número>"
      placeholder: "AB#123"
    validations:
      required: true
  - type: textarea
    id: descricao
    attributes:
      label: Descrição
      description: O que o serviço faz, em uma ou duas frases
  - type: checkboxes
    id: confirmacao
    attributes:
      label: Confirmação
      options:
        - label: O serviço segue o golden path (Java/Spring, contrato OpenAPI primeiro, esteira da plataforma)
          required: true
"""


def render(cat: dict) -> str:
    def opts(values):
        return "\n".join(f"        - {v}" for v in values)

    return TEMPLATE.format(produtos=opts(sorted(cat["produtos"])), times=opts(catalog.all_teams(cat)))


def main() -> int:
    cat = catalog.load(str(CATALOG))
    errors = catalog.check(cat)
    if errors:
        for err in errors:
            print(f"::error file=catalogo/produtos.yaml::{err}", file=sys.stderr)
        return 1
    content = render(cat)
    if "--check" in sys.argv:
        if FORM.read_text(encoding="utf-8") != content:
            print("::error file=.github/ISSUE_TEMPLATE/novo-servico.yml::Formulário desatualizado. "
                  "Rode `python3 scripts/render_form.py` e commite o resultado.", file=sys.stderr)
            return 1
        print("Formulário em dia com o catálogo.")
        return 0
    FORM.write_text(content, encoding="utf-8")
    print(f"Gerado {FORM.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
