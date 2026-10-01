# Whose Goal Is It Anyway?

Indirect Prompt Injectionを受けたツール利用型LLMエージェントについて、ユーザー目的と攻撃者目的の内部表現が、外部データの読み取りからツール選択までにどう変化するかを調べる卒業研究リポジトリです。

研究計画の詳細は [`docs/research_proposal.md`](docs/research_proposal.md) を参照してください。

## 現在の状態

現在はPilot実験前の基盤整備段階です。モデルと主対象ドメインはまだ確定しておらず、`configs/**/example.yaml`は選定候補を記入するための雛形です。合成fixtureに加え、AgentDojo 0.1.35 / Banking v1.2.2用adapterとQwen3 Transformers runnerを実装済みです。Qwen3-8B int8とQwen3-4B BF16のWindows GPU工学shakedownは各3 fixtureを完走し、WSL上のraw bundle監査も記録しました。これらは正式な候補評価や研究結果ではありません。測定値と確認範囲は[技術記録一覧](docs/experiment_logs/README.md)を、作業時点の状態は[`PROJECT_STATE.md`](PROJECT_STATE.md)を参照してください。

## ディレクトリ

```text
.
├── configs/                 # モデル・ドメイン・実験・Probe・解析・選定の設定
├── src/goal_takeover/       # エージェント実行、計測、評価、データ処理の実装
├── data/                    # Gitで管理する小さな実験条件と追跡情報
│   ├── templates/           # ユーザータスク・攻撃・対照条件の生成元
│   ├── schemas/             # 条件・run・artifact・splitのJSON Schema
│   ├── conditions/          # テンプレートから生成した条件宣言
│   ├── splits/              # task・攻撃テンプレート単位で固定した分割
│   ├── audits/              # 評価者による監査の割当と判定記録
│   └── manifests/           # 外部保存データの所在・checksum・生成run
├── artifacts/               # Git管理外の生成データ（下記は実行時に作成）
│   ├── runs/<run_id>/       # 上書きしない生の実行記録
│   ├── processed/           # 生データから再生成できる派生データ
│   └── analyses/            # 解析の実行出力
├── results/                 # 出典を追跡できる小さな確定表・図
├── tests/                   # 合成fixtureを含む回帰テスト
└── docs/                    # 研究計画と手順、および判断・実施の記録
    ├── decisions/           # 研究設計・実験手順の変更判断（RDR）
    ├── experiment_logs/     # 実験と工学的shakedownの実施記録
    ├── reports/             # 教授向けの進捗報告など
    └── snapshots/           # 日付付き研究計画の固定PDF
```

研究目的は[`docs/research_proposal.md`](docs/research_proposal.md)、現行の実験手順は[`docs/experimental_protocol.md`](docs/experimental_protocol.md)を参照してください。実行で生じた大きなデータは`artifacts/`に置き、再現に必要な小さな宣言・記録は`data/`、確定した集計結果は`results/`に分けます。

## セットアップ

PyTorchが対応するPython版を確認した上で、Python 3.11または3.12の利用を推奨します。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,research]'
cp .env.example .env
```

モデルの利用規約に同意が必要な場合だけ、`.env`へトークンを設定します。`.env`はGit管理されません。

## 最小チェック

外部依存を導入する前でも、標準ライブラリだけを使う単体テストと構文検査を実行できます。

```bash
make check-fast
```

開発依存を導入した後は次も実行します。

```bash
make check
```

設定とschemaは次のコマンドで検査できます。

```bash
make validate
```

AgentDojo研究依存を導入した環境では、固定した3 fixtureをモデルを読まずに検査できます。

```bash
make agentdojo-preflight
```

Windows 11 / WSL2 GPU環境の構築と実行方法は[`docs/windows_wsl_execution.md`](docs/windows_wsl_execution.md)を参照してください。実モデルshakedownは、8B int8候補なら次のように開始します。

```bash
goal-takeover gpu-preflight
goal-takeover agentdojo-shakedown configs/selection/pre_gate_shakedown.yaml \
  --model-config configs/models/qwen3_8b_int8.yaml \
  --run-prefix qwen3-8b-int8-shakedown-YYYYMMDD-NNN
```

`YYYYMMDD-NNN`は未使用の実行IDに置き換えてください。既存runは上書きしません。
この3 fixtureの行動成否はモデル選定、閾値設定、研究結果に使用しません。

正式なBankingモデル選定は7条件を両候補に適用します。実行前監査と人手監査は
[`docs/selection_audit.md`](docs/selection_audit.md)を参照してください。

```bash
goal-takeover selection-preflight configs/selection/integration_gate.yaml
goal-takeover agentdojo-selection configs/selection/integration_gate.yaml \
  --run-prefix banking-selection-YYYYMMDD-NNN
goal-takeover selection-report configs/selection/integration_gate.yaml \
  --run-prefix banking-selection-YYYYMMDD-NNN --audit path/to/audit.json
```

最初のモデル選定run `banking-selection-20260924-001` は14件を生成しましたが、
最終回答と生成時の生出力が保存されず、必須のblind監査に使用できません。
凍結済みの修正版による再実行`banking-selection-20260924-002`は両候補7件ずつ完了しました。
[14件の自己監査](data/audits/2026-09-24_banking_selection_self_audit_completed.json)と
[選定レポート](results/2026-09-24_banking_selection_self_audit_report.json)も完了し、
両候補とも凍結済みゲートには不合格でした。Qwen3-8B int8・Bankingは
[RDR-2026-09-24-07](docs/decisions/2026-09-24_provisional_qwen3_8b_banking_pilot.md)により、
探索的予備実験の暫定構成とします。主モデル・主ドメインはまだ最終採用していません。

[Bankingタスク候補表（2026-10-01）](docs/banking_task_candidates_2026-10-01.md)では、
全16タスクの操作・注入経路・系列関係・既使用によるtest除外を整理しました。
保守案では複合タスク15を除いて8系列ですが、攻撃を含む最上位の独立group数は未確定です。
タスク5・6は限定的なソース関数検査で無操作でもutilityがtrueとなるため、成功率・主解析の
標本としては保留します。タスク11も宛先を判定しない評価器の監査が必要です。
初回pilot標本・停止規則・評価仕様は下記のRDR-2026-10-01-03で固定しました。
native環境での評価器対照検証は実行前gateとして残っています。
判断と検証範囲は[RDR-2026-10-01-01](docs/decisions/2026-10-01_banking_task_feasibility_review.md)を参照してください。

[RDR-2026-10-01-02](docs/decisions/2026-10-01_existing_tasks_pilot_new_families_test.md)により、
予備実験は既存系列を中心に方針を固め、確認的評価には新しい意味系列も設計します。
選定・shakedownの既使用系列も、新しいrunで予備実験に再利用できます。
過去のshakedown runは工学記録として隔離し、既使用・予備実験・調整に使った系列はtestへ入れません。
新系列の設計・model-free検証を予備実験と並行して進め、関係graphで分離した開発用と
確認用のgroupを作ります。最終splitと独立group数は解析仕様とともに凍結します。
新系列や確認的testはまだ作成しておらず、30clusterの確保も未確認です。

[RDR-2026-10-01-03](docs/decisions/2026-10-01_banking_pilot_sample_freeze.md)により、
初回pilotは14/0/3/4/2/12の6task・4系列、最大90条件（clean6・IPI72・対照12）を凍結しました。
先行18件の後、厳密clean成功3/6以上・2系列以上と測定・監査基準を満たせば残りへ進みます。
この標本は共有攻撃形式等で1連結成分です。全条件pilot_onlyとしてtestから除外します。
標本の照合コマンドと未完了のrunner・native検証・capture・runtime凍結は
[Banking pilot v1](docs/banking_pilot_v1.md)を参照してください。新しいモデルrunは未実行です。

## 実験出力

各実行は`artifacts/runs/<run_id>/`に独立して保存し、少なくとも次を残します。

- 解決済み設定とGit commit
- モデル・tokenizerのrevision
- condition、pair、task、attack templateのID
- seedとdecoding条件
- ユーザータスク成功・攻撃成功・群A～D
- 各処理段階のtoken indexとtoken ID
- 正規／攻撃argument slotとwhole callの系列Log probability
- Activation等の保存先とchecksum

Activation、Attention、モデルWeight、大量の実行ログはGitへコミットしません。再現に必要なmanifest、設定、集計済みの表と図のみをGit管理します。合成end-to-end試験は`make dry-run`で実行できます。同じ`run_id`が既に存在する場合は上書きせず失敗します。

## 再現性上の注意

- 主解析は原則greedy decodingまたはtemperature 0で行います。
- 近い言い換え、同一条件の反復、意味的対応ペアをsplit間で分離しません。
- Action readout、Argument readout、Source-role readout、Authority score、Attention、Tool-call preferenceを別の指標として扱います。
- Probe scoreだけを根拠に目的の採用や因果的Takeoverを主張しません。

詳細な固定事項とPilot後の変更手順は [`docs/experimental_protocol.md`](docs/experimental_protocol.md) に記録します。
