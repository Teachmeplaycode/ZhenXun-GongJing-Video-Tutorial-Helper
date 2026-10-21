#!/usr/bin/env bash
# Adds the linyi.work site (deploy/linyi/linyi.work.caddy) to the shared Caddy gateway, which
# also serves mantramcp.cloud and aixit.club. Backs the Caddyfile up, appends in place (the file
# is bind-mounted, so its inode must not change), validates, then reloads without downtime.
# Anything fails → the backup is put back and nothing is reloaded. Run it once; it's a no-op after.
set -euo pipefail
GATEWAY=zhenyan-evidence-gateway
CADDYFILE="$HOME/zhenyan-evidence/Caddyfile"
BLOCK="$(dirname "$0")/linyi.work.caddy"

if grep -q '^linyi.work {' "$CADDYFILE"; then
  echo "linyi.work 已在 $CADDYFILE 里，不再添加"
  exit 0
fi
BACKUP="$CADDYFILE.bak-$(date +%Y%m%d-%H%M%S)"
cp -p "$CADDYFILE" "$BACKUP"
cat "$BLOCK" >> "$CADDYFILE"
if ! sudo docker exec "$GATEWAY" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile; then
  cat "$BACKUP" > "$CADDYFILE"
  echo "配置校验失败，已恢复原文件（备份 $BACKUP）"
  exit 1
fi
sudo docker exec "$GATEWAY" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
echo "已添加 linyi.work 并重载网关；原文件备份在 $BACKUP"
echo "证书签发需要几十秒，之后打开 https://linyi.work/ZhenXun/"
