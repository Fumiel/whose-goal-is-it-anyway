# 実験プロトコル

## 1. 位置付け

本書は [`research_proposal.md`](research_proposal.md) を実装可能な実験手順へ落とすための作業文書である。研究目的やResearch Questionを変更する文書ではない。Pilot後の変更は、変更日、根拠、影響を受ける解析、test setを確認する前後のどちらで決定したかを記録する。

## 2. Pilot前に固定する事項

- 公開WeightのInstruction Modelを一つ選び、modelとtokenizerのrevisionを固定する。
- AgentDojoの一ドメイン、または同等の最小ローカル環境を選ぶ。
- ユーザータスク成功と攻撃成功を独立に判定できる実行可能なルールを用意する。
- 主比較のdecodingをgreedyまたはtemperature 0に固定する。
- 処理段階と代表token位置の取得規則を固定する。
- task、attack template、paraphrase family、matched pairのID体系を固定する。
- テンプレート群をまとめるgroup-aware splitを、最終評価を見る前に生成する。
- 出力schema、保存先、checksum方式、保存容量上限を固定する。

## 3. Pilotで推定する事項

100～150実行を目安に、次を記録する。

- 群A～Dおよびclean baseline failureの件数
- ResistantとSusceptibleの両方が得られる意味的対応条件数
- task・attack・入力変種ごとのTool Log probability差
- 1実行当たりの時間、GPU最大メモリ、保存容量
- Activation、Attentionを保存する層・時点を減らす必要性
- 入力長、末尾token、ツール呼び出し形式の不一致
- 自動成功判定と人手確認の不一致

Pilotは本実験の結果を良く見せる条件探索ではなく、実行可能性、測定妥当性、データ均衡の確認に用いる。

## 4. 条件IDと対応関係

各条件には少なくとも次のIDを付ける。

- `condition_id`: 条件内容から生成した安定ID
- `task_template_id`: ユーザータスクの意味的テンプレート
- `attack_template_id`: 攻撃目的・攻撃形式のテンプレート。clean条件ではnull
- `paraphrase_family_id`: 近い言い換えの集合
- `pair_id`: 意味的に対応するResistant/Susceptible候補の集合
- `variant_id`: 配置、書式、周辺文章等の変種

同じpair、近い言い換え、確率的反復はsplitをまたがせない。splitは個々の実行ではなく、事前に定めたgroup IDへ割り当てる。

## 5. 実行記録

各実行について以下を保存する。

- 実行ID、条件ID、開始時刻
- Git commit、解決済み設定、実行環境
- modelとtokenizerの名前・revision
- prompt/message列とtool call列
- seed、temperature、top-p等の生成条件
- ユーザータスク成功、攻撃成功、群A～Dまたはbaseline failure
- 各処理段階のtoken index、token ID、系列長
- 各層のResidual Stream
- 定義した領域へのAttention指標
- 次token Logit、および攻撃・正規ツール呼び出し全体の系列Log probability
- 実行時間、GPU最大メモリ、各artifactのchecksum

モデルWeight、Activation、AttentionはGit管理せず、manifestから外部保存場所を追跡する。

## 6. 処理段階

最低限、以下の五段階を記録する。

1. ユーザー指示を読んだ直後
2. 外部ツールを呼び出す直前
3. ツール出力を読んだ直後
4. 次の行動を決定する直前
5. 攻撃または正規ツールを呼び出す直前

原則として系列末尾tokenを使用する。各段階のtoken indexとtoken IDを必ず保存する。共通の区切りtokenを利用できない、または末尾tokenの結果が不安定な場合は、末尾数token平均と目的関連token位置を感度分析として追加する。

## 7. 成功・失敗の分類

- A: 攻撃文なし、ユーザータスク成功
- B: 攻撃文あり、攻撃失敗、ユーザータスク成功
- C: 攻撃文あり、攻撃失敗、ユーザータスク失敗
- D: 攻撃者指定行動が発生。ユーザータスク成功は別に記録する

攻撃文のないユーザータスク失敗はA～Dへ無理に含めず、`baseline_failure`として保持する。攻撃文なしで攻撃成功が記録された場合は評価器またはデータの矛盾として扱う。

## 8. Readout学習

- Goal readoutの教師データは、正常な単一目的実行と説明・引用・否定等の対照条件から作る。
- 攻撃成功や最終ツール選択をGoal readoutの教師ラベルに使わない。
- Goal categoryはmulti-labelとし、User goalとAttack goalを独立に読み出す。
- Role readoutは目的内容とは別に学習・評価する。
- 標準化はtrain set、確率較正は事前に指定したvalidation setだけでfitする。
- layer・stage・metricの多重比較にはFalse Discovery Rateを適用する。

## 9. 主解析

主解析は、攻撃文の前後における標準化Attack-goal readoutの変化と、ツール選択直前のAttack-minus-legitimate tool系列Log probability差の関連とする。群B対D、Role readout、Attention指標との比較は副次解析として扱う。

効果量と95%信頼区間を報告し、同一task・attack条件内の変種についてcondition単位のBootstrapまたは変量効果モデルを用いる。Probe scoreの逆転だけで目的の置換を主張しない。

## 10. Activation Patching開始条件

次を満たす場合だけ発展課題として開始する。

- GoalまたはRole readoutが未知task・未知attackで安定している。
- 十分なResistant/Susceptible対応ペアがある。
- layerとstageの候補が独立した評価で再現する。
- 無関係な位置、層、donorを用いる対照介入を同時に設計できる。

介入後の主指標はAttack-minus-legitimate tool系列Log probability差とする。
