#!/usr/bin/env bash
# 前端发布：git 拉取最新代码，备份旧文件，同步到 Nginx 静态根目录。
# 用法：cd /opt/cycling && sudo bash deploy/upgrade_frontend.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# 本机 Nginx 为 root /usr/local/nginx/html；如需覆盖：CYCLING_STATIC_ROOT=/path sudo bash ...
DEST="${CYCLING_STATIC_ROOT:-/usr/local/nginx/html}"
STAMP="$(date +%Y%m%d%H%M%S)"
BACKUP="/var/lib/cycling/backup/frontend-$STAMP"

[ "$(id -u)" -eq 0 ] || { echo "请以 root 执行：sudo bash deploy/upgrade_frontend.sh" >&2; exit 1; }
[ -d "$ROOT/.git" ] || { echo "$ROOT 不是 git 仓库" >&2; exit 1; }
[ -d "$DEST" ] || { echo "Nginx 静态根目录不存在：$DEST" >&2; exit 1; }

# 1. 拉取最新代码（root 执行，.git 锁文件需要写权限）
git -C "$ROOT" pull --ff-only

# 2. 先备份旧文件，便于回滚
mkdir -p "$BACKUP"
for item in index.html src assets; do
  [ -e "$DEST/$item" ] && cp -a "$DEST/$item" "$BACKUP/"
done
echo "已备份旧前端到 $BACKUP"

# 3. 同步：只替换前端三项。不得对 $DEST 整体删除（cycling/、tmp/ 是数据目录）。
OWNER="$(stat -c '%U:%G' "$DEST" 2>/dev/null || true)"
copy_tree() {
  cp -a "$1" "$2.$$new"
  [ -e "$2" ] && rm -rf "$2"
  mv "$2.$$new" "$2"
  if [ -n "$OWNER" ]; then chown -R "$OWNER" "$2" 2>/dev/null || true; fi
}
cp -a "$ROOT/frontend/index.html" "$DEST/.index.html.$$new"
[ -e "$DEST/index.html" ] && rm -f "$DEST/index.html"
mv "$DEST/.index.html.$$new" "$DEST/index.html"
[ -n "$OWNER" ] && chown "$OWNER" "$DEST/index.html" 2>/dev/null || true
copy_tree "$ROOT/frontend/src"    "$DEST/src"
copy_tree "$ROOT/frontend/assets" "$DEST/assets"

echo "前端升级完成，无需重启 Nginx。"
echo "回滚：cp -a $BACKUP/index.html $DEST/ ; cp -a $BACKUP/src $DEST/ ; cp -a $BACKUP/assets $DEST/"
