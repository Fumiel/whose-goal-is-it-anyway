# Banking pilot capture修正後の実行前計測（2026-10-02）

この記録はWSL2のRTX 5060 Tiと暫定Qwen3-8B int8による工学検証であり、
新しいpilotのモデル行動結果ではない。標本・payload・停止規則と旧raw runは変更していない。
実行時のTransformersは4.57.6、PyTorchは2.10.0+cu128、AgentDojoは0.1.35。
実行codeはこの記録の作成時点で未commitであり、別runtime freezeも未作成である。
出発点と失敗理由は[最初の計測](2026-10-02_pilot_preflight_measurements.md)を参照する。

## Attentionの数値照合

`sdpa`を使ったモデル出力を維持し、Qwen3各層の入力から最後のqueryだけの
Q/K・RoPE・mask・softmaxを再計算した。173-tokenの短い入力について、**同じ
`eager` forward pass**で得た全36層のlast-query weightsと照合し、最大絶対差は
`3.0517578125e-05`だった。確率和の最大誤差は`0.00238895`で、BF16重みの丸めを含む。
別passの`sdpa`と`eager`は、量子化・実装差を含むため最終logitの最大差が`0.765625`、
Attention重みの最大差が`0.115234375`だった。この別pass差をhookの誤差と解釈しない。
同一pass照合は重みの再計算式を確認するが、長い実prefixの全値との逐一照合や
Attentionに基づく因果性を示さない。

| native固定prefix 2,082 token | 左右幅 | 選択位置 | 残差の直列化量 | GPU peak reserved | capture時間 |
|---|---:|---:|---:|---:|---:|
| 通常capture・全36層・範囲集約Attention | 16/16 | 130 | 38,341,816 B | 11,530,141,696 B（10.74 GiB） | 1.667秒 |
| 同上 | 32/32 | 146 | 43,060,408 B | 11,530,141,696 B（10.74 GiB） | 1.587秒 |
| 全sequence・全36層残差の独立計測 | 全2,082 | 2,082 | 614,010,152 B（585.6 MiB） | 11,530,141,696 B | 2.264秒 |

通常captureでは全Attention行列を保存していない。全sequence残差は有限値であり、
通常の0.05 GiB（51.2 MiB）には入らないが、別の1.5 GiB枠に入る。

## 一条件のbundle計測

先行IPI `banking_pilot_v1_4bcd2e89355ab958`で、native tool返却と実モデルの
capture・候補系列採点を使い、**エージェント行動だけをscript**してbundleを作った。
固定prefix診断は採点・token位置のみで、残差・Attentionの重複保存はない。
4測定を含み、所要46.76秒、GPU peak 12,022,972,416 B（11.20 GiB）、
bundle 39,683,252 B（37.845 MiB）で、通常の300秒・12 GiB・0.05 GiB以内だった。
これは選んだ一条件の工学試験であり、先行18すべての資源保証ではない。
script行動、採点margin、成功・失敗を研究結果へ使わない。

## 採用する範囲と未完了gate

[RDR-2026-10-02-01](../decisions/2026-10-02_pilot_capture_resource_revision.md)で通常IPI windowを
左右16 token、完全Attention 0件、通常run内の全sequence残差0件、固定prefixからの
別派生詳細取得を四task系列各一件と決めた。保存量にはJSON・manifest等も含めて
通常runの0.05 GiB上限を適用する。派生bundleには別上限とsource checksumを適用する。

修正後の`unittest`・`pytest`は各90件成功した。`compileall`、Ruff、repository宣言、
標本freeze照合も成功した。詳細経路のsource同一性・欠測・immutable処理はunit testで
確認した。新しいpilot sourceに対する詳細GPU取得は、先行runがまだないため未実施である。
task 14の人手審査、cleanな実行commit・runtime freezeは後続のgateである。
これらの前にpilotを開始しない。

測定の小出力と実験用scriptはGit対象外の
`artifacts/preflight/2026-10-02_capture_repair/`に保存した。4出力のSHA-256は順に、
`pilot_query_attention_gpu_20261002.jsonl`が
`adace7512896fbb63f40ddfd802601aa7ee9446bfeb1e9485cd71798d8f6fc38`、
`pilot_attention_same_pass_20261002.json`が
`8b40ee44b237bf854ab96ceed6cc1cac90b251dfd196a3aaee8560c112d27f54`、
`pilot_full_residual_gpu_20261002.json`が
`9d22eae68d062e11860a095ac5be36b5de3b8b3efcd14bab2236253ce3af7ca4`、
`pilot_full_bundle_gpu_20261002.json`が
`4639e1792b264b69954ef2ca73ebc341ccbff4bfbfde4293f7d452f8b09bffdc`である。
これらは工学試験の出力であり、raw pilot runではない。
