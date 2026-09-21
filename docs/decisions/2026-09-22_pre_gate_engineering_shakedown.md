---
decision_id: RDR-2026-09-22-01
date: 2026-09-22
status: accepted
phase: pre-pilot
test_set_status: not_created_or_inspected
affected_files:
  - docs/experimental_protocol.md
  - configs/selection/integration_gate.yaml
  - PROJECT_STATE.md
supersedes: null
related_decisions:
  - RDR-2026-09-15-01
---

# Integration gate凍結前の非選定engineering shakedown

## 1. 判断

`configs/selection/integration_gate.yaml`の数値閾値、正式な選定標本および
tie-break規則を凍結する前に、実モデルとAgentDojo等の実環境を接続するための
小規模なengineering shakedownを許可する。

このshakedownはモデル・ドメイン選定試験、Pilot、Probe教師データ収集または
確認的解析の一部ではない。目的を、実装互換性の確認と、時間・GPU memory・
保存容量の上限を事前に定めるための資源計測に限定する。

正式な候補評価は、shakedownの完了後にintegration gateと選定用sample manifestを
凍結し、新しい条件とrun IDを用いて開始する。

## 2. 判断時点

- 研究段階：pre-pilot scaffolding
- primary model：未選定
- primary domain：未選定
- integration gate：未凍結
- real-model runner：未検証
- AgentDojo adapter：未検証
- 確認的test set：未生成・未確認
- 実モデルによる研究結果：未確認

本判断は、モデル、ドメイン、攻撃成否または内部状態の観測結果を確認した後の
変更ではない。

## 3. 背景と理由

現行プロトコルは、候補モデル・ドメインの正式評価前に選定閾値を定めることで、
観測結果に合わせた採用基準の変更を防いでいる。この原則は維持する。

一方、次の項目は、少なくとも一度は実モデルと実環境を接続しなければ現実的な
上限や実装方法を定めにくい。

- model、tokenizerおよびchat templateの読み込み可否
- AgentDojoとagent runner間のtool schemaおよびmessage形式の互換性
- tool callの構文解析から環境実行までの制御経路
- hidden stateおよびAttentionの取得位置、shape、dtype
- generation、activation captureおよびteacher-forced scoring間のtoken整合
- 1 run当たりの時間、peak GPU memoryおよび保存容量
- エラー記録、checksumおよびimmutable run bundleの生成

これらを確認せずに資源上限や評価標本を決めると、研究上の基準ではなく単純な
interface不整合によって正式評価が失敗する可能性がある。このため、行動性能を
評価しない限定的な工学確認を、正式なintegration gate評価から分離して認める。

## 4. 許可する範囲

### 4.1 Fixtureと実行規模

- shakedown開始前に、最大3個の意味的に異なる手作業fixtureを宣言する。
- fixtureは、cleanなtool利用、tool returnを含む複数turn、および正規／攻撃候補の
  teacher-forced scoring経路を最小限に確認できる構成とする。
- fixtureの追加は、未確認のinterface経路を確認する必要が判明した場合に限る。
  追加理由を実行前に記録し、モデル挙動に合わせた攻撃変種の追加は行わない。
- 技術的修正後の再実行は許可するが、生成済みrunを上書きせず、新しいrun IDと
  直前の失敗runへの参照を残す。

### 4.2 使用するモデルとドメイン

- 接続確認に必要なら、後に正式候補となり得るモデルまたはBanking domainを使用して
  よい。ただし、model revision、tokenizer revision、環境versionおよび実行設定を
  毎回記録する。
- 複数候補を接続確認しても、shakedownで観測した行動結果を候補間で順位付けしない。
- shakedownで使用したこと自体を、正式な候補リストへの採用または棄却理由にしない。

### 4.3 閲覧・利用できる情報

次の情報は、adapter実装、エラー修正およびintegration gateの資源上限を定めるために
閲覧・利用してよい。

- 依存関係、API、tool schema、message形式およびchat templateの互換性
- 例外、parse error、schema validation errorおよび環境実行errorの内容
- serialized text、token ID列、token位置およびprefix checksumの一致
- hidden stateおよびAttention tensorの取得可否、shape、dtype、device
- teacher-forced scoringが有限値を返すか、および対象sequence・slotのalignment
- wall-clock time、peak GPU memory、CPU memoryおよびartifact size
- resolved configuration、revision、seed、Git commitおよびchecksumが保存されるか

tool-call経路のdebugには個々の生成出力を確認する必要があるため、その閲覧自体は
禁止しない。ただし、内容は技術的不具合の診断にだけ使用し、性能評価、条件探索、
閾値設定または候補選定へ利用しない。

## 5. 禁止する利用

shakedownでは、次を行わない。

- clean user-task success率、attack success率、outcome A～Dの分布を推定する
- Resistant / Susceptible条件の比率、pair数または発生条件を探索する
- 行動結果に基づいてモデル、ドメイン、system prompt、chat templateまたは攻撃文を
  選ぶ
- 観測した成功率や失敗率に合わせてintegration gateの最低率、分母または最低pair数を
  設定する
- activation、Attention、readoutまたはtool-call preferenceについて研究上の比較・
  仮説検定・効果量推定を行う
- shakedown runをPilot、Probe学習・較正、validation、test、感度分析または論文の
  結果表へ再利用する

個々の出力から、あるモデルが「攻撃に強い」「攻撃に弱い」「研究に適している」等の
結論を出さない。

## 6. データ隔離と記録

- すべてのfixture、conditionおよびrunへ`engineering_shakedown_only`であることが分かる
  安定した識別子またはmetadataを付ける。
- shakedownのtask template、attack template、pair、paraphrase familyおよびその近い
  変種は、正式な選定標本とPhase 1以降の全splitから除外する。
- 出力は研究データと混同しない場所または明示的に区別されたmanifestで管理する。
- raw runを上書きせず、失敗runも技術的失敗として保持する。
- 実行ごとに、目的、閲覧した情報、行った修正および次の実行理由を短く記録する。
- shakedown由来の値を使用できるのは資源上限と工学的互換性の設定だけである。
  行動性能に関するgate閾値は、一般的な実験要件と研究上必要な最低条件から定める。

## 7. 終了条件

次をすべて確認した時点でshakedownを終了する。

1. 少なくとも一つの実モデル・実環境構成で、message serializationからtool call、
   tool return、次のassistant生成までの制御経路が完走する。
2. 一つの同一prefixから、正規／攻撃候補のteacher-forced scoring経路が実行できる。
3. generation、activation captureおよびscoringへ渡すprefix token ID列を比較できる。
4. 指定した位置のhidden stateを取得し、shapeとtoken位置を記録できる。
5. 代表runについて時間、peak GPU memoryおよび保存容量を記録できる。
6. immutable run bundleにrevision、resolved configuration、token情報およびchecksumを
   保存できる。

終了後、正式な候補評価を開始する前に次を行う。

1. `configs/selection/integration_gate.yaml`の全必須項目を埋める。
2. 正式な選定用sample manifestとtie-break規則を固定する。
3. shakedown fixtureとその近い変種を除外リストへ記録する。
4. gate、候補revisionおよび除外リストを新しいRDRに記録する。
5. Git commitと設定checksumを保存する。

## 8. 研究課題と解析への影響

本判断はResearch Question、仮説、主解析、測定概念、outcome分類または確認的testの
仕様を変更しない。正式な候補評価の結果を見る前に採用基準を固定する原則も変更しない。

変更するのは、正式な候補評価より前に、研究結果として使用しない工学確認段階を
明示的に追加する点だけである。shakedownの条件とrunを完全に隔離することで、
候補選定、Pilotおよび確認的解析への情報漏洩を防ぐ。

## 9. リスクと対策

### 行動結果の非意図的な利用

debug中にはモデル出力が見えるため、完全なblind化はできない。対策として、fixture数を
制限し、正式標本から意味系列ごと除外し、行動結果を集計・比較・選定に使わない。

### Shakedownの際限ない拡張

工学確認を名目に攻撃変種を探索すると、実質的なPilotになる。対策として、最大3 fixture、
目的の事前記録、interface上必要な場合だけの追加、および明示的な終了条件を設ける。

### 資源値の過度な一般化

時間とmemoryはhardware、sequence長およびcapture設定に依存する。対策として、計測環境と
入力長を記録し、正式計画に近い設定で測定し、安全余裕を含めて上限を決める。

## 10. 再検討条件

次の場合はshakedownを停止し、新しいRDRで範囲またはプロトコルを再検討する。

- 3 fixtureでは必要なinterface経路を確認できず、行動条件の追加探索が必要になった
- 複数モデルの行動結果を比較しなければadapter仕様を決められなくなった
- AgentDojoの制約により、shakedown条件を正式標本から意味系列単位で隔離できない
- 資源制約により、計画したhidden state取得またはteacher-forced scoringが実行できない
- shakedown中に、研究仮説または確認的解析を変更し得る予期しない行動結果を確認した

