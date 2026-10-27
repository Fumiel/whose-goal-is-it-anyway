---
decision_id: RDR-2026-10-27-03
date: 2026-10-27
status: accepted
phase: phase2_argument_recipient_672_b5_collected_actual_llm_audited
test_set_status: not_created_or_inspected
affected_files:
  - src/goal_takeover/phase2/argument_recipient_672_transfer.py
  - docs/decisions/README.md
  - PROJECT_STATE.md
supersedes: null
related_decisions:
  - RDR-2026-10-27-01
  - RDR-2026-10-27-02
---

# 実走行112件の人手監査免除と、正準から実走行への転移評価の指標

## 判断（研究実施者、2026-10-27）

1. 実走行112件のLLM監査（単一判定者`gpt-6-sol`、112/112判定、自動strictと`user_task_success`が全件一致、機械的な人手確認候補0件）を受け、**この112件に人手監査は行わない**。RDR-2026-10-27-01が「無作為抽出を必須としない、不一致・要確認ログのみ人手確認」と定めており、その該当がなかったためである。112件は「人手監査済み」と表示しない。ラベルの出所は自動strict評価とLLM監査と明記する。
2. 次に正準取得から実走行への転移評価を行う。

## 転移評価の指標（結果を見る前に固定）

B5で固定したprobe（層8 / C=1.0、`argrec672-v1-an-003-B1_to_B5`）を**再fitせず**に使い、実走行112件の`Tend_assistant`残差と、同じ条件の正準取得の残差とを比べる。評価は一貫性の確認であり、probeの妥当性の確認ではない（B5の主指標は0.613で基準0.80未達）。

1. 条件ごとの`prefix_identical`：実走行の選択prefixのtoken ID列が、正準prefixと完全に一致するか。
2. 条件ごとの残差の一致：層8残差のコサイン類似度と相対L2差。prefixが一致する条件での最大相対L2差を、数値雑音の上限として報告する。
3. 条件ごと・4候補ごとのprobe決定値（decision function）の正準と実走行の差。全（条件×候補）での決定値のPearson相関、候補argmaxの一致率、決定値の絶対差の最大・中央値。
4. 参考の`role_swap_auc`：正準と実走行を並べ、実走行標本のうち検証split条件（32条件）と、そのうちG/H（16条件）について、露出した候補のみで算出する。12/12の均衡を満たさないため**記述的な値**として報告し、閾値判定・検定・信頼区間を作らない。
5. 訓練split条件（80条件）は、probeの学習に使った条件の実走行なので**学習内の一貫性確認**として別に報告し、妥当性の根拠にしない。
6. 層・C・probeは変更しない。結果を見て指標を差し替えない。prefixが不一致の条件は除外せず、一致/不一致で層別して報告する。

この評価は、条件由来の`argument_present`を教師ラベルとする規則（RDR-2026-10-27-01）を変えず、実走行の生成callやuser-task成功からラベルを作り直さない。
