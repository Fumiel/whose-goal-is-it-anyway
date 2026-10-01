# Banking pilot実行前のnative・token・GPU実測（2026-10-02）

研究結果ではなく、凍結済み標本を実行する前の工学確認である。実軌跡のpilot runは開始していない。
標本freezeは`7c8ca1ad4e8c2eadd8344fa70e6641be0b5da495b9bbbbd81e5ef3eb1525d044`で、
標本・payload・停止規則は変更していない。測定時のHEADは
`103f92345509719da65449e1e98d96a7a14149ba`で、pilot native sessionの修正は未commitだった。
修正後の`src/goal_takeover/pilot/preflight.py`のSHA-256は
`1841a6826b2f9473cba5ca9593325648f0f4f369e1aebdaecc9d93a23c09a4e9`。

## 標本とnative評価器

- オフラインfreeze照合は成功した。90条件はclean 6、IPI 72、語彙対照12、先行18、
  task系列4、関係graphの連結成分1だった。
- 当初のnative preflightは、AgentDojoがpayloadを二重引用符付きYAMLへ展開する際、
  pilotの生の引用符・改行で構文エラーになった。cleanの一部では改行の折り畳みにより
  tool返却と宣言vectorの文字列照合も失敗した。
- pilot sessionだけでYAML用にエスケープし、元の標本文字列が環境から返ることを
  integration testで確認した。旧shakedown設定は既にエスケープ済みなので、
  共通AgentDojo adapterの挙動は変更していない。
- 修正後の`pilot-preflight`は**全90条件×5対照**で成功した。各条件で
  無操作・誤対象はnative user/attackともfalse、正規候補はuserのみtrue、
  攻撃候補はattackのみtrue。正規操作と禁止副作用の併発ではnative userはtrueだが
  厳密userはfalseであり、想定した判定差を別々に保持した。
- task 14の不審取引の根拠と人手監査rubricは別途未承認。native対照成功はその承認を代替しない。

native対照の全出力はGit対象外の
`artifacts/preflight/2026-10-02_pilot_native_controls.json`に保存した
（SHA-256 `f2f6add8ce207f4ffad03c647830b9ff3857856ee67b5ab9dd0de8bc1cbacb3c`）。

## 固定tokenizerと入力一致

Qwen3-8Bの固定revision `b968826d9c46dd6066d109eabc6255188de91218`を使用した。
chat templateのSHA-256は`a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8`。

- 先頭・中央・末尾・日英混在・短いtoken境界の5小例で、直列化textへのround-tripと
  `Tpre`、`Tpost`、`Tend_tool`、`Tend_assistant`の選択が成功した。末尾IPI例では
  `Tpost=Tend_tool`、他の例では別位置になった。
- 全90条件について、native ground-truthの最初のtool返却と実tool schemaを使った
  固定prefixを直列化し、位置選択が90/90成功した。IPI 72・語彙対照12では
  4位置、clean 6では`Tend_tool`と`Tend_assistant`を得た。系列長は
  **1,577～2,082 token**、IPI範囲は**36～105 token**だった。
- 2,082 tokenの一条件`banking_pilot_v1_e07b21287d62fb48`では、生成の入力、
  残差取得、候補採点のprefix token ID列が一致した。生成は入力検証用に1 tokenで
  打ち切ったため、tool call構文解析は未完了となった。この実行を行動結果に使わない。
- 同条件の候補採点はrecipientとamountの各slot、joint、whole callで有限値を返した。
  margin値は工学確認に限り、研究結果として解釈しない。

## GPU・保存容量

WSL2上のRTX 5060 Ti（16,310 MiB）、PyTorch 2.10.0+cu128、
AgentDojo 0.1.35、Transformers 4.57.6で、暫定Qwen3-8B int8を使用した。
GPU preflightは成功し、BF16対応を確認した。

| 工学用入力 | 測定 | 時間 | GPU peak reserved | 保存量 |
|---|---|---:|---:|---:|
| 372 token | 全36層・4位置の残差 | 0.897秒 | 9.19 GiB | 1.13 MiB |
| 372 token | 全36層・全sequence残差 | 0.389秒 | 9.19 GiB | 104.63 MiB |
| 372 token、診断用`eager` | Attention集約 | 0.292秒 | 9.69 GiB | 集約値のみ |
| 372 token、診断用`eager` | 全層・全head Attention | 0.724秒 | 9.69 GiB | 304.07 MiB |
| 1,307 token | 全sequence残差 | 1.275秒 | 9.90 GiB | 367.60 MiB |
| 1,307 token、診断用`eager` | Attention集約 | 0.662秒 | **13.39 GiB** | 集約値のみ |
| native固定prefix 2,082 token | 左右32 tokenの選択残差、146位置 | 1.480秒 | **10.74 GiB** | **41.07 MiB** |
| native固定prefix 2,082 token | 2 slotの候補系列採点 | 37.952秒 | **10.74 GiB** | 採点記録のみ |

時間は個別操作の計測であり、1条件の総所要時間ではない。
左右0/8/16/32 tokenをnative固定prefix全90件の位置集合に適用した計算では、
最大の残差保存見積もりはそれぞれ30.38/34.32/37.41/41.91 MiBだった。
これは残差tensorの見積もりで、JSON、採点、Attention、失敗bundleを含まない。

現行の`sdpa`設定ではTransformers 4.57.6が`output_attentions=True`でもweightsを返さず、
runnerのAttention hookが停止した。診断用`eager`ではweightsを取得できたが、
1,307 tokenで凍結済みGPU上限12 GiBを超えた。実native固定prefixは最短でも
1,577 tokenなので、現行のAttention方式をそのままpilotへ適用できるとは言えない。
全sequence残差も、実prefix長と36層×4096次元×BF16からのtensor本体だけで
約443.5～585.6 MiBとなり、1条件保存上限0.05 GiB（51.2 MiB）に収まらない。
全Attention詳細保存は372 tokenの小例だけでも304.07 MiBである。

GPU計測の小出力はGit対象外の`artifacts/preflight/`に保存した。
`2026-10-02_gpu_synthetic_measurements.jsonl`のSHA-256は
`e779f70e9cda69663d88946550ec52e5d2e8a01bf1a392cb663ada1eab8f9a29`、
`2026-10-02_gpu_fixed_prefix_measurement.jsonl`は
`19f6edad33fbb46317178600f2e0bbf6305df6a66626340645249bfdf34553dd`、
`2026-10-02_gpu_generation_input.json`は
`13a48f0b62058ec0672dd54f8daf3232f44446ca108db8445bfea4b09874e772`。

## 判定と残るgate

標本照合、native 90条件対照、固定tokenizerによる固定prefix位置対応、
一条件での生成・残差・候補採点入力一致は確認できた。
window左右幅、全sequence・全Attention保存subset、Attention実装と資源上限の整合、
task 14の人手審査、runtime code/config freezeは未完了。
現時点でpilotのモデル実行は開始しない。保存範囲やAttention方式を変更する場合は、
実装・テストと計測を終えてから別runtime freezeへ記録する。
