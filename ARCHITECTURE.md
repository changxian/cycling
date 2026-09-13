# 骑行时光机 · 架构与作业参考

> 新会话先读本文件 + `PROJECT_MEMORY.md` 最近 2~3 条，即可进入工作状态，不必重读整个项目。
> 业务细节以 `PROJECT_MEMORY.md` 为准（它记录每次变更）；本文件只记录稳定的结构事实。

## 1. 项目定位

前后端分离的私人骑行手记：选照片 → 填文字 → 调 AI 生成多风格故事文案 → 导出独立 HTML。
支持多账号注册登录与画廊数据隔离（2026-09-13 引入）。

## 2. 技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | 原生 JavaScript（ES Module）+ 静态 HTML/CSS | 无框架、无 Node 构建、无打包工具 |
| 后端 | Python 3.10+ / Flask 3.1 | 单文件 `backend/app.py` 应用工厂 |
| 数据库 | SQLite（标准库 `sqlite3`） | 库文件在 `instance/` |
| 图片处理 | Pillow + pillow-heif | HEIC/HEIF 支持；MPO 取主图 |
| AI 调用 | requests + `backend/safe_http.py` | 普通账号强制公网；root 可内网 |
| 导出 | Jinja2 仅用于生成独立 HTML 故事文档 | 前端不渲染业务页面 |
| 本地开发 | `frontend/dev_server.py`（纯标准库） | 静态服务 + 代理 `/api/` `/cycling/` `/tmp/` |
| 生产部署 | Nginx + gunicorn + systemd | 配置在 `deploy/` |
| 测试 | Python pytest + Node 内置 `node:test` | 浏览器回归用 Playwright（可选） |

## 3. 目录结构与职责

```text
app.py / wsgi.py / requirements.txt   根目录兼容入口（调 backend/app.py）
backend/
  app.py              Flask 应用工厂、全部 API、SQLite、照片、AI、HTML 导出（核心文件，很大）
  accounts.py         多账号初始化/迁移：users、user_rides、user_journals、user_ai_config
  safe_http.py        普通账号 AI 请求公网限制（DNS 校验、固定 IP、禁代理）
  exports/            独立故事 HTML 模板与 story.css
frontend/
  index.html          静态入口
  src/app.js          路由分发（/ /login /register /settings /story-schemes /gallery /generate）
  src/api.js          请求封装、会话令牌、错误处理
  src/views.js        各页面视图渲染函数
  src/interactions.js 表单、图片选择/拖放（叠加语义）、登录注册交互
  src/photo-files.js  选图收集与格式校验（追加、去重、非法格式保留原列表）
  dev_server.py       本地静态服务 + 后端代理
instance/             SQLite 库、照片、HTML 导出、会话密钥（运行时数据，勿手改）
tests/                见第 5 节
deploy/               upgrade_frontend.sh / upgrade_backend.sh / nginx.conf / cycling.service
PROJECT_MEMORY.md     每次变更的明细记忆（新会话必读最近条目）
```

## 4. 业务架构

- **身份**：`/api/register` 注册 + 登录；会话身份取数据库记录。root 看全部画廊，普通账号只看自己的（按 owner_id 过滤配置/手记/结果/任务/私有照片）。
- **记录页（/）**：照片选择与拖放统一为**叠加**（`pendingFiles` 是待保存权威列表）；轮播预览区分已保存（服务器缩略图）与待保存（本地对象 URL）。
- **故事生成**：`story_units(journal) > 1` 走多段路径；每段 ≤45 字，携带全部前文防重复，`SequenceMatcher` 相似度 ≥0.8 本地拦截；单段/汇总 100~200 字。同步与异步任务共用同一持久化逻辑。
- **归档**：`persist_record` 在同一 SQLite 写事务内分配 `YYYYMMDD.html`、`YYYYMMDD_2.html` 编号文件名，存 `story_records(payload)`，失败回滚。`rides` 表按日期存最新结果，兼容旧查询。
- **照片**：上传生成 <200KB 缩略图存 `PHOTO_DIR/thumbs/`；原图登录可见，`/cycling/photos/thumbs/` 公开；HEIC 后端转码；MPO 取主图。
- **前端缓存**：全依赖链缓存版本号写在 `index.html` 与各 JS（形如 `20260913-accounts-1`），改前端后必须全链升版，否则浏览器执行旧代码。

## 5. 测试与验证

| 测试 | 类型 | 运行命令 |
| --- | --- | --- |
| `tests/test_app.py` | 后端 API 回归（pytest，隔离库+模拟 AI） | `python -m pytest tests/test_app.py` |
| `tests/test_accounts.py` | 账号/隔离回归 | `python -m pytest tests/test_accounts.py` |
| `tests/test_safe_http.py` | 公网限制回归 | `python -m pytest tests/test_safe_http.py` |
| `tests/photo_files.test.mjs` | 前端选图模块（node:test） | `node --test tests/photo_files.test.mjs` |
| `tests/thumbnail_views.test.mjs` | 前端视图模块 | `node --test tests/thumbnail_views.test.mjs` |
| `tests/journal_save.test.cjs` | 浏览器端到端（需 Playwright） | `NODE_PATH=/Users/changx/.hermes/hermes-agent/node_modules node --test tests/journal_save.test.cjs`（需沙箱外监听 127.0.0.1） |
| `tests/accounts_browser.test.cjs` | 账号浏览器端到端 | 同上，配 `tests/accounts_browser_server.py` |
| `tests/browser_smoke.py` | 旧冒烟，**已过期勿用**（断言与现 UI 失配） | — |

约定（来自 AGENTS.md）：
- 修 bug 先写**能复现问题的测试**再改代码；改完能跑就跑。
- 测试只使用隔离数据库与模拟 AI，不碰真实账号、不上传、不部署、不提交 git。

## 6. 添加新功能的作业流程

1. **读记忆**：`PROJECT_MEMORY.md` 最近条目 + 本文件第 3、4 节。
2. **定位模块**：按目录职责找到要改的文件；前端改动同时确认是否要升缓存版本。
3. **写复现/新用例**：
   - 后端逻辑 → `tests/test_app.py`（或对应 `test_*.py`）加用例，先跑失败。
   - 前端纯函数模块 → 新建或扩展 `tests/*.mjs`（参考 `photo_files.test.mjs` 的写法：直接 import `frontend/src/*.js`）。
   - 跨端交互 → 参考 `tests/journal_save.test.cjs` 的浏览器用例模式。
4. **实现**：保持与现有代码风格一致；可维护优先；不顺手改无关代码。
5. **验证**：新测试由红转绿 → 全量跑该模块相关测试 → `node --check`（JS）/ `python -m compileall`（Python）语法检查。
6. **记录**：按 `PROJECT_MEMORY.md` 现有格式追加条目（日期 + 变更说明 + 文件级明细 + 验证状态），便于下个会话续作。

## 7. 常见坑

- 改前端后忘升缓存版本号 → 浏览器跑旧代码。
- `tests/browser_smoke.py` 已过期，别拿它的失败当回归结果。
- 浏览器测试需监听本地端口，沙箱内会 `EPERM`，须沙箱外运行。
- 大文件（413）会中断会话：避免一次性粘贴大段二进制/长内容进对话。
- 不要以文件后缀判断图片真实编码（MPO 伪装成 PNG 的教训）。
