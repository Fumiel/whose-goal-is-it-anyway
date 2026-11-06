---
decision_id: RDR-2026-11-06-01
date: 2026-11-06
status: accepted
phase: phase2_argument_recipient_672_execution_design_review
test_set_status: not_created_or_inspected
affected_files:
  - docs/phase2_argument_selection_pointer_diagnostic_spec.md
  - docs/research_proposal.md
  - docs/experimental_protocol.md
  - configs/analysis/phase2_argument_selection_pointer_diagnostic_v1.json
  - src/goal_takeover/phase2/argument_recipient_672_selection_pointer.py
  - tests/test_argument_recipient_672_selection_pointer.py
  - docs/decisions/README.md
  - PROJECT_STATE.md
supersedes: null
related_decisions:
  - RDR-2026-09-15-01
  - RDR-2026-10-07-03
  - RDR-2026-10-26-01
  - RDR-2026-10-27-01
  - RDR-2026-10-27-02
---

# 引数選択の決定時点を問う方向への軌道修正

## 状態と適用範囲

研究実施者は2026-11-06に、本記録の方向、探索的パッチングの条件、診断の判定基準を採用した。計画書とプロトコルにはパッチング条件だけを反映した。研究の問い、題目、確認的回帰は改訂していない。

これは672条件の結果閲覧後の判断である。確認的testは未作成・未閲覧である。本記録は手順1の既存キャプチャの解析を認めるが、新規の収集とfitは各仕様とruntime freezeが揃うまで許可しない。

## 変更前の設計

- 確認的主解析は、`Tpre`から終端位置までの`argument_readout`変化、`authority_score`、両者の交互作用で`m_arg`を説明する回帰である（計画書第7節）。
- 672条件のprobe教師は`Tend_assistant`の残差で、到達基準は未知系列`role_swap_auc` 0.80である（RDR-2026-10-27-01）。
- 活性化パッチングは任意であり、11月10日までに標準達成目標の解析データが揃った場合だけ開始する（計画書第10節・第11節）。

## 変更の根拠

### 確認済みの開発結果

| 観測 | 分母・状態 | 出典 |
|---|---|---|
| G/H `role_swap_auc`はB1〜B5で0.521、0.477、0.526、0.536、0.613。B5のTF-IDFは0.531、ランダムラベル最大は0.576 | G/Hの48条件。同じ検証集合を5回閲覧した適応的な値 | [集計](../../results/2026-10-27_phase2_argument_recipient_672_b2_b5_and_actual_v1.json) |
| 教師強制の系列対数確率で、文面の口座のうち送金先が最上位 | 469/480。AUROC換算0.87〜0.91。train、探索的 | [検証PDF](../../output/pdf/2026-10-30_recipient_probe_verification.pdf) |
| 未知系列で役割0.50〜0.57、文面の有無0.54〜0.56、露出行のみの学習でも役割0.51〜0.53 | train 480条件の系列除外CV。検証PDFは探索的実行の値で「本実行が進行中」と記載 | 同上 |
| 実走行の厳格成功はtool由来46/48、user由来21/64。誤受取人はそれぞれ2件、12件 | 112条件、攻撃なし。自動評価とLLM監査、人手監査なし | [集計](../../results/2026-10-27_phase2_argument_recipient_672_b2_b5_and_actual_v1.json) |
| 全672条件の口座は`GB`で始まる | 条件宣言。実トークン化は未確認 | [条件宣言](../../data/templates/phase2_argument_recipient_672_v1.json) |

### 解釈の限界

上表から言えるのは、`Tend_assistant`の1トークンから、今回の線形probeと口座別ラベルでは受取人を読めなかったことだけである。「値は生成時に取り出される」は未検証の仮説であり、本記録の前提にしない。値の所在と選択の決定時点は別の問いである。

### 外部資料

次の2報告を検討材料にした。いずれも未追跡のローカルファイルであり、Git管理に入れるかは未決定である。報告内の主張は証拠そのものではなく、下の一次資料の確認状況とあわせて扱う。

| 資料 | 作成 | SHA-256 |
|---|---|---|
| `docs/deep_research/Novelty and Publication-Readiness Assessment of _Whose Goal Is It Anyway__2026-11-05.pdf` | ChatGPT Deep Research | `604f3c0fd9f208ed8d8bb882d61582b38e1b85fe1324e40dceb8d2e8d495c507` |
| `docs/deep_research/同一ツール引数乗っ取りIPI研究の新規性評価と軌道修正案（2026年11月5日）.pdf` | Claude Deep Research | `7c29d53fb7005c2857cfc64804146d9ce83291cf36e8ab34fa19fff961705562` |

2026-11-06に一次ページを確認した文献は次のとおりである。

| 文献 | 確認した内容 | 確認の限界 |
|---|---|---|
| Yu et al., [Readable Before Actionable](https://arxiv.org/abs/2610.05295), v1 | AgentDojoはSlackとWorkspace。役割方向の編集で悪意ある引数の使用が88.2%→12.4% | 付録Uは抽出要約経由。引数値のreadoutとpatchはないと判断したが要約に依存 |
| Wang et al., [Right Tool, Wrong Parameters](https://arxiv.org/abs/2611.04673), v1 | parameter poisoningの定義。AuthorityFlowでASR 93.06%→9.03% | 要旨のみ |
| Wu et al., [Tool Calling is Linearly Readable and Steerable](https://arxiv.org/abs/2605.07990) | 道具識別の読み出しと操舵。単一ターン・固定メニューの範囲 | v1を確認。v3は未確認。引数操舵0/30と"on the fly"の文は抽出要約経由 |
| Kale & Vishwanath, [Prompt-Injection Probes Learn the Conversation](https://arxiv.org/abs/2610.18408), v1 | 位置と長さだけで標準評価AUROC 0.91〜0.98 | 要旨のみ |
| Ahad et al., [Influence Is Not Authority](https://arxiv.org/abs/2608.29942), v1 | 必要な値の出所だけを変えると、因果信号が24件すべてで攻撃側へずれる | 要旨のみ |
| Kotawala, [Probing and Steering Prompt Injection Compliance](https://neurips.cc/virtual/2026/168286) | 最終プロンプトトークンで服従をAUROC 0.90で予測。抑制は主にタスク置換型 | ワークショップ発表の要旨のみ。どちらのDeep Research報告にも記載がない |

Mixing Mechanisms、Lookbacks、arXiv:2606.00566、PACT、Liao、SAIS '27の締切は未確認である。「注入下で引数値を読んだ研究はない」は網羅的な確認ではなく、暫定の判断として扱う。

## 提案する変更

### 1. 研究の問いを競合仮説として立てる

同一ツールの引数乗っ取りで、攻撃側と正規側の値の選択がいつ・どこで決まるかを問う。

- **H1 読解時の束縛：** 選択に関わる役割情報は口座スパン上で作られる。
- **H2 生成前のポインタ：** 値のidentityは読めなくても、どちらを使うかは`Tend_assistant`で読める。
- **H3 生成時の決定：** 選択は値の分岐トークンの近くで初めて定まる。

どの仮説も前提とせず、どの結果も報告する。

### 2. 案Aの回帰をそのまま採用しない

「取り出し元の決定 × role probe」で`m_arg`を説明する回帰は採用しない。取り出し元の決定を`m_arg`や同位置のロジットから作ると循環するためである。取り出し経路は介入効果として別に示す。計画書第7節の確認的回帰を置き換えるか維持するかは、位置スイープの結果を受けて別のRDRで決める。

### 3. 内容と権限の分離を前提にしない

内容×出所の2×2は入力条件の操作として組み、`m_arg`への交互作用を見る。潜在表現を分離できるかは結果として判定する。方向パッチングを分離の前提として使わない。

### 4. 評価基準

| 項目 | 提案 |
|---|---|
| 到達基準 | 0.80を緩めない。0.75への変更は結果閲覧後の緩和となるため採用しない |
| 追加基準 | 表層ベースライン差、クラスタ単位の信頼区間、ランダムラベル対照、未閲覧ファミリーでの再現を併記する |
| ベースライン | TF-IDFに加え、長さ・位置、口座identity、同位置のロジットを使う |
| G/H | 5回閲覧済みのため、新しい確認に使わない |
| 学習量 | 新しい根拠なしに学習条件を増やさない |

具体的な閾値は測定ごとの仕様で固定する。手順1は[診断仕様](../phase2_argument_selection_pointer_diagnostic_spec.md)に示す。

### 5. 進行順

1. 既存キャプチャによる選択ポインタ診断（訓練データのみ、新規実行なし）。
2. 実走行の誤受取人14件と成功失敗の分解。user由来21/64の原因を確認し、攻撃条件の比較軸を決める前提とする。pilotのD群31件を同一ツール・別ツールへ分解する。
3. 位置スイープの別仕様。口座スパン、`"recipient": "`、`GB`、最初の分岐トークンを分ける。スロット付近は中間層に限定し、同位置のロジットをベースラインにする（計画書第7節）。
4. 必要な場合に探索的パッチング。構造が揃う役割入替え対を優先する。

新しいキャプチャはそれぞれ別の取得仕様とruntime freezeを必要とする。

## 研究実施者の判断（2026-11-06）

1. **パッチング：** 開発データ上の探索的解析に限って許可する。2026-11-20までに開始できなければ行わない。卒論はパッチングなしで成立する構成とする。他のパッチング、Attention介入、別モデル・別domainの開始条件は変更しない。
2. **手順1：** 縮小案を採用せず、[診断仕様](../phase2_argument_selection_pointer_diagnostic_spec.md)のとおり実施する。手順1は位置・キャプチャが前回診断と同じ再解析であり、主な新規性はラベルと対照である。
3. **判定基準：** 仕様のR1〜R4を結果閲覧前に確定する。対内正解率への0.80の転用も確定する。
4. **主結果の位置づけ、題目、計画書の問い：** 今後の手順の結果を見てから判断する。それまでは現行の記載を維持する。

## 採用しなかった案

- **Claude報告の案Aをそのまま採用：** 未検証の取り出し仮説を前提とし、回帰に循環の懸念がある。
- **ChatGPT報告の因子分解を主張の中心にする：** 内容と権限の分離を前提としている。また、最近の関連研究と10月30日の診断を反映していない。
- **負の結果を主論文とする転換：** Kale & Vishwanathと近く、複数モデルでの再現が必要である。ただし、probeの一般化失敗は結果として報告する。
- **案C（内部信号によるprovenanceモニタ）：** 追加のAgentDojo実行を要し、防御研究としての競合も強い。

## 影響範囲

- **Research Question：** RQ1の測定分離とRQ3の統制は維持する。RQ2の回帰の扱いは未決定である。
- **データ：** 既存のrun、bundle、集計、G/H・I/Jの扱いは変更しない。
- **維持する制約：** 同一ツール引数乗っ取りへの範囲限定（RDR-2026-10-07-03）、probe増加を採用と解釈しないこと、介入なしに因果を主張しないこと、Qwen3-8B int8 / Bankingが暫定構成であること。
- **再現性：** 手順1は不変の派生出力として保存する。結果閲覧後に追加した解析は探索的と明記する。
