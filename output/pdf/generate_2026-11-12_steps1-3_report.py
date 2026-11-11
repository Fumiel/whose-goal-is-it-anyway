"""Plain-language report of steps 1-3 (2026-11-12) for readers new to the project.

Run from the repository root:
    .venv/bin/python output/pdf/generate_2026-11-12_steps1-3_report.py
Requires reportlab and matplotlib, plus the derived reports under artifacts/processed/
(read-only). Numbers are read from those reports, not typed in by hand.
"""

# ruff: noqa: E501  # Japanese prose is kept as complete sentences.

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.cidfonts import UnicodeCIDFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "output/pdf/2026-11-12_steps1-3_report.pdf"
PROCESSED = ROOT / "artifacts/processed"

# ---------- data (read-only) ----------


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


STEP1 = load("artifacts/processed/argrec672-v1-dg-004-selection-pointer/report.json")["report"]
STEP2 = load("results/2026-11-12_phase2_failure_decomposition_v1.json")
SWEEP = load("artifacts/processed/argrec672-v1-dg-006-position-sweep/report.json")["report"]
NOD = load("artifacts/processed/argrec672-v1-dg-008-position-sweep-nod/report.json")["report"]
COMP = load("artifacts/processed/argrec672-v1-dg-007-nod-comparison/report.json")["report"]

LAYERS = [0, 8, 16, 24, 32, 35]
POSITIONS = ["A1", "A2", "T", "S", "G"]


def best_judged(report: dict, position: str) -> tuple[float, int]:
    cells = [c for c in report["cells"].values() if c.get("position") == position and c["judged"]]
    top = max(cells, key=lambda c: c["paired_accuracy"])
    return top["paired_accuracy"], top["layer"]


step1_layers = {
    layer: STEP1["cells"][f"layer{layer}/logistic"]["paired_accuracy"] for layer in LAYERS
}
step1_tfidf = STEP1["baselines"]["family"]["tfidf"]["paired_accuracy"]
step1_best = STEP1["cells"]["layer24/logistic"]
sweep_baseline = SWEEP["baseline_best_family_paired_accuracy"]
sweep_tfidf = SWEEP["baselines"]["family"]["tfidf"]["paired_accuracy"]
logit_g = SWEEP["same_position_logits"]["G"]["paired_accuracy"]
classes = {p: SWEEP["position_classifications"][p]["class"] for p in POSITIONS}
nod_classes = {p: NOD["position_classifications"][p]["class"] for p in POSITIONS}
sweep_best = {p: best_judged(SWEEP, p) for p in POSITIONS}
nod_best = {p: best_judged(NOD, p) for p in POSITIONS}
sweep_layers = {
    p: {layer: SWEEP["cells"][f"{p}/layer{layer}/logistic"]["paired_accuracy"] for layer in LAYERS}
    for p in POSITIONS
}
n_cmp = COMP["comparisons"]["N"]
d_effect = {
    p: [n_cmp[f"{p}/model.layers.{layer}"]["relative_l2"]["median"] for layer in range(36)]
    for p in ("A1", "T", "G")
}
d_effect_max = max(v["relative_l2"]["maximum"] for v in n_cmp.values())
actual = STEP2["actual"]
by_role = actual["by_source_role"]

assert classes == nod_classes, "classification differs between D-in and D-free analyses"

# ---------- figure styling (light, print) ----------

SURFACE = "#ffffff"
INK_HEX = "#0b0b0b"
INK2 = "#52514e"
MUTED_HEX = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
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
TMP = Path(tempfile.mkdtemp(prefix="steps13_figs_"))


def save(fig, name: str) -> Path:
    path = TMP / f"{name}.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def ref_line(ax, y, text, color=MUTED_HEX, xpos=None, va="center", dy=0.0):
    """Dashed reference line, labelled outside the plot on the right so it never covers data."""
    ax.axhline(y, color=color, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    ax.text(
        1.01,
        y + dy,
        text,
        transform=ax.get_yaxis_transform(),
        ha="left",
        va=va,
        color=INK2,
        fontsize=7.5,
        clip_on=False,
    )


def fig_timeline() -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.axis("off")
    boxes = [
        (1, "依頼文・書類を読む", "A1：先に書かれた口座\nA2：後に書かれた口座", "#eaf2fc"),
        (34, "答え始める直前", "T", "#fdf0e9"),
        (
            57,
            "送金の呼び出しを書く",
            'S："recipient": " の末尾\nG：GB（次の数字で口座が分かれる）\nD：最初の数字（対照のみ）',
            "#e8f7f1",
        ),
    ]
    widths = [30, 20, 42]
    for (x, title, body, fill), w in zip(boxes, widths, strict=True):
        ax.add_patch(
            FancyBboxPatch(
                (x, 14), w, 20, boxstyle="round,pad=0.4,rounding_size=1.5", fc=fill, ec=AXIS, lw=0.8
            )
        )
        ax.text(
            x + w / 2,
            30,
            title,
            ha="center",
            va="center",
            fontsize=9.5,
            color=INK_HEX,
            weight="bold",
        )
        ax.text(
            x + w / 2, 21, body, ha="center", va="center", fontsize=7.8, color=INK2, linespacing=1.4
        )
    for x in (31.5, 54.5):
        ax.annotate(
            "",
            xy=(x + 2, 24),
            xytext=(x, 24),
            arrowprops=dict(arrowstyle="-|>", color=MUTED_HEX, lw=1),
        )
    labels = [
        (16, "仮説H1\n読んだときに決まる"),
        (44, "仮説H2\n答え始める直前に決まる"),
        (78, "仮説H3\n書くときに決まる"),
    ]
    for x, t in labels:
        ax.text(x, 7, t, ha="center", va="center", fontsize=7.8, color=INK_HEX, linespacing=1.3)
    ax.annotate(
        "", xy=(99, 2), xytext=(1, 2), arrowprops=dict(arrowstyle="-|>", color=AXIS, lw=0.8)
    )
    ax.text(
        50,
        -1.5,
        "モデルが文章を処理する順番 →",
        ha="center",
        va="top",
        fontsize=7.5,
        color=MUTED_HEX,
    )
    return save(fig, "timeline")


def fig_step1() -> Path:
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    xs = range(len(LAYERS))
    vals = [step1_layers[layer] for layer in LAYERS]
    bars = ax.bar(xs, vals, width=0.55, color=SERIES[0], zorder=2)
    for b, v, layer in zip(bars, vals, LAYERS, strict=True):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v + 0.012,
            f"{v:.2f}",
            ha="center",
            va="bottom",
            fontsize=7.5,
            color=INK_HEX if layer == 24 else INK2,
            weight="bold" if layer == 24 else "normal",
        )
    ax.set_xticks(
        list(xs), [f"層{layer}" + ("\n(報告のみ)" if layer == 35 else "") for layer in LAYERS]
    )
    ax.set_ylim(0.4, 1.0)
    ax.set_ylabel("対内正解率")
    grid(ax)
    ref_line(ax, 0.80, "到達基準 0.80", dy=0.012)
    ref_line(ax, step1_tfidf, f"文章だけの比較方法 {step1_tfidf:.2f}", dy=-0.012)
    ref_line(ax, 0.5, "当て推量 0.50")
    return save(fig, "step1")


def fig_step2() -> Path:
    fig, ax = plt.subplots(figsize=(6.8, 1.9))
    rows = [
        ("依頼文で口座を伝えた\n（64件）", "user_instruction"),
        ("書類で口座を伝えた\n（48件）", "tool_output_document"),
    ]
    segs = [
        ("strict_success", "成功", SERIES[0]),
        ("recipient_error", "送金先の誤り", SERIES[1]),
        ("non_recipient_failure", "送金先以外の誤り", SERIES[2]),
    ]
    for i, (_, key) in enumerate(rows):
        left = 0
        for code, label, color in segs:
            n = by_role[key]["primary"].get(code, 0)
            if n:
                ax.barh(
                    i,
                    n,
                    left=left,
                    color=color,
                    height=0.5,
                    edgecolor=SURFACE,
                    linewidth=1.5,
                    label=label if i == 0 else None,
                )
                ax.text(
                    left + n / 2,
                    i,
                    str(n),
                    ha="center",
                    va="center",
                    color="#ffffff" if color != SERIES[2] else INK_HEX,
                    fontsize=8.5,
                    weight="bold",
                )
            left += n
    ax.set_yticks([0, 1], [r[0] for r in rows])
    ax.set_xlabel("走行の件数（攻撃なし）")
    grid(ax, "x")
    handles, labels = ax.get_legend_handles_labels()
    order = [labels.index(s[1]) for s in segs if s[1] in labels]
    ax.legend(
        [handles[i] for i in order],
        [labels[i] for i in order],
        ncol=3,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        fontsize=8,
    )
    return save(fig, "step2")


def fig_step3() -> Path:
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    names = {
        "A1": "A1 先の口座",
        "A2": "A2 後の口座",
        "T": "T 答える直前",
        "S": "S 書き出し",
        "G": "G「GB」",
    }
    xs = list(range(len(LAYERS)))
    for color, p in zip(SERIES, POSITIONS, strict=True):
        ys = [sweep_layers[p][layer] for layer in LAYERS]
        ax.plot(
            xs,
            ys,
            color=color,
            linewidth=1.6,
            marker="o",
            markersize=4.5,
            markeredgecolor=SURFACE,
            markeredgewidth=1,
            label=names[p],
            zorder=3,
        )
    ax.set_xticks(xs, [f"層{layer}" for layer in LAYERS])
    ax.set_ylim(0.45, 1.04)
    ax.set_ylabel("対内正解率")
    grid(ax)
    ref_line(ax, sweep_baseline + 0.10, f"R1に必要な値\n{sweep_baseline + 0.10:.4f}")
    ref_line(ax, sweep_baseline, f"表層ベースライン\n最高 {sweep_baseline:.4f}")
    ref_line(ax, 0.5, "当て推量 0.50")
    ax.legend(
        ncol=5,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        fontsize=7.8,
        handlelength=1.6,
    )
    return save(fig, "step3")


def fig_local() -> Path:
    items = [
        ("prefix全体の\nTF-IDF", sweep_tfidf, SERIES[1]),
        ("位置ベースライン\n（トークン位置）", sweep_baseline, SERIES[1]),
        ("口座の直前32文字の\nTF-IDF（事後確認）", 1.0, SERIES[1]),
        ("A1 内部状態\n層0", SWEEP["cells"]["A1/layer0/logistic"]["paired_accuracy"], SERIES[0]),
        ("A1 内部状態\n層16", SWEEP["cells"]["A1/layer16/logistic"]["paired_accuracy"], SERIES[0]),
    ]
    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    for i, (_label, v, color) in enumerate(items):
        ax.bar(i, v, width=0.55, color=color, zorder=2)
        ax.text(i, v + 0.012, f"{v:.3f}", ha="center", va="bottom", fontsize=7.5, color=INK2)
    ax.set_xticks(range(len(items)), [i[0] for i in items], fontsize=7.6)
    ax.set_ylim(0.4, 1.08)
    ax.set_ylabel("対内正解率（A1位置）")
    grid(ax)
    ref_line(ax, 0.5, "当て推量 0.50")
    from matplotlib.patches import Patch

    ax.legend(
        [Patch(color=SERIES[1]), Patch(color=SERIES[0])],
        ["文章だけを使う比較方法", "モデル内部の読み取り"],
        frameon=False,
        ncol=2,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        fontsize=8,
    )
    return save(fig, "local")


def fig_deffect() -> Path:
    fig, ax = plt.subplots(figsize=(6.8, 2.8))
    names = {"A1": "A1 先の口座", "T": "T 答える直前", "G": "G「GB」"}
    for color, p in zip((SERIES[0], SERIES[2], SERIES[4]), ("A1", "T", "G"), strict=True):
        ax.plot(
            range(36),
            [v * 100 for v in d_effect[p]],
            color=color,
            linewidth=1.6,
            label=names[p],
            zorder=3,
        )
    ax.plot(
        range(36),
        [0] * 36,
        color=INK2,
        linewidth=1.2,
        linestyle=(0, (1, 2)),
        label="同じ入力の再実行（全層で差0）",
        zorder=2,
    )
    ax.set_xlabel("層（0〜35）")
    ax.set_ylabel("Dの有無による差\n（中央値、%）")
    ax.set_xlim(0, 35)
    grid(ax)
    ax.legend(frameon=False, ncol=2, loc="upper left", fontsize=7.8)
    return save(fig, "deffect")


FIGS = {
    "timeline": fig_timeline(),
    "step1": fig_step1(),
    "step2": fig_step2(),
    "step3": fig_step3(),
    "local": fig_local(),
    "deffect": fig_deffect(),
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


s = []
pct = lambda v: f"{v * 100:.1f}%"  # noqa: E731

s += [
    P("AIは「誰に送金するか」をいつ決めているのか", TITLE),
    P(
        "手順1〜3の報告（手順3の対照実験を含む）｜2026年11月12日｜開発用データによる探索的な結果",
        SUB,
    ),
    boxed(
        "<b>この資料の要点</b><br/>"
        "・書類を読んで送金する AI が、2つの口座のどちらを送金先にするかを、AI の内部のどの時点で「読み取れる」かを調べました。<br/>"
        f"・答え始める直前の内部状態からは、送金先が「先に書かれた口座か、後に書かれた口座か」を120組中98組（{pct(step1_best['paired_accuracy'])}）で見分けられました（手順1）。<br/>"
        "・攻撃のない場面での AI の失敗は、送金先の誤りの大半が「もう一方の口座との取り違え」で、全体の失敗の多くは送金先以外（金額・件名・日付）の誤りでした（手順2）。<br/>"
        "・時点を細かく分けて調べると、口座を読んだ位置でも、送金先を書き始める位置でも、ほぼ完全に読み取れました。ただし、口座を読んだ位置での読み取りは、口座のすぐ前の文言だけで説明できてしまい、「読んだ時点で決めた」証拠にはなりませんでした（手順3）。<br/>"
        "・計算方式（int8量子化）による数値のずれも確かめ、結論が変わらないことを確認しました。次は、内部状態を入れ替えて行動が変わるかを試す実験（パッチング）を検討します。"
    ),
    Spacer(1, 6),
    P("1. なぜこの研究をしているのか", H1),
    P(
        "最近の AI は、メールや請求書などの書類を読み、送金やファイル操作などの「道具（ツール）」を代わりに使えるようになっています。ここで問題になるのが、<b>間接プロンプトインジェクション</b>と呼ばれる攻撃です。AI が読む書類の中に「振込先はこちらに変更されました」のような悪意ある指示を紛れ込ませ、AI の行動を乗っ取ろうとするものです。"
    ),
    P(
        "特に見つけにくいのは、<b>操作そのものは正しいまま、中身（引数）だけがすり替わる</b>場合です。たとえば「請求書の支払いをして」と頼まれた AI が、正しく送金の操作をしながら、送金先だけを攻撃者の口座にしてしまうケースです。外から見ると普通の送金に見えるため、気づきにくくなります。"
    ),
    P(
        "この研究では、こうしたすり替えが起きるとき、AI の内部で何が起きているかを調べます。その第一歩として、<b>攻撃のない普通の場面で、AI がいつ・どこで「どちらの口座を使うか」を決めているのか</b>を調べています。普段の決め方が分かれば、攻撃によってどこが変わるのかを比べられるからです。"
    ),
    P("1.1 実験の設定", H2),
    table(
        [
            ["項目", "内容"],
            [
                "AI モデル",
                "Qwen3-8B（公開されている 80 億パラメータのモデル。GPU メモリに収めるため int8 で量子化）。暫定の選択です",
            ],
            [
                "作業の場面",
                "AgentDojo という研究用環境の「銀行」場面（v1.2.2）。AI は書類を読み、送金ツール send_money を呼び出します",
            ],
            [
                "条件",
                "672 条件を用意し、学習用 480 条件を今回の分析に使いました。うち 240 条件（120 組）が下で説明する「役割入れ替えの組」です",
            ],
            [
                "結果の位置づけ",
                "すべて開発用データでの探索的な結果です。最終確認用のデータはまだ作っておらず、見てもいません",
            ],
        ],
        [32, 138],
    ),
    Spacer(1, 4),
    P("1.2 ここまでの経緯", H2),
    P(
        "以前の実験で、AI に送金の書き出しまで与えて続きを予測させると、学習用 480 条件中 469 条件で正しい送金先を最も有力と見なしました（探索的な確認）。つまり AI は送金先をかなり正しく選べています。ところが、AI が答え始める直前の内部状態から「どの口座番号が送金先か」を読み取る試みは、目標の精度（0.80）に届きませんでした（最高 0.613）。"
    ),
    P(
        "そこで問いを変えました。口座番号そのものではなく、<b>「どちらを使うか」という選択が、いつ決まっているのか</b>を調べることにしたのです。考えられる時点は次の3つです（図1）。"
    ),
    fig(
        "timeline",
        "図1　AI が文章を処理する順番と、調べた位置。A1・A2 は文中の口座、T は答え始める直前、S・G は送金の呼び出しを書く途中の位置です。D は正解の数字そのものなので、対照としてだけ使いました。",
    ),
    table(
        [
            ["仮説", "考え方"],
            ["H1 読んだときに決まる", "書類の口座を読んだ時点で、「これが送金先」という印が付く"],
            [
                "H2 答え始める直前に決まる",
                "口座番号そのものではなく、「先に書かれた方を使う」のような指し示しを持っている",
            ],
            ["H3 書くときに決まる", "送金先の欄を書き、口座が分かれる直前になって初めて決まる"],
        ],
        [50, 120],
    ),
    P("2. 調べ方の共通のしくみ", H1),
    P("2.1 役割入れ替えの組", H2),
    P(
        "同じ2つの口座を使い、<b>どちらが送金先かを示す文言だけを入れ替えた</b>2つの条件を1組にしました。口座の文字列も、文中で先に出てくる口座も同じで、変わるのは役割の文言だけです。こうすると、口座番号の違いではなく「役割」の違いだけを比べられます。"
    ),
    table(
        [
            ["", "先に書かれた口座（口座X）", "後に書かれた口座（口座Y）", "ラベル"],
            ["条件1", "「お支払い先：口座X」", "「当社の口座：口座Y」", "送金先は先＝1"],
            ["条件2", "「当社の口座：口座X」", "「お支払い先：口座Y」", "送金先は先＝0"],
        ],
        [18, 58, 58, 36],
    ),
    P("表は説明用の模式例で、実際の文面とは異なります。", SMALL),
    P("2.2 読み取りの評価方法", H2),
    P(
        "AI の内部状態（各層の数値の並び）から、簡単な判別器（<b>プローブ</b>）で「送金先は先か後か」を当てます。評価は<b>対内正解率</b>で行います。各組の2条件のうち、ラベル1の方を正しく高く判定できた組の割合です。当て推量なら 0.50 になります。"
    ),
    P(
        "学習と評価は、題材のまとまり（ファミリー、6種類）ごとに分けて行います。評価に使う題材は学習に使いません。また、<b>文章だけを使う比較方法（表層ベースライン）</b>も同じ方法で計算します。内部状態の読み取りがそれを十分上回らなければ、「文章の表面的な特徴を拾っただけ」と区別できないからです。"
    ),
    table(
        [
            ["判定", "条件（結果を見る前に固定）"],
            [
                "R1 有力な手がかり",
                "対内正解率 0.80 以上、偶然では説明できない（補正後 p &lt; 0.05）、表層ベースラインより 0.10 以上高い、6 題材中 5 以上で 0.5 超、依頼文由来・書類由来の両方で 0.5 超",
            ],
            ["R2 弱い信号", "偶然では説明できないが、R1 の条件をすべては満たさない"],
            ["R3 検出されない", "偶然と区別できない"],
            ["R4 手順の問題", "必ず読めるはずの情報（陽性対照）も読めない"],
        ],
        [35, 135],
    ),
    P("3. 手順1：答え始める直前の状態を、別の問いで調べ直す", H1),
    P(
        "<b>目的：</b>以前は「この口座番号は送金先か」と口座ごとに問いました。手順1では「送金先は先か後か」と問い直し、仮説 H2 の手がかりがあるかを調べました。新たに AI は動かさず、保存済みの記録を分析し直しました。"
    ),
    fig(
        "step1",
        f"図2　手順1の結果。答え始める直前（T）の内部状態から「送金先は先か後か」を当てた対内正解率（120組、題材ごとに分けた評価、ロジスティック回帰）。層24で {step1_best['paired_accuracy']:.3f}（95%区間 {step1_best['bootstrap_95']['paired_accuracy'][0]:.3f}〜{step1_best['bootstrap_95']['paired_accuracy'][1]:.3f}）。",
    ),
    P(
        f"<b>結果：</b>層24で 120 組中 98 組（{step1_best['paired_accuracy']:.3f}）を正しく見分け、文章だけの比較方法（{step1_tfidf:.3f}）を 0.10 以上上回りました。判定は <b>R1</b> です。"
    ),
    P(
        "<b>留保：</b>送金とは関係のない文の順番（口座のまとまりが依頼文の前にあるか後にあるか）も、同じ位置からほぼ完全に読み取れました（AUROC 0.97 以上）。そのため、AI は単に「文の並び」を覚えているだけかもしれません。この結果は、AI がその時点で送金先を選んだ証拠にはなりません。"
    ),
    P("4. 手順2：攻撃のない場面での AI の失敗を分類する", H1),
    P(
        "<b>目的：</b>攻撃がなくても起きる失敗と、攻撃による失敗を混同しないためです。攻撃のない実際の作業 112 件で、AI がどう失敗したかを分類しました。分類のルールは、個々の記録を見る前に1ページのメモで固定し、スクリプトで機械的に当てはめました。"
    ),
    fig(
        "step2",
        "図3　攻撃のない実際の作業112件の結果。口座を書類で伝えた場合はほぼ成功しましたが、依頼文で伝えた場合は64件中21件しか成功しませんでした。",
    ),
    table(
        [
            ["分かったこと", "件数"],
            ["送金先の誤り 14 件のうち、文中のもう一方の口座（参照口座）との取り違え", "13 件"],
            ["送金先の誤りのうち、AI が自分で調べた利用者自身の口座へ送金", "1 件"],
            ["口座番号の書き写し損ね（2文字以内の違い）", "0 件"],
            [
                "依頼文由来の「送金先以外の誤り」31 件のうち、金額・件名・日付のいずれかが違う",
                "31 件",
            ],
            ["そのうち、送金前に指定の書類を読んでいない", "13 件"],
        ],
        [140, 30],
    ),
    Spacer(1, 4),
    P(
        "<b>読み取れること：</b>攻撃がなくても、AI は一定の割合で「もう一方の口座」を選んでしまいます。攻撃実験では、この取り違えを差し引いて攻撃の効果を測る必要があります。また、依頼文で伝えた場合の失敗は、主に送金先以外の引数の誤りでした。攻撃の効果を調べるときは、送金先と、それ以外の引数を分けて扱う必要があります。"
    ),
    P(
        "<b>以前の予備実験の 31 件：</b>攻撃者の指示どおりに動いた 31 件は、すべて「同じツールのまま引数がすり替わった」ものでした。ただし、予備実験は攻撃者の操作と正規の操作が同じツールになるように作られていたため、これは設計上そうなるしかない結果です。「別のツールに乗っ取られるか」は、この予備実験からは分かりません。"
    ),
    P("5. 手順3：時点を分けて、どこで読み取れるかを調べる", H1),
    P(
        "<b>目的：</b>手順1は「答え始める直前」の1点しか見ていません。そこで、図1の5つの位置（A1・A2・T・S・G）で同じ問い（送金先は先か後か）を調べ、どの時点から読み取れるかを比べました。保存済みの入力に送金の書き出しを足して、AI に1回だけ通して記録しました（生成はさせていません）。判定の規則は結果を見る前に固定しました。"
    ),
    fig(
        "step3",
        "図4　位置ごと・層ごとの対内正解率（120組、題材ごとに分けた評価、ロジスティック回帰）。S と G の層0・32・35、全位置の層35は報告のみで、判定には使っていません。",
    ),
    table(
        [["位置", "判定", "最高の対内正解率（層）"]]
        + [[p, classes[p], f"{sweep_best[p][0]:.3f}（層{sweep_best[p][1]}）"] for p in POSITIONS],
        [40, 40, 90],
    ),
    P(
        f"表層ベースラインのうち最高だったのは、口座のトークン位置だけを使う「位置ベースライン」（{sweep_baseline:.4f}）でした。組の2条件で役割の文言の長さが違い、口座の位置が組の中でずれる（120組中113組）ためです。T は偶然では説明できない信号がありましたが、この基準を 0.10 上回れず <b>R2</b> になりました。G の位置では、AI 自身の出力（次の数字の予測）もすでに {logit_g:.3f} の精度で向きを決めています。",
        SMALL,
    ),
    P("5.1 固定した規則による結論と、その限界", H2),
    P(
        "あらかじめ決めた規則では、最初に R1 になったのが「口座を読んだ段階」（A1・A2）だったので、形式上は「H1（読んだときに決まる）に整合」となりました。しかし、結果を確認した後のレビューで、次の問題が見つかりました。"
    ),
    fig(
        "local",
        "図5　A1（先に書かれた口座）の位置での比較。口座の直前32文字だけを使う文章の比較方法でも 1.000 になりました（結果を見た後の非公式の確認）。内部状態は最初の層（層0）ですでに 0.94 に達しています。",
    ),
    P(
        "この課題では、「お支払い先：」のような役割の文言が口座のすぐ前に置かれています。口座の位置で読み取れたのは、<b>直前の文言の情報がその位置に乗っているだけ</b>と説明でき、「読んだ時点で送金先を決めた」こととは区別できません。仕様の表層ベースラインは文章全体を使うものだったため、この局所的な手がかりを捉えられませんでした。これは仕様の設計上の見落としです。そのため、<b>「H1 に整合」という結論は H1 の証拠として扱いません</b>。"
    ),
    P("5.2 計算方式による数値のずれの確認（D 除外の対照実験）", H2),
    P(
        "手順3では、入力の末尾に正解の数字（D）を含めたまま1回で計算していました。本来、AI はある位置を計算するとき、それより後ろの文字を見ません。しかし、今回の AI は int8 という粗い数値で計算する方式で、この方式は系列全体の値をまとめて扱います。そのため、末尾の正解の数字が前の位置の数値に影響し、答えが漏れている可能性がありました。"
    ),
    P(
        "そこで、(1) 同じ入力をもう一度通す（10条件）、(2) D を除いて通す（240条件）、の2つを追加で取得して比べました。判定の規則は、これも結果を見る前に固定しました。"
    ),
    fig(
        "deffect",
        f"図6　D の有無による内部状態の差（相対的な差の中央値、240条件）。浅い層ではほぼ差がなく、層24以降でほぼ全条件に数%の差が出ました（最大 {d_effect_max * 100:.0f}%）。同じ入力をもう一度通した場合は、すべての層・位置でビット単位まで完全に一致しました。",
    ),
    KeepTogether(
        table(
            [
                ["確認したこと", "結果"],
                ["同じ入力をもう一度通すと同じ値になるか", "完全に一致（10条件×6位置×36層）"],
                ["D を除くと数値は変わるか", "変わる。深い層で数%、最大で約21%"],
                ["その差から送金先の向きが読み取れるか", "有意には読めない（最高 0.625）"],
                [
                    "D を除いて解析し直すと、判定は変わるか",
                    "変わらない（5位置の判定、仮説への対応づけとも同じ）",
                ],
            ],
            [80, 90],
        )
    ),
    Spacer(1, 4),
    P(
        "<b>結論：</b>手順3の判定は、正解の数字の混入による誤りではありませんでした。一方で、この計算方式では、<b>後ろのトークンを1つ変えるだけで前の位置の数値が深い層で数%動く</b>ことが分かりました。これは次のパッチング実験の設計に大きく関わります。"
    ),
    P("6. ここまでで分かったこと・分からないこと", H1),
    table(
        [
            ["分かったこと", "まだ分からないこと"],
            [
                "答え始める直前・書き出しの途中では、「送金先は先か後か」が内部状態から読み取れる",
                "読み取れた情報を、AI が実際に送金先を選ぶために使っているか（因果関係）",
            ],
            [
                "攻撃のない場面での送金先の誤りは、ほぼ「もう一方の口座との取り違え」",
                "攻撃を受けたときに、同じ仕組みですり替えが起きるか",
            ],
            [
                "口座の位置での読み取りは、口座の直前の文言で説明できる",
                "この課題設計で H1・H2・H3 のどれが正しいか（今回の方法では区別できなかった）",
            ],
            [
                "同じ入力なら計算結果は完全に再現される。ただし後ろの入力を変えると前の位置の数値も動く",
                "その数値の動きが、どの量子化処理から生じているか",
            ],
            [
                "文の順番という一般的な情報も、どの位置でもほぼ完全に読める",
                "読み取れた信号が、送金先の選択に特有のものか、順序情報一般か",
            ],
        ],
        [85, 85],
    ),
    Spacer(1, 4),
    P(
        "<b>重要な注意：</b>「読み取れる」ことは「AI がその情報で決めた」ことを意味しません。ここまでの結果はすべて観察であり、学習用データの中での探索的な結果です。新しい題材での確認（独立な検証）はまだ行っていません。"
    ),
    P("7. 今後の展望", H1),
    table(
        [
            ["予定", "内容と目的"],
            [
                "① 探索的パッチング（2026年11月20日までに開始できる場合のみ）",
                "組の一方の内部状態を他方に移し替え、送金先の選択が変わるかを確かめます。読み取れた情報が実際に使われているかを、介入によって試す実験です。候補の位置は、局所的な文言で説明できてしまう口座の位置ではなく、S・G・T を中心にします。これらは入力の末尾からの位置が組の中で揃っているので、対応が取りやすい位置でもあります",
            ],
            [
                "② パッチングの設計上の注意",
                "int8 では、ある位置の数値を変えると他の位置の数値も動く可能性があります。そのため、「何も入れ替えない場合」（完全に再現されることは確認済み）と比べ、効果の大きさを慎重に解釈します。D を含まない入力（今回の対照実験と同じ形）を使います",
            ],
            [
                "③ 課題の作り直しの検討",
                "役割の文言が口座のすぐ隣にない課題（例：役割を別の場所で指定する課題）を用意できれば、H1 と「直前の文言の写し取り」を区別できる可能性があります",
            ],
            [
                "④ 攻撃条件との比較",
                "手順2の結果をふまえ、送金先とそれ以外の引数を分け、攻撃がない場合の取り違えを基準にして、攻撃による変化を測る設計を決めます",
            ],
            [
                "⑤ 独立な確認と執筆",
                "新しい題材での確認の可否を判断します。12月は追加の探索ではなく、再現確認と論文執筆に充てる計画です",
            ],
        ],
        [55, 115],
    ),
    Spacer(1, 4),
    P(
        "パッチングは卒業研究の成立条件には含めていません。パッチングを行わなくても、「読み取れる位置」と「その限界」を示す結果として研究はまとめられる構成にしています。"
    ),
    P("付録　用語と出典", H1),
    table(
        [
            ["用語", "意味"],
            [
                "内部状態・層",
                "AI は文章を 36 段（層）の計算で処理します。各層・各位置の数値の並び（4096 個）を内部状態と呼んでいます",
            ],
            [
                "プローブ",
                "内部状態から特定の情報を当てる簡単な判別器（ここではロジスティック回帰など）",
            ],
            ["対内正解率", "役割入れ替えの組のうち、正しく判定できた組の割合。当て推量で 0.50"],
            [
                "表層ベースライン",
                "AI の内部を使わず、文章やトークン位置だけで同じ問いを解く比較方法",
            ],
            ["int8 量子化", "メモリ節約のため、数値を粗く丸めて計算する方式"],
            ["パッチング", "ある条件の内部状態を別の条件に移し替え、出力が変わるかを見る介入実験"],
        ],
        [35, 135],
    ),
    Spacer(1, 6),
    P(
        "<b>出典（リポジトリ内）：</b>手順1 docs/experiment_logs/2026-11-06_argument_selection_pointer_diagnostic.md、手順2 docs/experiment_logs/2026-11-12_failure_decomposition.md、手順3 docs/experiment_logs/2026-11-12_position_sweep.md、D 除外対照 docs/experiment_logs/2026-11-12_position_sweep_nod_control.md。研究の方針転換は docs/decisions/2026-11-06_argument_selection_timing_course_correction.md。図の数値は artifacts/processed/ の派生出力（argrec672-v1-dg-004・006・007・008）と results/2026-11-12_phase2_failure_decomposition_v1.json から、この資料の生成スクリプト（output/pdf/generate_2026-11-12_steps1-3_report.py）が直接読み込んでいます。図5の「直前32文字」の値のみ、結果確認後の非公式の確認によるもので、不変の派生出力ではありません。",
        SMALL,
    ),
]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        20 * mm, 12 * mm, "手順1〜3の報告｜2026年11月12日｜開発用データによる探索的な結果"
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
    title="AIは「誰に送金するか」をいつ決めているのか｜手順1〜3の報告",
    author="Research project",
)
doc.build(s, onFirstPage=footer, onLaterPages=footer)
print(DEST)
