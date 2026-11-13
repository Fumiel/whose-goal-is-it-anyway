# 探索的活性化パッチングの実行手順

正本は[仕様](phase2_activation_patching_spec.md)と[実装指示書](phase2_activation_patching_implementation_brief.md)。
[RDR-2026-11-14-03](decisions/2026-11-14_patching_preimplementation_review_corrections.md)の修正を含む。
2026-11-14の依頼範囲はコード実装・テスト・GPU事前確認までであり、本取得は起動しない。
下記の取得・解析コマンドは、別途指示を受けてから使用する。

## 実装と計算経路

- 新モジュールは`goal_takeover.phase2.activation_patching`と`local_wording_baseline`。
- 既存`activation_hooks.py`には独立した`ResidualPatch`だけを追加した。置換フックをcaptureフックより先に登録する。
  出力をcloneして1位置のベクトルだけを書き換え、既存ResidualCaptureは変更しない。
- prefixは`[0,T)`、suffixは`[T,G]`の18token。prefixのlogitsは使わないため`logits_to_keep=1`とし、
  suffixは全18位置のlogitsを取得する。prefixとsuffixで取得位置の添字を混同しない。
- キャッシュはTransformersの`DynamicCache.crop()`でGまたはTの直前へ戻し、長さを検査する。
  同一計算の繰り返しと自己置換のビット比較で復元を検証する。
- 2候補は先の口座・後の口座の順。最初のtokenはGから、以後は前のtokenだけを`[1,1]`で入力して採点する。
  候補間の共通部分の省略・一括採点・バッチ化はしない。
- recipient先頭の`patching_recipient_first_v1`を境界確認専用に構成する。
  既存の引数名ソート方式のserializerや過去の入力は変更しない。
- 凍結宣言全体の整合性検査を行うことと、検証側run bundleを開かず、検証行を取得・fit・評価に使わないことを別々に記録する。

## 事前確認まで

実装と合成テストをコミットし、作業ツリーがクリーンであることを確認する。
コマンドはリポジトリのルートから実行する。モデル・tokenizerは固定revisionのローカルキャッシュを使用する。

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching tokenizer-preflight configs/analysis/phase2_activation_patching_v1.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching gpu-preflight configs/analysis/phase2_activation_patching_v1.json
```

出力は以下へ新規作成する。既存ファイルがあれば開始前に停止する。

- `artifacts/phase2-activation-patching-tokenizer-preflight-<commit7>.json`
- `artifacts/phase2-activation-patching-gpu-preflight-<commit7>.json`

GPU事前確認はcondition ID昇順の先頭2条件について、正常計算、90介入、正常再確認を実行する。
必要なmatched/cross donorの訓練側条件も正常計算だけ行う。追加donorと繰り返し検査の時間は別記する。
正常LD・delta・介入効果はレポートへ出さない。残差の既存値との差、分布の一致・checksum、時間・メモリだけを記録する。
失敗時も新しい事前確認レポートを保持し、本取得へは進まない。修正が必要な場合はコードを別commitとし、
古い事前確認レポートを上書きせず、そのcommitの事前確認を実行する。

事前確認の合格条件は自己置換30セルの厳密一致、キャッシュ復元の厳密一致、G最終層の全語彙分布のdonorとの一致、
GPU 12 GiB以内、2パス合計の1条件600秒以内である。時間上限だけを[RDR-2026-11-14-04](decisions/2026-11-14_patching_time_limit_revision.md)で300秒から改訂した。先頭2条件の合格は他条件の上限保証ではない。
今回の実行ではここで止める。局所文言ベースラインの本実行も行わない。

旧300秒での失敗レポートは保持する。上限改訂後は、改訂をコミットしたクリーンなHEADで両事前確認を新規実行し、
新しいcommit名のレポートを作る。過去のfailedをpassedへ書き換えたり、旧レポートを新しい上限で再判定したりしない。
SSH端末への依存を避ける再実行では、`set -o noclobber`のうえで`nohup setsid --wait env ...`を使い、
stdout/stderrをWSL側の新規ログへ保存してstdinを`/dev/null`へ向ける（[再確認記録](experiment_logs/2026-11-14_activation_patching_preflight_recheck.md)と同じ方法）。

## 本取得の準備と実行（別途指示が必要）

事前確認と同じクリーンなcommitで環境lockを新規作成する。

```bash
set -o noclobber
.venv/bin/pip freeze > artifacts/phase2-activation-patching-environment-<commit7>.lock
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching freeze configs/analysis/phase2_activation_patching_v1.json --tokenizer-report <path> --gpu-report <path> --environment-lock <path>
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching capture configs/analysis/phase2_activation_patching_v1.json --runtime-freeze <path>
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching collection-manifest configs/analysis/phase2_activation_patching_v1.json --runtime-freeze <path> --output data/manifests/<date>_phase2_activation_patching_collection.json
```

freezeは`artifacts/phase2-activation-patching-runtime-<commit7>.freeze.json`へ新規作成する。
新しいcommitでは事前確認を実行し直し、別freezeを作る。旧freezeを更新して対応させない。
本取得開始は2026-11-20 23:59 JSTまでにcaptureを起動した時点とし、事前確認の起動とは区別する。

本取得は全240条件のdonor正常計算を先に実行し、CPUに正常残差と分布を保持してから介入する。
1条件につき1個の不変bundleを作る。完了済みbundleは来歴・checksum照合後にスキップする。
技術失敗は第1パスも含めて不変bundleに保存して停止する。失敗済みIDの再利用は認めない。
再開時もdonorの正常計算は作り直すが、既存bundleは変更しない。

## 解析（別途指示が必要）

収集manifestと記録を別commitへ保存し、取得とは異なるクリーンなcommitで一度だけ実行する。

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching analyze configs/analysis/phase2_activation_patching_v1.json --runtime-freeze <path>
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.local_wording_baseline run configs/analysis/phase2_activation_patching_v1.json
```

出力は`artifacts/processed/argrec672-v1-dg-009-patching/`と`argrec672-v1-dg-010-local-wording-baseline/`。
既存出力があれば計算前に停止する。元データや過去の判定を上書きしない。
G最終層の陽性対照は口座全体のP-STRONGと独立に確認する。書き出しの崩れも破壊判定に含める。
crossは同じ口座・順序の別文脈への移動として記述し、提示順と口座identityの分離や文脈の必要性を主張しない。
