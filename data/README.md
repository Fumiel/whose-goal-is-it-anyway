# Data layout

このディレクトリには、実験条件を再生成・追跡するための小さな宣言ファイルだけをGit管理します。

- `templates/`: task、attack、controlの生成元
- `schemas/`: condition、run、artifact、split recordのJSON Schema
- `conditions/`: templateから生成した小さな条件manifest
- `splits/`: group単位の固定split
- `manifests/`: 外部保存artifactの相対名、checksum、生成run

生成直後の不変runは`artifacts/runs/`、再生成可能な派生データは`artifacts/processed/`へ保存します。解析実行出力は`artifacts/analyses/`、Git管理する小さな確定結果は`results/`へ分けます。

実際のPromptやツール出力に個人情報・秘密情報を含めません。第三者由来データを使う場合は、利用条件と取得元をmanifestへ記録します。
