---
decision_id: RDR-2026-09-15-01
date: 2026-09-15
status: accepted
phase: pre-pilot
test_set_status: not_created_or_inspected
affected_files:
  - docs/research_proposal.md
  - docs/experimental_protocol.md
supersedes: null
---

# Pilot前の研究焦点・測定単位・実験規模の改訂

## 1. 判断の要約

旧計画のTakeover Point中心の設計から、goal content、authorityおよびtool action/argument preferenceを分離して測定する設計へ変更する。同一tool・異argumentのIPIを確認的解析の中心に置き、agent boundaryとtool-output内token位置の二つの時間軸から、内部readoutと後続するargument preferenceの関係を調べる。

Activation Patching、Attention介入および別モデル・別ドメイン評価は、卒業研究の成立条件から外し、観測解析が期限内に完了した場合だけ行う発展課題とする。

## 2. 判断時点

- 研究段階：Pilot実施前
- モデル：未選定
- 主対象ドメイン：未選定
- end-to-end model runner：未完成
- AgentDojo adapter：未検証
- 確認的test set：未生成・未確認
- 実験結果：未確認

この判断はPilotやtest setの結果を見て研究仮説を変更したものではなく、関連研究との新規性比較と2026年12月までに主要結果を確定するという時間制約に基づく事前変更である。

## 3. 根拠資料

変更判断時に、外部資料「卒業研究計画_関連研究調査と改訂提言_最終版.docx」の本文を確認した。この資料はリポジトリ外で提供されたため、本RDRから絶対パスでは参照せず、内容のうち採用した判断と一次資料を以下に記録する。

新規性の境界を判断するため、主に次の研究を参照した。

- [AgentDojo](https://arxiv.org/abs/2406.13352)：ユーザー効用と攻撃成功を区別する評価基盤。
- [Are you still on track!?](https://arxiv.org/abs/2406.00799v3)：Activation差分によるTask Drift検知。
- [Prompt Injection as Role Confusion](https://arxiv.org/abs/2603.12277)：生成前のRole表現と攻撃成功の関連。
- [IterInject](https://arxiv.org/abs/2605.24659)：中後層のAttention機構と介入。
- [IPI exposure hidden-state study](https://arxiv.org/abs/2608.02657)：hidden stateによるIPI exposure検知とknowledge-action gap。
- [AgentSentry](https://arxiv.org/abs/2602.22724)：tool-return境界のtemporal causal takeoverとtakeover pointの局在化。
- [AutoDojo](https://arxiv.org/abs/2606.15057)：task underspecification、特にaction-open taskとIPI成功の関係。
- [Designing and Interpreting Probes with Control Tasks](https://aclanthology.org/D19-1275/)：Probeのselectivityとcontrol task。
- [Towards Best Practices of Activation Patching](https://arxiv.org/abs/2309.16042)：Activation Patchingのmetricとcorruption方法への依存性。

2026年の研究には査読前preprintを含む。その結果を確立した一般機構とはみなさず、研究計画の新規性の境界と比較対象として使用する。卒業論文提出前に版と査読状況を再確認する。

## 4. 変更前の設計

- 題目と中心概念に「Goal-Representation Takeover」と「Takeover Point」を用いていた。
- 要約、送信、削除等のactionカテゴリを中心にgoal contentを測定していた。
- User goalとAttack goalが同じカテゴリの場合は、主比較から除外する可能性があった。
- Goal readout、Role readout、Attentionおよびtool-name中心のLogit差を比較していた。
- 五つの自然言語的な処理段階を設けていたが、実装上は同じserialized prefixとtoken位置を重複して観測する可能性があった。
- 攻撃文前後のreadout変化と、最終時点のattack-tool対legitimate-tool marginとの相関を主解析としていた。
- Activationを保存する実行を約1,400件予定し、原則として全層のAttentionも取得する設計だった。
- Activation Patchingを第四のResearch Questionとしていた。

## 5. 採用した変更

### 5.1 題目と新規性

題目を「Indirect Prompt Injection下のLLMエージェントにおける目的内容・権限帰属・ツール引数選好の表現遷移解析」へ変更した。

新規性は、IPI exposure、Role confusion、Attentionまたはtakeover pointを単独で示すことではなく、次の三者を区別し、同一tool・異argument条件で関係を調べることに置く。

1. actionまたはargument内容が内部状態から読み出せる程度
2. 内容がどのsource/authority条件に置かれたかを読み出せる程度
3. 正規／攻撃tool call、特にargumentへの行動選好

### 5.2 Research Question

Research Questionを次の三つへ整理した。

1. matched conditionと未知familyでaction・argument内容とsource/authority条件を独立に読み出せるか。
2. IPI span処理後のattacker argument readoutとauthority readoutは、後続するargument marginとどのtoken位置・層・agent boundaryで関連するか。
3. その関連がIPI exposure、表面特徴、task openness、入力長、攻撃位置およびAttentionを考慮しても残るか。

Activation PatchingはResearch Questionから外し、発展的な因果検証とした。

### 5.3 Goalの測定単位

旧Goal readoutを次の測定へ分けた。

- `action_readout`
- `argument_readout`
- `authority_readout`
- `tool_call_preference`

内容の`mention`はcontent readout、具体的行動への`commitment`はtool-call preferenceとして操作的に分ける。行動結果から`adopted`または`committed`ラベルを作り、同じ行動を予測するProbeは循環的になるため作らない。Probe scoreの上昇だけを目的の採用または因果的利用とは解釈しない。

### 5.4 同一tool・異argument条件

User goalとAttack goalが同じactionカテゴリでも、recipient、account、amount、file ID等のargumentが異なる条件を除外しない。これを確認的解析の中心条件とし、正規呼出しと攻撃呼出しを同一prefixからteacher forcingする。

主行動指標を`argument_slot_margin`とし、次を併記する。

- `whole_call_margin_total`
- `whole_call_margin_normalized`
- `first_discriminating_token_margin`
- tool種別が異なる場合の`tool_name_margin`

すべてのmarginはattack minus legitimateの向きへ統一する。複数tokenのargumentまたはtool名を最初のtokenだけで評価しない。

### 5.5 二つの時間軸

観測時点を次のように変更した。

- Agent boundary：`B0`、`B1`、副次的な`B2_plus`
- Tool-output内位置：`Tpre`、`Tpost`、`Tend_tool`、`Tend_assistant`

各観測で、元のmessage列、実際のserialized textまたはtoken列、`prefix_id`、token index、token ID、系列長、選択規則およびchat templateを保存する。異なるstage名でも同じ`prefix_id`とtoken indexなら独立した時点として扱わない。

### 5.6 Task openness

taskを`fully_specified`、`param_open`、`action_open`へ事前分類する。確認的解析は`fully_specified`と`param_open`を中心とし、正当な外部委任との区別が難しい`action_open`は副次的なmoderation解析とする。

### 5.7 確認的主解析

主解析を一つに固定する。`B1`のtool-output内で、`Tpre`からvalidationで事前指定した終端位置までに生じるattacker argument readoutの変化とauthority readoutが、後続するdecision boundaryの`argument_slot_margin`を説明するかを評価する。

IPI exposureまたはTask Drift、task openness、入力長、attack span位置および必要最小限の表面的特徴を共変量または層別要因として扱う。最終層・最終tokenのreadoutと同じ位置のLogit差は構造的に相関し得るためsanity checkとする。

推論単位は個々のsurface variantではなく、taskとattack goal/styleから構成した最高位clusterとする。効果量と95%信頼区間はcluster単位のBootstrapまたはPermutationで求める。

### 5.8 Probeの妥当性

次を必須とした。

- matched text / different authority条件
- TF-IDF等のlexical baseline
- 同じgroup構造を保ったrandom-label control
- task、attack goal/styleおよび近いparaphraseを跨がせないsplit
- 未知task familyまたは未知attack familyでの評価
- trainのみでの前処理、validationのみでのlayer・正則化・閾値・較正選択
- test setの一回限りの評価

### 5.9 実験規模、保存対象、期限

Activationを保存する暫定総数を約1,400件から約450～700件へ変更した。

- Pilot：80～120
- Probe教師・matched control：200～300
- 確認的IPI：独立clusterを最低30、各cluster 3～4 surface variant
- Clean baseline：60～100

surface variant数より独立したtask/attack family数を優先する。Attentionはspanへの集約値を通常保存し、full Attention matrixはPilot subsetまたは事前指定したlayer/headに限定する。

2026年11月30日までに主解析と主要図表を確定し、12月は再現確認と執筆に使用する。Activation Patching、Attention介入または別モデル・別ドメイン評価は、11月10日までに標準達成目標のデータが揃った場合だけ開始する。

## 6. 採用しなかった案

- `status`、`adoption`、`commitment`をすべて独立したProbeとして学習する。
- Many-tier authority hierarchyを主実験へ導入する。
- 「Commitment Transition Region」等の新しい固有用語を中心概念として導入する。
- 全実行でfull Attention matrixを保存する。
- Activation Patchingを卒業研究成立の必須条件とする。
- 複数モデルまたは複数ドメインを主実験へ含める。
- 固定した約1,400実行をsurface paraphrase中心で収集する。
- first-discriminating-tokenだけを主行動指標にする。

これらは新規性を追加し得るが、独立した構成概念の妥当性確認、実装、計算量または解釈上の負担が大きく、12月までに主要結果を確定する条件と両立しにくいと判断した。

## 7. 影響範囲

### Research Questionと仮説

- 旧Takeover Point仮説を撤回した。
- Goal readout、Role readoutおよびAttentionの単純比較を主解析から外した。
- attacker argument readout、authority readoutおよび後続argument marginの関係を確認的主解析とした。
- A～Dは保持するが、B対Dは副次解析へ変更した。

### データとmetadata

既存IDに加え、少なくとも次が必要になる。

- `attack_goal_id`
- `attack_style_id`
- `argument_slot_id`
- `task_openness`
- `prefix_id`

正規／攻撃callの対象文字列、token ID列、各tokenの条件付きLog probability、slot境界および合計方法も保存する。

### 実装

本RDR作成時点では、文書のみを更新している。設定、JSON Schemaおよび実装コードは新しいプロトコルへまだ同期していない。Pilot開始前に、少なくとも以下を更新する必要がある。

- experiment/model/domain/probe設定
- condition/run schema
- stageとtoken-position選択
- canonical callおよびargument-slot scoring
- span単位のAttention集約
- group-aware splitと妥当性テスト

### 既存データ

既存の研究データまたは生成済みrun directoryは変更していない。将来プロトコルを変更する場合も、既存runを上書きせず新しいrun IDとresolved configurationを作成する。

## 8. 想定される利点

### 新規性

- IPI exposureまたはRole confusionの再検出に留まらず、内容・authority・argument preferenceの結合を問える。
- 同一tool・異argumentという実務上重要な攻撃を扱える。
- tool-output内token進行とagent boundaryを混同せず比較できる。

### 実現可能性

- full Attention保存と必須Patchingを外すことで、計算・保存・実装負担を減らせる。
- 一つの確認的主解析に絞ることで、11月中の結果確定と陰性結果の解釈が可能になる。
- Go/No-Go基準により、adapter、Probeまたはscoringが失敗した場合でもbehavioral analysisへ縮小できる。

## 9. リスクと不利益

- 一モデル・一ドメインのため一般化可能性は限定される。
- argument slotのcanonical serializationとtoken alignmentがモデルtemplateに依存する。
- authority readoutが表面的なRoleや書式を読むだけになる可能性がある。
- 独立cluster数が不足すると、複雑な変量効果モデルを安定して推定できない。
- Activation Patchingを実施しない場合、因果的な主張はできない。

これらに対し、revision固定、lexical baseline、matched control、group-aware split、cluster-level inference、限定的な主張および事前のNo-Go条件を用いる。

## 10. 再検討条件

次の場合は本判断を再検討し、新しいRDRを作成する。

- 9月末までにend-to-end実行、自動評価またはcanonical scoringが安定しない。
- `B0/B1`またはtool-output内token位置を再現可能に取得できない。
- Probeが未知familyでlexical baselineを安定して上回らない。
- `fully_specified`または`param_open`でSusceptible例を十分に得られない。
- 実測した計算時間または保存容量が約450～700実行の計画に収まらない。
- 新しい関連研究により、内容・authority・argument preferenceの組合せにも直接的な重複が判明する。

再検討時は過去の本ファイルを直接書き換えず、後続RDRから本判断を`supersedes`または部分的に置換する判断として参照する。
