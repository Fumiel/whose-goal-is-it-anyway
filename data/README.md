# Data layout

このディレクトリには、実験条件を再生成・追跡するための小さな宣言ファイルだけをGit管理します。

- `templates/`: task、attack、controlの生成元
- `schemas/`: conditionとrun recordのJSON Schema
- `splits/`: group単位の固定split
- `manifests/`: 外部保存artifactの相対名、checksum、生成run
- `raw/`: 生成直後の不変データ。Git管理外
- `processed/`: rawから再生成可能な派生データ。Git管理外

実際のPromptやツール出力に個人情報・秘密情報を含めません。第三者由来データを使う場合は、利用条件と取得元をmanifestへ記録します。
