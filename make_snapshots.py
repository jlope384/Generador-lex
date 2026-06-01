"""Genera copias (snapshots) acumulativas del proyecto, una por etapa.

Cada carpeta ``entregas-por-etapa/etapa-N-...`` contiene el proyecto *tal como
estaba al terminar la etapa N*: los módulos implementados hasta esa etapa en su
versión final y los aún no implementados en su versión "stub" original (tomada
de ``git HEAD``).  Sirven como referencia del avance incremental; los commits se
hacen por separado (ver ``GUIA-DE-COMMITS.md``).

    python3 make_snapshots.py

No realiza ningún commit.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

GIT_ROOT = Path(__file__).resolve().parent
PROJECT = GIT_ROOT / "yalex_project" / "yalex_project"
DEST = GIT_ROOT / "entregas-por-etapa"
HEAD_PREFIX = "yalex_project/yalex_project"

# Módulo de yapargen -> etapa en la que alcanza su versión final.
MODULE_STAGE = {
    "grammar": 1, "yapar_parser": 1,
    "first_follow": 2, "lr0_items": 2,
    "lr0_automaton": 3, "visualize": 3,
    "slr_table": 4, "diagnostics": 4, "parse_runner": 4, "slr_parser": 4,
    "lr1_items": 5, "lalr_automaton": 5, "lalr_table": 5,
    "codegen": 6, "pipeline": 6,
}
# Módulos pre-existentes (finales desde la etapa 1).
ALWAYS_FINAL = {"token_contract", "yapar_reader"}

STAGE_NAMES = {
    1: "etapa-1-gramatica-yalp",
    2: "etapa-2-first-follow-closure",
    3: "etapa-3-automata-lr0",
    4: "etapa-4-tabla-slr-parser",
    5: "etapa-5-lalr",
    6: "etapa-6-integracion-cli-reporte",
}

# Archivos de nivel superior nuevos/actualizados sólo en la etapa 6.
STAGE6_ONLY = [
    "pipeline.py",  # (en yapargen, se maneja por MODULE_STAGE)
]


def head_text(rel_path: str) -> str:
    """Contenido de un archivo en git HEAD."""
    return subprocess.run(
        ["git", "show", f"HEAD:{HEAD_PREFIX}/{rel_path}"],
        cwd=GIT_ROOT, capture_output=True, text=True, check=True,
    ).stdout


def import_safe_stub(module: str) -> str:
    """Stub original de HEAD, con la unión PEP 604 convertida a typing.Union.

    Los stubs de slr_table/lalr_table tienen ``int | Production | None`` a nivel
    de módulo, que falla al importarse en Python 3.9; aquí se hace importable sin
    cambiar su semántica (siguen lanzando NotImplementedError).
    """
    text = head_text(f"yapargen/{module}.py")
    text = text.replace("from typing import Literal",
                        "from typing import Literal, Union")
    text = text.replace("int | Production | None", "Union[int, Production, None]")
    return text


def ignore(_dir, names):
    drop = {"__pycache__", "build", "entregas-por-etapa"}
    return [n for n in names if n in drop or n.endswith(".pyc")]


def build_stage(stage: int) -> Path:
    dest = DEST / STAGE_NAMES[stage]
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(PROJECT, dest, ignore=ignore)

    # 1) Módulos de yapargen aún no implementados -> stub importable de HEAD.
    for module, mod_stage in MODULE_STAGE.items():
        if mod_stage > stage:
            target = dest / "yapargen" / f"{module}.py"
            if module == "pipeline":
                # pipeline.py no existe antes de la etapa 6.
                if target.exists():
                    target.unlink()
                continue
            target.write_text(import_safe_stub(module), encoding="utf-8")

    # 2) Archivos de nivel superior: versión antigua (HEAD) antes de la etapa 6.
    if stage < 6:
        for rel in ["run_yapar.py", "README.md", "run_smoke_tests.py",
                    "yapargen/__init__.py"]:
            (dest / rel).write_text(head_text(rel), encoding="utf-8")
        # Estos sólo aparecen en la etapa 6.
        for extra in ["tests/test_yapar.py", "tools/build_report.py", "docs",
                      "GUIA-DEL-PROYECTO.md"]:
            p = dest / extra
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
        # tools/ queda vacío -> quitarlo si no tiene nada.
        tools = dest / "tools"
        if tools.exists() and not any(tools.iterdir()):
            tools.rmdir()

    # 3) requirements.txt: matplotlib (todas) + reportlab (sólo etapa 6).
    req = dest / "requirements.txt"
    if stage < 6:
        req.write_text("matplotlib\n", encoding="utf-8")
    else:
        req.write_text("matplotlib\nreportlab\n", encoding="utf-8")

    return dest


def verify(stage: int, dest: Path) -> None:
    """Comprueba que el snapshot importa yapargen sin errores."""
    code = (
        "import sys; sys.path.insert(0, '.');"
        "import importlib;"
        "[importlib.import_module('yapargen.'+m) for m in "
        "['grammar','yapar_parser','first_follow','lr0_items','lr1_items',"
        "'lr0_automaton','lalr_automaton','slr_table','lalr_table','slr_parser',"
        "'parse_runner','diagnostics','visualize','codegen','token_contract',"
        "'yapar_reader'] if (__import__('pathlib').Path('yapargen/'+m+'.py').exists())];"
        "import yapargen; print('import OK')"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=dest,
                       capture_output=True, text=True)
    status = "OK" if r.returncode == 0 else "FALLÓ"
    print(f"  etapa {stage}: import {status}"
          + ("" if r.returncode == 0 else f" -> {r.stderr.strip().splitlines()[-1:]}"))


def main() -> int:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    print(f"Generando snapshots en {DEST}/")
    for stage in range(1, 7):
        dest = build_stage(stage)
        n_py = len(list((dest / "yapargen").glob("*.py")))
        print(f"- {STAGE_NAMES[stage]}  ({n_py} módulos en yapargen)")
        verify(stage, dest)
    (DEST / "LEEME.txt").write_text(
        "Snapshots acumulativos del proyecto, uno por etapa.\n"
        "Son material de referencia del avance; los commits se hacen siguiendo\n"
        "GUIA-DE-COMMITS.md (en la raíz del repositorio).\n",
        encoding="utf-8",
    )
    print("Listo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
