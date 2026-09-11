#!/usr/bin/env bash
# 前端升级：git 拉取最新代码后，把 frontend/ 同步到 Nginx 的静态根目录，无需重启任何服务。
# 用法：在服务器项目目录 /opt/cycling 中执行  bash deploy/upgrade_frontend.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="/opt/cycling/frontend"
STAMP="$(date +%Y%m%d%H%M%S)"
BACKUP="/var/lib/cycling/backup/frontend-$STAMP"

[ -d "$ROOT/.git" ] || { echo "$ROOT 不是 git 仓库" >&2; exit 1; }

cd "$ROOT"
git pull --ff-only

# 备份被替换的内容
mkdir -p "$BACKUP"
for item in index.html src assets; do
  [ -e "$DEST/$item" ] && cp -a "$DEST/$item" "$BACKUP/"
done
echo "已备份旧前端到 $BACKUP"

# 同步 frontend/ 全部内容（原生 JS，无构建步骤，直接复制即可）
rsync -a --delete "$ROOT/frontend/" "$DEST/"
chown -R cycling:cycling "$DEST" 2>/dev/null || true

echo "前端升级完成。回滚方式：rsync -a --delete $BACKUP/ $DEST/ && chown -R cycling:cycling $DEST"
