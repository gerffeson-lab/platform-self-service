"""Ponto de entrada do self-service (workflow selfservice.yaml e esteira do catálogo).

    cli.py operacao               detecta a operação (label da issue ou input do dispatch)
    cli.py validar <operação>     valida, comenta na issue e publica o pedido para o próximo job
    cli.py executar <operação>    executa o pedido validado e avisa na issue
    cli.py formularios [--check]  gera os Issue Forms a partir do catálogo

Contrato com o workflow, por variáveis de ambiente:
    EVENT_NAME, ISSUE_NUMBER, ISSUE_BODY, REQUESTER
    INPUT_OPERACAO, INPUT_DADOS (JSON)        no workflow_dispatch
    APP_TOKEN    token da GitHub App da plataforma (org: times, repositórios)
    AZDO_ORG, AZDO_TOKEN   organização do Azure DevOps e token de leitura de work items (opcionais)
    ISSUES_TOKEN GITHUB_TOKEN do workflow (comentar e rotular as issues)
    PEDIDO (JSON), NEW_REPO_VISIBILITY, RUN_URL   no executar"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from selfservice import catalog, forms  # noqa: E402
from selfservice.boards import Boards, BoardsError  # noqa: E402
from selfservice.github import GitHub  # noqa: E402
from selfservice.operacoes import OPERACOES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CATALOGO = ROOT / "catalogo"
TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"
LABEL_INVALIDO, LABEL_CONCLUIDO = "pedido-invalido", "concluido"
ENV = os.environ


def output(key: str, value: str) -> None:
    if ENV.get("GITHUB_OUTPUT"):
        with open(ENV["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    print(f"{key}={value}")


def summary(markdown: str) -> None:
    if ENV.get("GITHUB_STEP_SUMMARY"):
        with open(ENV["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(markdown + "\n")


def is_issue() -> bool:
    return ENV.get("EVENT_NAME") == "issues"


def issues() -> GitHub:
    return GitHub(ENV["ISSUES_TOKEN"], ENV["GITHUB_REPOSITORY_OWNER"])


def app() -> GitHub:
    return GitHub(ENV["APP_TOKEN"], ENV["GITHUB_REPOSITORY_OWNER"])


def boards() -> Boards | None:
    """Sem AZDO_ORG e AZDO_TOKEN, o work item só tem o formato conferido."""
    org, token = ENV.get("AZDO_ORG", ""), ENV.get("AZDO_TOKEN", "")
    if bool(org) != bool(token):
        raise SystemExit("::error::Configure AZDO_ORG e AZDO_TOKEN juntos (ou nenhum dos dois).")
    if not org:
        print("::warning::Azure Boards não configurado: o work item só tem o formato conferido.")
        return None
    return Boards(org, token)


def atualizar_titulo(mod, pedido: dict) -> None:
    """Completa o título da issue (ex.: "[novo-servico] crt-credito-autorizador"). A edição feita
    com o GITHUB_TOKEN não dispara o workflow de novo."""
    titulo = mod.titulo(pedido) if hasattr(mod, "titulo") else None
    if titulo and titulo != ENV.get("ISSUE_TITLE", ""):
        issues().title(ENV["GITHUB_REPOSITORY"], ENV["ISSUE_NUMBER"], titulo)


def lista(erros: list[str]) -> str:
    return "\n".join(f"- {e}" for e in erros)


# ------------------------------------------------------------------ comandos

def cmd_operacao() -> int:
    if is_issue():
        # Estado ATUAL da issue, não o do evento: uma edição feita durante a criação fica na
        # fila e só roda depois; aí a issue já está fechada e não deve ser validada de novo.
        atual = issues().issue(ENV["GITHUB_REPOSITORY"], ENV["ISSUE_NUMBER"])
        ops = [label for label in atual["labels"] if label in OPERACOES]
        ativa = atual["state"] == "open" and LABEL_CONCLUIDO not in atual["labels"]
        output("operacao", ops[0] if ativa and len(ops) == 1 else "")
        return 0
    op = ENV.get("INPUT_OPERACAO", "")
    if op not in OPERACOES:
        print(f"::error::Operação desconhecida: {op!r}. Disponíveis: {', '.join(OPERACOES)}")
        return 1
    output("operacao", op)
    return 0


def cmd_validar(op: str) -> int:
    mod, cat = OPERACOES[op], catalog.carregar(CATALOGO)
    if is_issue():
        campos = forms.parse(ENV.get("ISSUE_BODY", ""), mod.formulario(cat))
    else:
        dados = json.loads(ENV.get("INPUT_DADOS") or "{}")
        campos = {str(k): str(v) for k, v in dados.items()} if isinstance(dados, dict) else {}
    pedido, erros = mod.validar({k: v.strip() for k, v in campos.items()}, cat)

    gh = app()
    try:
        erros += mod.checar(pedido, gh, boards())
    except BoardsError as exc:  # falha de infraestrutura: não culpa o pedido
        print(f"::error::{exc}")
        if is_issue():
            issues().comment(ENV["GITHUB_REPOSITORY"], ENV["ISSUE_NUMBER"],
                             "⚠️ Não foi possível consultar o Azure Boards agora; a plataforma foi avisada. "
                             f"Detalhes: {ENV.get('RUN_URL', '')}")
        return 1
    nao_autorizado = mod.autorizar(pedido, gh, ENV.get("REQUESTER", ""))
    if is_issue():
        atualizar_titulo(mod, pedido)

    if not erros and not nao_autorizado:
        output("valido", "true")
        output("pedido", json.dumps(pedido, ensure_ascii=False))
        summary(f"### Pedido válido ({op})\n{mod.resumo(pedido)}")
        if is_issue():
            repo, num = ENV["GITHUB_REPOSITORY"], ENV["ISSUE_NUMBER"]
            issues().labels(repo, num, remove=LABEL_INVALIDO)
            issues().comment(repo, num, f"✅ Pedido válido. {mod.resumo(pedido)} O resultado aparece aqui em instantes.")
        return 0

    output("valido", "false")
    summary(f"### Pedido inválido ({op})\n{lista(nao_autorizado + erros)}")
    if not is_issue():
        print(lista(nao_autorizado + erros))
        return 1
    repo, num = ENV["GITHUB_REPOSITORY"], ENV["ISSUE_NUMBER"]
    if nao_autorizado:
        issues().comment(repo, num, f"⛔ **Pedido não autorizado.**\n\n{lista(nao_autorizado)}\n\n"
                                    "Peça ao tech lead do time para abrir o pedido.")
        issues().close(repo, num, "not planned")
    else:
        issues().comment(repo, num, "❌ **Pedido inválido.** Corrija editando esta issue; a validação roda de "
                                    f"novo automaticamente.\n\n{lista(erros)}")
        issues().labels(repo, num, add=LABEL_INVALIDO)
    return 0


def cmd_executar(op: str) -> int:
    mod = OPERACOES[op]
    visibilidade = ENV.get("NEW_REPO_VISIBILITY") or "public"
    if visibilidade not in ("public", "internal", "private"):
        print(f"::error::NEW_REPO_VISIBILITY inválida: {visibilidade}")
        return 1
    cfg = {"visibilidade": visibilidade, "server_url": ENV.get("GITHUB_SERVER_URL", "https://github.com")}
    pedido = json.loads(ENV["PEDIDO"])
    try:
        mensagem = mod.executar(pedido, app(), cfg, cat=catalog.carregar(CATALOGO))
    except Exception as exc:
        print(f"::error::{exc}")
        if is_issue():
            issues().comment(ENV["GITHUB_REPOSITORY"], ENV["ISSUE_NUMBER"],
                             f"❌ Falha ao executar o pedido; a plataforma foi avisada. Detalhes: {ENV.get('RUN_URL', '')}")
        return 1
    summary(mensagem)
    if is_issue():
        repo, num = ENV["GITHUB_REPOSITORY"], ENV["ISSUE_NUMBER"]
        issues().comment(repo, num, mensagem)
        issues().labels(repo, num, add=LABEL_CONCLUIDO)
        issues().close(repo, num, "completed")
    return 0


def cmd_formularios(check: bool) -> int:
    try:
        cat = catalog.carregar(CATALOGO)
    except ValueError as exc:
        cat, erros = {}, [str(exc)]
    else:
        erros = catalog.check(cat)
    if erros:
        for e in erros:
            print(f"::error file=catalogo::{e}", file=sys.stderr)
        return 1
    desatualizados = []
    for op, mod in OPERACOES.items():
        destino, conteudo = TEMPLATES / f"{op}.yml", forms.render(mod.formulario(cat))
        if check:
            if not destino.exists() or destino.read_text(encoding="utf-8") != conteudo:
                desatualizados.append(destino.relative_to(ROOT))
        else:
            destino.write_text(conteudo, encoding="utf-8")
            print(f"Gerado {destino.relative_to(ROOT)}")
    for d in desatualizados:
        print(f"::error file={d}::Formulário desatualizado. Rode `python3 scripts/cli.py formularios` "
              "e commite o resultado.", file=sys.stderr)
    if check and not desatualizados:
        print("Formulários em dia com o catálogo.")
    return 1 if desatualizados else 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "operacao":
        return cmd_operacao()
    if cmd in ("validar", "executar") and len(argv) == 3 and argv[2] in OPERACOES:
        return (cmd_validar if cmd == "validar" else cmd_executar)(argv[2])
    if cmd == "formularios":
        return cmd_formularios("--check" in argv)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
