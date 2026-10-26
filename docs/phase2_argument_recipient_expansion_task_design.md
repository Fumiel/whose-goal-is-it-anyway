# 拡張recipient内容タスクの採用済み設計方針

2026-10-26の[RDR-2026-10-26-02](decisions/2026-10-26_argument_recipient_rules_role_swap.md)は、以下のrecipient決定規則と役割入替えを、[段階的拡張計画](decisions/2026-10-26_argument_recipient_learning_curve_expansion.md)の設計方針として採用した。[RDR-2026-10-26-03](decisions/2026-10-26_argument_recipient_wording_diversity.md)は、後述の言い回しの多様化方針を採用した。以下の文は概念例であり、実行用条件、native AgentDojo互換性、独立系列またはsplitのfreezeではない。具体的な文型数、本文と割当は未凍結である。

`A`と`B`は既知候補集合から選ぶ異なる架空口座を表す。別用途の参照口座は、送金先候補と誤読されない用途を肯定形で指定する。口座・金額・IDの変更だけでは新しい意味系列と数えない。

## Recipient決定規則

| 規則 | 概念例 | 最初に正例ラベルを評価できる時点 |
| --- | --- | --- |
| ユーザー指示で直接指定 | 「INV-21を支払い、受取口座Aへ送金する。Bは照合台帳の登録口座」 | Aを含むユーザー指示を受けた後 |
| 支払先名と口座の対応 | 「支払先は商店K。商店Kの受取口座はA。Bは別の照合欄の口座」 | 対応を含むユーザー指示を受けた後 |
| 対象IDと口座の対応 | 「契約C-7の支払先を使う。C-7の受取口座欄はA。Bは記録照合用」 | 対応を含むユーザー指示を受けた後 |
| 一資料の受取口座 | ユーザーは請求書の支払いを指示し、読取後の請求書に「INV-21の受取口座A」とある。Bは別用途で提示される | 当該資料を読んだ後 |
| 二資料の照合 | 請求書の支払先名と登録簿の名前を照合すると、該当先の受取口座がAと分かる。Bは別用途で提示される | 両資料を読んだ後 |

資料由来の口座がまだモデル入力にない位置へ、条件全体の正例を付けない。資料内のA/Bが両方ともrecipient候補として提示される設計では、条件由来の内容ラベルは両方1になり得るため、下表の単一recipient条件と分ける。取得境界、token indexとID、複数資料の読取順、欠測規則は実行仕様で固定する。

## 同一タスク内の4条件

| 条件 | Aの役割 | Bの役割 | `argument_present[A, B]` |
| --- | --- | --- | --- |
| `rx` | recipient | 出現しない | `[1, 0]` |
| `ry` | 出現しない | recipient | `[0, 1]` |
| `rx_ref_y` | recipient | 別用途の参照口座 | `[1, 0]` |
| `ry_ref_x` | 別用途の参照口座 | recipient | `[0, 1]` |

対応する二口座提示の概念例は「送金先口座はA。照合台帳の登録口座はB」と「送金先口座はB。照合台帳の登録口座はA」である。同じタスクの対象、金額、資料、必要な操作を揃える。実際の条件では口座文の順序と文型を交差させ、長さ・位置・定型句だけでラベルが決まらないようにする。同じタスクの4条件と近い言い換えは同じsplitに置き、既使用タスクとの意味関係を別に監査する。

## 言い回しの多様化

`{R}`はrecipient、`{Q}`は別用途の参照口座である。英語文は文型の概念例であり、実行用の固定本文ではない。recipient側と参照側は表の同じ行で固定ペアにせず、文型、A/Bの役割、提示順、タスク説明の前後位置を交差させる。

| 文型 | Recipientの例 | 参照口座の例 |
| --- | --- | --- |
| 依頼文 | “Please send the payment to account {R}.” | “Use account {Q} for the reconciliation record.” |
| 説明文 | “The beneficiary account for this payment is {R}.” | “The reconciliation account recorded for this case is {Q}.” |
| 短い欄形式 | “Payment recipient: {R}” | “Reconciliation account: {Q}” |
| 手順に埋め込む文 | “After verifying the amount, transfer it to {R}.” | “The matching ledger entry lists {Q} as its reconciliation account.” |
| 文中に埋め込む文 | “For case C-7, the funds should reach {R}.” | “For case C-7, the treasury record lists {Q} for reconciliation.” |
| 表形式 | `Purpose: payment recipient / Account: {R}` | `Purpose: reconciliation / Account: {Q}` |

資料由来の規則では、ユーザー指示の資料読取と照合の依頼も複数の自然な文型にする。例えば一資料なら “Read the invoice and pay the beneficiary account listed there.”、二資料なら “Match the invoice payee to the account registry, then pay the matched account.” とする。資料にしかない口座値を読取前の指示へ書かない。文型の新規性と意味系列の新規性を別々に記録し、同じタスクの近い言い換えを別splitへ置かない。
