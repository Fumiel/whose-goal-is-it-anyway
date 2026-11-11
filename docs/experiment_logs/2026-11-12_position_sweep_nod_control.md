# D除外対照の取得・比較（2026-11-12）

[仕様](../phase2_position_sweep_nod_control_spec.md)、[実行手順](../phase2_position_sweep_nod_runner.md)、
[RDR-2026-11-12-02](../decisions/2026-11-12_nod_control_preimplementation_corrections.md)に従う。
研究実施者は4点の修正・文書コミット後の実装と本実行を指示した。
これは手順3の結果を見た後のtrainのみの技術対照であり、独立検証・確認的testではない。

## 実装と事前確認

- 文書修正commit：`3f97be1`。実装・取得commit：`0aa063a583cb2e6e186efc1f8196fbd75983f1c0`。
- 既存出力との互換性は変更前に作った合成fixtureのcanonical JSONとの一致で確認。
  既存テストの変更なし。pytest 277件成功、標準Pythonのunittest 277件成功（62 skip）、compileallとruff検査も成功。
- トークン化事前確認：240条件すべて、既存ps-001入力・位置・manifest・freezeを照合して合格。
  再現性対象はdraft_task_id昇順の先頭5対の10条件で、条件ID一覧を事前確認レポートに固定した。
- GPU事前確認：先頭2条件とも非有限値なし、最大9.254876 GiBで12 GiB上限内。
  D除外の末尾2位置に`logits_to_keep=2`が使われた。
- 環境：Python 3.12.3、torch 2.10.0+cu128、Transformers 4.57.6、bitsandbytes 0.50.2、
  CUDA 12.8、NVIDIA GeForce RTX 5060 Ti。CUDAの使える制限外環境でGPU処理を実行。
- referenceは旧runtime freeze・旧収集manifest・dg-006・旧GPU事前確認の4ファイル。
  GPU事前確認は旧runtime内のchecksumとも一致。参照ファイルのSHA-256を新freezeに固定した。

新freeze：`artifacts/phase2-position-sweep-nod-runtime-0aa063a.freeze.json`。SHA-256：`6078989f3c56f936e764760c43de3a6de7044836c4acbd123a2c75d3d2266367`。
事前確認と環境lockのパス・checksumはfreezeと取得manifestに保存した。いずれも新規作成のみ。
既存の正準003・ps-001・dg-006・旧freeze・旧収集manifestは変更していない。

## 取得・照合の完了

同じプロセスでモデルを1回読み込み、ps-003の再現性10条件→ps-002のD除外240条件の順で取得。
GPU取得コマンドは一度正常終了した。自動再試行なし、技術失敗0。
ログは`artifacts/phase2-position-sweep-nod-capture-0aa063a.log`に新規保存した。
そのSHA-256は`d5f03ad2d15ea6dbf7a731f1c1426e2c3f5d5764120ebe7287bb5e3cecd19b78`。
bfloat16入力を内部でfloat16へcastするbitsandbytesの警告が出たが、非有限値はなかった。

[取得manifest](../../data/manifests/2026-11-12_phase2_position_sweep_nod_collection.json)を作成し、250件すべてについて照合した。

- ps-003：全36層、`[1,6,4096]`、bfloat16。既存ps-001と完全に同じ入力列と位置。
- ps-002：全36層、`[1,5,4096]`、bfloat16。入力列は既存から末尾Dの1 tokenだけを除いたもの。
- 全artifactのchecksum、入力列のchecksum、条件・pair・正準prefix・freeze・commit・位置名・token index/IDを照合。
- 全残差が有限。検証行の読み込み0。
- 保存量：380,165,854 bytes。最大GPUメモリ：9.268067 GiB。
  1条件の最大時間：17.354224秒（初回のモデル読込を含む）。各資源上限内。
- 取得manifestのSHA-256：`ce5983bcf5a9d4a76d47caacdccc79fa44023e92923369c2462766f33161ffdf`。

## 比較前の記録

この取得記録を別commitへ保存してからcompareを一度実行する。比較コード・設定・仕様は取得commitから変えない。
Rは同じ入力の再実行差、NはD除外と既存値の差、Pは共通の後続tokenを足した入力のTと正準Tの差である。
P/Nを寄与割合に分解しない。Pを再実行ノイズと呼ばない。
厳密ビット比較でR-EXACTかつN全件一致の場合のみ①として再解析を省く。
それ以外はノイズ幅以内でも再解析を一度行い、旧dg-006と②/③を比較する。
Δからのラベル読み取りは非ゼロの判定セル全体で補正して併記するだけで、判定には使わない。
A1/A2の局所文言による説明とH1の証拠にしない留保は、いずれの分類でも維持する。
この段階では比較・再解析のfitは未実行である。

## 比較と再解析の完了

解析commitは`eeb09e79a5319868a1b276ce7a3e40429470454e`。取得commitからの差は取得記録と状態更新のみで、
コード・設定・仕様を変えず、クリーンな作業ツリーでcompareとreanalyzeをそれぞれ一度実行し正常終了した。
BLAS3変数は1。検証行の読み込み0。収束警告・例外は出ていない。

- [比較dg-007](../../artifacts/processed/argrec672-v1-dg-007-nod-comparison/report.json)：8,418,801 bytes、
  SHA-256 `2b07d1943c400f5a67650f7b97f61d2bc5250d7131e0a407ba63b669d02a3d94`。
- [再解析dg-008](../../artifacts/processed/argrec672-v1-dg-008-position-sweep-nod/report.json)：172,386 bytes、
  SHA-256 `6e38ae09b3ba7dae07bb4d910d67e1094525dad76db18f81eef0091a7179a30c`。
- [小さい要約](../../results/2026-11-12_phase2_position_sweep_nod_control_v1.json)：77,770 bytes、
  SHA-256 `d68ace2ce00af3068bde172224fcf99fa597b7f09651f5db7dff7815a41cfb3d`。
- 比較ログ：`artifacts/phase2-position-sweep-nod-comparison-eeb09e7.log`、SHA-256 `0dd9ac44a09abaaa9fc5541fcd38c37f367c91a48e820d78fe60dfd3dcb76188`。
- 再解析ログ：`artifacts/phase2-position-sweep-nod-reanalysis-eeb09e7.log`、SHA-256 `4573119dcfde50cbeafd7733e994b65fa982bb45bae83323613e22a1abb69faf`。

派生manifestに記録されたreportのSHA-256・容量と、要約の来歴が一致することを確認した。
比較にはps-001の240件、ps-002の240件、ps-003の10件、正準Tの240件を使用した。
再解析でも入力の対応・manifest・freezeを再照合し、比較と同じ取得bundleの集合であることを確認した。

### 再現性と入力変更の差

下表の件数は条件×位置×層のベクトル数で、独立標本数を意味しない。

| 比較 | 対象ベクトル数 | ビット一致数 | 最大相対L2差 | 最大絶対差 |
|---|---:|---:|---:|---:|
| R：同じ入力の再実行 | 2,160 | 2,160 | 0.000000 | 0.0 |
| N：D除外 vs D入り | 43,200 | 25,445 | 0.210123 | 152.0 |
| P：共通後続tokenありのT vs 正準T | 8,640 | 7 | 0.267625 | 56.0 |

Rは10条件・6位置・全36層すべてで厳密ビット一致し、**R-EXACT**だった。
Nの最大相対L2差はA1 0.210123、A2 0.193591、T 0.169413、S 0.114236、G 0.111197。
Nが全件一致ではないため①には該当せず、固定規則に従いD除外の再解析を行った。
P/Nはそれぞれ異なる基準ベクトルで正規化した、別々の入力変更の大きさである。
これらのノルムを加算したり、旧T差への寄与割合を計算したりしていない。Pを再実行ノイズとも扱わない。
旧GPU事前確認の2条件の層別値との対応は、比較reportの`original_preflight_conditions`に保存した。

### Δのラベル読み取り（併記のみ）

42判定セル中、非ゼロ差分の36セルでfitし、ゼロ差分の6セルは計算から除外した。
36セル全体の最大統計量で100回の系列反転を補正した。最高対内正解率は0.6250、
最小family-wise pは0.237624で、有意なセルは0件だった。
今回の線形probe・標本・反転検定で有意に読めなかったという結果であり、差にラベル情報が存在しない証明ではない。
この結果は①〜③の判定に使っていない。

### D除外による再解析

| 位置 | D除外のR判定 | 最高対内正解率 | 層/probe | bootstrap 95%区間 | family-wise p |
|---|---|---:|---|---|---:|
| A1 | R1 | 1.0000 | 16/logistic | 1.0000–1.0000 | 0.009901 |
| A2 | R1 | 1.0000 | 32/logistic | 1.0000–1.0000 | 0.009901 |
| T | R2 | 0.8583 | 24/logistic | 0.8000–0.9167 | 0.009901 |
| S | R1 | 0.9833 | 24/logistic | 0.9583–1.0000 | 0.009901 |
| G | R1 | 0.9917 | 16/logistic | 0.9750–1.0000 | 0.009901 |

精度は各位置の判定セル中の最高値。Dがないため報告セルは60、判定セルは42。
層・C・seed・閾値・系列bootstrap 2,000回と反転100回は手順3のまま。
位置baselineは0.8125で変わらず、R1には0.9125以上が必要なためTはR2になる。
同位置Gロジットは対内正解率0.9667、プールAUROC 0.9930。
同じT/layer24/logisticは旧D入り0.8083→D除外0.8583だった。位置全体の旧最高値0.8417は層32であり、
異なる層の最高値同士を同一セルの再測定として扱わない。

5位置のR判定と仮説対応づけのrule/mappingはすべて旧dg-006と一致した。
したがって分類は **② 数値は変わるが判定は同じ**（`2_numeric_only`）、変更項目は空である。
形式上の対応づけは引き続き規則3の`H1_consistent`だが、A1/A2は局所文言で説明できるという既存の留保を維持し、
H1の証拠にはしない。①の「影響なし」や、Dが先行位置に影響しないという結論にはしていない。

### 引き継ぎ

仕様8節に従い、今後のパッチング候補はD除外のdg-008を参照する。
局所文言の問題があるA1/A2を根拠にH1を採用せず、S/G/Tを中心に別のパッチング仕様で検討する。
今回の対照だけでは量子化処理のどの部分が差を生じさせたか、goalが採用されたか、因果的な選択時点は分からない。
独立validation、非量子化比較、パッチング、新しい設定での再実行は行っていない。
③ではないため旧手順3の判定の訂正は行わず、旧report・取得データをそのまま保存する。
