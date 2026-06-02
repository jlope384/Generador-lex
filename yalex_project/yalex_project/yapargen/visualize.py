"""Visual + textual rendering of LR automata and parse trees.

Three representations are produced for an automaton so the tool works on any
machine:

* a **Graphviz ``.dot``** file — the canonical, dependency-free representation
  that any Graphviz viewer (or VS Code / an online renderer) can open;
* a **PNG** drawn with matplotlib using a deterministic BFS-layered layout, so a
  picture is available even without the Graphviz ``dot`` binary installed;
* a **plain-text** dump of the states and transitions.

If the Graphviz ``dot`` binary *is* on PATH it is also used to render a high
quality ``*.gv.png`` next to the matplotlib image.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Union

from .lr0_automaton import LR0Automaton
from .lalr_automaton import LALRAutomaton

AnyAutomaton = Union[LR0Automaton, LALRAutomaton]


# ── item-set rendering (handles both LR(0) and LR(1)/LALR states) ───────────
def _state_lines(state) -> list[str]:
    """Display lines for an item set.

    LALR states hold LR(1) items; those are grouped by their LR(0) core so the
    lookaheads of one core collapse onto a single line (``A -> α.β , a/b``).
    LR(0) states fall back to one ``str(item)`` per line.
    """
    items = list(state)
    if items and hasattr(items[0], "lookahead"):
        from .lr1_items import merge_lookaheads
        return merge_lookaheads(state)
    return sorted(str(it) for it in items)


# ── text / DOT ──────────────────────────────────────────────────────────────
def automaton_to_text(automaton: AnyAutomaton, title: str = "LR automaton") -> str:
    """Return a human-readable dump of states and transitions."""
    lines = [title, "=" * len(title), ""]
    for i, state in enumerate(automaton.states):
        marker = "  (inicial)" if i == automaton.start_state else ""
        lines.append(f"I{i}{marker}:")
        for item in _state_lines(state):
            lines.append(f"    {item}")
        outgoing = sorted(
            (sym, j) for (s, sym), j in automaton.transitions.items() if s == i
        )
        for sym, j in outgoing:
            lines.append(f"      --{sym}--> I{j}")
        lines.append("")
    return "\n".join(lines)


def automaton_to_dot(automaton: AnyAutomaton, title: str = "LR automaton") -> str:
    """Return the Graphviz DOT source for *automaton*."""
    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"')

    lines = [
        "digraph LR {",
        '  rankdir=LR;',
        f'  labelloc="t"; label="{esc(title)}";',
        '  node [shape=box, fontname="Courier", fontsize=10];',
        '  edge [fontname="Courier", fontsize=10];',
        '  start [shape=point, width=0.12];',
        f'  start -> "I{automaton.start_state}";',
    ]
    for i, state in enumerate(automaton.states):
        body = "\\l".join(esc(s) for s in _state_lines(state))
        lines.append(f'  "I{i}" [label="I{i}\\n{body}\\l"];')
    # Merge parallel edges (same source/target) into one label.
    merged: dict[tuple[int, int], list[str]] = {}
    for (i, sym), j in automaton.transitions.items():
        merged.setdefault((i, j), []).append(sym)
    for (i, j), syms in merged.items():
        label = esc(", ".join(sorted(syms)))
        lines.append(f'  "I{i}" -> "I{j}" [label="{label}"];')
    lines.append("}")
    return "\n".join(lines)


# ── rendering ─────────────────────────────────────────────────────────────────
def _bfs_levels(automaton: AnyAutomaton) -> dict[int, int]:
    """Assign each state a column index = its BFS distance from the start."""
    from collections import deque

    level = {automaton.start_state: 0}
    queue = deque([automaton.start_state])
    adj: dict[int, list[int]] = {}
    for (i, _sym), j in automaton.transitions.items():
        adj.setdefault(i, []).append(j)
    while queue:
        u = queue.popleft()
        for v in adj.get(u, []):
            if v not in level:
                level[v] = level[u] + 1
                queue.append(v)
    # Any unreachable state (should not happen) goes in the last column.
    far = (max(level.values()) + 1) if level else 0
    for i in range(len(automaton.states)):
        level.setdefault(i, far)
    return level


def render_automaton(
    automaton: AnyAutomaton,
    output_path: str | Path,
    title: str = "Autómata LR(0)",
) -> dict[str, Path]:
    """Render *automaton* to ``.dot``, ``.txt`` and a matplotlib ``.png``.

    Returns a dict of the artifact paths that were written.  The PNG is best
    effort: if matplotlib fails for any reason the DOT/text files are still
    produced.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    png_path = out if out.suffix == ".png" else out.with_suffix(".png")
    dot_path = png_path.with_suffix(".dot")
    txt_path = png_path.with_suffix(".txt")

    dot_src = automaton_to_dot(automaton, title)
    dot_path.write_text(dot_src, encoding="utf-8")
    txt_path.write_text(automaton_to_text(automaton, title), encoding="utf-8")

    artifacts = {"dot": dot_path, "text": txt_path}

    # If the Graphviz binary is available, use it for a crisp render too.
    dot_bin = shutil.which("dot")
    if dot_bin:
        gv_png = png_path.with_suffix(".gv.png")
        try:
            subprocess.run(
                [dot_bin, "-Tpng", str(dot_path), "-o", str(gv_png)],
                check=True, capture_output=True,
            )
            artifacts["graphviz_png"] = gv_png
        except Exception:
            pass

    try:
        _render_png_matplotlib(automaton, png_path, title)
        artifacts["png"] = png_path
    except Exception as exc:  # pragma: no cover - visualization is best effort
        artifacts["png_error"] = exc  # type: ignore[assignment]

    return artifacts


def _render_png_matplotlib(automaton: AnyAutomaton, png_path: Path, title: str) -> None:
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "yapargen-mpl"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch

    levels = _bfs_levels(automaton)
    # Group states by column.
    columns: dict[int, list[int]] = {}
    for state, lvl in sorted(levels.items()):
        columns.setdefault(lvl, []).append(state)

    pos: dict[int, tuple[float, float]] = {}
    x_gap, y_gap = 4.2, 2.6
    max_rows = max((len(v) for v in columns.values()), default=1)
    for lvl, members in columns.items():
        n = len(members)
        # Vertically centre each column.
        offset = (max_rows - n) / 2.0
        for row, state in enumerate(members):
            pos[state] = (lvl * x_gap, -(row + offset) * y_gap)

    n_cols = (max(columns) + 1) if columns else 1
    fig_w = max(12, n_cols * 3.6)
    fig_h = max(7, max_rows * 2.3)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    ax.set_title(title, fontsize=14, fontweight="bold")

    # Draw transitions first (so boxes sit on top).
    merged: dict[tuple[int, int], list[str]] = {}
    for (i, sym), j in automaton.transitions.items():
        merged.setdefault((i, j), []).append(sym)

    for (i, j), syms in merged.items():
        label = ",".join(sorted(syms))
        x1, y1 = pos[i]
        x2, y2 = pos[j]
        if i == j:
            # Self-loop: small arc above the node.
            loop = FancyArrowPatch(
                (x1 - 0.6, y1 + 0.7), (x1 + 0.6, y1 + 0.7),
                connectionstyle="arc3,rad=1.8",
                arrowstyle="-|>", mutation_scale=12, color="#777", lw=1.0,
            )
            ax.add_patch(loop)
            ax.text(x1, y1 + 1.5, label, ha="center", va="bottom",
                    fontsize=8, color="#1a5276")
            continue
        rad = 0.12 if x2 >= x1 else -0.18
        arrow = FancyArrowPatch(
            (x1, y1), (x2, y2),
            connectionstyle=f"arc3,rad={rad}",
            arrowstyle="-|>", mutation_scale=13, color="#5d6d7e", lw=1.1,
            shrinkA=26, shrinkB=26,
        )
        ax.add_patch(arrow)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 + rad * 4
        ax.text(mx, my, label, ha="center", va="center", fontsize=8,
                color="#1a5276",
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))

    # Draw state boxes.
    for i, state in enumerate(automaton.states):
        x, y = pos[i]
        items = _state_lines(state)
        header = f"I{i}"
        text = header + "\n" + "\n".join(items)
        is_start = (i == automaton.start_state)
        ax.text(
            x, y, text, ha="center", va="center", fontsize=7.5,
            family="monospace",
            bbox=dict(
                boxstyle="round,pad=0.35",
                fc="#fdf6e3" if is_start else "#eaf2f8",
                ec="#b9770e" if is_start else "#2e86c1",
                lw=1.6,
            ),
        )

    xs = [p[0] for p in pos.values()] or [0]
    ys = [p[1] for p in pos.values()] or [0]
    ax.set_xlim(min(xs) - 3, max(xs) + 3)
    ax.set_ylim(min(ys) - 2.5, max(ys) + 3)
    fig.tight_layout()
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── parse trees ───────────────────────────────────────────────────────────────
def render_parse_tree(tree: object, output_path: str | Path) -> Path:
    """Render a parse tree to PNG.

    *tree* is any node exposing ``label: str`` and ``children: list`` (see
    :class:`yapargen.parse_runner.ParseTreeNode`).  Leaves have no children.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "yapargen-mpl"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # First pass: assign x positions to leaves left-to-right, depth as y.
    positions: dict[int, tuple[float, float]] = {}
    edges: list[tuple[int, int]] = []
    labels: dict[int, str] = {}
    counter = [0]
    leaf_x = [0.0]

    def label_of(node) -> str:
        return getattr(node, "label", None) or str(node)

    def children_of(node):
        return getattr(node, "children", None) or []

    def walk(node, depth: int) -> int:
        nid = counter[0]
        counter[0] += 1
        labels[nid] = label_of(node)
        kids = children_of(node)
        if not kids:
            x = leaf_x[0]
            leaf_x[0] += 1.0
            positions[nid] = (x, -depth)
            return nid
        child_ids = [walk(k, depth + 1) for k in kids]
        x = sum(positions[c][0] for c in child_ids) / len(child_ids)
        positions[nid] = (x, -depth)
        for c in child_ids:
            edges.append((nid, c))
        return nid

    walk(tree, 0)

    fig_w = max(6, leaf_x[0] * 1.1)
    depth = -min((y for _, y in positions.values()), default=0)
    fig_h = max(4, (depth + 1) * 1.2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    ax.set_title("Árbol de parseo", fontsize=13, fontweight="bold")

    for parent, child in edges:
        x1, y1 = positions[parent]
        x2, y2 = positions[child]
        ax.plot([x1, x2], [y1, y2], color="#85929e", lw=1.0, zorder=1)

    for nid, (x, y) in positions.items():
        is_leaf = nid not in {p for p, _ in edges}
        ax.text(
            x, y, labels[nid], ha="center", va="center", fontsize=9,
            family="monospace",
            bbox=dict(
                boxstyle="round,pad=0.3",
                fc="#d5f5e3" if is_leaf else "#eaf2f8",
                ec="#239b56" if is_leaf else "#2e86c1",
                lw=1.3,
            ),
            zorder=2,
        )

    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out
