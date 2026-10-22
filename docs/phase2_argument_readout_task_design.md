# Phase 2 `argument_readout` タスク設計方針

2026-10-22。研究者が採用した方針は[RDR-2026-10-22-02](decisions/2026-10-22_argument_readout_task_design.md)に記録する。本書は新規条件の設計指針であり、候補口座・条件数・split・実行環境を凍結した仕様ではない。研究課題は[研究計画](research_proposal.md)、実行手順は[実験プロトコル](experimental_protocol.md)を優先する。

6系列・24タスク・96条件という小規模開発セットのレビュー用草案は[別文書](phase2_argument_readout_96_condition_draft.md)に置く。[RDR-2026-10-22-03](decisions/2026-10-22_argument_probe_staged_controls.md)により、この初回セットではユーザー指示中のrecipient内容を扱い、tool出力中のIPI、引用・禁止、両口座がrecipient候補になる条件は追加セットへ分ける。24タスクの具体案、splitと実行仕様は未承認・未凍結である。

## 測定対象とラベル

最初の主対象はBankingの`send_money.recipient`である。候補は架空の口座IDとし、金額、パスワード、予定取引ID、異なるツールの引数を同一probeへ混ぜない。他のslotの読み出しは、必要なら別probeによる副次・探索的評価とする。

候補値`v`について、条件で提示された**送金操作のrecipient内容**として`v`が明示されていれば`argument_present[v] = 1`、そうでなければ0とする。ユーザーが許可したか、禁止・引用したか、tool output中か、モデルが実際に送金したかはこのラベルに反映しない。例えば「Bへ送金するな」はB=1、「送金先はA、照会IDはB」はA=1、B=0である。正規Aと代替Bの双方が送金先候補として提示された入力ではA=B=1を許す。文字列Bが単に出現するだけでrecipient候補と特定できない場合はB=0とする。曖昧な書式の注釈規則と裁定例はモデル結果を見る前に固定する。

教師ラベルは条件宣言と事前の注釈規則から生成する。攻撃成功、A～D群、生成されたtool call、最終状態を教師にしない。`argument_readout`は内容の読み出しであり、`source_role_readout`、操作的な`authority_score`、後続callの系列対数確率差で測る`tool_call_preference`と区別する。

## 対応条件の作り方

各意味系列内に、単一目的の教師条件と、同じ候補が異なる文脈に現れる対応条件を作る。候補A/Bを正規側・代替側へ入れ替え、user instruction、tool output、引用、説明、禁止を可能な範囲で交差させる。同じ文字列集合を保ちながら、一方をrecipient、他方を照会IDなど別slotに置く条件と、その逆を含める。書式・長さ・出現位置がラベルを一意に予測しないようにし、欠けたcellを記録する。

単一目的条件で学習したprobeを、両候補が同時に提示されるIPI条件へ適用するのは分布の移動である。開発用validationには両候補提示の条件を含め、各候補の読み出しと欠測を別々に確認する。結果が不十分なら主解析に使えるとみなさず、教師条件や適用範囲の変更を新しい記録で扱う。

## Probeと評価の設計

最初の実装候補は、候補値ごとに独立した正則化付き線形二値分類器である。一入力に複数の正例を許すため、相互排他的なsoftmaxラベルを基本形にしない。特徴量は指定した層・位置の残差ストリームから取得し、標準化等はtrainだけでfitする。主解析の攻撃側読み出し変化は、当該条件の攻撃候補`v_A`に対する同じprobeの連続scoreを、指定した`Tpre`と終端位置で比較する。線形decision scoreを第一候補とし、scoreの種類、符号、scale、層、位置、正則化、較正はtraining / validationだけで選び、test前に固定する。

評価では候補別・macroの識別性能、balanced accuracy、対応条件での性能、欠測、group単位の不確実性を報告する。文字列出現検出は健全性確認とし、主な妥当性検査は、語彙を揃えたrecipient対別slotの条件、正規・代替の入替え、未知系列、TF-IDF等の語彙baseline、group構造を保ったrandom-label controlとする。文字列出現だけの課題で語彙baselineを上回ることを要求しない。性能の数値閾値をこの方針書から推定しない。

## 系列、候補値、分割

主なvalidation対象は、**候補引数値は学習時に既知で、意味的なtaskまたはattack系列は未知**という条件である。未知の口座値を新しいクラスとしてzero-shot復号する評価は発展課題とする。候補口座は4～6種類を初期の設計目安とするが、実際の値・数・class balanceは新規収集の仕様で決める。

系列は口座値、名前、金額、近い言い換えだけで増やさない。正規目的、recipientの決定規則、参照資料、必要な操作の組合せ、具体的な攻撃目的・形式を点検する。`argument_value_id`は候補値の識別子で、値の共有だけでは独立系列の証拠にも、分割をつなぐedgeの自動免除にもならない。`task_template_id`、`attack_goal_id`、`attack_style_id`、`attack_template_id`、`pair_id`、`paraphrase_family_id`等の意味と粒度を新規収集前に宣言し、既使用系列を含む関係graphを作る。共通する具体的な攻撃目標・形式、近縁タスク、対応pair等があれば現行プロトコルに従ってedgeを張り、連結成分単位でtrain / validation / testへ割り当てる。「recipientの変更」という広いカテゴリと具体的な攻撃目標を同一IDにしない。関係graphでv2側につながった新条件を独立validationと呼ばない。

既存の二文書v2五条件はtrain側の同一連結成分であり、候補値や系列の多様性、未知系列性能を示さない。v1は後続判断によりprobe教師・validationから除外され、pilotの旧90条件も`pilot_only`のままである。

## 新規収集仕様で固定する項目

- 候補口座の実値、`argument_value_id`、各候補の正負・同時提示cell数
- 各系列の正規目的、recipient決定規則、文書・tool、攻撃目的と文脈
- 曖昧な言及、禁止、引用、別slot参照のラベル裁定規則
- 条件・pair・attack IDの粒度、関係graph、split、漏洩検査
- 正規／攻撃callの同一tool・主要slot差分、独立した成功述語とmodel-free対照
- 取得位置、欠測規則、評価指標・選択規則、監査・runtime freezeと停止規則

これらを満たす新規仕様とmodel-free検証ができるまで、新しいモデルrunを研究用probeデータとして開始しない。確認的test用系列はPhase 3凍結まで隔離する。
