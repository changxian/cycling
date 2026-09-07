# 骑行时光机

Flask + SQLite + HTML/CSS/Vanilla JS 实现的私人骑行手记。五个页面涵盖登录、上传、AI 配置、结果预览和时光画廊。支持多图和六种文案风格，生成的每种风格单独展示。

## 本地运行

需要 Python 3.10 或更新版本。

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

访问 http://127.0.0.1:5000 ，默认账号 `root`，密码 `admin123`。端口可通过 `PORT=5001 python app.py` 更换。

1. 登录后打开「AI 配置」，填写 OpenAI 兼容服务的 Base URL、API Key 与模型。
2. Base URL 应包含服务要求的版本前缀，例如 `https://api.openai.com/v1`；也支持完整的 `/chat/completions` 地址。模型默认为 `gpt-4o`。图片生成需要支持图片输入的模型。
3. 返回首页，填写可选数据、添加可选照片，至少选择一种风格后生成。
4. 成功后会保存 HTML 并进入预览；「返回修改」会恢复数据、风格和照片。「时光画廊」按日期倒序列出文件。

未配置真实 AI 时不生成模拟结果。照片会作为 Base64 发送给所配置的 AI 服务。每次最多 8 张，单张最多 10 MB，总请求最多 40 MB；支持 JPEG、PNG、WebP。上传后转换为最长边 1600px 的 JPEG，并移除 EXIF 元数据。

## 数据与文件

默认使用项目内 `instance/`，便于直接在本机运行：

| 内容 | 本地默认位置 | 生产环境变量 |
| --- | --- | --- |
| SQLite | `instance/cycling.sqlite3` | `CYCLING_DATABASE` |
| 生成的 HTML | `instance/cycling/YYYYMMDD.html` | `CYCLING_OUTPUT_DIR` |
| 照片 | `instance/photos/<随机ID>.jpg` | `CYCLING_PHOTO_DIR` |
| 会话签名密钥 | `instance/secret.key` | `CYCLING_SECRET_KEY` |

生产环境按需求设置生成目录 `/usr/local/nginx/html/cycling/` 和照片目录 `/usr/local/nginx/html/tmp/`，见 `.env.example`。应用不会自动读取 `.env`，请通过 shell 或 systemd 的 `EnvironmentFile` 注入环境变量。

同一天对应一个 HTML 文件；再次成功生成同一日期会更新该日记录。修改日期会生成另一条记录，原日期仍保留。失败的 AI 请求不覆盖已有结果，新上传的临时照片会清理。成功记录中后来被移除的照片保留在磁盘，以免旧页面或历史链接失效。生成的 HTML 内嵌样式，照片使用 `/tmp/` 路径；迁移页面需同时迁移照片。

画廊实际扫描 HTML 目录，包含非本应用生成但命名有效的 `YYYYMMDD.html` 文件；优先使用数据库元数据，否则从文件标题获取摘要信息。数据库、照片目录、HTML 目录和会话密钥都应持久化并备份。SQLite 包含服务密钥，数据库文件权限为 `0600`；不要放到 Nginx 公开目录中。

## Linux / Nginx 部署

将项目放在 `/opt/cycling`，创建专用服务用户并安装 Python 依赖：

```sh
sudo useradd --system --home /opt/cycling --shell /usr/sbin/nologin cycling
sudo install -d -o cycling -g cycling /var/lib/cycling
sudo install -d -o cycling -g cycling /usr/local/nginx/html/cycling /usr/local/nginx/html/tmp
sudo chown -R cycling:cycling /opt/cycling
sudo -u cycling python3 -m venv /opt/cycling/.venv
sudo -u cycling /opt/cycling/.venv/bin/pip install -r /opt/cycling/requirements.txt
sudo install -m 600 /opt/cycling/.env.example /etc/cycling.env
```

编辑 `/etc/cycling.env` 设置部署路径、稳定的 `CYCLING_SECRET_KEY` 以及登录密码。默认账号密码按需求保留；公开部署时用 `CYCLING_USERNAME`、`CYCLING_PASSWORD` 覆盖。启用 HTTPS 后将 `CYCLING_COOKIE_SECURE=1`。服务通过 systemd 读取环境文件，应用服务用户不需要读取 `/etc/cycling.env`。

```sh
sudo cp /opt/cycling/deploy/cycling.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cycling
```

将 `deploy/nginx.conf` 放入 Nginx `http {}` 下加载的配置目录，修改域名，配置 TLS 证书后执行 `nginx -t` 再重载。Nginx 需要 `http_auth_request_module`（`nginx -V` 可检查）。该配置直接提供 HTML 与照片，同时通过 Flask 会话鉴权；**不要将这两个目录改为无鉴权的静态目录**，否则会绕过登录要求。Nginx 必须能读取生成目录，且其全局 `mime.types` 应已加载。

没有 auth_request 模块时，删除两个静态 `location` 和内部鉴权 `location`，让所有请求通过 `location /` 交给 Flask；访问控制仍有效。Gunicorn 使用 150 秒超时，覆盖 AI 120 秒读取超时。登录端点在 Nginx 层限制请求频率。

## 接口

所有业务页面、API、记录 HTML 和上传照片都需要登录。所有 POST 请求需要 CSRF：表单使用 `csrf_token`，AJAX 使用页面 `<meta name="csrf-token">` 对应的 `X-CSRF-Token` 请求头。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET / POST | `/login` | 登录页面 / 验证账号 |
| POST | `/logout` | 清除会话 |
| GET | `/` | 记录表单；`?edit=YYYY-MM-DD` 恢复已有记录 |
| POST | `/upload` | multipart 数据、照片、风格，调用 AI 并保存 |
| GET | `/settings` | 配置页面 |
| POST | `/settings/save` | 保存配置，支持表单或 JSON |
| GET | `/api/config` | 返回 Base URL、模型和 `has_key`，不返回密钥 |
| POST | `/api/generate` | 与上传流程相同，支持 JSON 或 multipart |
| GET | `/generate` | 上次生成结果；支持 `?date=YYYY-MM-DD` |
| GET | `/gallery` | 从磁盘扫描的画廊 |
| GET | `/cycling/YYYYMMDD.html` | 已保存 HTML |
| GET | `/tmp/<ID>.jpg` | 已保存照片 |
| GET | `/auth/check` | Nginx 会话鉴权，返回 204 或 401 |

生成字段：`date`、`distance`、`duration`（如 `02:30`）、`elevation`、`speed`、`cadence`、`heart_rate`、`styles`（必填数组）。风格 ID 为 `funny`、`inspiring`、`poetic`、`suspense`、`cinematic`、`diary`。Multipart 以重复字段传多风格/多照片。编辑时传 `edit_date` 与 `retained_photos` 数组；仅接受原记录已有照片。

AJAX 传 `Accept: application/json`。生成成功返回 `record`、`redirect`、`html_url`；失败返回 `error` 和相应 HTTP 状态码。API 不向前端返回密钥或 AI 服务的原始错误内容。更换 Base URL 时必须重新输入 API Key，防止把原服务密钥无意发送给另一服务。

## 测试

```sh
.venv/bin/python -m pytest -q
```

测试使用临时目录与模拟 AI HTTP 响应，验证登录、CSRF、密钥保护、数据校验、多风格、图片编码、重复日期更新、返回修改、HTML 转义、磁盘画廊、异常清理及写入失败回滚。不会向真实 AI 服务发送请求或产生费用。

可选浏览器流程测试（同样使用隔离数据和模拟 AI）：

```sh
pip install playwright
python -m playwright install chromium
python tests/browser_smoke.py
```

覆盖桌面 1440px、手机 390px / 320px 页面与完整操作流程，截图输出至 `test-results/`。真实 AI 服务连通性和目标机器 Nginx 配置需要在提供密钥及部署环境后验证。

## 素材

骑行摄影：[Kirsten Frank / Unsplash](https://unsplash.com/photos/rCeH116HQAo)，本地文件 `static/cycling.jpg`。界面图标使用 [Lucide](https://lucide.dev)，本地固定版本 0.468.0，ISC 许可证见 `static/lucide.LICENSE`。应用正常运行不依赖外部字体或图标 CDN。
