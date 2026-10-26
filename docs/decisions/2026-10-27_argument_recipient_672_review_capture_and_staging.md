---
decision_id: RDR-2026-10-27-01
date: 2026-10-27
status: accepted
phase: phase2_argument_recipient_672_execution_preparation
test_set_status: not_created_or_inspected
affected_files:
  - docs/phase2_argument_recipient_672_task_text_draft.md
  - data/templates/phase2_argument_recipient_672_draft.json
  - docs/experimental_protocol.md
  - PROJECT_STATE.md
  - data/splits/phase2_argument_recipient_672_review_checkpoints.json
  - docs/phase2_argument_recipient_672_graph_review.md
  - src/goal_takeover/phase2/argument_recipient_672_cv.py
  - src/goal_takeover/phase2/argument_recipient_672_metric.py
  - data/splits/phase2_argument_recipient_672_review_actual_sample.json
  - configs/audits/phase2_argument_recipient_672_codex_prompt_v1.md
  - data/schemas/phase2_argument_recipient_672_codex_audit.schema.json
  - configs/experiments/phase2_argument_recipient_672_v1.yaml
  - data/templates/phase2_argument_recipient_672_v1.json
  - data/splits/phase2_argument_recipient_672_v1.json
  - data/manifests/phase2_argument_recipient_672_v1.freeze.json
supersedes: null
related_decisions:
  - RDR-2026-10-26-01
  - RDR-2026-10-26-02
  - RDR-2026-10-26-04
  - RDR-2026-10-26-05
  - RDR-2026-10-26-06
  - RDR-2026-10-26-07
  - RDR-2026-10-14-01
---

# 672条件本文の採用、正準履歴取得、累積学習曲線と監査対象

## 2026-10-27の研究実施者判断

1. [672条件の現行本文草案](../phase2_argument_recipient_672_task_text_draft.md)はレビュー済みとして、現状の168タスク・672条件の本文、資料、条件由来ラベル、期待callを採用する。元の草案JSONは変更せず、実行用宣言を別versionとして作る。これはmodel-free/tokenizer試験の通過をモデルのタスク成功と同一視する判断ではない。
2. 現在のA～F学習候補、G～J検証候補を固定する意向で、系列間および既使用系列との関係を監査する。同一・近縁タスクを分割間に置かない原則は維持する。cross-split edgeが確認された場合にそれを消して独立検証と呼ばず、関係と指標への影響を先に記録する。
3. 全条件のprobe教師用には、U系列ではユーザー指示の正準prefix、D1/D1Mでは指定資料1件、D2では指定資料2件を正しい順で読んだ正準履歴を与え、その露出後の残差を取得する。別途選ぶ実走行標本で行動と教師用取得からの転移を確認する。教師ラベルは条件由来の`argument_present`であり、生成callやuser-task成功から作り直さない。
4. 主測定位置は各正準prefixの**assistant生成直前の最後のprompt token**（`Tend_assistant`）とする。正答口座の最終tokenを主位置へ変更しない。絶対index、token ID、境界、prefix checksumを残す。
5. 学習曲線はB1を学習して検証系列で評価し、B1+B2、…、B1～B5と累積して**同じ指定済み検証系列**でprobe性能を確認する。途中の結果を理由に規則を変更しない。繰り返し閲覧した検証値は適応的な開発結果として扱い、未閲覧の独立確認とは呼ばない。B1～B5の各96条件と累積480条件という規模はRDR-2026-10-26-06に従う。
6. 別系統LLM中心の監査方針の下で、人手確認する重要箇所はLLM判定の不一致、モデルの繰り返し応答など生ログを読む必要がある例とし、無作為抽出は必須としない。人手確認の判定・裁定を自動判定と別欄へ保存する。

## 同日の関係graph判断

実装準備中の本文照合で、検証候補I4の「請求書＋支払先の名義確認登録簿から口座を選ぶ」課題はtrain側の既使用二文書照合に、J3の「預り金を元の顧客へ返す」課題は既使用REF返金に近いと判定した。研究実施者は**現在の系列と割当を維持し、近縁候補を独立validationの主集計から除外して別報告する**方針を選んだ。

ファミリー内の系列を近縁として保守的に一成分へまとめる現行方針では、I4およびJ3からのedgeはそれぞれI・Jファミリー全体をtrain成分へ接続する。従ってI・Jの96条件は開発用の関連系列診断として毎段階報告しても、独立未知系列AUROCの主集計には入れない。この判断時点ではG・Hの96条件を残るcross-split edgeの監査待ちとした。これは現在のseries ID、本文、train/validation配置を変更しない判断である。

同日の追加の本文照合では、Gの公的納付・交通料金とtrainの継続的な民間料金、Hの売上分配・印税・紹介／成果報酬とtrainの商品購入・役務報酬は、具体的な支払目的と資料が異なると確認した。共有する口座文型や読取形式だけではedgeを張らない既存規則に従い、研究実施者は**G・Hを独立validationの主集計に採用**した。G・Hの96条件を同じ集合で各段階評価し、I・Jの96条件を関連系列診断として並記する。全192件を独立validationの分母に入れない。

さらに研究実施者は、RDR-2026-10-26-01の既定指標を部分改訂し、最初の新規fitの前に**`role_swap_auc`を主指標**として採用した。各候補口座について、二口座をともに提示する`rx_ref_y`・`ry_ref_x`だけを使い、recipient内容ラベル1と参照ラベル0のAUROCを計算し、4候補を等重み平均する。対象は独立主集計G・Hの48条件（各候補12正例・12負例）である。0.80の開発上の到達基準はこの主指標へ適用する。従来のlexical-present 4候補平均AUROCは旧96条件との比較用の副指標として残す。I・Jで同じ計算をしてもtrain近縁診断として別報告し、主指標へ混ぜない。欠測・AUROC未定義時の規則は最初のfit前に実行仕様へ固定する。

旧96条件の取り扱いについて研究実施者は、**主学習曲線のtrainを新規B1～B5だけ**と決めた。RDR-2026-10-26-05による旧REC/DON 32条件の学習使用許可は取り消さないが、主曲線には算入しない。旧64条件も主曲線には算入しない。旧条件を使う解析は、結果閲覧済み資料を利用した別の補助分析として事前に仕様を分ける。

層と正則化Cは、**B1の学習8系列だけ**で系列1つずつを除いたCVにより1組選び、B1～B5で固定する。候補は旧96条件と同じ層0、8、16、24、32、35とC=0.01、0.1、1.0の18組とする。各候補で8個のfoldの系列外scoreをまとめ、B1の二口座入替え48条件に対する4候補等重み`role_swap_auc`で選ぶ。同点時は候補表の早い層、次に小さいCを選ぶ。各foldの標準化と線形logistic probeは残る7系列だけでfitする。B1で選んだ組をその後の全段階に使い、G・Hの値で再選択しない。このCVは既使用train成分を跨ぐため、独立未知系列の検証と呼ばない。

実走行標本は各56系列から1タスクを事前選択し、その`rx_ref_y`と`ry_ref_x`を両方走らせる**112条件**とする。[選択案](../../data/splits/phase2_argument_recipient_672_review_actual_sample.json)ではファミリー内の系列番号を順に見て、3タスク位置を1→2→3と巡回させる。これによりU0/UN/UIまたはD1/D1M/D2の形式を標本へ含める。標本は行動と正準教師用取得から実走行への転移確認に用い、残り560条件の行動成功率を推定したようには扱わない。

監査LLMには**Codex CLIの`gpt-6-sol`**を使用する。研究実施者によれば条件本文の意味的内容は主にClaudeが作成した。ただしCodexも設計に関与したため、RDR-2026-10-26-05の「設計補助とは別系統」という強い独立性条件はこの監査では満たさない。この部分を明示的な限定改訂とし、報告では「Qwen実験モデルおよび主たる本文作成Claudeとは別だが、設計関与のあるCodexによる監査」と表示する。Codex監査を独立人手監査と同格には扱わず、判定不一致と反復応答の生ログを人手確認する方針は維持する。CLIは読み取り専用・JSON出力とし、実測したCLI版、モデル応答の識別情報、固定prompt、入出力checksumを監査記録に残す。現ホストの`codex --version`は`codex-cli 0.164.0`だったが、監査開始時の版とモデル利用可否はまだ未検証である。

研究実施者は[監査prompt v1](../../configs/audits/phase2_argument_recipient_672_codex_prompt_v1.md)と[JSON schema](../../data/schemas/phase2_argument_recipient_672_codex_audit.schema.json)を実走行前の仕様として採用した。自動評価結果を入力packetから伏せ、観測されたread結果・送金call・状態だけでuser-task成功、受取人正確性、必要資料読取を判定する。監査promptの変更は旧判定を上書きせず別versionとして記録する。

技術上限は先行96条件と同じ**GPU 12 GiB、1条件300秒、保存0.05 GiB**とする。上限超過や技術失敗は不変failure bundleを保存して収集を停止し、同じrun IDで再試行しない。再開には新しいrun IDと来歴を使う。

これらの判断を[実行設定](../../configs/experiments/phase2_argument_recipient_672_v1.yaml)、別versionの672条件・split・graph・チェックポイント・実走行標本、および[design freeze](../../data/manifests/phase2_argument_recipient_672_v1.freeze.json)へ反映した。design freezeは入力9ファイルのchecksumを持ち、672条件・480/192配置・112件標本と一致する。**runtime freezeは未作成で、新規研究runはまだ始めない。**

同日、commit `8dd8670`に対するnative・tokenizer・GPU事前検査とruntime freezeを別のGit無視領域へ保存した。その後、runnerがruntime freeze内の環境・事前検査ファイルのchecksumを再確認する改修を行った。旧freezeは上書きせず、新commitの同一commit検査と別runtime freezeを作成してから研究runを開始する。Codex CLI `0.164.0`と`gpt-6-sol`は合成packetでJSON schemaの工学試験を通過したが、実走行監査は未開始である。

## この判断で未固定の実行前事項

- 新規の本文修正や追加系列が生じた場合のcross-split edge再審査。現行配置の主集計認定は上記の具体本文と既使用系列の照合に限る。
- 前処理・較正の詳細とその適用範囲、主指標の欠測・未定義時の規則。最初の新規fit前に固定する。
- 検証系列の閲覧範囲と停止規則の数値。全検証系列を各段階に使う場合、留保集合は残らないことを明示する。
- 実行時CLI版と`gpt-6-sol`利用可否、LLM判定と人手裁定の一致率の扱い、同一commit GPU検査とruntime freeze。

本判断は、旧96条件と既存run・監査・probe結果を変更しない。Qwen3-8B int8 / BankingはPhase 2開発用の暫定構成のままで、主モデル・主ドメインの正式採用や確認的testの開始ではない。新規研究runは同一commitの事前gateとruntime freezeが揃うまで開始しない。
