# 骑行时光机

前后端分离的私人骑行手记。原生 JavaScript 前端负责五个页面和交互，Flask 后端负责 JSON API、SQLite、照片处理、AI 调用与 HTML 导出。两端独立运行，通过同源代理连接。

## 项目结构

```text
frontend/
  index.html          静态入口，支持五个页面的直接访问
  src/app.js          根据页面路径加载数据并渲染
  src/api.js          API 请求、会话令牌和错误处理
  src/views.js        页面视图
  src/interactions.js 表单、上传、登录和退出交互
  assets/             CSS、图标和图片
  dev_server.py       本地静态服务与 API 代理（Python 标准库）
backend/
  app.py              Flask 应用工厂和 API
  wsgi.py             Gunicorn 入口
  requirements.txt    后端生产依赖
  exports/            HTML 导出模板与独立样式
instance/             原有数据库、照片、HTML 和会话密钥
deploy/               Nginx 和 systemd 配置
tests/                API 回归与前后端浏览器流程测试
```

后端不会渲染登录、首页、配置、画廊或预览页面。Jinja 仅用于生成要保存的独立 HTML 文档。前端无需 Flask、Node.js 或打包工具，可单独部署 `index.html`、`src/`、`assets/`。导出文档样式位于 `backend/exports/story.css`，前端预览样式位于 `frontend/assets/story.css`，各自随对应服务部署。

## 本地运行

需要 Python 3.10 或更新版本。在项目根目录安装依赖：

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

终端一，启动后端，默认端口 8000：

```sh
.venv/bin/python -m backend.app
```

终端二，启动前端，默认端口 5173：

```sh
.venv/bin/python frontend/dev_server.py
```

浏览器访问 [http://127.0.0.1:5173](http://127.0.0.1:5173)，默认账号 `root`，密码 `admin123`。首次使用先在「AI 配置」保存服务地址和密钥。

自定义端口或后端地址：

```sh
PORT=8001 .venv/bin/python -m backend.app
.venv/bin/python frontend/dev_server.py --port 5174 --backend http://127.0.0.1:8001
```

前端代理 `/api/`、`/cycling/`、`/tmp/` 请求到后端。浏览器始终访问前端地址，Cookie 和 CSRF 通过代理传递，因此不需要开放跨域权限。前端和后端可以运行在不同机器上，通过代理配置连接。`dev_server.py` 仅用于本地开发，生产环境使用 Nginx。

根目录 `app.py`、`wsgi.py` 是兼容启动入口：`python app.py` 现在启动后端 API（默认 8000），不再提供前端页面。

## 功能与数据

支持骑行数据选填、多图上传和六种文案风格。每次最多 8 张照片，单张最多 30 MB，总请求最多 300 MB；支持 JPEG、PNG、WebP，上传后转换为最长边 1600px 的 JPEG 并移除 EXIF 元数据。发送图片给 AI 前，后端会额外压缩为小于 1 MB 的 JPEG 请求载荷；保存及导出的图片不受这一步影响。

Base URL 应包含服务需要的版本前缀，例如 `https://api.openai.com/v1`，也支持完整的 `/chat/completions` 地址。默认模型 `gpt-4o`；上传照片时需要支持图片输入的模型。照片会以 Base64 发送给所配置的服务。未配置真实 AI 时不生成模拟结果。

拆分沿用项目根目录的 `instance/`，不会创建新的 `backend/instance/`。现有配置、照片、记录和登录签名密钥无需迁移。独立搬迁后端时，通过环境变量指定这些存储位置。

| 内容 | 本地默认位置 | 环境变量 |
| --- | --- | --- |
| SQLite | `instance/cycling.sqlite3` | `CYCLING_DATABASE` |
| 生成的 HTML | `instance/cycling/YYYYMMDD.html` | `CYCLING_OUTPUT_DIR` |
| 照片 | `instance/photos/<随机ID>.jpg` | `CYCLING_PHOTO_DIR` |
| 会话签名密钥 | `instance/secret.key` | `CYCLING_SECRET_KEY` |

生产环境按原需求设置 HTML 目录 `/usr/local/nginx/html/cycling/` 和照片目录 `/usr/local/nginx/html/tmp/`，变量示例见 `.env.example`。应用不自动读取 `.env`，由 shell 或 systemd 注入。

同一天对应一个 HTML 文件，再次成功生成会更新该日记录；修改日期会新增另一日记录。失败请求不会覆盖已有结果，并清理本次新上传的照片。成功记录中被移除的旧照片保留在磁盘，避免历史链接失效。画廊扫描实际 HTML 目录，包括命名有效的历史文件。HTML 内嵌样式且可不登录直接访问；多图会以自动轮播方式展示，保留原始宽高比以适配电脑和手机。导出页图片通过公开的 `/cycling/photos/` 路径加载，迁移时需要同时保留照片。

SQLite 包含 API Key，应放在非公开目录中。数据库文件权限为 `0600`；持久化并备份数据库、照片、HTML 和会话密钥。

## API 约定

页面路径 `/login`、`/`、`/settings`、`/story-schemes`、`/generate`、`/gallery` 由前端提供。后端业务接口均以 `/api/` 开头，成功与失败都返回 JSON（`/api/auth/check` 除外）；未登录返回 401，不会返回登录页 HTML。

| 方法 | 路径 | 返回或用途 |
| --- | --- | --- |
| GET | `/api/session` | 公开接口，返回 `authenticated` 和 `csrf_token` |
| POST | `/api/login` | 账号密码登录，返回新会话状态与 CSRF 令牌 |
| POST | `/api/logout` | 清除登录状态，返回新的匿名会话令牌 |
| GET | `/api/meta` | 日期、风格、数据字段、记录数量及配置状态 |
| GET | `/api/config` | Base URL、模型、故事方案、`has_key`；不返回密钥 |
| POST / PUT | `/api/config` | 保存配置，支持 JSON 或表单 |
| GET / POST | `/api/story-schemes` | 获取各语气的多条故事方案，或为指定语气新增一条方案 |
| POST | `/api/generate` | 上传、AI 生成并保存记录；支持 JSON / multipart |
| GET | `/api/rides` | 磁盘画廊，返回日期倒序的 `items` 数组 |
| GET | `/api/rides/YYYY-MM-DD` | 返回指定日期的 `record` 和 `filename` |
| GET | `/api/result?date=YYYY-MM-DD` | 指定或最近生成结果；无最近记录时 `record: null` |
| GET | `/api/auth/check` | Nginx 会话鉴权，返回 204 或 401 |
| GET | `/cycling/YYYYMMDD.html` | 可公开访问的独立 HTML |
| GET | `/tmp/<ID>.jpg` | 登录后访问照片 |

先调用 `/api/session`，保留会话 Cookie。所有 POST / PUT / PATCH / DELETE 请求必须携带 `X-CSRF-Token`；登录和退出后使用接口返回的新令牌。兼容 multipart 表单内的 `csrf_token`。生成接口返回 `record`、前端结果页 `redirect` 和 `html_url`。错误返回 `{ "error": "说明" }`；会话过期还返回 `redirect: "/login"`。

生成字段：`date`、`distance`、`duration`（如 `02:30`）、`elevation`、`speed`、`cadence`、`heart_rate`、`styles`（必填数组）。风格 ID：`funny`、`inspiring`、`poetic`、`suspense`、`cinematic`、`diary`。Multipart 通过重复字段传多风格和多张 `photos`。编辑时传 `edit_date`、`retained_photos` 数组，仅接受原记录中的照片。

保存配置时，API Key 留空保留原值；更换 Base URL 必须重新输入密钥。密钥不返回前端，也不会写入生成的 HTML。故事方案在独立的“故事方案”页面中按语气新增，可为每种语气保存多条；生成时会从每个所选语气的方案中随机选择一条作为写作参考。

原 `/upload`、`/settings/save`、`/logout` 等服务端表单接口已替换为以上 API；外部调用方需要同步修改路径。

## Linux / Nginx 部署

```text
浏览器 -> Nginx
           /、/login、/settings、/story-schemes、/gallery、/generate -> 前端 index.html
           /assets/、/src/                         -> 前端静态文件
           /api/                                  -> Flask / Gunicorn
           /cycling/                              -> 公开静态 HTML（含公开导出图片）
           /tmp/                                  -> 登录后访问的后台图片
```

项目放在 `/opt/cycling`，创建专用服务用户并准备目录：

```sh
sudo useradd --system --home /opt/cycling --shell /usr/sbin/nologin cycling
sudo install -d -o cycling -g cycling /var/lib/cycling
sudo install -d -o cycling -g cycling /usr/local/nginx/html/cycling /usr/local/nginx/html/tmp
sudo chown -R cycling:cycling /opt/cycling
sudo -u cycling python3 -m venv /opt/cycling/.venv
sudo -u cycling /opt/cycling/.venv/bin/pip install -r /opt/cycling/backend/requirements.txt
sudo install -m 600 /opt/cycling/.env.example /etc/cycling.env
```

修改 `/etc/cycling.env` 中的路径、稳定的 `CYCLING_SECRET_KEY`、账号密码。启用 HTTPS 后设置 `CYCLING_COOKIE_SECURE=1`。

```sh
sudo cp /opt/cycling/deploy/cycling.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cycling
```

Gunicorn 启动入口是 `backend.wsgi:app`。将 `deploy/nginx.conf` 放入 Nginx `http {}` 下的配置目录，修改域名和前端 `root`，配置 TLS 后执行 `nginx -t` 再重载。Nginx 必须加载 `mime.types`，使 ES 模块以 JavaScript MIME 类型返回。

配置需要 `http_auth_request_module`，可通过 `nginx -V` 检查。`/cycling/` 生成页及其 `/cycling/photos/` 图片可公开访问；`/tmp/` 后台图片仍通过 `/api/auth/check` 检查登录。没有该模块时，删除内部 `/_cycling_auth` location，并将 `/tmp/` 的内容改为 `proxy_pass http://127.0.0.1:8000;`；保留前端与 `/api/` 的分流。

两个服务可独立发布：前端只需替换 `index.html`、`src/`、`assets/`；后端只需更新 `backend/` 与对应依赖。Nginx 的 `/api/` upstream 可替换为独立后端机器地址。不要把整个仓库或 `instance/` 作为网站根目录。
### 升级发布

服务端代码保持 git 仓库形式放在 `/opt/cycling`。`deploy/` 下提供两个发布脚本：

```sh
# 前端升级：git pull 后同步 frontend/ 到静态根目录，Nginx 直接生效，无需重启
bash deploy/upgrade_frontend.sh

# 后端升级：备份数据 -> git pull -> 安装依赖 -> 重启 cycling 服务
sudo bash deploy/upgrade_backend.sh
```

两个服务可独立发布。后端升级前脚本会把数据库、会话密钥、导出 HTML 和照片目录备份到 `/var/lib/cycling/backup/backend-<时间戳>/`；前端同理备份到 `frontend-<时间戳>/`。升级后先验证登录与 `/api/meta`，再决定是否需要回滚（脚本输出中附有回滚命令）。数据文件（`instance/`、`/usr/local/nginx/html/` 下的内容）不属于代码，升级时不要覆盖，只更新代码与依赖。

## 验证

```sh
.venv/bin/python -m pytest -q
```

覆盖 JSON 登录与 CSRF 轮换、PUT 鉴权、密钥保护、原有持久化、输入校验、多风格、图片编码、修改、画廊、失败清理与写入回滚。

浏览器测试启动独立的前端代理、后端服务和模拟 AI，不使用真实密钥：

```sh
.venv/bin/pip install playwright
.venv/bin/python -m playwright install chromium
.venv/bin/python tests/browser_smoke.py
```

检查完整用户流程、页面直接访问、桌面 1440px / 手机 390px / 320px 布局。截图位于 `test-results/`。真实 AI 连通性及目标服务器 Nginx 配置需要在对应环境验证。

## 素材

摄影：[Kirsten Frank / Unsplash](https://unsplash.com/photos/rCeH116HQAo)，位于 `frontend/assets/cycling.jpg`。图标：[Lucide](https://lucide.dev)，版本 0.468.0，许可证见 `frontend/assets/lucide.LICENSE`。运行时不依赖外部字体或图标 CDN。
