#!/usr/bin/env bash
# 前端升级：git 拉取最新代码后，把前端静态文件同步到 Nginx 根目录。
# 用法：在服务器项目目录 /opt/cycling 中执行 sudo bash deploy/upgrade_frontend.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# 当前服务器的 Nginx 配置为 root /usr/local/nginx/html。
# 如后续调整 Nginx root，可在执行时覆盖：CYCLING_STATIC_ROOT=/path sudo bash ...
DEST="${CYCLING_STATIC_ROOT:-/usr/local/nginx/html}"
STAMP="$(date +%Y%m%d%H%M%S)"
BACKUP="/var/lib/cycling/backup/frontend-$STAMP"

[ "$(id -u)" -eq 0 ] || { echo "请以 sudo 执行：sudo bash deploy/upgrade_frontend.sh" >&2; exit 1; }
[ -d "$ROOT/.git" ] || { echo "$ROOT 不是 git 仓库" >&2; exit 1; }
[ -d "$DEST" ] || { echo "Nginx 静态根目录不存在：$DEST" >&2; exit 1; }

# 以 cycling 用户更新 git 工作树（.git 属主是 cycling，root 会留下 root 属主的锁/ref）。
GIT_USER="${CYCLING_GIT_USER:-cycling}"
id "$GIT_USER" >/dev/null 2>&1 || GIT_USER="$SUDO_USER"
sudo -u "$GIT_USER" git -C "$ROOT" pull --ff-only

# 同步：只用 cp/mv/rm，不依赖 rsync。只替换三个目标，删除范围限于 src/ 与 assets/。
cp -a "$ROOT/frontend/index.html" "$DEST/.index.html.new"
mv "$DEST/.index.html.new" "$DEST/index.html"

for item in src assets; do
  if [ -d "$ROOT/frontend/$item" ]; then
    cp -a "$ROOT/frontend/$item" "$DEST/.sync-$item-new"
    [ -e "$DEST/$item" ] && rm -rf "$DEST/$item"
    mv "$DEST/.sync-$item-new" "$DEST/$item"
  fi
done

# 仅处理前端文件。不得对 $DEST 执行整体 --delete，那里还包含 cycling/、tmp/ 等数据目录。
mkdir -p "$BACKUP"
for item in index.html src assets; do
  [ -e "$DEST/$item" ] && cp -a "$DEST/$item" "$BACKUP/"
done
echo "已备份旧前端到 $BACKUP"

# 原生 JS 无构建步骤。目录单独同步，删除范围只限 src/ 和 assets/。
rsync -a "$ROOT/frontend/index.html" "$DEST/index.html"
rsync -a --delete "$ROOT/frontend/src/" "$DEST/src/"
rsync -a --delete "$ROOT/frontend/assets/" "$DEST/assets/"

echo "前端升级完成，无需重启 Nginx。"
echo "回滚：cp -a $BACKUP/index.html $DEST/；再 cp -a $BACKUP/src $DEST/ 与 $BACKUP/assets $DEST/。"
