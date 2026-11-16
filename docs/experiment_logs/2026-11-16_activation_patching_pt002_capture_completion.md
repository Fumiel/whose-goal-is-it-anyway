# pt-002本取得の完了（2026-11-16）

[RDR-2026-11-15-01](../decisions/2026-11-15_patching_capture_recovery_and_retry.md)の実行順序4にあたる、
`argrec672-v1-pt-002`本取得の完了記録。起動は[起動記録](2026-11-15_activation_patching_pt002_capture_launch.md)にある。
研究実施者の指示により、Claude Codeが実行中の確認と完了後の検査を読み取り専用で行い、本記録を作成した。

本記録は工学的な実行記録であり、研究結果ではない。確認したのは、プロセスの状態、実行ログ、
各bundleの`run.json`の時間・メモリ・来歴・ログ制限の項目、`manifest.json`が宣言するファイルのサイズとchecksum、
`dmesg`、`nvidia-smi`だけである。`results.json`の内容は開いておらず、正常LD・delta・介入効果は集計していない。
collection manifestとパッチング解析は未実行である。

## 完了状況

| 項目 | 値 |
|---|---|
| 開始 | 2026-11-15 03:42:14 JST（PID 40193） |
| donor正常計算 | 240/240、04:03:34 JSTに完了。1件5.14〜6.02秒、合計1252.1秒 |
| 最初のbundle | `argrec672-v1-pt-002-c368`、介入段階の終了は04:10:31 JST |
| 最後のbundle | `argrec672-v1-pt-002-c363`、ログ上の完了は2026-11-16 08:11:49 JST |
| 終了 | ログ末尾は`240`と`PATCHING_EXIT_CODE=0` |
| 経過時間 | 約28時間30分 |
| 状態 | 240/240がcompleted。技術失敗0、再試行（`-a2`）0、run単位の失敗記録（`*-donor-failure-*`）0 |
| 試行 | 全件`attempt: 1` |
| 来歴 | 全件のcommitが`0b99c178ba374489f99fdd6d634add0ff465bd77`、`git_dirty: false`、runtime freezeのSHA-256が`d718cec44eb37472a71d4c0eec3ee91bba5bb4766de96f9ebd69b0c0132e3915` |
| bundle | 240件とも同じ10ファイル（`manifest.json`と宣言ファイル9件）。宣言ファイル2160件のサイズとSHA-256はすべて一致し、宣言外のファイルはない |
| 容量 | 宣言ファイル合計424,529,137 bytes（1件約1.8 MB）。保存上限は条件あたり0.05 GiB・全体2.0 GiB |

実行中は、実行用の作業ツリーを`0b99c17`のdetached HEADのまま保ち、checkoutしなかった。
完了とプロセスの終了を確認した後、本記録の作成のために`main`へcheckoutした。
`pt-001`の49 bundleは変更していない。

### 実行ログ

| ファイル | bytes | SHA-256 |
|---|---:|---|
| `artifacts/phase2-activation-patching-capture-0b99c17.log` | 66528 | `5fa64faed959641623222421e2e2c83d54b2e8490dbdb4cabdc725119bf4ac38` |

- 型変換メッセージ（`MatMul8bitLt: inputs will be cast from`）がログに出たのは1回だけだった。
- 最後のbundleの`log_filter_cumulative`では、抑制件数は194,866,559件である。
- 他に出ていたのは、モデル読込時の`torch_dtype` deprecation警告と、checkpoint読込の進捗表示だけだった。

## 資源の記録（240件）

| 項目 | 値 |
|---|---|
| 記録上の所要時間（`elapsed_seconds`。donor正常計算と介入の2パス合計） | 最小424.2秒、平均444.1秒、最大461.8秒。570秒・600秒を超えた件はない |
| 実時刻で測った介入段階の時間 | 最小412.9秒、平均416.8秒、最大424.1秒 |
| bundleの完了間隔（実時刻） | 平均422.1秒、最小417.8秒、最大429.6秒 |
| GPUピーク | 9.402〜9.510 GiB（上限12 GiB） |
| VmRSS（介入段階の終了時） | 2.5624〜2.5644 GiB。最初に完了したc368は2.5624 GiB |
| VmHWM | 最大4.744 GiB |
| MemAvailable（開始時・終了時） | 8.137〜8.407 GiB |
| swap使用量 | 最大12 KiB |
| memory pressure（`some`/`full`のavg60） | 全件0 |

- 実時刻の時間は、donor群ごとの`started_at`/`finished_at`（`datetime.now(UTC)`）から計算した。
- 介入段階の最初のdonor群の開始から、最後の群の終了までの時間である。

## 監視区間と停止基準（段階B）

最初の20件（完了順）は、RDR-2026-11-15-01の4節の停止基準(a)〜(d)にいずれも該当しなかった。
(a)〜(c)は、その後の全240件でも該当しなかった。
確認は、2026-11-15 04:01、05:17、15:20、21:32、23:49と2026-11-16 03:06、03:48 JSTの目視、および完了後の全件検査による。
手動停止は行っていない。

| 基準 | 最初の20件 | 全240件 |
|---|---|---|
| (a) 連続2条件が570秒超 | 該当なし（最大428.7秒） | 該当なし（最大461.8秒） |
| (b) swapが1 GiB超かつ増加 | 該当なし | 該当なし（最大12 KiB） |
| (c) MemAvailableが2 GiB未満 | 該当なし | 該当なし（最小8.137 GiB） |
| (d) VmRSSが最初の完了条件より1 GiB以上大きい | 該当なし（増加0.0017 GiB） | 該当なし（増加0.0020 GiB） |

5節の600秒超過時の手順と、技術失敗の再試行経路は使わなかった。

## 所見：WSLのmonotonic時計のずれ

**内容**

記録上の所要時間は、実行が進むにつれて約430秒から約458秒へ伸びた。
一方、実時刻で測った介入段階の時間はほぼ一定だった。

| 完了順 | 記録上の時間の平均 | 実時刻の介入段階の平均 | monotonic/実時刻の比 |
|---|---:|---:|---:|
| 1〜48 | 430.8秒 | 416.0秒 | 1.010 |
| 49〜96 | 437.2秒 | 416.0秒 | 1.025 |
| 97〜144 | 442.4秒 | 416.3秒 | 1.037 |
| 145〜192 | 452.5秒 | 417.7秒 | 1.058 |
| 193〜240 | 457.5秒 | 418.1秒 | 1.068 |

**比の算出**

- 比は、donor群ごとの`time.monotonic()`による秒の合計を、同じ区間の実時刻の差で割った値である。
- 最初の件は1.000、最後の件は1.0735だった。
- 実行中（11-15 21:32 JST頃）に同じ比をその場で測ると、20秒で1.089、110秒で1.046だった。

**考えられる原因**

- clocksourceは`tsc`だった。
- `dmesg`には`systemd-journald: Time jumped backwards`が完了後の時点で387回あった。
- これらから、WSL2 VMのmonotonic時計が速く進み、実時刻はホストとの同期で戻されていたと考える。
- 実際の計算速度が落ちたのではないと判断する。
- 根拠：
  - 実時刻の間隔が一定だった。
  - RSS、swap、memory pressure、GPUの温度・クロックに変化がなかった（11-15 15:20時点で49℃、2797 MHz、速度制限なし）。
  - forward種別（prefix・suffix・token）の時間が同じ割合で伸びていた。
- 時計のずれの原因そのもの（ホスト側の要因、ずれが増える理由）は確認していない。

**pt-001との比較**

`pt-001`の完了bundleで、`intervention_seconds`とbundleファイルの更新間隔を比べた。
比は最初の件が1.000、最後の件が0.999で、このずれはなかった。
したがって、`pt-001`が事前確認より約11%遅かったのは実際の遅れであり、この現象とは別である（原因は引き続き未確定）。

**影響**

- 600秒上限の判定は`time.monotonic()`による時間で行っている。
- 今回、記録上の時間は実時刻より最大約7.4%過大だったが、上限との余裕は大きく、判定結果は変わらなかった。
- `elapsed_seconds`などの時間項目は記録どおりの値として保持し、補正しない。
- 判断事項として残す：今後の時間計測で、実時刻の併記や時計の状態の記録を行うか。
  - 今回の計算・判定には影響しない。
  - 変える場合はコードとruntime freezeの変更になるため、別のRDRで判断する。

## collection manifest

研究実施者の指示により、2026-11-16 13:14 JSTにcleanな`main`（`a05e41c`）で次を実行した（終了コード0）。
このコマンドは取得commitとの一致を要求しない（`load_plan(..., matching=False)`）。
manifestの`git_commit`には、freezeのcommit `0b99c17`が記録される。

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.activation_patching collection-manifest configs/analysis/phase2_activation_patching_v1.json --runtime-freeze artifacts/phase2-activation-patching-runtime-0b99c17.freeze.json --output data/manifests/2026-11-16_phase2_activation_patching_collection.json
```

| 出力 | bytes | SHA-256 |
|---|---:|---|
| [collection manifest](../../data/manifests/2026-11-16_phase2_activation_patching_collection.json) | 163090 | `375a6944e91b92d1cfbba597be96bc7d2771e997daef9e8c669b6658aedbde6c` |

作成後に次を確認した。

- `condition_count`は240。run IDとcondition IDに重複はない。
- すべてのrun IDが`argrec672-v1-pt-002-cNNN`である。
- 全件`attempt: 1`で、試行一覧は各1件（completed）。`retried_condition_count`は0、run単位の失敗記録は0件。
- 各runの`manifest_sha256`は、bundleの`manifest.json`と240件すべて一致した。
- runtime freezeのSHA-256は`d718cec4…`、`total_bytes`は425,353,057。validationの使用は0件。

作成時に読まれたのは、各bundleの`manifest.json`と`run.json`だけである。`results.json`の内容は読まれていない。

## 次の手順

runnerの手順に従い、本manifestと本記録をcommitした後、取得とは異なるcleanなcommitでパッチング解析を一度だけ実行する。
解析は研究実施者の指示を受けてから行う。
