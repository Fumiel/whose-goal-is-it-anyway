# Windows 11 / WSL2実行環境

この文書は、MacBookから自宅LAN内のWindows GPU PCを操作してpre-gate shakedownを実行するための手順である。インターネットへSSHを公開しない。

## Windows側

1. NVIDIAの現行Studio DriverをWindowsへ導入し、PowerShellの`nvidia-smi`でRTX 5060 Tiを確認する。
2. 「オプション機能」でOpenSSH Serverを有効化し、サービスを自動起動にする。
3. Macの公開鍵をWindowsユーザーの`authorized_keys`へ登録する。鍵接続を確認後、`sshd_config`でパスワード認証を無効化する。
4. Windows Defender FirewallではPrivateプロファイルかつLocalSubnetからのTCP 22だけを許可する。ルーターのポート転送は設定しない。
5. ルーターでWindows PCのDHCP予約を設定し、電源接続中のスリープを無効化する。
6. `wsl --install -d Ubuntu-24.04`を実行する。

ユーザープロファイル直下の`.wslconfig`は次を初期値とする。

```ini
[wsl2]
memory=12GB
processors=8
swap=16GB
localhostForwarding=true
```

変更後は`wsl --shutdown`で反映する。Linux用NVIDIAカーネルドライバーはWSL内へ導入しない。

## WSL側

リポジトリは`/mnt/c`ではなくLinuxホーム配下へcloneする。

```bash
sudo apt update
sudo apt install -y git python3.12-venv tmux
git clone https://github.com/Fumiel/whose-goal-is-it-anyway.git
cd whose-goal-is-it-anyway
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -e '.[dev,research]'
```

PyTorch以外の具体的な解決バージョンは、導入直後に次で固定する。

```bash
python -m pip freeze --all > artifacts/environment-lock.txt
goal-takeover gpu-preflight
goal-takeover agentdojo-preflight configs/selection/pre_gate_shakedown.yaml
```

`artifacts/environment-lock.txt`は実行環境の記録でありGitへコミットしない。長時間実行は、WindowsへSSH接続後に次のように開始する。

```powershell
wsl.exe -d Ubuntu-24.04 -- bash -lc "cd ~/whose-goal-is-it-anyway && tmux new -As goal-takeover"
```

コードの同期はGitで行う。モデルweight、生activation、raw run bundleをMacへコピーしない。

