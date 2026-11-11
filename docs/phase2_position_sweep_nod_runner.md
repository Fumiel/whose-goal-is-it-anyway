# D除外対照の実行手順

[仕様](phase2_position_sweep_nod_control_spec.md)と[指示書](phase2_position_sweep_nod_control_implementation_brief.md)、
[RDR-2026-11-12-02](decisions/2026-11-12_nod_control_preimplementation_corrections.md)を正本とする。
研究実施者はレビュー修正のコミット後の実装と本実行を指示した。パッチングは今回の範囲に含まない。
既存のps-001、正準003、dg-006、旧freeze・収集manifestは読み取り専用である。

## 実装と互換性

- 新規設定：`configs/analysis/phase2_position_sweep_nod_v1.json`。モデルと解析値は既存sweep_configから読む。
- 新規処理：`src/goal_takeover/phase2/position_sweep_nod.py`。入力・参照照合、事前確認、freeze、250件取得、
  collection manifest、ベクトル比較、Δのラベル読み取り、条件付き再解析とCLI。
- 一般化：`position_sweep_capture.forward_capture`（末尾2/3位置のlogit）と位置数可変のschema確認。
  既存capture_conditionの出力は保存済み合成fixtureのcanonical JSONと比較する。
- 一般化：`position_sweep_analysis.analyze`と`validate_inputs`のkeyword-only position_names。
  既定6位置の出力は変更前に生成した合成fixtureとバイト一致することを検査する。
- 新規テスト：`tests/test_position_sweep_nod.py`。既存テストは変更しない。
  合成fixtureの由来は`tests/fixtures/position_sweep_nod_legacy_README.md`。

テストの対応：位置・先頭5対・参照照合は仕様2/3節、順伝播・freeze・不変保存は3節、
厳密ビット比較・名前による対応は4節、Δのゼロセル除外と全体補正は5節、
出力互換性・設定維持とfit前停止は6節、再解析条件と②③の判定は7節。
+0/-0はint16としてビットを比較し区別する。R-NOISEでは観測幅以内でも再解析する。
P/Nを寄与割合へ分解せず、Pを再実行ノイズと呼ばない。

実装上の補足：既存writer・bundle構成・logit計算・probe計算を再利用する。
失敗は来歴と例外を持つ小さいfailure bundleとして保持し、停止する。
比較は全36層の各条件値と位置×層の集計を保存する。Δのfitは判定42セル中の非ゼロセルだけとし、
その最大統計量で補正する。ゼロセルだけならfitせず帰無配列は空とする。
比較と再解析はmanifest、runtime freeze、入力列、旧収集manifestのSHA-256まで照合する。
R-EXACTかつN全件ビット一致の場合だけ再解析を省き、それ以外は1回実行する。

## 事前確認・取得（同一のクリーンなcommit）

リポジトリ直下で実行する。全パスは相対で、絶対パス・`..`・外部symlinkを拒否する。
`<commit7>`は取得commitの先頭7文字に置き換える。レポートとfreezeは新規作成のみ。
GPUが制限環境内で利用できない場合、同じコマンドを承認された制限外環境で実行する。
ローカルのモデルを使う場合は`HF_HUB_OFFLINE=1`を指定できる。

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod tokenizer-preflight configs/analysis/phase2_position_sweep_nod_v1.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod gpu-preflight configs/analysis/phase2_position_sweep_nod_v1.json
set -o noclobber
.venv/bin/python -m pip freeze > artifacts/phase2-position-sweep-nod-environment-<commit7>.lock
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod freeze configs/analysis/phase2_position_sweep_nod_v1.json --tokenizer-report artifacts/phase2-position-sweep-nod-tokenizer-preflight-<commit7>.json --gpu-report artifacts/phase2-position-sweep-nod-gpu-preflight-<commit7>.json --environment-lock artifacts/phase2-position-sweep-nod-environment-<commit7>.lock
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod capture configs/analysis/phase2_position_sweep_nod_v1.json --runtime-freeze artifacts/phase2-position-sweep-nod-runtime-<commit7>.freeze.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod collection-manifest configs/analysis/phase2_position_sweep_nod_v1.json --runtime-freeze artifacts/phase2-position-sweep-nod-runtime-<commit7>.freeze.json --output data/manifests/2026-11-12_phase2_position_sweep_nod_collection.json
```

出力：`artifacts/phase2-position-sweep-nod-*-<commit7>.*`のレポート・lock・freeze、
`artifacts/runs/argrec672-v1-ps-003-cNNN`の再現性10件、`argrec672-v1-ps-002-cNNN`のD除外240件。
再現性10件→D除外240件の順に、モデルを1回だけ読み込む。
資源上限は各300秒・0.05 GiB、総量2 GiB、GPU12 GiB。自動再試行なし。
完了済みはchecksumと来歴を検査してスキップし、失敗済みは新IDでのやり直しを要求する。

取得manifestと実行ログをコミットし、次の解析は別commitのクリーンな作業ツリーで行う。

## 比較と条件付き再解析（それぞれ一度）

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod compare configs/analysis/phase2_position_sweep_nod_v1.json --runtime-freeze artifacts/phase2-position-sweep-nod-runtime-<commit7>.freeze.json
```

出力は`artifacts/processed/argrec672-v1-dg-007-nod-comparison/report.json`。
`report.reanalysis_required`が真の場合のみ次を実行する。偽ならfit前に拒否する。

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod reanalyze configs/analysis/phase2_position_sweep_nod_v1.json --runtime-freeze artifacts/phase2-position-sweep-nod-runtime-<commit7>.freeze.json
```

出力は`artifacts/processed/argrec672-v1-dg-008-position-sweep-nod/report.json`。
BLAS3変数はimport前にも未設定なら1に設定するが、コマンドでも明示する。
既存出力はfit前に拒否する。検証条件は読み込まない。

結果はtrainのみの結果閲覧後の技術対照である。D除外で判定が変わる場合は新しい結果を基準値として、
旧ログに訂正を追記する。元のreportと取得データは変更しない。
Dの影響の有無にかかわらず、A1/A2の局所文言の説明とH1の証拠にしない留保を維持する。
小さい要約は`results/`、実行・検証記録は`docs/experiment_logs/`へ保存する。

## 実装検証（2026-11-12、合成CPU試験）

- unittest：`Ran 277 tests in 8.022s`、`OK (skipped=62)`（標準Python）。
- compileall：成功。
- ruff check：`All checks passed!`。
- ruff format --check：`286 files already formatted`。
- pytest：`277 passed in 34.91s`（研究用依存関係のある.venv）。
- 既存テストの変更なし。新規15テストは合成データのみであり研究結果ではない。

初回の新規テストは`2 failed, 12 passed, 3 subtests passed`だった。
1件は不完全対を作るfixtureが選択対象外の対を削っていたこと、もう1件は合成freezeに
`files_sha256`がないこと（`KeyError: 'files_sha256'`）が原因だった。
fixtureを修正して上記の全件検証を実施した。
