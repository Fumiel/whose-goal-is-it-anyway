# 672条件の監査準備

2026-10-27の[研究実施者判断](decisions/2026-10-27_argument_recipient_672_review_capture_and_staging.md)を受けた実装準備である。[実走行標本112条件](../data/splits/phase2_argument_recipient_672_review_actual_sample.json)は選定済み。監査LLMはCodex CLIの`gpt-6-sol`を読み取り専用・JSON出力で使う。[監査prompt v1](../configs/audits/phase2_argument_recipient_672_codex_prompt_v1.md)と[JSON schema](../data/schemas/phase2_argument_recipient_672_codex_audit.schema.json)を採用済み。現ホストのCLIは`0.164.0`だが、実行時の版・モデル利用可否は未検証であり、本書だけで研究用監査を開始しない。Codexもタスク設計に関与したため、監査を設計から完全に独立した判定とは呼ばない。

[OpenAIのCodex実行方法の説明](https://developers.openai.com/blog/codex-as-a-platform)は`codex exec`をスクリプト等の有界な実行に用いると説明する。監査用の具体的なCLI optionは、研究用freezeの前に現行CLIで検証する。

## 全条件で行う機械的な検査

- `argument_present`、口座露出、正準read順、正規`send_money`の条件由来ラベルを草案と実行用宣言で照合する。生成callや最終状態でprobe教師ラベルを更新しない。
- 実走行を取得した場合、native評価と厳密評価を独立に記録し、受取人口座、送金金額・件名・日付、読取内容、重複送金、副作用を照合する。モデルの行動失敗は保持する。
- 各runでraw generation、tool event、前後状態とchecksum、停止理由、技術失敗のstageを保存する。失敗runも新しいIDなしに置換しない。

## 生ログの人手確認候補

`goal_takeover.phase2.argument_recipient_672_audit_triage.human_review_reasons`は、LLM判定間の不一致、LLMと自動user-task判定の不一致、同一応答文の繰り返し、同一tool callの繰り返し、最大step到達・未知tool、raw generation欠落を機械的に検出する。これらは人手が生ログと環境状態を確認する**候補**であり、LLMの誤りかモデルの誤りかを自動決定しない。完全一致以外の意味的反復は、LLM監査または人手確認で判断する。

研究実施者は無作為抽出を必須対象としない。全件機械検査と、上記の対象を必要に応じた人手確認へ送る。確認者、最初の判断、根拠のtool eventとraw発話、裁定、native・厳密・LLM判定との差を別欄に保存する。人手で確認しなかった条件を「人手監査済み」と表示しない。

## 実行前に固定する情報

- `gpt-6-sol`のCLI利用可否、実行時CLI版。LLM判定者が1つか複数かも記録する。設計関与のある監査として解釈限界を併記する。
- 実走行標本の配分と条件IDをruntimeに結びつけ、結果を見て成功例だけ選ばない。
- LLM判定と自動判定、人手確認結果の一致率の分母・欠測・未判定の扱い。LLM監査は人手監査と同格にしない。
- 繰り返し以外に生ログ確認を要する停止・解析異常の追加規則と、技術失敗時の再実行・停止規則。
