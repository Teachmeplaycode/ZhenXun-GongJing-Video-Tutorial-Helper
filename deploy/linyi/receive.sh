#!/usr/bin/env bash
# Runs on the server as the forced command of the GitHub deploy key (see deploy/linyi/README.md):
# reads a source archive (git archive HEAD backend front deploy | gzip) from stdin, puts it in
# place of ~/projects/zhenxun keeping deploy/linyi/.env and the data volume, rebuilds and restarts.
# A failed build or an unhealthy start puts the previous code back and restarts that.
set -euo pipefail
trap '' HUP PIPE  # a dropped connection must not stop a swap half way
APP="$HOME/projects/zhenxun"
NEW="$APP.new"
PREV="$APP.prev"
COMPOSE="deploy/linyi/compose.yaml"
exec 9>"$HOME/.zhenxun-deploy.lock"
flock 9

rm -rf "$NEW"
mkdir -p "$NEW"
tar -xzf - -C "$NEW"
[ -f "$APP/deploy/linyi/.env" ] && cp -p "$APP/deploy/linyi/.env" "$NEW/deploy/linyi/.env"

healthy() {
  for _ in $(seq 1 30); do
    [ "$(sudo docker inspect -f '{{.State.Health.Status}}' zhenxun 2>/dev/null)" = healthy ] && return 0
    sleep 3
  done
  return 1
}

rm -rf "$PREV"
mv "$APP" "$PREV"
mv "$NEW" "$APP"
cd "$APP"
if sudo docker compose -f "$COMPOSE" up -d --build && healthy; then
  echo "deployed: $(date -u +%FT%TZ)"
  sudo docker image prune -f >/dev/null
  exit 0
fi
echo "deploy failed: putting the previous version back" >&2
rm -rf "$APP.failed"
mv "$APP" "$APP.failed"
mv "$PREV" "$APP"
cd "$APP"
sudo docker compose -f "$COMPOSE" up -d --build
exit 1
