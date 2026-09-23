---
decision_id: RDR-2026-09-24-01
date: 2026-09-24
status: accepted
phase: before_formal_integration_gate
test_set_status: not_created_or_inspected
affected_files:
  - configs/selection/integration_gate.yaml
  - PROJECT_STATE.md
supersedes: null
related_decisions:
  - RDR-2026-09-22-01
  - RDR-2026-09-22-02
---

# 統合試験ゲートの一部事前決定

## 判断

`configs/selection/integration_gate.yaml`に、正式候補の設定参照、両候補が全必須基準を満たした場合の優先規則、1 run当たりの資源上限を記入する。これは**部分決定であり、正式ゲートの凍結ではない**。選定用sample manifest、行動性能の閾値と分母、評価器監査の標本数、対応clusterとpairの最低数は未設定である。これらを埋めてゲートと標本を凍結するまで、候補の正式評価を開始しない。

## 決めた値と根拠

| 項目 | 値 | 根拠 |
| --- | --- | --- |
| モデル候補 | `qwen3_8b_int8.yaml`、`qwen3_4b_bf16.yaml` | RDR-2026-09-22-02で宣言済み。revisionは各モデル設定に固定済み。 |
| ドメイン第一候補 | `agentdojo_banking_v1_2_2.yaml` | 研究計画と既存プロトコルの第一候補。採用は正式ゲート通過後。 |
| shakedown除外元 | `pre_gate_shakedown.yaml` | task ID、attack template ID、近い言い換えの除外規則を記録済み。正式sample manifestにも適用する。 |
| 両候補通過時の優先 | Qwen3-8B int8 | RDR-2026-09-22-02の事前宣言した容量上の優先規則を正式ゲートのtie-breakにも採用。8Bが一項目でも不合格なら適用しない。 |
| 1 runの時間上限 | 300秒 | shakedownで記録された最大62.5秒の約4.8倍。正式標本の長い実行への余裕を取った工学上限。 |
| peak GPU memory上限 | 12 GiB | shakedownで記録された最大9.53 GiBから約2.47 GiBの余裕を取った工学上限。 |
| bundle保存量上限 | 0.05 GiB | shakedownで監査された最大1,602,643 byteの約33倍。長いprefixや記録増への余裕を取った工学上限。 |

資源値だけにshakedownの観測を用いた。3 fixtureのuser-task success、attack success、outcome差、margin、モデル間の行動差は、上記の決定と閾値設定に使用していない。時間・容量の上限はこの実行環境と現在のselected-position保存方式に対する値であり、総実験の容量保証ではない。

## 未決定と次の凍結条件

- 同じ事前規則で両候補に適用する選定用sample manifestと、shakedown系列・近い言い換えの除外確認
- clean task成功、tool call解析、環境実行、評価器一致、teacher-forced scoringの最低率・分母・信頼区間の扱い
- 同一tool・異なるargumentの最低cluster数、Resistant / Susceptible対応候補の最低pair数または分布条件
- 人手監査の抽出・blind化・裁定手順と標本数
- runの時間・memory・保存量上限を超えた場合の集計・再試行規則、および総容量見積り

これらは研究上の最低必要量と正式標本の設計から、候補結果を見る前に決める。値が現在の記録からは導けないため、`null`を残した。全項目の凍結時に新しいRDRでGit commitと設定checksumを記録する。

## 影響と限界

研究課題、outcome定義、確認的解析、主モデル・主ドメインの未選定状態は変わらない。確認的testは作成・閲覧していない。shakedown runは選定・Pilot・probe・validation・testへ再利用しない。正式ゲートが複数候補を通した場合にのみtie-breakを適用し、候補がどれも通らなければ既存プロトコルの代替domainまたは最小環境の判断へ進む。
