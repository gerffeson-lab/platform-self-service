"""Personaliza um repositório gerado a partir do platform-java-boilerplate:
nome do artefato, pacote Java, classe principal, time responsável e system (sigla).

O boilerplate continua compilável (sem placeholders), e a troca acontece aqui."""

import os
import shutil

TEMPLATE_NAME = "platform-java-boilerplate"   # artifactId, nome da aplicação, catálogo
TEMPLATE_PACKAGE = "platformjavaboilerplate"  # com.acme.platformjavaboilerplate
TEMPLATE_CLASS = "PlatformJavaBoilerplate"    # PlatformJavaBoilerplateApplication
TEMPLATE_TEAM = "plataforma"                  # time dono no catalog-info e no CODEOWNERS
TEMPLATE_SYSTEM = "system: acme"              # system (sigla) no catalog-info
JAVA_ROOTS = ("src/main/java/com/acme", "src/test/java/com/acme")
SKIP_DIRS = {".git", "target"}


def to_package(name: str) -> str:
    return name.replace("-", "")


def to_class(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("-"))


def walk_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            yield os.path.join(dirpath, filename)


def personalizar(root: str, name: str, system: str, org: str, team: str) -> int:
    """Aplica nome, pacote, classe, time e system no repositório clonado em `root`."""
    package, cls = to_package(name), to_class(name)

    # 1. Move os diretórios do pacote Java
    for base in JAVA_ROOTS:
        old = os.path.join(root, base, TEMPLATE_PACKAGE)
        if os.path.isdir(old):
            shutil.move(old, os.path.join(root, base, package))

    # 2. Renomeia arquivos com o nome da classe do boilerplate
    for path in list(walk_files(root)):
        filename = os.path.basename(path)
        if TEMPLATE_CLASS in filename:
            os.rename(path, os.path.join(os.path.dirname(path), filename.replace(TEMPLATE_CLASS, cls)))

    # 3. Substitui o conteúdo (a ordem importa: do mais específico para o mais geral)
    replacements = [
        (f"com.acme.{TEMPLATE_PACKAGE}", f"com.acme.{package}"),
        (TEMPLATE_CLASS, cls),
        (TEMPLATE_NAME, name),
        (f"group:{TEMPLATE_TEAM}", f"group:{team}"),
        (f"@{org}/{TEMPLATE_TEAM}", f"@{org}/{team}"),
        (TEMPLATE_SYSTEM, f"system: {system}"),
    ]
    changed = 0
    for path in walk_files(root):
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except (UnicodeDecodeError, OSError):
            continue  # arquivo binário
        new = content
        for old, repl in replacements:
            new = new.replace(old, repl)
        if new != content:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)
            changed += 1
    return changed
