"""Formulários das operações: a mesma definição gera o Issue Form e lê as respostas da issue,
então rótulo e parser nunca divergem."""

import json
import re
from dataclasses import dataclass, field

HEADER = "# GERADO por scripts/cli.py formularios a partir do catálogo. Não edite à mão."


@dataclass(frozen=True)
class Campo:
    id: str
    label: str
    tipo: str  # input | dropdown | textarea | checkboxes
    descricao: str = ""
    placeholder: str = ""
    obrigatorio: bool = True
    opcoes: tuple = ()


@dataclass(frozen=True)
class Formulario:
    id: str            # também é a label que identifica a operação na issue
    nome: str
    descricao: str
    titulo: str
    intro: str
    campos: tuple = field(default_factory=tuple)


def _q(value: str) -> str:
    """Escalar YAML seguro (string JSON é YAML válido)."""
    return json.dumps(value, ensure_ascii=False)


def render(form: Formulario) -> str:
    out = [HEADER, f"name: {_q(form.nome)}", f"description: {_q(form.descricao)}",
           f"title: {_q(form.titulo)}", f"labels: [{_q(form.id)}]", "body:"]
    if form.intro:
        out += ["  - type: markdown", "    attributes:", "      value: |"]
        out += [f"        {line}".rstrip() for line in form.intro.strip().splitlines()]
    for c in form.campos:
        out += [f"  - type: {c.tipo}", f"    id: {c.id}", "    attributes:", f"      label: {_q(c.label)}"]
        if c.descricao:
            out.append(f"      description: {_q(c.descricao)}")
        if c.placeholder:
            out.append(f"      placeholder: {_q(c.placeholder)}")
        if c.tipo == "dropdown":
            out += ["      options:"] + [f"        - {_q(o)}" for o in c.opcoes]
        if c.tipo == "checkboxes":
            out += ["      options:"]
            for o in c.opcoes:
                out += [f"        - label: {_q(o)}", "          required: true"]
        elif c.obrigatorio:
            out += ["    validations:", "      required: true"]
    return "\n".join(out) + "\n"


def parse(body: str, form: Formulario) -> dict:
    """Issue Forms chegam como blocos '### Rótulo' seguidos do valor."""
    por_label = {c.label: c.id for c in form.campos if c.tipo != "checkboxes"}
    campos = {}
    for m in re.finditer(r"^###\s+(.+?)\s*$\n(.*?)(?=^###\s|\Z)", body or "", re.S | re.M):
        label, valor = m.group(1).strip(), m.group(2).strip()
        if label in por_label:
            campos[por_label[label]] = "" if valor == "_No response_" else valor
    return campos
