# 骑行时光机 · 项目记忆

> 目标：新会话快速恢复上下文，不必重读目录结构。更新原则：改动核心结构/数据模型/运行方式时同步这里。

## 一句话
前后端分离的私人骑行手记：原生 JS 五页面（登录/记录/设置/故事方案/画廊）+ Flask 后端（JSON API、SQLite、照片、AI、HTML 导出）。两端独立运行，本地经代理连接，生产走 Nginx。

## 目录
- `backend/app.py`  Flask 应用工厂 + 全部 API（唯一后端源文件，~950 行）。`backend/wsgi.py` Gunicorn 入口。`backend/exports/` 导出 HTML/CSS 模板。
- `frontend/index.html` 入口；`frontend/src/{app,views,interactions,api}.js`；`frontend/assets/{app,story}.css`；`frontend/dev_server.py` 本地静态+API 代理。
- `instance/` 数据（SQLite、照片、导出 HTML、secret.key），**不是代码**，别覆盖。
- `tests/test_app.py` API 回归；`tests/browser_smoke.py` 浏览器流程。`deploy/` Nginx/systemd/升级脚本。

## 运行
```
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
.venv/bin/python -m backend.app                # 后端 :8000
.venv/bin/python frontend/dev_server.py          # 前端 :5173（代理 /api /cycling /tmp）
```
默认账号 `root` / `admin123`。先「AI 配置」填 Base URL + 密钥。

## 验证
```
.venv/bin/python -m pytest -q                 # API 回归（当前全绿）
.venv/bin/python tests/browser_smoke.py       # 需 playwright+chromium
```

## 数据模型（重点）
- SQLite 四表：`ai_config`(id=1)、`rides`(date,payload)、`ride_journals`(date,payload)、`story_tasks`（异步故事任务：task_id/date/status/total/done/segments/error）。
- **journal（当天手记）用 `groups` 权威模型**：一次“保存本次记录”= 一组 `{id, text, photos[]}`，图文绑定。
  - `ride_journals.payload` 存 `{date, groups[], background_music}`。
  - 旧扁平 `texts[]/photos[]` 由 `normalize_groups` 自动迁移：每条文字→独立组；历史照片→一个 `legacy` 无文案组。
  - 派生工具：`journal_photos(journal)`=各组照片并集；`journal_texts(journal)`=非空文案。
- **删除语义**（前后端一致）：
  - 删文案 = 删整组（文案+全部图）：`DELETE /api/journals/<date>/group/<gid>`。
  - 删图：组内多图→仅删该图；最后一张且有文案→确认“文案是否一并删”，确认走 group、不确认走 photo 保留文案；最后一张无文案→仅删图。`DELETE /api/journals/<date>/photo/<gid>/<name>`。
  - 空组（无文案且无图）自动丢弃。
- `rides`（生成结果）payload 含 `photos[]`（扁平）、`journal_entries[]`（扁平文案），导出 HTML/画廊用。`generate` 里新上传的未保存照片会作为“纯图组”并入 journal。
- **图片上传**：前端接受 JPG、PNG、WebP、HEIC/HEIF，并在 MIME 缺失时按扩展名兜底；后端通过 `pillow-heif` 解码苹果照片，将 HEIF 统一转为 JPEG 保存，以确保浏览器和导出页可显示。
- **分段生成（按总次数）**：`story_units(journal)` 把当天手记拆成生成单元——无图组 1 个单元；带 n 张图的组 n 个单元（每张图各配该组文案）。
  - `len(units) <= 1`：同步旧逻辑（单次 `generate_copy`）。
  - `> 1`：建 `story_tasks` 任务并立即返回 `{task}`，后台线程 `run_story_task` 逐单元调 `generate_segment_copy`（每单元一次 AI），最后 `generate_copy` 汇总终稿；结果写 `rides.payload.story_segments`（`[{photo|None, text}]`，无图单元 photo 为 null）。
  - 进度查询：`GET /api/story-tasks/<task_id>`；前端提交后若返回 `task` 则轮询到 done/failed 再跳 `/generate?date=`。
- **导出页卡片流（`story_content.html`）**：有 `story_segments` 时照片并入 `story-segments` 卡片从上到下排（图 16/10 在上、文案在下），无图单元渲染 `story-segment--text-only` 虚线卡片+`✻` 占位；无分段时照片仍走静态网格 `.story-photos`。前端 `resultView` 预览同款。导出 `story.html` 已移除死轮播脚本。

## 前端关键 ID/类（记录页）
- 照片轮播 `.photo-carousel .carousel-slide[data-group-id][data-retained]`，删图按钮 `.remove-photo[data-group-id][data-photo]`。
- 文案轮播 `#text-carousel .text-card[data-group-id][data-text]`，删文案按钮 `.remove-text`（动态 append）。
- 隐藏字段 `#edit-group-id`；保存按钮 `#save-journal`；表单 `#ride-form` 提交 `/api/generate`。
- 选择器 `#photo-input` 每次选择会替换待上传列表；拖放会追加。待上传列表支持移除单张，避免此前失败的文件随下一次上传重复提交。

## 已知问题（非本次引入）
- **2026-09-12 MPO 上传已修复**：用户样本 `IMG_8051.PNG` 实际被 Pillow 识别为 MPO（多图像 JPEG），被 `save_photos` 白名单拒绝。后端现接受 MPO，使用主图并按方向信息转正、转存普通 JPEG。真实样本经隔离 `/api/journals` 保存和读取验证通过；54 项后端测试通过，含大写 PNG 的 10 种模式/MIME 组合及 MPO 主图回归。此前 HEIF 和前端队列修改并非该样本根因。不要将文件后缀当作真实编码证据。
- `tests/browser_smoke.py` 相对当前 UI 已过期：断言 `[name="api_key"]`（设置页保存后已移除 name）与 `.photo-preview`（已重构为 `.photo-carousel`）均会失败。属既有失配，未在本次范围内修改。

## 红线（沿用 AGENTS.md）
删除库/批量删文件/改外部接口/上传数据/操作真实账号 = 先确认；不主动提交 git；密钥绝不入代码。
