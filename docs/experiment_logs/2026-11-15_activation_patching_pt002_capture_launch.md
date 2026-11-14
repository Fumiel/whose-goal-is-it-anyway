# pt-002本取得の起動（2026-11-15）

[RDR-2026-11-15-01](../decisions/2026-11-15_patching_capture_recovery_and_retry.md)の実行順序3・4にあたる記録。
研究実施者の指示により、Claude Codeが環境lockとruntime freezeを作成し、本取得は研究実施者がtmux内で手動で起動した。
本記録は起動時点の事実だけを記録し、完了状況・介入効果は含まない。

## 環境lockとruntime freeze

[段階Aの事前確認](2026-11-15_activation_patching_pt002_preflight.md)と同じcommit `0b99c17`
（`0b99c178ba374489f99fdd6d634add0ff465bd77`）をdetached HEADでcheckoutし、作業ツリーがcleanな状態で作成した。

```bash
set -o noclobber
.venv/bin/pip freeze > artifacts/phase2-activation-patching-environment-0b99c17.lock
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.activation_patching freeze configs/analysis/phase2_activation_patching_v1.json --tokenizer-report artifacts/phase2-activation-patching-tokenizer-preflight-0b99c17.json --gpu-report artifacts/phase2-activation-patching-gpu-preflight-0b99c17.json --environment-lock artifacts/phase2-activation-patching-environment-0b99c17.lock
```

| 出力 | bytes | SHA-256 |
|---|---:|---|
| [環境lock](../../artifacts/phase2-activation-patching-environment-0b99c17.lock) | 2897 | `b8da0f1bc1f7112ef576a833e455fffb3a7c76218804f571a78d9a8482fbbb8d` |
| [runtime freeze](../../artifacts/phase2-activation-patching-runtime-0b99c17.freeze.json) | 2417 | `d718cec44eb37472a71d4c0eec3ee91bba5bb4766de96f9ebd69b0c0132e3915` |

freezeの状態は`frozen`、commitは`0b99c17`。上限はGPU 12 GiB・1条件600秒・保存0.05 GiB/条件・全体2.0 GiB、デコードは決定的。
本取得と同じ照合（`load_plan(..., matching=True)`）でモデルを読み込まずに読み込めること、
240条件すべてが1回目の試行として未実行（既存試行0件、先頭`argrec672-v1-pt-002-c368`）であることを確認した。

## 起動

研究実施者が既存のtmuxセッション`goal-takeover`内で、`0b99c17`のcleanな作業ツリーから次を実行した
（`tmux new -s pt002`は入れ子のため作成されず、既存セッションで実行した）。

```bash
set -o noclobber
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.activation_patching capture configs/analysis/phase2_activation_patching_v1.json --runtime-freeze artifacts/phase2-activation-patching-runtime-0b99c17.freeze.json > artifacts/phase2-activation-patching-capture-0b99c17.log 2>&1 < /dev/null; echo "PATCHING_EXIT_CODE=$?" >> artifacts/phase2-activation-patching-capture-0b99c17.log
```

- Pythonプロセスの開始：**2026-11-15 03:42:14 JST**（PID 40193、親はtmuxサーバー配下のbash）
- 起動確認時（03:44 JST頃）：donor正常計算22/240、1件約5.3秒、MemAvailable約8.7 GiB、swap使用量0
- 実行ログ：`artifacts/phase2-activation-patching-capture-0b99c17.log`

仕様の開始の定義（clean commitと対応するruntime freezeのもとで、2026-11-20 23:59 JSTまでに本取得コマンドを起動する）は、
`pt-001`（2026-11-14）に続き、`pt-002`でも満たした。

## 以後の運用

RDR-2026-11-15-01の段階Bとして、最初の20件を監視区間とし、手動停止基準(a)〜(d)を適用する。
手動停止・技術失敗・再試行があれば、別の実験ログに時刻・理由・確認した値を記録する。
実行中は実行用の作業ツリーで`git checkout`等を行わない。本記録は別のworktreeで`main`にコミットした。
