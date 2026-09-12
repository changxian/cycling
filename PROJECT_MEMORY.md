# 骑行时光机 · 项目记忆

## 2026-09-12 待上传图片轮播预览
- 变更说明：选图与拖放后即时追加到图片轮播，支持轮播和文件名列表双向移除，保存仅提交剩余图片。
- `interactions.js` 使用本地对象URL预览，不提前上传；`pendingFiles` 为待保存权威列表，待保存幻灯片用 `data-pending-index` 标记，不带 `data-retained`，防止生成时当作已保存图片重复提交。移除和退出页面释放对象URL。
- 空轮播也初始化轨道和切换控件；`carousel-update` 更新活动页、总数、空态及自动轮播。选择后显示本批第一张，移除最后一张恢复空态，再次选择仍可预览。
- 已保存照片仍使用服务器缩略图，待保存照片附文件名与“待保存”标识。浏览器不能解码的HEIC/损坏照片显示提示，仍可移除；HEIC保存后由后端转码并显示缩略图。
- 删除已保存图片或文字组改为接口成功后更新对应DOM，不再刷新导致待上传队列丢失；保留既有确认与图文组语义。保存进行中锁定队列修改。
- 前端全依赖链缓存版本：`20260912-photo-preview-1`。修改仅在本地，未提交、未部署、未操作真实账号。
- 验证：浏览器新增预览断言修改前失败（5张已选、轮播0张），修改后完整回归通过，覆盖混合已保存/待保存移除、5+1叠加、取消/非法格式、切换、双向移除、保存请求实际文件、空态重加、拖放和预览失败提示。Node前端4项与后端73项测试通过，修改JS语法检查通过。此前浏览器审批服务503阻塞已解除，本轮通过批准使用模拟数据完成验证。

## 2026-09-12 上传缩略图与展示优化
- 变更说明：上传生成小于200KB缩略图，所有骑行照片默认显示缩略图，仅独立故事HTML点击打开原图。
- `create_thumbnail` 生成严格小于200,000字节的JPEG，最大边初始1600像素，逐步降质量和尺寸，转正方向、透明背景填白；保存于 `PHOTO_DIR/thumbs/<原文件名>.jpg`。上传事务失败沿用清理机制，同时清理本次缩略图；空目录允许保留。
- `/tmp/thumbs/<原文件名>.jpg` 需登录；`/cycling/photos/thumbs/<原文件名>.jpg` 可公开访问。历史照片按需生成后缓存，原图接口与保存规则沿用原逻辑。不新增删除历史照片逻辑。
- 前端 `photoUrl`、画廊缩略图字段及独立HTML图片源均指向缩略图；独立HTML链接仍指原图。前端依赖缓存版本为 `20260912-thumbnails-1`。
- 历史HTML经 `cycling_html` 返回时替换图片源，原归档文件不改写；画廊历史HTML元数据兼容原图与缩略图地址。
- Nginx故事HTML路由改为代理后端并接受数字编号；新增两类缩略图代理路径。发布必须同步完整前后端、模板与Nginx配置并重启/重载。未部署，未操作真实账号或上传数据。
- 验证：新增3项测试先因功能缺失失败；最终后端73项、前端4项通过，Python与JS语法检查通过。前端测试覆盖记录、画廊、普通/分段预览；后端覆盖大图、原图保留、历史补图、缓存、访问权限、方向/透明背景及HTML链接。Nginx本机未安装，配置加载需部署时验证。

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
- 选择器 `#photo-input` 与拖放统一为叠加：每次选择/拖放都追加到待上传列表（此前选择会整体覆盖、拖放追加）。`collectPhotoFiles` 已移除 `replace` 选项（2026-09-12-photo-stack）。

## 已知问题（非本次引入）
- **2026-09-12 接口有 5 组、页面却提示无照片的根因已确认**：用户 Edge 的 `views.js` 实际来自磁盘缓存，旧代码读取 `journal.photos`、`journal.texts`；接口已返回 `journal.groups`，旧代码因此渲染空态。服务器文件与本地一致，不代表浏览器执行的版本一致。通过当前页面开发者工具只读确认，强制刷新后已恢复 5 张图片轮播和 2 条文字。
  - 最终修改仅针对缓存：`index.html` 静态资源与整个 ES 模块依赖链统一携带 `?v=20260912-groups-1`；Nginx `/src/` 和入口禁止存储及条件 304，`/assets/` 强制重新验证。以后发布前端变更时同步更新入口和模块引用中的版本号，不能只改入口脚本。
  - 上一轮轮播定位和图片加载提示改动已还原；空文字是用户未填写，不是数据丢失；图片文件较大并非“无照片”空态根因。不改后端字段，也不向接口加冗余旧字段。
  - `tests/journal_save.test.cjs` 用真实浏览器 HTTP 缓存先缓存旧字段视图，再加载新入口及用户提供的 5 组数据，验证 5 张图片、2 条文字及文字切换。修复前失败 0 != 5，修复后通过；54 项后端测试及 2 项照片文件测试也全部通过。运行：`node --test tests/journal_save.test.cjs`（需安装 Playwright 和 Chrome，可用 `NODE_PATH` 指向现有 Playwright 目录）。
  - 当前浏览器通过强制刷新已恢复；本地缓存修复尚未发布到服务器。部署需同步完整前端并应用 Nginx 配置，先 `nginx -t` 再重载；本机没有 Nginx，不能声称已验证服务器配置加载。
- **2026-09-12 MPO 上传已修复**：用户样本 `IMG_8051.PNG` 实际被 Pillow 识别为 MPO（多图像 JPEG），被 `save_photos` 白名单拒绝。后端现接受 MPO，使用主图并按方向信息转正、转存普通 JPEG。真实样本经隔离 `/api/journals` 保存和读取验证通过；54 项后端测试通过，含大写 PNG 的 10 种模式/MIME 组合及 MPO 主图回归。此前 HEIF 和前端队列修改并非该样本根因。不要将文件后缀当作真实编码证据。
- `tests/browser_smoke.py` 相对当前 UI 已过期：断言 `[name="api_key"]`（设置页保存后已移除 name）与 `.photo-preview`（已重构为 `.photo-carousel`）均会失败。属既有失配，未在本次范围内修改。

## 红线（沿用 AGENTS.md）
删除库/批量删文件/改外部接口/上传数据/操作真实账号 = 先确认；不主动提交 git；密钥绝不入代码。

## 2026-09-12 同日多故事与轮播清空
- 变更说明：生成成功后清空本次轮播图文；同日故事按序号独立归档，保留原 HTML。
- `story_records(filename PRIMARY KEY, payload)` 保存每篇故事；启动时兼容回填旧 `rides`，优先使用 payload.filename。`rides` 继续按日期保存最新结果，兼容现有日期查询及编辑入口。
- `persist_record(data, journal)` 在同一 SQLite 写事务内分配 `YYYYMMDD.html` / `YYYYMMDD_2.html` / `YYYYMMDD_3.html` 等文件名、保存归档和更新手记；同时检查磁盘文件与归档记录，避免覆盖旧文件。失败回滚。
- 成功后仅清空生成快照中未被改动的手记组；生成期间新增/编辑的组保留。历史照片文件不删除，失败保留已保存手记。同步和异步共用该逻辑。
- 画廊从归档获取每篇故事的信息，按日期及数字序号倒序；结果页使用 record.filename。记录页不自动把上一篇故事照片带入新故事，显式 retained_photos 仍兼容。
- 前端全依赖链缓存版本：`20260912-stories-2`。
- 验证新增：同日多故事及原文件保留、轮播清空、后台生成期间新增记录、直接上传、同步/异步 AI 失败保留、导出失败回滚、已有 HTML 及重启兼容；浏览器测试增加空轮播与编号 HTML 链接检查。
- 本轮仅修改本地代码与测试，未提交、未部署，未操作真实数据。

## 2026-09-12 多段骑行故事字数与重复约束
- 变更说明：限制多段骑行文案为45字以内，并携带全部前文避免重复表达。
- 沿用现有 `len(story_units(journal)) > 1` 分段路径（单组多图也适用）；`generate_segment_copy` 接收 `previous_segments`，每次提示词携带本任务此前全部成功分段，要求语义、句式和意象不重复。
- 分段去除首尾空白后最多45个字符，含标点；超过上限时沿用任务失败处理，不保存不合格故事、不清空手记，不新增自动重试。
- 本地去除标点和空白、忽略大小写后，以 `SequenceMatcher` 相似度 >= 0.8 拦截明显近似文案；语义差异依赖模型遵循提示词，不能保证识别全部同义改写。
- 同步单段和最终汇总仍沿用原有100至200字规则；未改接口结构，未调用真实AI、未上传或部署、未提交。
- 验证：新增7项测试先失败后通过；完整后端68项测试通过，后端与测试文件语法检查通过。

## 2026-09-12 图片选择改为叠加
- 变更说明：记录页图片选择器与拖放统一为叠加；此前 `#photo-input` 每次选择会整体覆盖待上传列表（第二次选 1 张，之前的 5 张丢失）。
- `frontend/src/interactions.js`：`addFiles` 去掉 `replace` 参数，选择器 change 事件不再传 `{ replace: true }`；选择 0 张（取消选择）直接忽略，不清空已有列表；格式校验失败仍保留原列表并提示。
- `frontend/src/photo-files.js`：`collectPhotoFiles` 移除 `replace` 选项，统一追加；混入不支持格式时保留原列表并返回错误提示。
- 前端全依赖链缓存版本：`20260912-photo-stack-1`（覆盖旧 `20260912-stories-2`）。
- 测试：`tests/photo_files.test.mjs` 更新为叠加语义（含 5+1=6 用例与混入非法格式保留原列表用例）；`tests/journal_save.test.cjs` 既有断言（连续两次选择必须累加、6 张）即为复现测试。
- 验证状态：单测 3/3 通过、两文件 `node --check` 通过；浏览器回归因审批服务 503 未运行，需 `NODE_PATH=/Users/changx/.hermes/hermes-agent/node_modules node --test tests/journal_save.test.cjs` 补跑。
