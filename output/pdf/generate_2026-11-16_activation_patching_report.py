"""Plain-language report of the exploratory activation patching (2026-11-16).

Run from the repository root:
    .venv/bin/python output/pdf/generate_2026-11-16_activation_patching_report.py
Requires reportlab and matplotlib, plus the derived reports under artifacts/processed/
(read-only). Numbers are read from those reports, not typed in by hand, except for the
engineering facts of the capture run, which are taken from the dated experiment logs.
"""

# ruff: noqa: E501  # Japanese prose is kept as complete sentences.

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.cidfonts import UnicodeCIDFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "output/pdf/2026-11-16_activation_patching_report.pdf"

# ---------- data (read-only) ----------


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


PATCH = load("artifacts/processed/argrec672-v1-dg-009-patching/report.json")
NOD = load("artifacts/processed/argrec672-v1-dg-008-position-sweep-nod/report.json")["report"]
COLLECTION = load("data/manifests/2026-11-16_phase2_activation_patching_collection.json")

CELLS = PATCH["cells"]
HEALTH = PATCH["health"]
MAPPING = PATCH["hypothesis_mapping"]
LAYERS = [0, 4, 8, 12, 16, 20, 24, 28, 32, 35]
READ_LAYERS = [0, 8, 16, 24, 32, 35]
POSITIONS = ["T", "S", "G"]
NAMES = {"T": "T 答え始める直前", "S": "S 送金先の欄の書き出し", "G": "G 口座の書き始め「GB」"}


def cell(p: str, layer: int) -> dict:
    return CELLS[f"{p}/layer{layer}"]


g24 = cell("G", 24)
g20 = cell("G", 20)
s24 = cell("S", 24)
eligible = g24["eligible_pairs"]
excluded = len(g24["excluded_pairs"])
runs_per_cell = 2 * eligible
cross_ratio = MAPPING["evidence_cells"][0]["cross_to_matched_mean_ratio"]
readout = {
    p: {
        layer: NOD["cells"][f"{p}/layer{layer}/logistic"]["paired_accuracy"]
        for layer in READ_LAYERS
    }
    for p in POSITIONS
}
read_class = {p: NOD["position_classifications"][p]["class"] for p in POSITIONS}
strong_cells = [k for k, v in CELLS.items() if v["class"] == "P-STRONG"]
partial_cells = [k for k, v in CELLS.items() if v["class"] == "P-PARTIAL"]
disrupt_cells = [k for k, v in CELLS.items() if v["class"] == "P-DISRUPT"]
t_disrupt = [cell("T", layer)["disrupted_fraction"] for layer in (0, 4, 8, 12, 16)]

assert all(HEALTH.values()), "health checks must all pass for this report's wording"
assert MAPPING["mapping"] == "H3_consistent" and MAPPING["rule"] == 2
assert MAPPING["shallowest_strong_layers"] == {"G": 24, "S": None, "T": None}
assert not disrupt_cells
assert all(v["eligible_pairs"] == eligible for v in CELLS.values())
assert COLLECTION["condition_count"] == 240 and COLLECTION["retried_condition_count"] == 0

# ---------- figure styling (light, print) ----------

SURFACE = "#ffffff"
INK_HEX = "#0b0b0b"
INK2 = "#52514e"
MUTED_HEX = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
POS_COLOR = {"T": SERIES[2], "S": SERIES[3], "G": SERIES[0]}
for _font in ("NotoSansCJK-Regular.ttc", "NotoSansCJK-Bold.ttc"):
    _path = Path("/usr/share/fonts/opentype/noto") / _font
    if _path.exists():
        from matplotlib import font_manager

        font_manager.fontManager.addfont(str(_path))
plt.rcParams.update(
    {
        "font.family": "Noto Sans CJK JP",
        "font.size": 9,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
    }
)
TMP = Path(tempfile.mkdtemp(prefix="patching_figs_"))


def save(fig, name: str) -> Path:
    path = TMP / f"{name}.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def ref_line(ax, y, text, dy=0.0):
    ax.axhline(y, color=MUTED_HEX, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    ax.text(
        1.01,
        y + dy,
        text,
        transform=ax.get_yaxis_transform(),
        ha="left",
        va="center",
        color=INK2,
        fontsize=7.5,
        clip_on=False,
    )


def box(ax, x, y, w, h, fill, title, body="", title_size=9, body_size=7.6):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.5", fc=fill, ec=AXIS, lw=0.8
        )
    )
    if body:
        ax.text(
            x + w / 2,
            y + h * 0.70,
            title,
            ha="center",
            va="center",
            fontsize=title_size,
            color=INK_HEX,
            weight="bold",
        )
        ax.text(
            x + w / 2,
            y + h * 0.32,
            body,
            ha="center",
            va="center",
            fontsize=body_size,
            color=INK2,
            linespacing=1.35,
        )
    else:
        ax.text(
            x + w / 2,
            y + h / 2,
            title,
            ha="center",
            va="center",
            fontsize=title_size,
            color=INK_HEX,
            weight="bold",
        )


def arrow(ax, x0, y0, x1, y1, color=MUTED_HEX, lw=1.0, style="-|>"):
    ax.annotate(
        "", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle=style, color=color, lw=lw)
    )


def fig_timeline() -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.axis("off")
    specs = [
        (
            1,
            30,
            "依頼文・書類を読む",
            "2つの口座（先に書かれた口座・\n後に書かれた口座）が出てくる",
            "#eaf2fc",
        ),
        (35, 18, "答え始める直前", "T", "#fdf0e9"),
        (
            58,
            41,
            "送金ツールの呼び出しを書く",
            'S："recipient": " の末尾\nG：口座の最初の2文字「GB」\n（この次の数字で2つの口座が分かれる）',
            "#e8f7f1",
        ),
    ]
    for x, w, title, body, fill in specs:
        box(ax, x, 14, w, 21, fill, title, body)
    arrow(ax, 32, 24.5, 34.5, 24.5)
    arrow(ax, 54, 24.5, 57.5, 24.5)
    for x, t in [
        (16, "仮説H1\n読んだときに決まる"),
        (44, "仮説H2\n答え始める直前に決まる"),
        (78, "仮説H3\n書くときに決まる"),
    ]:
        ax.text(x, 6.5, t, ha="center", va="center", fontsize=7.8, color=INK_HEX, linespacing=1.3)
    arrow(ax, 1, 1.5, 99, 1.5, color=AXIS, lw=0.8)
    ax.text(
        50, -1.5, "AI が文章を処理する順番 →", ha="center", va="top", fontsize=7.5, color=MUTED_HEX
    )
    return save(fig, "timeline")


def fig_pair() -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 2.5))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 36)
    ax.axis("off")
    box(
        ax,
        1,
        20,
        47,
        14,
        "#eaf2fc",
        "条件 x",
        "「お支払い先：口座X」…「当社の口座：口座Y」\n→ AI は先に書かれた口座 X に送金する",
    )
    box(
        ax,
        52,
        20,
        47,
        14,
        "#fdf0e9",
        "条件 y（役割の文言だけを入れ替えた相手）",
        "「当社の口座：口座X」…「お支払い先：口座Y」\n→ AI は後に書かれた口座 Y に送金する",
    )
    ax.text(
        50,
        9,
        "口座 X・Y の文字列も、文中に出てくる順番も同じ。違うのは「どちらが支払い先か」を示す文言だけです。\n"
        "そのため、組の2条件で AI の答えが違えば、その違いは役割の文言から来ていると考えられます。",
        ha="center",
        va="center",
        fontsize=8,
        color=INK2,
        linespacing=1.5,
    )
    return save(fig, "pair")


def fig_patch() -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 52)
    ax.axis("off")

    def lane(y, label, fill, tokens, highlight):
        ax.text(1, y + 4, label, ha="left", va="center", fontsize=8.5, color=INK_HEX, weight="bold")
        for i, tok in enumerate(tokens):
            x = 18 + i * 13.5
            fc = "#ffffff" if i != highlight else fill
            ax.add_patch(
                FancyBboxPatch(
                    (x, y), 11, 8, boxstyle="round,pad=0.2,rounding_size=1", fc=fc, ec=AXIS, lw=0.8
                )
            )
            ax.text(x + 5.5, y + 4, tok, ha="center", va="center", fontsize=7.4, color=INK2)

    tokens = ["…書類…", "…依頼…", "T", "…", "S", "G"]
    lane(38, "移し替え元\n（条件 x）", "#cfe1f7", tokens, 5)
    lane(14, "移し替え先\n（条件 y）", "#cfe1f7", tokens, 5)
    arrow(ax, 18 + 5 * 13.5 + 5.5, 37.5, 18 + 5 * 13.5 + 5.5, 22.8, color=SERIES[0], lw=1.6)
    ax.text(
        18 + 5 * 13.5 - 1,
        30,
        "ある層の内部状態\n（4096個の数値）を\nそのまま上書き",
        ha="right",
        va="center",
        fontsize=7.4,
        color=SERIES[0],
        linespacing=1.3,
    )
    ax.text(
        57,
        6,
        "上書きしたあと、条件 y の AI が「口座 X と口座 Y のどちらを書きやすいか」がどれだけ条件 x の向きへ動くかを測ります。\n"
        "1回の実験で書き換えるのは「1つの位置 × 1つの層」だけです（図の例は G の位置）。",
        ha="center",
        va="center",
        fontsize=7.8,
        color=INK2,
        linespacing=1.5,
    )
    return save(fig, "patch")


def fig_gauge() -> Path:
    fig, ax = plt.subplots(figsize=(7.0, 1.6))
    ax.set_xlim(-0.25, 1.25)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.plot([0, 1], [0.55, 0.55], color=AXIS, lw=6, solid_capstyle="round", zorder=1)
    ax.plot([0, 0.5], [0.55, 0.55], color="#cfe1f7", lw=6, solid_capstyle="round", zorder=2)
    for v, t in [
        (0, "0\n変化なし\n（条件 y のまま）"),
        (0.5, "0.5\n半分まで移った"),
        (1, "1\n移し替え元（条件 x）と\n同じところまで移った"),
    ]:
        ax.plot([v], [0.55], "o", color=SERIES[0], ms=7, zorder=3)
        ax.text(v, 0.32, t, ha="center", va="top", fontsize=7.6, color=INK2, linespacing=1.3)
    ax.text(
        0.5,
        0.93,
        "正規化効果（NE）：送金先の好みが、どれだけ相手の向きへ移ったか",
        ha="center",
        va="center",
        fontsize=8.5,
        color=INK_HEX,
        weight="bold",
    )
    return save(fig, "gauge")


def fig_heatmap() -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    data = [[cell(p, layer)["mean"] for layer in LAYERS] for p in POSITIONS]
    im = ax.imshow(data, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    short = {"P-STRONG": "強", "P-PARTIAL": "部分", "P-NONE": "", "P-DISRUPT": "破壊"}
    for i, p in enumerate(POSITIONS):
        for j, layer in enumerate(LAYERS):
            c = cell(p, layer)
            v = c["mean"]
            color = "#ffffff" if v > 0.55 else INK_HEX
            label = f"{v:.2f}" if abs(v) >= 0.005 else "0.00"
            tag = short[c["class"]]
            ax.text(
                j,
                i - (0.13 if tag else 0),
                label,
                ha="center",
                va="center",
                fontsize=7.6,
                color=color,
                weight="bold" if tag == "強" else "normal",
            )
            if tag:
                ax.text(j, i + 0.25, tag, ha="center", va="center", fontsize=6.6, color=color)
    ax.set_xticks(range(len(LAYERS)), [f"層{layer}" for layer in LAYERS])
    ax.set_yticks(range(3), [NAMES[p] for p in POSITIONS])
    ax.axvline(6.5, color=SERIES[1], lw=1.2, linestyle=(0, (4, 2)))
    ax.text(
        6.5,
        -0.75,
        "← 中間層（層24以下）｜深い層 →",
        ha="center",
        va="bottom",
        fontsize=7.4,
        color=SERIES[1],
    )
    for spine in ax.spines.values():
        spine.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cb.ax.tick_params(labelsize=7)
    cb.set_label("正規化効果の平均", fontsize=7.5)
    return save(fig, "heatmap")


def fig_layers() -> Path:
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    xs = list(range(len(LAYERS)))
    ax.axvspan(-0.4, 6.5, color="#f6f5f1", zorder=0)
    ax.text(3, 1.07, "中間層（仮説との対応づけに使う範囲）", ha="center", fontsize=7.4, color=INK2)
    ax.text(8.2, 1.07, "深い層", ha="center", fontsize=7.4, color=INK2)
    for p in POSITIONS:
        means = [cell(p, layer)["mean"] for layer in LAYERS]
        lo = [cell(p, layer)["interval"][0] for layer in LAYERS]
        hi = [cell(p, layer)["interval"][1] for layer in LAYERS]
        ax.fill_between(xs, lo, hi, color=POS_COLOR[p], alpha=0.18, lw=0, zorder=2)
        ax.plot(
            xs,
            means,
            color=POS_COLOR[p],
            lw=1.7,
            marker="o",
            ms=4.2,
            mec=SURFACE,
            mew=1,
            label=NAMES[p],
            zorder=3,
        )
    ax.set_xticks(xs, [f"層{layer}" for layer in LAYERS])
    ax.set_ylim(-0.06, 1.12)
    ax.set_xlim(-0.4, 9.4)
    ax.set_ylabel("正規化効果の平均\n（帯は95%区間）")
    grid(ax)
    ref_line(ax, 0.5, "強い効果の基準\n平均 0.50")
    ax.annotate(
        f"層24：{g24['mean']:.2f}",
        xy=(6, g24["mean"]),
        xytext=(4.3, 0.78),
        fontsize=7.8,
        color=SERIES[0],
        arrowprops=dict(arrowstyle="-", color=SERIES[0], lw=0.8),
    )
    ax.legend(ncol=3, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.07), fontsize=7.8)
    return save(fig, "layers")


def fig_breakdown() -> Path:
    fam = g24["family_means"]
    items = (
        [
            ("x→y", g24["direction_means"]["ne_x_to_y"], SERIES[0]),
            ("y→x", g24["direction_means"]["ne_y_to_x"], SERIES[0]),
        ]
        + [(f"題材{k}", v, SERIES[2]) for k, v in sorted(fam.items())]
        + [
            ("依頼文で\n伝えた", g24["source_role_means"]["user"], SERIES[3]),
            ("書類で\n伝えた", g24["source_role_means"]["tool"], SERIES[3]),
        ]
    )
    fig, ax = plt.subplots(figsize=(6.8, 2.6))
    for i, (_, v, color) in enumerate(items):
        ax.bar(i, v, width=0.6, color=color, zorder=2)
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=7.2, color=INK2)
    ax.set_xticks(range(len(items)), [i[0] for i in items], fontsize=7.4)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("正規化効果の平均")
    grid(ax)
    ref_line(ax, 0.5, "平均の基準 0.50")
    ref_line(ax, 0.25, "方向ごとの基準 0.25")
    ax.legend(
        [Patch(color=SERIES[0]), Patch(color=SERIES[2]), Patch(color=SERIES[3])],
        ["移し替えの向き", "題材のまとまり（6種類）", "口座の伝え方"],
        frameon=False,
        ncol=3,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        fontsize=7.8,
    )
    return save(fig, "breakdown")


def fig_cross() -> Path:
    layers = [20, 24, 28, 32, 35]
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    width = 0.36
    for k, (key, label, color) in enumerate(
        [
            ("matched", "対の相手から移す", SERIES[0]),
            ("cross", "別の題材の文書から移す\n（同じ口座・同じ順番）", SERIES[1]),
        ]
    ):
        vals = [
            cell("G", layer)["mean"] if key == "matched" else cell("G", layer)["cross"]["mean"]
            for layer in layers
        ]
        xs = [i + (k - 0.5) * width for i in range(len(layers))]
        ax.bar(xs, vals, width=width * 0.95, color=color, label=label, zorder=2)
        for x, v in zip(xs, vals, strict=True):
            ax.text(x, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=7, color=INK2)
    ax.set_xticks(range(len(layers)), [f"G 層{layer}" for layer in layers])
    ax.set_ylim(0, 1.42)
    ax.set_ylabel("正規化効果の平均")
    grid(ax)
    ax.legend(frameon=False, ncol=2, loc="upper left", fontsize=7.6)
    return save(fig, "cross")


def fig_read_vs_move() -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), sharex=True)
    xs = list(range(len(READ_LAYERS)))
    for p in POSITIONS:
        axes[0].plot(
            xs,
            [readout[p][layer] for layer in READ_LAYERS],
            color=POS_COLOR[p],
            lw=1.6,
            marker="o",
            ms=4,
            mec=SURFACE,
            label=NAMES[p],
        )
        axes[1].plot(
            xs,
            [cell(p, layer)["mean"] for layer in READ_LAYERS],
            color=POS_COLOR[p],
            lw=1.6,
            marker="o",
            ms=4,
            mec=SURFACE,
        )
    axes[0].set_title("① 読める（以前の位置スイープ）", fontsize=8.6, color=INK_HEX, loc="left")
    axes[1].set_title("② 移せる（今回のパッチング）", fontsize=8.6, color=INK_HEX, loc="left")
    axes[0].set_ylabel("対内正解率\n（当て推量で0.50）")
    axes[1].set_ylabel("正規化効果の平均")
    axes[0].set_ylim(0.45, 1.03)
    axes[1].set_ylim(-0.05, 1.03)
    for ax in axes:
        ax.set_xticks(xs, [f"層{layer}" for layer in READ_LAYERS], fontsize=7.4)
        grid(ax)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        ncol=3,
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.06),
        fontsize=7.6,
    )
    fig.subplots_adjust(wspace=0.38)
    return save(fig, "read_vs_move")


FIGS = {
    "timeline": fig_timeline(),
    "pair": fig_pair(),
    "patch": fig_patch(),
    "gauge": fig_gauge(),
    "heatmap": fig_heatmap(),
    "layers": fig_layers(),
    "breakdown": fig_breakdown(),
    "cross": fig_cross(),
    "read_vs_move": fig_read_vs_move(),
}

# ---------- document ----------

pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
FONT = "HeiseiKakuGo-W5"
NAVY = colors.HexColor("#16324f")
BLUE = colors.HexColor("#206a9d")
PALE = colors.HexColor("#eef5fa")
WARM = colors.HexColor("#fdf3ec")
INK = colors.HexColor("#1c2933")
MUTED = colors.HexColor("#52616d")
LINE = colors.HexColor("#c6d8e6")


def style(name, size, leading, color=INK, after=0, **kw):
    return ParagraphStyle(
        name,
        fontName=FONT,
        fontSize=size,
        leading=leading,
        textColor=color,
        spaceAfter=after,
        wordWrap="CJK",
        **kw,
    )


TITLE = style("title", 19, 27, NAVY, 6)
SUB = style("sub", 9.5, 15, MUTED, 12)
H1 = style("h1", 13.5, 21, NAVY, 6, spaceBefore=12, keepWithNext=1)
H2 = style("h2", 11, 17, BLUE, 4, spaceBefore=8, keepWithNext=1)
BODY = style("body", 9.4, 16, INK, 7)
SMALL = style("small", 8, 12.5, MUTED, 4)
CAP = style("cap", 8, 12, MUTED, 8)
CELL = style("cell", 8.4, 13, INK)
CELLH = style("cellh", 8.4, 13, NAVY)
BOX = style("box", 9.4, 16, NAVY)


def P(text, st=BODY):
    return Paragraph(text, st)


def fig(key, caption, width=165):
    from reportlab.lib.utils import ImageReader

    path = FIGS[key]
    w, h = ImageReader(str(path)).getSize()
    img = Image(str(path), width=width * mm, height=width * mm * h / w)
    return KeepTogether([img, P(caption, CAP)])


def table(rows, widths, header=True, fill=PALE):
    data = [[P(c, CELLH if header and i == 0 else CELL) for c in row] for i, row in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], hAlign="LEFT")
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), fill))
    t.setStyle(TableStyle(cmds))
    return t


def boxed(text, fill=PALE):
    t = Table([[P(text, BOX)]], colWidths=[170 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


f2 = lambda v: f"{v:.2f}"  # noqa: E731
f3 = lambda v: f"{v:.3f}"  # noqa: E731
ci = lambda c: f"{c['interval'][0]:.3f}〜{c['interval'][1]:.3f}"  # noqa: E731

s = []
s += [
    P("AI の内部状態を入れ替えると、送金先は変わるか", TITLE),
    P("探索的パッチングの報告｜2026年11月16日｜開発用データによる探索的な結果", SUB),
    boxed(
        "<b>この資料の要点</b><br/>"
        "・書類を読んで送金する AI について、「送金先を先に書かれた口座にするか、後に書かれた口座にするか」という好みが、AI 内部のどこに置かれているかを、<b>内部状態を入れ替える実験（パッチング）</b>で調べました。<br/>"
        f"・送金先の口座を書き始める位置（G）では、第24層の状態を対の相手のものに入れ替えるだけで、好みが平均で約{g24['mean'] * 100:.0f}%相手の向きへ移りました。より深い層ほど移る割合は大きく、第35層ではほぼ100%でした。<br/>"
        "・一方、答え始める直前（T）と送金先の欄の書き出し（S）では、どの層を入れ替えても、好みはほとんど移りませんでした。以前の実験では、これらの位置からも好みを「読み取る」ことはできていました。<br/>"
        "・あらかじめ決めた規則では「仮説H3（送金先は書くときに決まる）に整合」となります。ただし、根拠は規則の範囲の境界にある1か所（Gの第24層）だけで、確認用の独立なデータでの検証もまだです。<br/>"
        "・手順が正しく動いていることを確かめる3つの検査（何も変えない入れ替え・必ず移るはずの入れ替え・再計算）は、すべてビット単位で一致しました。"
    ),
    Spacer(1, 6),
    P("1. この研究の背景", H1),
    P(
        "最近の AI は、メールや請求書などの書類を読み、送金などの「道具（ツール）」を代わりに使えるようになっています。ここで問題になるのが<b>間接プロンプトインジェクション</b>です。AI が読む書類に「振込先が変わりました」のような悪意ある指示を紛れ込ませ、AI の行動を乗っ取る攻撃です。特に見つけにくいのは、送金という操作は正しいまま、<b>送金先だけがすり替わる</b>場合です。"
    ),
    P(
        "この研究では、そうしたすり替えが AI の内部でどう起きるかを理解するため、まず<b>攻撃のない普通の場面で、AI がいつ・どこで「どちらの口座に送るか」を決めているのか</b>を調べています。使っている AI は公開モデルの Qwen3-8B（int8 で量子化）、作業の場面は研究用環境 AgentDojo の「銀行」場面です。"
    ),
    fig(
        "timeline",
        "図1　AI が文章を処理する順番と、今回調べた3つの位置（T・S・G）。3つの仮説は「送金先がどの段階で決まるか」についての考え方です。仮説H1（読んだとき）は、今回は対象にしていません。",
    ),
    P("1.1 これまでに分かっていたこと", H2),
    P(
        f"前回までの実験（位置スイープ）では、各位置の内部状態から「送金先は先に書かれた口座か、後に書かれた口座か」を簡単な判別器で当てられるかを調べました。その結果、S と G ではほぼ完全に（判定 {read_class['S']}・{read_class['G']}）、T でも偶然以上に（判定 {read_class['T']}）読み取れました。"
    ),
    P(
        "しかし、<b>「読み取れる」ことは「AI がその情報を使って送金先を決めている」ことを意味しません</b>。情報がたまたまそこに残っているだけかもしれないからです。そこで今回は、内部状態を実際に入れ替えて、AI の答えが変わるかを試しました。これがパッチングです。"
    ),
    P("2. パッチングのしくみ", H1),
    P("2.1 役割入れ替えの組", H2),
    P(
        "実験には、同じ2つの口座を使い、<b>どちらが送金先かを示す文言だけを入れ替えた</b>2つの条件を1組として使います（図2）。組の2条件では AI の送金先が逆になるはずなので、内部状態の違いには「どちらに送るか」の違いが含まれているはずです。"
    ),
    fig("pair", "図2　役割入れ替えの組（説明用の模式例で、実際の文面とは異なります）。"),
    P("2.2 内部状態の入れ替え", H2),
    P(
        "AI は文章を36段（層）の計算で処理し、各位置・各層に 4096 個の数値の並び（内部状態）を持っています。パッチングでは、組の一方（移し替え元）の、ある位置・ある層の内部状態を、もう一方（移し替え先）の同じ位置・同じ層に<b>丸ごと上書き</b>します（図3）。そのあと AI の計算を続け、送金先の好みがどれだけ移し替え元の向きへ動いたかを測ります。"
    ),
    fig(
        "patch",
        "図3　パッチングの模式図。移し替え元の G の位置の、ある層の内部状態を、移し替え先の同じ場所に上書きします。",
    ),
    P(
        "好みの強さは、「口座 X の残りの数字列」と「口座 Y の残りの数字列」を AI がどれだけ書きやすいかの差で表します。上書きによってこの差が、対の相手の値までどれだけ近づいたかを<b>正規化効果</b>と呼びます（図4）。"
    ),
    fig(
        "gauge",
        "図4　正規化効果の読み方。0 なら上書きしても変化なし、1 なら移し替え元と同じ好みになったことを意味します。両方向（x→y と y→x）の平均を組の値にします。",
    ),
    P("2.3 実験の設定", H2),
    table(
        [
            ["項目", "内容"],
            [
                "対象",
                f"開発用データの役割入れ替え 240 条件（120 組、40 系列、6 種類の題材）。正常な計算で好みの差が小さすぎる・向きが逆の {excluded} 組は、あらかじめ決めた規則で集計から除き、{eligible} 組を使いました",
            ],
            [
                "調べた場所",
                "3 つの位置（T・S・G）× 10 の層（0, 4, 8, …, 32, 35）＝ 30 か所。1 回の実験で書き換えるのは 1 か所だけです",
            ],
            [
                "移し替え元",
                "① 対の相手（主な実験）、② 自分自身（何も変わらないはずの対照）、③ 別の題材の文書で、同じ口座が同じ順番で出てくるもの（比較用）",
            ],
            ["実験の回数", "1 条件あたり 30 か所 × 3 種類 ＝ 90 回、全体で 21,600 回"],
            [
                "結果の位置づけ",
                "開発用データでの探索的な結果です。最終確認用のデータはまだ作っておらず、見てもいません",
            ],
        ],
        [30, 140],
    ),
    Spacer(1, 4),
    P("2.4 判定の規則（結果を見る前に固定）", H2),
    table(
        [
            ["判定", "条件", "意味"],
            [
                "強い効果",
                "正規化効果の平均 0.50 以上、95%区間の下限 0.25 以上、両方向とも平均 0.25 以上、6 題材中 5 以上で正、口座を依頼文で伝えた場合と書類で伝えた場合の両方で正",
                "その 1 か所の状態だけで、好みの大部分を移せる",
            ],
            ["部分的な効果", "95%区間の下限が 0 より大きい", "一部を移せる"],
            ["効果なし", "それ以外", "検出できるほどには移せない"],
            [
                "破壊",
                "上書き後、2 つの口座のどちらかを書く確率や、送金の書き出しを書く確率が半分未満に落ちる",
                "好みを移したのではなく、計算を壊した",
            ],
        ],
        [24, 96, 50],
    ),
    Spacer(1, 4),
    P(
        "仮説との対応づけでは、<b>第24層以下を「中間層」</b>とし、中間層で強い効果が出た位置だけを使うと決めていました。最も深い層（第28層以上）の上書きは、出力そのものを直接置き換えてしまうため、「どこで決まったか」の証拠としては弱いからです。T の中間層で強い効果があれば H2、T にはなく S か G の中間層にあれば H3 に「整合する」と記述します。"
    ),
    PageBreak(),
    P("3. 結果", H1),
    P("3.1 30 か所すべての結果", H2),
    fig(
        "heatmap",
        f"図5　30 か所それぞれの正規化効果の平均（{eligible} 組）。「強」は強い効果、「部分」は部分的な効果の判定です。点線の左側が中間層（第24層以下）です。",
    ),
    P(
        f"強い効果が出たのは <b>G の第24・28・32・35 層の 4 か所だけ</b>でした。部分的な効果は {len(partial_cells)} か所（S の第24・28 層、G の第20 層）で、破壊と判定された場所はありませんでした。T では、どの層を入れ替えても正規化効果はほぼ 0 でした。"
    ),
    fig(
        "layers",
        "図6　層ごとの正規化効果の平均と 95%区間（40 系列を単位としたブートストラップ）。G だけが第24層で急に上がり、深い層ほど 1 に近づきます。",
    ),
    P(
        f"G の第24層では平均 {f3(g24['mean'])}（95%区間 {ci(g24)}）で、強い効果の基準をすべて満たしました。そのすぐ手前の第20層は {f3(g20['mean'])} で、効果は小さいものでした。つまり、G の位置で好みを移せるようになるのは、第20層と第24層の間です。"
    ),
    P("3.2 G の第24層の内訳", H2),
    fig(
        "breakdown",
        "図7　G の第24層の正規化効果を、移し替えの向き・題材・口座の伝え方に分けたもの。どの分け方でも同じくらいの効果が出ており、一部の条件だけに偏った結果ではありません。",
    ),
    P(
        f"両方向、6 種類すべての題材、口座を依頼文で伝えた場合と書類で伝えた場合のどちらでも、効果は 0.64〜0.72 の範囲に収まりました。上書き後の答えの向き（どちらの口座を書きやすいか）が移し替え元と一致した割合は {g24['donor_sign_agreement_rate'] * 100:.0f}% でした。"
    ),
    P("3.3 「読める」と「移せる」は別のこと", H2),
    fig(
        "read_vs_move",
        "図8　左：以前の実験で、内部状態から送金先の向きを読み取れた度合い（D 除外の再解析）。右：今回、内部状態を入れ替えて好みを移せた度合い。同じ 6 つの層で比べています。",
    ),
    P(
        f"S の位置では、第16層以降で送金先の向きをほぼ完全に読み取れていました（第24層で {readout['S'][24]:.3f}）。それでも、その状態を入れ替えても好みはほとんど移りません（第24層で {f3(s24['mean'])}）。T も同じです。これは、<b>情報がそこにあっても、AI がその場所の情報を使って答えを決めているとは限らない</b>ことを示しています。たとえば、同じ情報が他の位置にも残っていれば、後の計算はそちらを読むので、1 か所を書き換えても答えは変わりません。"
    ),
    P("3.4 別の文書から移しても同じように移る", H2),
    fig(
        "cross",
        "図9　G の位置で、対の相手から移した場合と、別の題材の文書（同じ口座が同じ順番で出てくるもの）から移した場合の比較。",
    ),
    P(
        f"G の第24層では、別の題材の文書から移した場合の効果（{f3(g24['cross']['mean'])}）が、対の相手から移した場合（{f3(g24['mean'])}）の約 {cross_ratio:.1f} 倍でした。つまり、<b>対の相手と同じ文書である必要はなく</b>、同じ口座が同じ順番で出てくる文書であれば、好みは同じように移りました。ただし、この比較では「口座そのもの」と「口座が出てくる順番」の両方を揃えているため、AI が移しているのが「どの口座か」なのか「先か後か」なのかは区別できません。"
    ),
    P("3.5 手順が正しく動いていることの確認", H2),
    table(
        [
            ["確認したこと", "期待される結果", "結果"],
            [
                "自分自身の状態で上書きする（何も変えない）",
                "上書きしない計算と完全に同じになる",
                "全 240 条件・30 か所でビット単位まで一致",
            ],
            [
                "G の最終層を相手の状態で上書きする",
                "次の文字の予測が相手と完全に同じになる（必ず移るはずの対照）",
                "全 240 条件で全語彙の予測分布がビット単位で一致",
            ],
            ["上書きの前後で、上書きしない計算をやり直す", "やり直しても同じ値になる", "一致"],
        ],
        [55, 60, 55],
    ),
    Spacer(1, 4),
    P(
        f"T の浅い層では、上書きした実行の {min(t_disrupt) * 100:.0f}〜{max(t_disrupt) * 100:.0f}% で、送金の書き出しを書く確率が半分未満に下がりました。ただし、中央値はほぼ 0 で、どの場所も「破壊」とは判定されていません。こうした実行は、個別の成功例としては扱いません。",
        SMALL,
    ),
    P("4. この結果から言えること・言えないこと", H1),
    P("4.1 あらかじめ決めた規則による結論", H2),
    boxed(
        "<b>仮説H3（送金先は書くときに決まる）に整合</b><br/>"
        "答え始める直前（T）の中間層では強い効果に届かず、口座を書き始める位置（G）の中間層（第24層）では届きました。"
        "これは「答える直前の 1 か所の状態だけで送金先の好みを移せる」という H2 の予想とは合わず、「書くときに使われる状態で移せる」という H3 の予想と合います。",
        fill=WARM,
    ),
    Spacer(1, 6),
    P("4.2 注意すべき点", H2),
    table(
        [
            ["注意点", "説明"],
            [
                "根拠は境界の 1 か所だけ",
                "「中間層」は第24層以下と決めており、根拠になったのはその上限の第24層だけです。第20層の効果は小さく（0.02）、もし境界を 1 段浅く決めていれば「深い層だけで移せた」（対応づけなし）となっていました。規則は結果を見る前に固定したもので、結果を見てから変えることはしません",
            ],
            [
                "G は口座を書く直前",
                "G の次の文字で 2 つの口座が分かれます。そのため、G で移せたことは「書く直前の状態だけで移せた」ことにとどまり、送金先がそこで初めて決まったことは示しません",
            ],
            [
                "移せない ≠ 使われていない",
                "T・S で移せなかったのは、1 か所を入れ替えるだけでは足りなかったということです。そこに情報がないとか、AI がその情報を使っていないとは言えません",
            ],
            [
                "何が移ったかは分からない",
                "別の文書からでも移ったため、「どの口座か」と「先か後か」のどちらの情報が移ったのかは区別できません",
            ],
            [
                "探索的な結果",
                "開発用データ（40 系列）だけの結果で、30 か所の比較の補正もしていません。攻撃のある場面、量子化しない計算、新しい題材での確認はしていません",
            ],
        ],
        [40, 130],
    ),
    P("5. 実験の実施記録", H1),
    table(
        [
            ["項目", "内容"],
            [
                "取得",
                f"2026年11月15日 03:42 に開始し、11月16日 08:11 に完了（約 28.5 時間）。{COLLECTION['condition_count']} 条件すべてが 1 回目で完了し、技術的な失敗・再試行はありませんでした",
            ],
            [
                "資源",
                "1 条件あたり約 7 分。GPU メモリは最大約 9.5 GiB（上限 12 GiB）、パソコン側のメモリにも余裕がありました",
            ],
            [
                "記録の確認",
                "保存した 2,160 ファイルすべてについて、サイズとチェックサムが一致することを確認しました",
            ],
            [
                "時計のずれ",
                "WSL（Windows 上の Linux）の時計が実時間より最大約 7% 速く進み、記録上の所要時間が長めに出ていました。計算の速さ自体は一定で、結果には影響しません",
            ],
            ["解析", "取得とは別のコード版で、2026年11月16日に 1 回だけ実行しました（約 14 秒）"],
        ],
        [30, 140],
    ),
    P("6. 今後の予定", H1),
    table(
        [
            ["予定", "内容と目的"],
            [
                "① 局所文言ベースラインの正式記録",
                "口座のすぐ前の文言だけで送金先の向きを当てられるかを、正式な手順で記録します（以前は非公式の確認のみ）。GPU は使いません",
            ],
            [
                "② 結果の位置づけの整理",
                "H3 に整合という結論が境界の 1 か所に依存することを明記したうえで、論文での書き方を決めます",
            ],
            [
                "③ 独立な確認と執筆",
                "新しい題材での確認の可否を判断します。12 月は追加の探索ではなく、再現確認と論文執筆に充てる計画です",
            ],
        ],
        [55, 115],
    ),
    Spacer(1, 4),
    P(
        "パッチングは卒業研究の成立条件には含めていません。今回の結果は、「読み取れる位置」と「介入で移せる位置」が一致しないことを示す探索的な結果として扱います。"
    ),
    P("付録　用語と出典", H1),
    table(
        [
            ["用語", "意味"],
            [
                "内部状態・層",
                "AI は文章を 36 段（層）の計算で処理します。各層・各位置の 4096 個の数値の並びを内部状態と呼んでいます",
            ],
            [
                "パッチング",
                "ある条件の内部状態を別の条件の同じ場所に上書きし、出力が変わるかを見る介入実験",
            ],
            [
                "正規化効果",
                "上書きで送金先の好みがどれだけ相手の向きへ移ったか。0 で変化なし、1 で相手と同じ",
            ],
            [
                "対内正解率",
                "役割入れ替えの組のうち、内部状態から送金先の向きを正しく当てられた組の割合。当て推量で 0.50",
            ],
            ["95%区間", "40 系列を単位に 2,000 回の再標本化で求めた、平均のばらつきの目安"],
            ["int8 量子化", "メモリ節約のため、数値を粗く丸めて計算する方式"],
        ],
        [35, 135],
    ),
    Spacer(1, 6),
    P(
        "<b>出典（リポジトリ内）：</b>解析の記録 docs/experiment_logs/2026-11-16_activation_patching_analysis.md、取得の完了記録 docs/experiment_logs/2026-11-16_activation_patching_pt002_capture_completion.md、仕様 docs/phase2_activation_patching_spec.md、運用の判断 docs/decisions/2026-11-15_patching_capture_recovery_and_retry.md。"
        "図の数値は、パッチング解析の不変出力（artifacts/processed/argrec672-v1-dg-009-patching/report.json）と、位置スイープの D 除外再解析（argrec672-v1-dg-008）から、この資料の生成スクリプト（output/pdf/generate_2026-11-16_activation_patching_report.py）が直接読み込んでいます。要約は results/2026-11-16_phase2_activation_patching_v1.json にあります。",
        SMALL,
    ),
]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        20 * mm, 12 * mm, "探索的パッチングの報告｜2026年11月16日｜開発用データによる探索的な結果"
    )
    canvas.drawRightString(190 * mm, 12 * mm, f"{doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(
    str(DEST),
    pagesize=A4,
    leftMargin=20 * mm,
    rightMargin=20 * mm,
    topMargin=18 * mm,
    bottomMargin=20 * mm,
    title="AI の内部状態を入れ替えると、送金先は変わるか｜探索的パッチングの報告",
    author="Research project",
)
doc.build(s, onFirstPage=footer, onLaterPages=footer)
print(DEST)
