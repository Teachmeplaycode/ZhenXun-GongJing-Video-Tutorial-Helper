#!/usr/bin/env bash
# One-time setup, run on your Mac from the repository root: bash deploy/linyi/setup-auto-deploy.sh
# Makes a key that can only run the deploy script on the server, and gives it to GitHub Actions:
#   1. a new ed25519 key pair in a temporary folder
#   2. the server: ~/.local/bin/zhenxun-receive, and the public key in authorized_keys with
#      command="…zhenxun-receive",no-port-forwarding,no-pty — it cannot open a shell or a tunnel
#   3. GitHub: secrets DEPLOY_SSH_KEY (the private key) and DEPLOY_KNOWN_HOSTS (the server's host key)
#   4. the local copy of the private key is deleted
# Run again to replace the key (the old one is removed from the server first).
set -euo pipefail
HOST=ubuntu@43.160.195.13
TAG=github-actions-deploy-zhenxun
DIR="$(mktemp -d)"
trap 'rm -rf "$DIR"' EXIT

ssh-keygen -q -t ed25519 -N "" -C "$TAG" -f "$DIR/key"
scp -q deploy/linyi/receive.sh "$HOST:/tmp/zhenxun-receive"
ssh "$HOST" "install -D -m 755 /tmp/zhenxun-receive ~/.local/bin/zhenxun-receive && rm /tmp/zhenxun-receive \
  && touch ~/.ssh/authorized_keys && sed -i '/$TAG/d' ~/.ssh/authorized_keys \
  && echo 'command=\"/home/ubuntu/.local/bin/zhenxun-receive\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty $(cat "$DIR/key.pub")' >> ~/.ssh/authorized_keys"
gh secret set DEPLOY_SSH_KEY < "$DIR/key"
ssh-keyscan -t ed25519 43.160.195.13 2>/dev/null | gh secret set DEPLOY_KNOWN_HOSTS
echo "好了：之后每次 main 更新、测试通过，GitHub 会自动部署到 https://linyi.work/ZhenXun/"
