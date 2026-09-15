# 卒業研究計画案

## 研究題目

### 仮題

Indirect Prompt Injection下のLLMエージェントにおける目的内容・権限帰属・ツール引数選好の表現遷移解析

### 英題

Tracing Goal Content, Authority Attribution, and Tool-Argument Commitment in LLM Agents under Indirect Prompt Injection

## 1. 研究背景と問題意識

大規模言語モデル（LLM）は、外部のメール、ファイル、Webページなどを読み取り、必要に応じてツールを呼び出すAIエージェントとして利用されている。しかし、外部データに悪意ある命令が埋め込まれていると、本来は処理対象である文章を命令として解釈し、不正な行動を実行する可能性がある。この攻撃はIndirect Prompt Injection（IPI）と呼ばれる。

AgentDojoは、メール、オンラインバンキング、旅行予約などの環境で、エージェントのPrompt Injection攻撃と防御を評価するベンチマークであり、ユーザータスク成功と攻撃成功を区別して評価できる [1]。既存研究では、主に攻撃成功率、ユーザータスク成功率、攻撃検知性能などの外部的な結果が評価されてきた。

内部状態を利用する研究として、Are you still on track!?は、外部データを読む前後のActivation差分からTask Driftを線形分類器で検出できることを示した [2]。Prompt Injection as Role Confusionは、モデルが入力元のラベルだけでなく文章の書き方から発言者のRoleを内部的に推定し、Roleの混同が生成開始前から攻撃成功と関連すると報告している [3]。IterInjectは、中後層における攻撃文へのAttention増幅と、その機構への介入結果を報告している [4]。さらに、生成前hidden stateからIPIへの露出を判別できる一方、その信号が安全な行動へ必ずしも結び付かないknowledge-action gapが報告されている [5]。AgentSentryはmulti-turn IPIをtemporal causal takeoverとして扱い、tool-return境界におけるcounterfactual re-executionからtakeover pointを局在化している [6]。

これらを踏まえると、「IPIへの露出を内部状態から検出できる」「Role表現またはAttentionが攻撃成功と関連する」「時間的なtakeover pointが存在する」という主張だけでは新規性が限定される。本研究は、目的に関する情報を、(i) action、(ii) argumentsまたはconstraints、(iii) source/authority条件、(iv) 具体的なtool callへの行動選好に分ける。特に、正規行動と攻撃行動が同じtoolを使用し、recipient、account、amount、target IDなどの引数だけが異なるIPIを中心に、内容が読めること、権限ある指示として表現されること、具体的な引数が選好されることの分離と結合を調べる。

なお、2026年の関連研究には査読前preprintを含むため、報告された結果を確立した一般機構とはみなさず、本研究の新規性の境界と比較対象として慎重に扱う。

## 2. 研究目的とResearch Question

本研究の目的は、IPIを受けたツール利用型LLMエージェントについて、攻撃内容が内部状態に表現されることと、その内容が権限ある指示として扱われ、具体的なtool actionまたはargumentの選好へ結び付くことを区別して観測することである。Task Drift、IPI exposure、Role readoutおよびAttentionは比較用の指標とし、主眼をgoal content・authority・tool-call preferenceの関係に置く。

次のResearch Questionを設定する。

1. 同一内容をUser命令、Tool出力、引用、説明、否定・禁止などに置いたmatched conditionと未知のtaskまたはattack familyにおいて、action・argument内容とsource/authority条件を独立に読み出せるか。
2. IPI spanの処理後、攻撃者側argumentのreadoutとauthority readoutは、後続する正規tool callと攻撃tool call、特に引数部分の系列Log probability差と、どのtoken位置・層・agent boundaryで関連するか。
3. その関連は、IPI exposure、表面的な語彙・書式、task openness、入力長、攻撃位置およびattack-span Attentionを考慮しても、後続する行動選好と安定して対応するか。

Activation PatchingはResearch Questionの成立条件には含めず、十分な対応事例と独立に再現する候補領域が得られた場合だけ、介入方法と評価指標に関するbest practice [9]を踏まえた発展的な因果検証として行う。

本研究の中心的な新規性は、goal content、authorityおよびtool action/argument preferenceを異なる測定として扱い、tool-output内のtoken進行とagent loopの境界という二つの時間軸で、同一tool・異argumentのIPIを含めて追跡する点にある。ただし、readoutの増加だけを目的の採用とは解釈せず、介入なしに因果的な「乗っ取り」を主張しない。

## 3. 実験対象と範囲

内部状態を取得できる2B～8B程度の公開WeightのInstruction Modelを用い、単一モデル・単一ドメインから開始する。モデルとドメインは、以下を満たすかを小規模な統合試験で確認してから固定する。

- 決定論的な主比較でclean taskとtool callingが安定する。
- 正規呼出しと攻撃呼出しを同一prefixからteacher forcingで評価できる。
- ユーザータスク成功と攻撃成功を実行後の環境状態から独立に判定できる。
- 同一tool・異argumentの正規／攻撃counterfactualを構成できる。

引数置換を形式化しやすいBankingを第一候補とするが、canonical tool-call scoringまたはエージェント接続が安定しない場合は、同様に宛先や対象IDを評価できる単一の代替ドメインへ切り替える。主実験では一モデル・一ドメインを維持し、別モデル・別ドメインの一般化評価は必須としない。

task opennessを次のように事前分類する [7]。

- `fully_specified`: actionと主要argumentがUser promptで指定される。
- `param_open`: actionは指定され、argumentを外部データから取得する。
- `action_open`: 実行するaction自体を外部データへ委ねる。

確認的解析は解釈しやすい`fully_specified`と、同一tool・異argument攻撃を扱える`param_open`を中心とする。`action_open`は権限混同と正当な委任を分けにくいため、副次的なmoderation解析に限定する。

主な攻撃経路は、ツールが返す外部データに攻撃命令を埋め込むIPIとする。各実行は次の四群に分類する。

- 群A：攻撃文がなく、ユーザータスクに成功
- 群B：攻撃文があり、攻撃には失敗するがユーザータスクに成功
- 群C：攻撃文があり、攻撃とユーザータスクの両方に失敗
- 群D：攻撃者が指定した不正な行動を実行（ユーザータスク成功・失敗を別途記録）

群A～Dは外部妥当性のために保持するが、主解析は連続的なtool-call preferenceを用い、群B対群Dの二値比較は副次解析とする。攻撃文のない実行でユーザータスクに失敗した場合は、A～Dへ含めず`baseline_failure`として保持する。

## 4. 条件構成と行動指標

同じ入力とモデルから計算される内部状態とLogitは、確率的生成で最初の異なるtokenが選ばれるまでは原則として同一である。そのため、同じ入力を乱数seedだけ変えて得た成功実行と失敗実行は、分岐前の内部状態差を説明する主比較には用いない。

主解析では、ユーザー目的と攻撃者目的を固定し、ユーザー指示、攻撃文の言い換え、攻撃文の配置、無害な周辺文章および書式を制御して変化させた、意味的に対応する入力変種を作る。モデルを固定し、主比較はgreedy decodingまたは同等の決定論的設定で実行する。選定モデルがその設定で安定しない場合は、モデルを変更するか、決定論的なteacher-forced scoringを主解析として生成結果と分離する。確率的生成は、各条件のAttack Success Rateを推定する補助評価に限る。

正規呼出し $a_L$ と攻撃呼出し $a_A$ を同一のserialized prefixからteacher forcingし、次の指標を保存する。

1. `argument_slot_margin`: 対応するargument slot全体の系列Log probability差。主な行動指標とする。
2. `whole_call_margin_total`と`whole_call_margin_normalized`: canonical tool call全体の系列Log probability差について、合計値とtoken数で正規化した値を保存する。
3. `first_discriminating_token_margin`: $a_L$と$a_A$が最初に分岐するtokenでのLogit差。tokenization依存性を確認する診断指標とする。
4. `tool_name_margin`: tool種別が異なる条件だけで使用する。

主指標は、値が大きいほど攻撃呼出しを選好するよう、次の向きに統一する。

$$
m_{\mathrm{arg}} = \log P(\mathrm{argument}_{A} \mid x)
- \log P(\mathrm{argument}_{L} \mid x)
$$

多tokenのargumentまたはtool callについて、最初のtokenだけから結論を出さない。同一tool・異argument条件は除外せず、むしろ確認的解析の中心条件とする。

## 5. 取得する内部情報と二つの時間軸

各実行について、Transformer各層のResidual Stream、定義したspanへのAttention集約値、次token Logitおよび正規／攻撃tool callの系列Log probabilityを保存する。また、外部データを読む前後のActivation差分をTask DriftまたはIPI exposure検知のベースラインに使用する。

「いつ」をagent loopの境界と単一forward pass内のtoken位置に分ける。

### Agent boundary

- `B0`: User instructionまでをserializeし、最初のAssistant生成を開始する直前。
- `B1`: 最初のtool returnまでをserializeし、次のAssistant生成を開始する直前。IPIが次行動へ影響できる主要境界。
- `B2_plus`: 後続のtool return後に次のAssistant生成を開始する直前。遅延効果を調べる副次時点。

### Tool-output内token位置

- `Tpre`: injected span直前のtoken。
- `Tpost`: injected span直後のtoken。
- `Tend_tool`: tool output末尾のtoken。
- `Tend_assistant`: chat template上のAssistant生成開始marker。`Tend_tool`と同じtokenでない場合は分けて保存する。

各時点について、元のmessage列、実際にモデルへ渡したserialized textまたはtoken列、そのchecksumから生成する`prefix_id`、系列長、token index、token ID、選択規則およびchat templateを保存する。異なる段階名でもserialized prefixとtoken位置が同一なら、別の観測時点として重複計上しない。末尾数token平均は感度分析に限り、主解析の位置はPilotおよびvalidationで固定する。

Attentionは攻撃span、User goal span、tool metadata spanへの集約量を通常保存し、全層・全headのfull Attention matrixはPilotの少数例または事前指定した候補だけに限定する。Attentionの大きさだけから判断理由を断定せず、補助的な記述量として扱う。

## 6. Readoutの構成と解釈

「モデルが目的を採用したか」は直接観測できないため、次の測定を区別する。

- `action_readout`: send、transfer、deleteなど、action内容がResidual Streamから読み出せる程度。
- `argument_readout`: recipient、account、amount、file IDなど、具体的argumentまたはconstraintが読み出せる程度。
- `authority_readout`: 同一内容がUser命令、Tool由来の非信頼内容、引用、説明、否定・禁止など、どのsource/authority条件に置かれたかを読み出せる程度。
- `tool_call_preference`: 正規／攻撃tool call、特にargumentへの行動選好。ProbeではなくLog probability marginで測定する。

action・argument readoutの教師データには、攻撃成否ではなく、目的が一つだけ明示された正常な単一目的実行と対照条件を用いる。authority readoutには、可能な限り同一文字列を異なるRole、引用、説明、禁止等に配置したmatched text条件を用いる。攻撃成功と最終的なtool selectionはreadoutの教師ラベルに使用せず、学習後の外部評価にのみ用いる。

内容の`mention`はcontent readout、具体的行動への`commitment`はtool-call preferenceとして操作的に区別する。行動結果から`adopted`または`committed`ラベルを作って同じ行動を予測するProbeは、循環的になるため主解析では作らない。readoutスコアの増加は、内容が読み出し可能であることを示すに留まり、権限付与、採用または因果的寄与を単独では示さない。

Probeの妥当性確認には、Probeが表面的対応や無意味なラベルを学習しただけではないかを調べるcontrol-taskの考え方 [8]を踏まえ、少なくとも次を含める。

- matched text / different authority条件
- TF-IDF等を用いたlexical baseline
- 同じgroup構造を保ったrandom-label control
- task、attack goal、attack styleおよび近いparaphraseを跨がせないgroup-aware split
- 未知task familyまたは未知attack familyでの評価
- trainのみでの標準化、validationのみでのlayer・正則化・閾値・較正方法の選択

test setは最後に一度だけ確認し、Pilot、attack選択、layer選択または閾値調整に使用したfamilyを確認的testへ含めない。

## 7. 解析方法と対照条件

確認的主解析は一つに固定する。`B1`のtool-output内`Tpre`から事前指定した終端位置における攻撃者argument readoutの変化と、その終端位置におけるauthority readoutが、後続するdecision boundaryの`argument_slot_margin`を説明するかを評価する。終端位置は`Tend_tool`または`Tend_assistant`からvalidationで選び、IPI exposure baseline、task openness、入力長、攻撃位置および表面的特徴を共変量または層別要因として扱う。

中間層の候補領域、token位置、前処理、正則化および判定閾値はPilotとvalidationだけで決定し、そこで使用したtask/attack familyは確認的testから除外する。最終層・最終tokenのreadoutと同じ位置のLogit差は、構造的に相関し得るためsanity checkに下げ、主張の中心にしない。

主な対照条件として、無害な命令文、同じ攻撃語彙を含む説明・引用・禁止、長さを揃えた無害文、同じ内容を異なるRoleへ置いた条件、異なる言い回しの攻撃を含める。Task Drift、IPI exposure、Role readout、PCA等の可視化、群B対群D、Attentionおよび`B2_plus`は副次解析とする。全layer×全positionの探索的mapを示す場合は探索的解析と明記し、False Discovery Rateを制御する。

推論単位は個々のsurface variantではなく、taskとattack goal/styleから構成した独立clusterとする。効果量と95%信頼区間を、最高位cluster単位のBootstrapまたはPermutationで報告する。十分なcluster数と安定した推定が得られた場合だけ、変量効果モデルを補助的に用いる。

## 8. 実験規模と統計計画

12月までに主結果を確定するため、実行数を先に固定するのではなく、独立cluster数、実装時間および保存容量を優先する。単一モデル・単一ドメインについて、Activationを保存する実行の暫定総数を約450～700とする。

- Pilot：80～120実行
- Probe教師・matched control：200～300実行
- 確認的IPI：task×attack goal/styleの独立clusterを最低30、各clusterにつき3～4 surface variantを目安とする
- Clean baseline：60～100実行

最終的な配分はPilot後に凍結する。surface paraphraseだけを増やして見かけ上の標本数を大きくせず、`attack_goal_id`と`attack_style_id`を分け、多様な意味・style familyを優先する。ResistantとSusceptibleの両方が得られる意味的対応条件は最低20組、目標30組とするが、群B・群Dの件数だけを主解析の成立条件にはしない。

確率的生成は、marginが0に近い条件と各task/attackの代表条件を優先し、生成設定を固定して各10回程度行う。この補助評価では原則としてActivationを保存しない。

学習・検証・テストは暫定的に60%、20%、20%とするが、実行単位で無作為分割しない。同じtask、attack goal、attack style、pair、近いparaphraseおよび確率的反復をsplit間で分離しない。検定方法、主要な説明変数、共変量、除外規則および感度分析はtest確認前に凍結する。

## 9. 期待される成果と達成基準

攻撃失敗例でも攻撃内容自体は早期に読み出せる一方、攻撃を受け入れやすい条件では、内容の有無よりauthority readoutとargument preferenceの結び付きが中間層から後半層で強くなると予想する。また、`action_open`なtaskほど攻撃内容と正当な委任の区別が難しくなると予想する。

### 必須達成目標

- 公開LLMを用いた単一ドメインのツール利用型エージェントを構築する。
- 正確なserialized prefixとtoken位置に対応したResidual Streamを取得する。
- ユーザータスク成功、攻撃成功、A～Dおよびbaseline failureを独立に記録する。
- Task DriftまたはIPI exposure Probeを比較用baselineとして再現・評価する。
- 同一prefixから正規／攻撃canonical tool callの系列Log probabilityを評価する。

### 標準達成目標

- matched controlからaction/argument readoutとauthority readoutを構成し、lexical baselineと比較する。
- `Tpre`から事前指定した終端位置までのreadout変化と、後続するargument marginの関連を定量化する。
- task opennessとgroup構造を考慮した効果量および95%信頼区間を報告する。
- 陽性・陰性のいずれでも、goal content、authority、tool-call preferenceを区別した解釈を提示する。

### 発展達成目標

- 意味的に対応した双方向Activation Patchingによって候補状態の因果的寄与を検証する。
- 別モデルまたは別ドメインで小規模な一般化評価を行う。

## 10. 研究工程と期限

12月は追加の探索実験ではなく、執筆と再現確認に充てる。2026年9月15日時点の工程を次のように設定する。

1. 9月15日～9月27日：モデル・ドメインを選定し、AgentDojoまたは最小環境との接続、canonical tool-call scoring、成功判定を動作させる。
2. 9月28日～10月11日：80～120実行のPilotを行い、群分布、scorer、token位置、計算時間、保存容量を確認する。
3. 10月12日～10月25日：matched controlとProbeの妥当性を確認し、条件family、split、主要層・位置および主解析を凍結する。
4. 10月26日～11月15日：確認的データを収集する。
5. 11月16日～11月30日：主解析、感度分析、図表作成を行い、卒業研究の主要結果を確定する。
6. 12月：再現確認、本文執筆、関連研究の最新版・査読状況の再確認を行う。

Activation Patchingまたは別モデル・別ドメインの実験は、11月10日までに標準達成目標の解析に必要なデータが揃った場合だけ開始する。

## 11. リスク、Go/No-Go基準と代替案

- 9月末までにエンドツーエンド実行、自動成功判定またはcanonical call scoringが安定しない場合は、単一の代替ドメインまたはAgentDojo形式を参考にした最小環境へ切り替える。
- 選定モデルが決定論的設定でclean taskまたはtool callingを安定して実行できない場合は、thinking設定を混在させず、別モデルを選ぶかteacher-forced behavioral scoringを主解析とする。
- Probeが未知familyでlexical baselineを安定して上回らない場合は、「目的表現」という強い主張を下げ、具体的なtool action/argument表現またはbehavioral temporal attributionへ主題を縮小する。
- `fully_specified`または`param_open`条件でSusceptible例が不足する場合は、Pilotで事前評価したattack familyまたは強度を独立要因として追加する。test結果を見た後に条件を選び直さない。
- 全Attention保存が容量または実行時間を支配する場合は、span集約値だけを残し、Residual Streamとbehavioral scoreを優先する。
- 11月10日までに主解析用データが揃わない場合は、Activation Patching、Attention介入および別モデル・別ドメイン評価を行わない。
- Activation Patchingで効果が得られない場合も、観測解析を主成果とし、介入結果は発展的または否定的結果として報告する。

## 参考文献

[1] E. Debenedetti, J. Zhang, M. Balunović, L. Beurer-Kellner, M. Fischer, and F. Tramèr, “[AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents](https://arxiv.org/abs/2406.13352),” NeurIPS 2024 / arXiv:2406.13352, 2024.

[2] S. Abdelnabi, A. Fay, G. Cherubin, A. Salem, M. Fritz, and A. Paverd, “[Are you still on track!? Catching LLM Task Drift with Activations](https://arxiv.org/abs/2406.00799v3),” arXiv:2406.00799v3, 2024.

[3] C. Ye, J. Cui, and D. Hadfield-Menell, “[Prompt Injection as Role Confusion](https://arxiv.org/abs/2603.12277),” ICML 2026 / arXiv:2603.12277v6, 2026.

[4] Z. Chen, J. Chen, L. Luo, K. Xu, X. Huang, T. Sun, and X. Jiang, “[IterInject: Indirect Prompt Injection Against LLM Agents via Feedback-Guided Iterative Optimization](https://arxiv.org/abs/2605.24659),” arXiv:2605.24659v1, 2026.

[5] J. Dong, Y. Liu, M. Zhang, et al., “[Your Agentic LLMs Secretly Encode Indirect Prompt-Injection Exposure in Hidden States](https://arxiv.org/abs/2608.02657),” arXiv:2608.02657v2, 2026.

[6] T. Zhang, Y. Xu, J. Wang, et al., “[AgentSentry: Mitigating Indirect Prompt Injection in LLM Agents via Temporal Causal Diagnostics and Context Purification](https://arxiv.org/abs/2602.22724),” arXiv:2602.22724v1, 2026.

[7] X. Ma, T. Li, C. Xiao, Z. Yu, N. Zhang, and Y. Vorobeychik, “[AutoDojo: Adaptive Attacks Expose Superficial Defenses and User-Underspecification Limits in LLM Agents](https://arxiv.org/abs/2606.15057),” arXiv:2606.15057v1, 2026.

[8] J. Hewitt and P. Liang, “[Designing and Interpreting Probes with Control Tasks](https://aclanthology.org/D19-1275/),” EMNLP-IJCNLP 2019.

[9] F. Zhang and N. Nanda, “[Towards Best Practices of Activation Patching in Language Models: Metrics and Methods](https://arxiv.org/abs/2309.16042),” ICLR 2024 / arXiv:2309.16042, 2024.
