"""Rebuild the plain-language three-step PDF with the completed Step 1 result.

Run with ``python output/pdf/generate_2026-11-06_next_steps_plain_explanation_step1_result.py``.
Requires reportlab. The original PDF is left unchanged.
"""

# ruff: noqa: E501  # Japanese prose is kept as complete sentences.

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BASE = Path(__file__).resolve().parent
DEST = BASE / "2026-11-06_next_steps_plain_explanation_step1_result.pdf"
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
FONT = "HeiseiKakuGo-W5"
NAVY = colors.HexColor("#16324f")
BLUE = colors.HexColor("#206a9d")
PALE = colors.HexColor("#eef5fa")
INK = colors.HexColor("#1c2933")
MUTED = colors.HexColor("#52616d")


def style(name, size, leading, color=INK, space_after=0, **kw):
    return ParagraphStyle(
        name,
        fontName=FONT,
        fontSize=size,
        leading=leading,
        textColor=color,
        wordWrap="CJK",
        spaceAfter=space_after,
        **kw,
    )


title = style("title", 20, 29, NAVY, 8)
subtitle = style("subtitle", 10, 16, MUTED, 15)
h1 = style("h1", 13, 21, NAVY, 7, spaceBefore=13)
h2 = style("h2", 11, 18, BLUE, 5, spaceBefore=8)
body = style("body", 9.5, 16, INK, 8)
small = style("small", 8.1, 13, MUTED, 5)
table_head = style("tablehead", 9.3, 15, NAVY)
table_body = style("tablebody", 9.1, 15, INK)
lead = style("lead", 10.2, 17, NAVY)


def P(text, sty=body):
    return Paragraph(text, sty)


def section(label, text):
    return [P(label, h1), P(text)]


story = []
story += [
    P("AIは「誰に送金するか」を、いつ決めているのか", title),
    P("3つの手順と、終わった手順1の結果｜2026年11月6日更新", subtitle),
    P(
        "<b>今回分かったこと：</b>AIが答え始める直前の記録から、「送金先が文章の先に書かれた口座か、後に書かれた口座か」を、120組中98組で見分けられました。ただし、文章の順番そのものを覚えているだけかもしれません。AIがその時点で送金先を決めた証拠には、まだなりません。",
        lead,
    ),
    Spacer(1, 7),
    HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c6d8e6")),
]
story += section(
    "背景：何を調べている研究か",
    "最近のAIは書類を読み、送金などの操作も代行できます。問題になるのは、読ませる書類に「振込先はこちらに変更」といった悪意のある指示を紛れ込ませる攻撃です。送金という操作は正しいまま、送金先だけがすり替わることがあります。この研究では、そのときAIの内部で何が起きるかを調べます。",
)
story += [
    P("これまでに分かったこと", h1),
    P(
        "攻撃のない場面では、AIは送金先をかなり区別できています。こちらで送金の書き出しまで与えて続きを予測させると、学習用の480件中469件で正しい送金先を最も有力と見なしました。一方、答え始める直前の内部の様子から口座番号そのものを読み取る試みは、目標の精度に届きませんでした。そこで、番号ではなく「先か後か」という別の問いで、同じ記録を調べ直しました。",
    ),
    P("考えられる3つの可能性", h1),
]
possibilities = [
    [
        P("A　読んだとき", table_head),
        P("書類を読みながら、口座番号に「これが送金先」と付箋を貼る。", table_body),
    ],
    [
        P("B　答え始める直前", table_head),
        P("番号そのものではなく、「先に書かれた方を使う」と覚えている。", table_body),
    ],
    [
        P("C　書くとき", table_head),
        P("送金先の欄を書くときに、初めてどちらかを決める。", table_body),
    ],
]
t = Table(possibilities, colWidths=[135, 345], hAlign="LEFT")
t.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), PALE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 1), 0.5, colors.white),
            ("LEFTPADDING", (0, 0), (-1, -1), 11),
            ("RIGHTPADDING", (0, 0), (-1, -1), 11),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]
    )
)
story += [
    t,
    Spacer(1, 9),
    P(
        "手順1はBにつながる手がかりを調べました。手順2で実際の失敗を整理し、手順3でA・B・Cの時点を調べます。",
        small,
    ),
    PageBreak(),
]

story += [P("手順1　同じ記録を、別の問いで調べ直す", title)]
story += [
    P("実施済み｜新たにAIを動かさず、既存の学習用記録を分析", subtitle),
    P("何を調べたか", h2),
    P(
        "前回は「この口座番号は送金先か」と、番号ごとに問いました。今回は「送金先は先に書かれた方か、後に書かれた方か」を問いました。同じ2つの口座を使い、役割を示す文章だけが入れ替わる組を比べています。"
    ),
    P("結果", h2),
    P(
        "<b>120組中98組で正しく見分けました（約82％）。</b>文章だけを使う比較方法は120組中85組（約71％）でした。6種類の題材を一つずつ学習から外して調べた全体の結果です。あらかじめ決めた基準では、次に確かめる価値のある手がかりに当たります。"
    ),
    P("結果から言えること・言えないこと", h2),
    P(
        "答え始める直前の内部には、送金先が文章の先か後かを見分ける手がかりがありました。調べる道具が、確実に分かるはずの情報を読めることも確認できました。"
    ),
    P(
        "ただし、送金とは関係のない文章の順番も強く読み取れました。今回の手がかりは、単に文の並びを覚えているだけかもしれません。実際にどの口座へ送金するかを決めたことや、攻撃に対する反応を示した結果ではありません。まだ使っていない別の題材で確かめる必要があります。"
    ),
    P("手順2　AIの失敗の中身を分類する", title),
    P("これから実施｜内部の様子ではなく、実際の行動を調べる", subtitle),
    P("何をするか", h2),
    P(
        "攻撃のない実際の作業で、別の口座へ送金した14件の中身を調べます。候補の取り違えか、番号の書き写し損ねかを分けます。また、依頼文で口座を伝えた64件中21件しか作業全体に成功しなかった理由を、送金先の誤りと、それ以外の誤りに分けます。以前の予備実験で攻撃者の指示どおりに動いた31件も、送金先だけのすり替えか、別の操作への変更かを区別します。"
    ),
    P("なぜ必要か", h2),
    P(
        "攻撃がなくても起こる失敗と、攻撃による失敗を混同しないためです。今後の攻撃実験で何と何を比べるべきかを決める材料になります。",
        body,
    ),
    PageBreak(),
]

story += [
    P("手順3　いくつもの時点で、内部の様子を記録し直す", title),
    P("これから実施｜手順2の結果を踏まえて、別の実験として設計", subtitle),
]
story += [
    P("何をするか", h2),
    P(
        "書類の口座番号を読んでいるとき、AIが答え始める直前、送金先の欄を書き始めるとき、そして口座ごとに違う数字を書くときを分けて調べます。今回の口座はどれも同じ「GB」で始まるので、最初の2文字だけではどちらを選んだか分かりません。同じ2つの口座を保ち、役割を示す文章だけを入れ替えた組を比べます。"
    ),
    P("なぜ必要か", h2),
    P(
        "手順1は答え始める直前の一時点だけを調べました。そこで手がかりが見えても、いつ作られたか、送金先を書くときにも使われるかは分かりません。複数の時点を比べて、3つの可能性のどれに近いかを調べます。"
    ),
    P("何が分かるか、どこに限界があるか", h2),
    P(
        "送金先に関する手がかりを、どの時点で読み取れるかが分かります。ただし、読み取れることと、それが行動の原因であることは別です。送金先を書く直前には次の文字を予測しているため、読み取りやすくなる可能性もあります。その影響も比べます。"
    ),
    P("3つの手順のあとに残ること", h1),
    P(
        "この3つだけで、書類中の悪意ある指示が送金先を変える仕組みまでは分かりません。手順1と3は主に攻撃のない場面を調べるためです。手順2で失敗の中身を確かめたうえで、攻撃を受けたときの比較を設計します。"
    ),
    P(
        "内部の状態を実際に入れ替え、行動が変わるかを試す追加実験は、2026年11月20日までに始められる場合に限って試行的に行います。卒業論文の主な結論や題目を見直すかは、その後の結果を見て判断します。"
    ),
    Spacer(1, 10),
    HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#c6d8e6")),
    Spacer(1, 7),
    P(
        "数値は開発中の試行結果で、最終評価用データによる確認ではありません。480件中469件は学習用データでの確認、112件の作業結果は自動判定とAIによる確認で、人による全件確認ではありません。手順1の98/120組も既存の学習用記録を使った結果です。",
        small,
    ),
]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(43, 34, "2026年11月6日更新｜手順1の結果を反映")
    canvas.drawRightString(A4[0] - 43, 34, str(doc.page))
    canvas.restoreState()


doc = SimpleDocTemplate(
    str(DEST),
    pagesize=A4,
    leftMargin=43,
    rightMargin=43,
    topMargin=42,
    bottomMargin=54,
    title="AIは「誰に送金するか」を、いつ決めているのか｜手順1の結果",
    author="Research project",
)
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(DEST)
