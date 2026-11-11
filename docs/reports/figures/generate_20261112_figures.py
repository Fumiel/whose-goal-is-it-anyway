"""Figures for the 2026-11-12 progress report (docs/reports/進捗報告_大場_20261112.md).

Run from the repository root:
    .venv/bin/python docs/reports/figures/generate_20261112_figures.py
Numbers are read (read-only) from the immutable derived reports under
artifacts/processed/ and the small summary in results/. Nothing is typed in by
hand except the post-result informal local-wording check (Fig. 6), which has no
immutable derived output and is quoted from docs/experiment_logs/2026-11-12_position_sweep.md.
"""

# ruff: noqa: E501

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/reports/figures"


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


STEP1 = load("artifacts/processed/argrec672-v1-dg-004-selection-pointer/report.json")["report"]
STEP2 = load("results/2026-11-12_phase2_failure_decomposition_v1.json")
SWEEP = load("artifacts/processed/argrec672-v1-dg-006-position-sweep/report.json")["report"]
NOD = load("artifacts/processed/argrec672-v1-dg-008-position-sweep-nod/report.json")["report"]
COMP = load("artifacts/processed/argrec672-v1-dg-007-nod-comparison/report.json")["report"]

LAYERS = [0, 8, 16, 24, 32, 35]
POSITIONS = ["A1", "A2", "T", "S", "G"]
JUDGED_LAYERS = {
    "A1": {0, 8, 16, 24, 32},
    "A2": {0, 8, 16, 24, 32},
    "T": {0, 8, 16, 24, 32},
    "S": {8, 16, 24},
    "G": {8, 16, 24},
}

# Reference palette (dataviz skill references/palette.md, light mode), fixed order.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
SURFACE = "#ffffff"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

for name in ("NotoSansCJK-Regular.ttc", "NotoSansCJK-Bold.ttc"):
    p = Path("/usr/share/fonts/opentype/noto") / name
    if p.exists():
        font_manager.fontManager.addfont(str(p))
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


def save(fig, name: str) -> None:
    fig.savefig(OUT / f"20261112_{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def ref_line(ax, y, text, dy=0.0):
    ax.axhline(y, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
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


def box(ax, x, y, w, h, fill, title, body, title_size=9.5, body_size=7.8):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2", fc=fill, ec=AXIS, lw=0.8
        )
    )
    ax.text(
        x + w / 2,
        y + h - 3.2,
        title,
        ha="center",
        va="center",
        fontsize=title_size,
        color=INK,
        weight="bold",
    )
    ax.text(
        x + w / 2,
        y + (h - 5) / 2,
        body,
        ha="center",
        va="center",
        fontsize=body_size,
        color=INK2,
        linespacing=1.45,
    )


def arrow(ax, x0, y0, x1, y1):
    ax.annotate(
        "", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1)
    )


# Fig. 1: what the agent does and where an argument hijack happens.
def fig_agent() -> None:
    fig, ax = plt.subplots(figsize=(7.6, 2.7))
    ax.set_xlim(-1.5, 102.5)
    ax.set_ylim(0, 40)
    ax.axis("off")
    box(
        ax, 0, 12, 21, 24, "#eaf2fc", "利用者の依頼", "「請求書を読んで\n書かれた口座に\n支払って」"
    )
    box(ax, 25, 12, 22, 24, "#f3f2ee", "ツール①\nread_file", "書類（請求書）を\n読み込む")
    box(
        ax,
        51,
        12,
        22,
        24,
        "#fdf0e9",
        "書類の中身",
        "支払先口座 X\n＋（攻撃時のみ）\n「口座 Z へ変更」",
    )
    box(
        ax,
        77,
        12,
        24,
        24,
        "#e8f7f1",
        "ツール②\nsend_money",
        "recipient = ?\namount, subject,\ndate",
    )
    for x in (21.3, 47.3, 73.3):
        arrow(ax, x, 22, x + 3.4, 22)
    ax.text(
        50,
        5,
        "同一ツール引数乗っ取り：② は正しく send_money のまま、recipient だけが X → Z にすり替わる",
        ha="center",
        fontsize=8.2,
        color=INK,
    )
    ax.text(
        50,
        0.5,
        "本報告の実験（手順1〜3）は攻撃なし。まず「X と参照口座のどちらを recipient にするか」がいつ決まるかを調べた",
        ha="center",
        fontsize=7.6,
        color=INK2,
    )
    save(fig, "fig1_agent")


# Fig. 2: measurement positions on the token sequence, with the real (fictional) example.
def fig_positions() -> None:
    fig, ax = plt.subplots(figsize=(7.6, 3.3))
    ax.set_xlim(-1.5, 101.5)
    ax.set_ylim(0, 46)
    ax.axis("off")
    box(
        ax,
        0,
        18,
        37,
        26,
        "#eaf2fc",
        "① 書類を読む（prefix内）",
        "…Remit payment for this invoice\nto account GB86…364.  ← A1\nPaying account of the\naccount holder: GB41…452  ← A2",
        body_size=7.4,
    )
    box(
        ax,
        40,
        18,
        17,
        26,
        "#fdf0e9",
        "② 答え始める直前",
        "assistant 発話の\n先頭直前の\n最後のトークン\n← T",
        body_size=7.4,
    )
    box(
        ax,
        60,
        18,
        40,
        26,
        "#e8f7f1",
        "③ 送金呼出しを書く（固定の書き出し）",
        '<tool_call> {"name": "send_money",\n "arguments": {"recipient": "  ← S\nGB  ← G（次の数字で口座が分岐）\n8 / 4 …  ← D（正解の数字。報告のみ）',
        body_size=7.4,
    )
    arrow(ax, 37.5, 31, 39.5, 31)
    arrow(ax, 57.5, 31, 59.5, 31)
    ax.text(18.5, 13, "口座段階：H1「読んだ時に決まる」", ha="center", fontsize=8, color=INK)
    ax.text(48.5, 13, "生成前段階：H2", ha="center", fontsize=8, color=INK)
    ax.text(80, 13, "書き出し段階：H3「書く時に決まる」", ha="center", fontsize=8, color=INK)
    ax.annotate(
        "", xy=(99, 8), xytext=(1, 8), arrowprops=dict(arrowstyle="-|>", color=AXIS, lw=0.8)
    )
    ax.text(
        50,
        4.5,
        "モデルがトークンを処理する順番 →（各位置で36層の残差ベクトル［4096次元］を保存）",
        ha="center",
        fontsize=7.6,
        color=MUTED,
    )
    ax.text(
        50,
        0.5,
        "例は実データの条件 A1-1-rx_ref_y（架空の請求書）。A1・A2 は役割ではなく「文中で先／後に出る口座」で決める",
        ha="center",
        fontsize=7.3,
        color=MUTED,
    )
    save(fig, "fig2_positions")


# Fig. 3: step 2 failure decomposition by recipient rule.
def fig_step2() -> None:
    rules = [
        ("D1", "D1 資料1件"),
        ("D1M", "D1M 複数項目の資料"),
        ("D2", "D2 2資料の照合"),
        ("U0", "U0 指示（紛らわしい名0）"),
        ("UN", "UN 指示（同1）"),
        ("UI", "UI 指示（同2）"),
    ]
    segs = [
        ("strict_success", "厳格成功", SERIES[0]),
        ("recipient_error", "受取人の誤り", SERIES[1]),
        ("non_recipient_failure", "受取人以外の誤り", SERIES[2]),
    ]
    by = STEP2["actual"]["by_recipient_rule"]
    fig, ax = plt.subplots(figsize=(7.0, 3.0))
    for i, (code, _label) in enumerate(reversed(rules)):
        left = 0
        for key, slabel, color in segs:
            n = by[code]["primary"].get(key, 0)
            if n:
                ax.barh(
                    i,
                    n,
                    left=left,
                    color=color,
                    height=0.6,
                    edgecolor=SURFACE,
                    linewidth=2,
                    label=slabel if i == 0 else None,
                )
                ax.text(
                    left + n / 2,
                    i,
                    str(n),
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="#ffffff" if color == SERIES[0] else INK,
                    weight="bold",
                )
            left += n
        ax.text(left + 0.4, i, f"計{by[code]['runs']}", va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(range(len(rules)), [r[1] for r in reversed(rules)])
    ax.axhline(2.5, color=AXIS, linewidth=0.8)
    ax.text(27.5, 4.0, "資料由来\n46/48 成功", fontsize=7.5, color=INK2, va="center")
    ax.text(27.5, 1.0, "指示由来\n21/64 成功", fontsize=7.5, color=INK2, va="center")
    ax.set_xlim(0, 31)
    ax.set_xlabel("実走行の件数（攻撃なし、事前選択の112条件、各1回）")
    grid(ax, "x")
    h, lab = ax.get_legend_handles_labels()
    ax.legend(
        h, lab, ncol=3, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), fontsize=8
    )
    save(fig, "fig3_step2")


# Fig. 4: step 3 position x layer (D-in, dg-006), judged cells marked.
def fig_step3() -> None:
    names = {
        "A1": "A1 先の口座",
        "A2": "A2 後の口座",
        "T": "T 答える直前",
        "S": "S 書き出し末尾",
        "G": "G「GB」",
    }
    base = SWEEP["baseline_best_family_paired_accuracy"]
    fig, ax = plt.subplots(figsize=(7.0, 3.5))
    xs = list(range(len(LAYERS)))
    for color, p in zip(SERIES, POSITIONS, strict=True):
        ys = [SWEEP["cells"][f"{p}/layer{L}/logistic"]["paired_accuracy"] for L in LAYERS]
        ax.plot(xs, ys, color=color, linewidth=2, zorder=3, label=names[p])
        for x, L, y in zip(xs, LAYERS, ys, strict=True):
            judged = L in JUDGED_LAYERS[p]
            ax.scatter(
                [x],
                [y],
                s=34,
                zorder=4,
                color=color if judged else SURFACE,
                edgecolor=color if not judged else SURFACE,
                linewidth=1.6 if not judged else 1.0,
            )
    step1_t = STEP1["cells"]["layer24/logistic"]["paired_accuracy"]
    ax.scatter([3], [step1_t], marker="D", s=30, color=INK2, zorder=5)
    ax.annotate(
        f"手順1のT（層24）{step1_t:.3f}",
        xy=(3, step1_t),
        xytext=(3.25, 0.66),
        fontsize=7.3,
        color=INK2,
        arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7),
    )
    ax.set_xticks(xs, [f"層{L}" for L in LAYERS])
    ax.set_ylim(0.45, 1.04)
    ax.set_ylabel("対内正解率（120対）")
    grid(ax)
    ref_line(ax, base + 0.10, f"R1に必要\n{base + 0.10:.4f}")
    ref_line(ax, base, f"表層ベースライン\n最高 {base:.4f}（位置）")
    ref_line(ax, 0.5, "当て推量 0.50")
    ax.legend(
        ncol=5,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        fontsize=7.8,
        handlelength=1.6,
    )
    ax.text(
        0.0,
        -0.17,
        "塗りつぶし点＝判定に使う層、白抜き点＝報告のみの層。logistic probe、6ファミリー除外。",
        transform=ax.transAxes,
        fontsize=7.2,
        color=MUTED,
    )
    save(fig, "fig4_step3")


# Fig. 5: D-free vs D-in, best judged accuracy per position.
def best(report, p):
    cells = [c for c in report["cells"].values() if c.get("position") == p and c["judged"]]
    return max(c["paired_accuracy"] for c in cells)


def fig_nod() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.9), gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    n_cmp = COMP["comparisons"]["N"]
    for color, p in ((SERIES[0], "A1"), (SERIES[2], "T"), (SERIES[4], "G")):
        ax.plot(
            range(36),
            [n_cmp[f"{p}/model.layers.{L}"]["relative_l2"]["median"] * 100 for L in range(36)],
            color=color,
            linewidth=2,
            label=p,
        )
    ax.plot(
        range(36),
        [0] * 36,
        color=INK2,
        linewidth=1.2,
        linestyle=(0, (1, 2)),
        label="同一入力の再実行 R（全て差0）",
    )
    ax.set_xlim(0, 35)
    ax.set_xlabel("層")
    ax.set_ylabel("相対L2差の中央値（%）")
    ax.set_title("(a) Dの有無による残差の差（240条件）", fontsize=8.5, color=INK, loc="left")
    grid(ax)
    ax.legend(frameon=False, fontsize=7.2, loc="upper left")
    ax = axes[1]
    xs = range(len(POSITIONS))
    d_in = [best(SWEEP, p) for p in POSITIONS]
    d_out = [best(NOD, p) for p in POSITIONS]
    w = 0.36
    ax.bar(
        [x - w / 2 - 0.01 for x in xs],
        d_in,
        width=w,
        color=SERIES[0],
        label="D入り（手順3）",
        zorder=2,
    )
    ax.bar(
        [x + w / 2 + 0.01 for x in xs],
        d_out,
        width=w,
        color=SERIES[1],
        label="D除外（対照）",
        zorder=2,
    )
    for x, p in zip(xs, POSITIONS, strict=True):
        cls = NOD["position_classifications"][p]["class"]
        ax.text(x, 1.015, cls, ha="center", fontsize=7.8, color=INK)
    ax.set_xticks(list(xs), POSITIONS)
    ax.set_ylim(0.5, 1.06)
    ax.set_ylabel("判定セル中の最高対内正解率")
    ax.set_title("(b) 判定（上の文字）は両方で同じ", fontsize=8.5, color=INK, loc="left")
    grid(ax)
    ax.legend(frameon=False, fontsize=7.2, loc="lower center", bbox_to_anchor=(0.5, -0.38), ncol=2)
    fig.tight_layout()
    save(fig, "fig5_nod")


# Fig. 6: local wording explains A1.
def fig_local() -> None:
    items = [
        (
            "prefix全体の\nTF-IDF",
            SWEEP["baselines"]["family"]["tfidf"]["paired_accuracy"],
            SERIES[1],
        ),
        (
            "位置ベースライン\n（token位置3値）",
            SWEEP["baseline_best_family_paired_accuracy"],
            SERIES[1],
        ),
        ("口座の直前32文字\nのTF-IDF（事後）", 1.0, SERIES[1]),
        ("A1 残差\n層0", SWEEP["cells"]["A1/layer0/logistic"]["paired_accuracy"], SERIES[0]),
        ("A1 残差\n層16", SWEEP["cells"]["A1/layer16/logistic"]["paired_accuracy"], SERIES[0]),
    ]
    fig, ax = plt.subplots(figsize=(6.6, 2.7))
    for i, (_l, v, c) in enumerate(items):
        ax.bar(i, v, width=0.55, color=c, zorder=2)
        ax.text(i, v + 0.012, f"{v:.3f}", ha="center", va="bottom", fontsize=7.5, color=INK2)
    ax.set_xticks(range(len(items)), [i[0] for i in items], fontsize=7.6)
    ax.set_ylim(0.4, 1.09)
    ax.set_ylabel("対内正解率（A1、120対）")
    grid(ax)
    ref_line(ax, 0.5, "当て推量 0.50")
    ax.legend(
        [Patch(color=SERIES[1]), Patch(color=SERIES[0])],
        ["モデルを使わない文章・位置の比較法", "モデル内部（残差）の読み取り"],
        frameon=False,
        ncol=2,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        fontsize=8,
    )
    save(fig, "fig6_local")


if __name__ == "__main__":
    assert {p: SWEEP["position_classifications"][p]["class"] for p in POSITIONS} == {
        p: NOD["position_classifications"][p]["class"] for p in POSITIONS
    }
    fig_agent()
    fig_positions()
    fig_step2()
    fig_step3()
    fig_nod()
    fig_local()
    print("ok")
