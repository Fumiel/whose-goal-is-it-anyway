# 96条件案と既使用系列の関係graph予備監査

作成日: 2026-10-22。対象は[96条件設計草案](phase2_argument_readout_96_condition_draft.md)の**タスク系列レベルの案**であり、実行用のcondition graph・split manifestではない。具体的な本文・資料を含む現在の草案を照合したが、正式な条件ID・意味IDとmodel-free対照を固定した時点で全条件と既存条件のedgeを再計算する。モデル結果に基づく系列選別はしていない。

[タスク単位の予備edge一覧](../data/splits/phase2_argument_readout_96_draft.graph.json)では、同一タスクのA～Dを一ノードへ畳み、既存train成分への近縁edgeを明示した。現時点のedgeではtrain側1成分とvalidation候補2成分である。REC-3は既存家賃調整との近さを避け、料金改定から会員区分による会費選択へ改めた。DON-3の助成枠とEXP-4の経費承認は、承認という一般手順を共有し、2026-10-22の改訂後はどちらも数値条件で複数項目から1件を選ぶ形になったが、正規目的・対象・資料が異なるため、この草案ではedgeを張らない。正式仕様時に再確認する。

## 照合した既存記録

- [既存Bankingタスク候補表](banking_task_candidates_2026-10-01.md): `bill_payment`（user task 0/10）、`friend_refund`（3/4）、`rent_adjustment`（2/9/12）、`subscription_payment`（5/6）、`device_purchase_adjustment`（11）などの意味系列と既使用・評価器保留を確認した。
- [pilot条件テンプレート](../data/templates/banking_pilot_v1.json): 請求書支払い、友人返金、家賃調整がpilotの標本にあり、請求書と返金で`send_money`の攻撃目標`send_to_attacker`を共有することを確認した。pilotの90条件は同一連結成分で`pilot_only`である。
- [二文書v2 graph](../data/splits/phase2_two_document_paths_v2.graph.json): 発注書・承認先一覧の送金系列はpilotの請求書系列へ保守的に接続済みで、train側の`component_2db488e29b6eaafa`に属する。
- [分割規則](experimental_protocol.md): 同じ意味テンプレート、攻撃目的・形式・テンプレート、対応pair、近い言い換え、反復と明らかな近縁タスクのedgeを維持し、連結成分単位で分割する。

## 系列レベルのedge判定

| 新系列 | 既存・新系列との関係 | 暫定判定 | 配分への影響 |
| --- | --- | --- | --- |
| INV 請求書 | pilot `bill_payment`および二文書v2の支払資料照合と近い。特にINV-4は二文書照合に近い。 | train側既存成分へのedgeを要する | trainに置く。未知系列validationとは数えない。 |
| REF 個人間返金 | pilot `friend_refund`と正規目的を共有する。 | train側既存成分へのedgeを要する | trainに置く。 |
| PRD 商品代金 | PRD-4の注文・納品照合は二文書v2の発注書・承認資料照合と近い。 | train側へ保守的なedgeを置く候補 | trainに置く。 |
| EXP 費用精算 | REF-1/2/4の立替精算・差額計算とEXP-1/2/3が近い。 | REFへのedgeを置く候補 | 当初のvalidation案を取り下げ、trainへ移す。 |
| REC 定期支払い | 既存の`subscription_payment`は履歴を使う差額送金・予定送金作成、`rent_adjustment`は予定取引更新であり、今回案の当期単発送金とは操作と資料が異なる。REC-3は会員区分の選択であり料金改定ではない。 | 具体的な共有目的・資料・操作によるpilotへのedgeは現草案で確認されない | validation候補に移す。正式仕様で独立性を再判定する。 |
| DON 寄付・資金移動 | 既存の請求書・返金・家賃・発注書系列とは、承認目的と対象決定規則が異なる。 | 現時点で具体的なedgeなし。資金配分とEXPの承認精算が近くならないよう本文を確認する | validation候補を維持する。 |

今回の96条件には攻撃テキストを入れないため、既存の`send_to_attacker`や`direct_payment_override_in_purchase_order`を新条件の`attack_goal_id` / `attack_style_id`として転記しない。攻撃関連IDはnullとする。同じ4つの候補口座と`send_money.recipient`を共有することだけではedgeの十分な理由にならない。一方、同じ「送金」でも具体的な正規目的・選択規則・資料が近ければedgeを記録する。後続IPIセットで攻撃目的・形式を共有すれば、現在分かれて見える系列が結合する可能性がある。

## 現時点の結論と再確認条件

提案の6テーマは、上表の配分修正をしたうえで**具体的なタスク草案の作成には進める**。4系列train・2系列validationという数は、独立した4対2の連結成分数ではない。少なくともINV/REFと既存pilot・v2はtrain側でつながる。REC/DONは暫定validation候補であり、正式な24タスク・96条件の正規目的、資料、文面、`task_template_id`、`pair_id`を見て再判定する。いずれかがpilotまたはtrainへつながる場合、その系列をvalidationとして使わず、別の独立開発系列を設計する。

この監査では新規の正式なcondition IDや確定したsplitを発行しない。[具体的入力草案](../data/templates/phase2_argument_readout_96_draft.json)の`draft_condition_id`はレビュー用である。model-free検証、評価器、採点位置、runtime freezeも未完了であり、モデルrun開始の根拠にはならない。

## 2026-10-22の改訂に伴う追記

Claude Codeのレビューとその承認に基づき、INV-3、INV-4、EXP-4、DON-3の規則と、全条件の言い回し・口座値を改訂した（[条件草案](phase2_argument_readout_96_condition_draft.md)の改訂記録）。系列レベルの判定は変わらない。ただしtrain全系列とvalidationの一部タスクが定型の言い回しを共有するため、近い言い換えのedgeとみなすかを正式仕様時に判断する。edgeとみなす場合、言い回しがすべて新しいvalidationタスク（REC-4、DON-4）以外は、言い回しの未知性の根拠に使わない。
