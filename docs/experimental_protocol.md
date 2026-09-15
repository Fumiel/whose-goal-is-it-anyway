# 実験プロトコル

## 1. 位置付け

本書は [`research_proposal.md`](research_proposal.md) を実装可能な実験手順へ落とすための作業文書である。研究目的やResearch Questionは研究計画書を正とし、本書だけで変更しない。

研究設計およびプロトコルの変更理由は、[`decisions/README.md`](decisions/README.md)から参照できる個別のResearch Decision Recordに記録する。Pilot後にプロトコルを変更する場合は、変更日、根拠、影響を受ける仮説・解析、変更が確認的test setの確認前か後かを記録する。Pilot、条件選択またはlayer選択に使用したfamilyは確認的testへ再利用しない。

## 2. Pilot前に固定する事項

- 公開WeightのInstruction Modelを一つ選び、modelとtokenizerのrevisionを固定する。
- AgentDojoの一ドメイン、または同等の最小ローカル環境を一つ選ぶ。
- chat template、tool schema、dtype、decoding設定を固定する。
- ユーザータスク成功と攻撃成功を独立に判定できる実行可能なルールを用意する。
- 主比較をgreedy decodingまたは同等の決定論的設定とし、モデル選定時にclean utilityとtool-call安定性を確認する。
- 正規tool callと攻撃tool callを同一prefixからteacher forcingするcanonical serializationを固定する。
- `B0`、`B1`、`B2_plus`および`Tpre`、`Tpost`、`Tend_tool`、`Tend_assistant`の取得規則を固定する。
- task、attack goal、attack style、argument slot、paraphrase family、matched pair、prefixのID体系を固定する。
- group-aware splitを確認的結果を見る前に生成する。
- 出力schema、保存先、checksum方式、保存容量上限を固定する。
- 自動評価器の小標本を人手監査し、不一致の扱いを固定する。

## 3. モデル・ドメイン選定ゲート

Bankingを第一候補とするが、名称だけで決定しない。候補ごとに小規模な統合試験を行い、次を満たす一モデル・一ドメインを9月末までに固定する。

- 決定論的条件でclean taskを実用的な割合で完了できる。
- tool callを安定してparseし、環境で実行できる。
- 正規／攻撃のcanonical callとargument slotを一意に構成できる。
- 同一tool・異argumentのIPI条件を構成できる。
- ユーザータスク成功と攻撃成功の自動判定を、人手監査と十分に一致させられる。
- 1実行当たりの時間と保存容量が11月中旬までのデータ収集に収まる。

いずれかが満たせない場合は、同様にrecipientまたはtarget IDを扱える単一の代替ドメイン、またはAgentDojo形式を参考にした最小ローカル環境へ切り替える。複数ドメインを同時に主対象としない。

## 4. Pilotと凍結事項

Pilotは80～120実行を目安とし、次を記録する。

- 群A～Dおよびclean `baseline_failure`の件数
- `fully_specified`、`param_open`、`action_open`ごとの件数と攻撃成功率
- ResistantとSusceptibleの両方が得られる意味的対応条件数
- task、attack goal/style、surface variantごとの行動margin分布
- canonical call全体とargument slotのtoken alignment
- `B0`、`B1`および`Tpre`、`Tpost`、`Tend_tool`、`Tend_assistant`の位置選択成功率
- 同じ`prefix_id`を異なる観測時点として重複記録していないか
- 1実行当たりの時間、GPU最大メモリ、Residual StreamとAttentionの保存容量
- 自動成功判定と人手確認の不一致
- Probe用matched conditionの生成可能数とgroup構造

Pilotは、実行可能性、測定妥当性、データ均衡を確認するために用いる。結果を良く見せるattack、layerまたは閾値の探索に使用しない。Pilotで使用したtask/attack familyは確認的testへ入れない。

Pilot後、確認的testを見る前に以下を凍結する。

- モデル、ドメイン、revision、chat templateおよびdecoding
- task/attack familyとtask opennessの構成
- splitと確認的test family
- canonical callとargument slotの定義
- 主要なlayer領域、token位置、Probe前処理および正則化
- 主解析モデル、共変量、除外規則、BootstrapまたはPermutation手順
- 実行数、cluster数、保存対象および容量上限

## 5. 条件IDと対応関係

各条件には少なくとも次のIDと属性を付ける。

- `condition_id`: 条件内容から生成した安定ID
- `task_template_id`: ユーザータスクの意味的テンプレート
- `attack_goal_id`: 攻撃が要求する意味的なgoal
- `attack_style_id`: 攻撃の書式、偽装または表現style
- `attack_template_id`: goalとstyleを組み合わせた具体的テンプレート
- `argument_slot_id`: 正規／攻撃呼出しが異なる主なargument slot
- `task_openness`: `fully_specified`、`param_open`または`action_open`
- `paraphrase_family_id`: 近い言い換えの集合
- `pair_id`: 意味的に対応するResistant/Susceptible候補の集合
- `variant_id`: 配置、書式、周辺文章等のsurface variant
- `prefix_id`: 実際にモデルへ渡したtoken列またはserialized prefixのchecksum由来ID

clean条件では攻撃関連IDをnullとする。同じtask、attack goal、attack style、pair、近いparaphraseおよび確率的反復はsplitをまたがせない。splitは個々の実行ではなく、事前に定めた最高位のgroup IDへ割り当てる。

## 6. 実行記録

各実行について以下を保存する。

- 実行ID、条件ID、開始時刻
- Git commit、解決済み設定、実行環境
- modelとtokenizerの名前・revision
- chat template、tool schema、dtype
- 元のmessage列、serialized text、token列、`prefix_id`
- model出力、parse済みtool call、環境状態の変化
- seed、temperature、top-p、thinking設定等の生成条件
- ユーザータスク成功、攻撃成功、群A～Dまたは`baseline_failure`
- task opennessと各種group ID
- 各boundary/positionのtoken index、token ID、系列長および選択規則
- 各層のResidual Stream
- 定義したspanへのAttention集約値
- 次token Logitと正規／攻撃canonical callのteacher-forced score
- `argument_slot_margin`、`whole_call_margin_total`、`whole_call_margin_normalized`、`first_discriminating_token_margin`および適用可能な場合の`tool_name_margin`
- 実行時間、GPU最大メモリ、各artifactのchecksum

モデルWeight、Activation、full Attention matrixおよび大量の実行出力はGit管理せず、manifestから外部保存場所を追跡する。生成済みrun directoryは変更せず、再処理または設定変更時は新しいrun IDを作る。

## 7. 観測時点とtoken位置

観測時点を二つの時間軸で定義する。

### Agent boundary

- `B0`: User instructionまでをserializeし、最初のAssistant生成を開始する直前。
- `B1`: 最初のtool returnまでをserializeし、次のAssistant生成を開始する直前。
- `B2_plus`: 後続の各tool return後に次のAssistant生成を開始する直前。副次解析用。

### Tool-output内位置

- `Tpre`: injected span直前。
- `Tpost`: injected span直後。
- `Tend_tool`: tool output末尾。
- `Tend_assistant`: Assistant生成開始marker。`Tend_tool`と同じtokenでない場合は分けて保存する。

各観測は、実際にforward passへ渡したtoken列上の位置として定義する。異なるstage名でも`prefix_id`とtoken indexが同一なら、独立した時点として扱わない。攻撃span、User goal span、tool metadata spanについて開始・終了token indexを保存する。tokenizerのoffset mappingが利用できない場合は、文字列からtoken列への対応規則と曖昧例の除外規則をPilot前に固定する。

主解析の位置は`B1`内の`Tpre`、`Tend_tool`または`Tend_assistant`からvalidationで一つを選ぶ。`Tpost`、末尾数token平均、目的関連span平均および`B2_plus`は感度分析または副次解析とする。

## 8. 行動score

正規呼出し $a_L$ と攻撃呼出し $a_A$ は、同一の`prefix_id`とcanonical serializationを用いてteacher forcingする。すべてのmarginはattack minus legitimateの向きへ統一する。

- `argument_slot_margin`: 対応するargument slot全体の系列Log probability差。確認的主指標。
- `whole_call_margin_total`: canonical call全体の系列Log probability差。
- `whole_call_margin_normalized`: token数で正規化したcanonical callの差。
- `first_discriminating_token_margin`: 最初に異なるtokenのLogitまたはLog probability差。診断指標。
- `tool_name_margin`: tool名が異なる条件だけで計算する。

各系列scoreには、対象文字列、token ID列、各tokenの条件付きLog probability、開始・終了位置および合計方法を保存する。複数tokenのtool名またはargumentを最初のtokenだけで評価しない。正規／攻撃callの長さが異なる場合は、totalとnormalizedを併記し、主指標のargument slot定義をPilot前に固定する。

## 9. 成功・失敗の分類

- A: 攻撃文なし、ユーザータスク成功
- B: 攻撃文あり、攻撃失敗、ユーザータスク成功
- C: 攻撃文あり、攻撃失敗、ユーザータスク失敗
- D: 攻撃者指定行動が発生。ユーザータスク成功は別に記録する

攻撃文のないユーザータスク失敗はA～Dへ含めず、`baseline_failure`として保持する。攻撃文なしで攻撃成功が記録された場合は、評価器またはデータの矛盾として扱う。A～Dは外部挙動の記述と副次解析に用い、確認的主解析は連続marginを用いる。

## 10. Readout学習と妥当性確認

### Content readout

- `action_readout`と`argument_readout`を分ける。
- 教師データは正常な単一目的実行と、説明、引用、否定、禁止、過去記述等の対照条件から作る。
- 攻撃成功、A～Dまたは最終tool selectionを教師ラベルに使わない。
- 同一action・異argument条件を除外しない。

### Authority readout

- 同一または厳密に対応する文字列をUser、Tool、引用、説明、禁止等へ配置したmatched conditionを優先する。
- 入力上のRoleまたは実験条件が読み出せることと、モデルがその内容を採用したことを区別する。
- 行動結果から`adopted`または`committed`ラベルを作り、同じ行動を予測するProbeは作らない。

### 必須の妥当性対照

- TF-IDF＋logistic regression等のlexical baseline
- 同じgroup構造を保ったrandom-label controlとselectivity
- 未知task familyまたは未知attack familyでの評価
- train setだけでの標準化および特徴前処理
- validation setだけでのlayer、正則化、閾値および較正方法の選択
- test setの一回限りの評価

ProbeごとにAUROC等の識別性能だけでなく、適用可能な場合はBrier scoreまたはECE、groupごとの効果量と95%信頼区間を報告する。Probe scoreはdecodabilityを示す測定であり、採用、権限付与または因果的利用を単独で示さない。

## 11. 確認的主解析

確認的主解析は、`B1`のtool-output内で`Tpre`から事前指定した終端位置までに生じるattacker argument readoutの変化とauthority readoutが、後続するdecision boundaryの`argument_slot_margin`を説明するかを評価する。

主要な説明変数と共変量はtest確認前に固定する。

- attacker argument readoutの変化
- authority readout
- IPI exposureまたはTask Drift baseline
- task openness
- 入力長
- attack spanの位置
- 必要最小限の表面的特徴

最終層・最終tokenのreadoutと同じ位置のLogit差は、構造的に相関し得るためsanity checkとする。群B対群D、Role readout、Attention、PCA、`B2_plus`、全layer×position mapは副次または探索的解析とする。

推論単位はsurface variantではなく、taskとattack goal/styleから構成した最高位clusterとする。効果量と95%信頼区間はcluster単位のBootstrapまたはPermutationで求める。十分なcluster数と安定した推定がある場合だけ変量効果モデルを補助的に使用する。探索的な多層・多位置比較にはFalse Discovery Rateを適用する。

## 12. Attentionの保存と解釈

通常の全実行では、各decision位置から次のspanへのAttention massをonlineまたは直後に集約して保存する。

- attack span
- User goal span
- tool metadata span
- 必要に応じた無害な対照span

full Attention matrixはPilotの少数例と、validationで事前指定したlayer/headだけに限定する。Attention massは補助的な記述量であり、Attention knockout等の統制された介入を行わない限り因果的説明として扱わない。容量または実行時間が制約となる場合は、full Attention、集約Attention、Residual Streamの順ではなく、full Attentionを最初に削減し、Residual Streamと行動scoreを優先する。

## 13. 実験規模とsplit

Activationを保存する暫定総数は約450～700実行とする。

- Pilot：80～120
- Probe教師・matched control：200～300
- 確認的IPI：独立clusterを最低30、各cluster 3～4 surface variant
- Clean baseline：60～100

数値はPilot後に実行時間、保存容量、群分布およびcluster内相関を確認して凍結する。surface variantを増やすことよりtask/attack familyの多様性を優先する。

split比は暫定的にtrain 60%、validation 20%、test 20%とする。同じtask、attack goal、attack style、pair、近いparaphraseおよび確率的反復をsplit間で分離しない。Pilotや選択に用いたfamilyは確認的testへ含めない。

確率的なAttack Success Rate評価はmarginが0付近の条件と代表条件に限り、各10回程度実行する。原則として確率的反復ではActivationを保存しない。

## 14. Activation Patching開始条件

Activation Patchingは11月10日までに標準達成目標のデータが揃い、次をすべて満たす場合だけ開始する。

- action/argumentまたはauthority readoutが未知familyでlexical baselineを上回る。
- 十分なResistant/Susceptible matched pairがある。
- layerとtoken位置の候補が独立したvalidationで再現する。
- 意味的に対応したin-distribution donorを用意できる。
- random donor、semantic mismatch、隣接layer/positionを対照として用意できる。
- target marginだけでなくclean action likelihood、出力分布の変化およびtask utilityを評価できる。

Resistant→SusceptibleとSusceptible→Resistantの双方向介入を行う。主な介入指標には、方向を明記したLogit differenceと、次の正規化効果量を用いる。

$$
\mathrm{recovery} =
\frac{LD_{\mathrm{patched}} - LD_{\mathrm{susceptible}}}
{LD_{\mathrm{resistant}} - LD_{\mathrm{susceptible}}}
$$

分母が0に近い例の除外規則を事前に固定する。target marginの変化だけでは単なる表現破壊を除外できないため、utility guardを満たさない介入を「安全な回復」と解釈しない。

## 15. Go/No-Go基準と期限

- **9月末**：end-to-end実行、自動成功判定またはcanonical call scoringが安定しなければ、単一の代替ドメインまたは最小環境へ切り替える。
- **10月11日**：`B0/B1`とtool-output token位置を再現可能に取得できなければ、within-output解析を縮小し、`B0/B1`のboundary解析を主とする。
- **10月25日**：Probeが未知familyでlexical baselineを安定して上回らなければ、「目的表現」という主張を下げ、具体的tool action/argument表現またはbehavioral temporal attributionへ主題を縮小する。
- **11月10日**：確認的主解析用のデータが揃っていなければ、Activation Patching、Attention介入および別モデル・別ドメイン評価を中止する。
- **11月30日**：主解析、感度分析および主要図表を確定する。12月は再現確認と執筆に使用する。

陰性結果であっても、評価器、matched control、Probe妥当性、splitおよび主解析が凍結済みであれば研究結果として保持する。No-Goによる縮小は失敗の隠蔽ではなく、事前に定めた代替計画として新しいRDRに記録する。
