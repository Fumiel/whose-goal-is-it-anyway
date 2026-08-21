# Generated outputs

実験出力は`outputs/runs/<run_id>/`へ保存し、既存runを上書きしません。推奨するrun構成は次の通りです。

```text
<run_id>/
├── resolved_config.yaml
├── environment.json
├── input.json
├── messages.jsonl
├── tool_calls.jsonl
├── outcome.json
├── token_positions.json
├── logits.safetensors
├── activations.safetensors
├── attentions.safetensors
└── checksums.json
```

このREADME以外の`outputs/`配下はGit管理されません。共有すべき集計結果は、元run IDと生成手順を伴う小さな表・図として別途管理します。
