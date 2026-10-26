# Recipient内容probe用672条件のタスク本文草案（レビュー用）

**作成日: 2026-10-26。作成: Claude Code（claude-opus-5-5）、研究実施者の依頼による。状態: 研究実施者のレビュー前。** [RDR-2026-10-26-06](decisions/2026-10-26_argument_recipient_672_three_task_structure.md)で採用した3タスク構造・文型規模に従い、[改訂版v1](phase2_argument_recipient_672_review_draft_v1.md)の56系列候補を具体的な英語本文へ展開した。**条件宣言、関係graph、split、native evaluator、runtimeのfreezeではなく、モデル・native tool・tokenizerでは未検証である。**

**後続状況（2026-10-27）:** 研究実施者は現行本文をレビュー済みとして採用した。[RDR-2026-10-27-01](decisions/2026-10-27_argument_recipient_672_review_capture_and_staging.md)を参照。上記の作成時点の状態は履歴として残す。native全件対照と固定tokenizer全件検査は別の[環境記録](phase2_argument_recipient_672_environment.md)で報告する。実行用graph・split・runtimeのfreezeはまだない。

- 生成コード: [`argument_recipient_672_draft.py`](../src/goal_takeover/datasets/argument_recipient_672_draft.py)
- 生成物: [`phase2_argument_recipient_672_draft.json`](../data/templates/phase2_argument_recipient_672_draft.json)（手で編集せず、コードから再生成する）
- 検査: [`test_argument_recipient_672_draft.py`](../tests/test_argument_recipient_672_draft.py)

再生成: `PYTHONPATH=src python3 -m goal_takeover.datasets.argument_recipient_672_draft data/templates/phase2_argument_recipient_672_draft.json`

## 構成

| | 系列 | タスク | 条件 | ファミリー |
| --- | ---: | ---: | ---: | --- |
| 学習（B1～B5、各96条件） | 40（U25・D15） | 120 | 480 | A～F |
| 検証 | 16（U7・D9） | 48 | 192 | G～J |

各タスクの4条件（`rx`、`ry`、`rx_ref_y`、`ry_ref_x`）は`draft_pair_id`を共有する。候補口座は旧96条件の`v1`～`v4`と同じ値である。旧REC/DON 32条件の学習側算入はJSONの`reused_development_material`に記すだけで、本草案の条件には含めない。

## 決定規則ごとの入力構造

| 規則 | ユーザー指示 | 資料 | 口座の露出境界 |
| --- | --- | --- | --- |
| `U0` | 口座文（対象は「this invoice」等） | 1項目の請求情報（口座なし） | `user_to_assistant` |
| `UN` | 支払先名で対象を指定し、その名前に口座を対応 | 2項目（別支払先1件、どちらもopen、対象位置は入替え） | `user_to_assistant` |
| `UI` | 項目IDで対象を指定し、そのIDに口座を対応 | 同一支払先の3項目（全てopen、対象位置は入替え） | `user_to_assistant` |
| `D1` | 資料の読取と支払を依頼（口座なし） | 1項目＋口座文（詳細の前または後） | `first_tool_to_assistant` |
| `D1M` | 項目IDを指定（口座なし） | 3項目すべてopen。各項目の直下に固有の口座文（対象はrecipient文、他2項目は候補ではない架空IBAN）。対象の位置は系列ごとに変える | `first_tool_to_assistant` |
| `D2` | 請求書と登録簿の照合を依頼（口座なし） | 請求書（口座なし）＋登録簿（対象の支払先と別の支払先1件がそれぞれ固有の口座を持つ。別の口座は候補ではない架空IBAN。行の順序は変える） | `later_tool_to_assistant` |

参照口座文は、Uではユーザー指示の口座文の前後、`D1`では口座文ブロック内、`D1M`・`D2`では資料の先頭側または末尾に置く。どちらを先にするかは`reference_first_variant`で各タスク交互にし、二口座条件のrecipient先行が各splitでちょうど半数になる。末尾の定型文（日付・件名・1回だけ送金）は旧96条件と同じである。

## 文型

文型表はユーザー指示用（`IR`/`IV`、`IQ`/`QV`）と資料用（`DR`/`DV`、`DQ`/`DW`）に分け、各役割で学習16種類、検証専用8種類（`IV`、`QV`、`DV`、`DW`）を置いた。recipient文は依頼・説明・欄・手順・文中・表の6形式、参照文は4語義（`payer_account`、`reconciliation_ledger`、`transaction_history`、`receipt_archive`）である。参照文はすべて肯定形で、別の受取人の口座を表す文はない。

- 学習: recipient文16種を順に使い、参照文は組が重ならないようずらす（ユーザー指示用75タスク、資料用45タスクで組の重複なし）。
- 検証: 4層（`train_seen`、`recipient_novel`、`reference_novel`、`both_novel`）を順に割り当て、検証専用の全文型と4語義を各文脈で使う。

## 均衡（生成物で確認済み）

- 各バッチで候補口座ごとに正例24・参照例12、検証で正例48・参照例24。
- 各バッチは6ファミリーを含み、U5・D3系列。
- source別の候補均衡は完全ではない（学習のユーザー指示由来で正例72～78）。

## 検証コードが拒否する誤り

露出前の漏れ（Dの口座がユーザー指示にある、Uの口座が資料にある、`D2`の口座が請求書側にある）、ラベルと出現の不一致、口座の重複出現、正規callと金額・件名の不一致、資料に金額・件名がない、ファイルパスが指示に1回でない、否定・禁止文、学習側の検証専用文型使用、学習側の文型組の重複、`rx`と`ry`の口座以外の差、ファミリーが学習・検証に跨がる場合。

## レビューで見てほしい点と既知の限界

1. 題材・支払先・金額の自然さと、関係graphで近縁と判定すべき系列（v1 §5.2の候補edge）。
2. 参照文が送金先と誤読されないか（特に`IQ01`「I am paying from my own account」、`DQ05`、`IQ10`「Use account … for the reconciliation record」）。
3. 2026-10-26のレビュー指摘（[RDR-2026-10-26-07](decisions/2026-10-26_argument_recipient_672_d1m_d2_revision_and_rdr_reconciliation.md)）により、D1MとD2は項目ID・支払先名を照合しないと口座を選べない構造に修正した。UN・UI・D1M・D2の対象位置は入れ替えたが、位置と規則別の候補数は完全には均衡していない。
4. 他項目・他支払先の口座は候補ではない架空IBANで、ラベルには影響しない。その分、資料由来の正例は「指定項目の口座として提示された候補」を意味する。
5. `C3`（結婚祝い）など個人間の題材では、資料の「Amount」欄が実際の案内状より形式的である。
6. 主指標、取得位置、教師強制prefixの有無、関係graph、split、native evaluator登録、監査仕様、runtimeは未決定・未凍結である。旧`argument_readout_native`は資料が4条件共通である前提のため、条件ごとの資料に対応する拡張が必要である。
