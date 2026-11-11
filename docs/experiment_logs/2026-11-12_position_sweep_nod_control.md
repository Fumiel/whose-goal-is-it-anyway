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
