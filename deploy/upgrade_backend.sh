#!/usr/bin/env bash
# 后端升级：备份数据 -> git 更新代码 -> 安装依赖 -> 重启 cycling 服务。
# 用法：在服务器项目目录 /opt/cycling 中执行  sudo bash deploy/upgrade_backend.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"
STAMP="$(date +%Y%m%d%H%M%S)"
BACKUP="/var/lib/cycling/backup/backend-$STAMP"

[ "$(id -u)" -eq 0 ] || { echo "请以 sudo 执行（会备份数据并重启服务）" >&2; exit 1; }
[ -d "$ROOT/.git" ] || { echo "$ROOT 不是 git 仓库，无法更新代码" >&2; exit 1; }

# 1. 备份数据：数据库、会话密钥（本地默认在 instance/）；
#    生产环境的 HTML / 照片目录以 /etc/cycling.env 中配置为准。
mkdir -p "$BACKUP"
[ -e "$ROOT/instance/cycling.sqlite3" ] && cp -a "$ROOT/instance/cycling.sqlite3" "$BACKUP/"
[ -e "$ROOT/instance/secret.key" ] && cp -a "$ROOT/instance/secret.key" "$BACKUP/"
if [ -f /etc/cycling.env ]; then
  # 在子 shell 中 source 环境文件（key=value 格式），读取导出目录
  eval "$(grep -E '^CYCLING_(OUTPUT_DIR|PHOTO_DIR)=' /etc/cycling.env || true)"
  [ -n "${CYCLING_OUTPUT_DIR:-}" ] && cp -a "$CYCLING_OUTPUT_DIR" "$BACKUP/cycling-html" 2>/dev/null || true
  [ -n "${CYCLING_PHOTO_DIR:-}" ] && cp -a "$CYCLING_PHOTO_DIR" "$BACKUP/photos" 2>/dev/null || true
fi
echo "数据备份到 $BACKUP"

# 2. 更新代码（git 仓库，/opt/cycling 即工作树）
cd "$ROOT"
git pull --ff-only

# 3. 安装依赖（以服务用户 ubuntu 执行，保持 .venv 属主一致）
sudo -u ubuntu "$VENV/bin/pip" install -r "$ROOT/backend/requirements.txt"

# 4. 重启服务并检查
systemctl restart cycling
sleep 2
if systemctl is-active --quiet cycling; then
  echo "后端升级完成，cycling 服务已重启。"
  echo "回滚方式：git checkout <旧提交> && $VENV/bin/pip install -r backend/requirements.txt && systemctl restart cycling；数据文件可从 $BACKUP 恢复。"
else
  echo "服务启动失败！查看：journalctl -u cycling --no-pager" >&2
  exit 1
fi
