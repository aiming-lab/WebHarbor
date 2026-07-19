# WebHarbor 网站 Clone Guidance

这份文档说明 WebHarbor 是如何把一个真实网站做成可本地运行、可重置、可用于 GUI agent benchmark 的镜像环境，并给出新增一个网站的实操流程。

## 1. 这个 repo 所谓的 clone 是什么

WebHarbor 不是简单把网页 HTML 静态下载下来，也不是运行时代理真实网站。它做的是一个确定性的本地镜像：

- 用真实网站做参照，采集关键页面结构、导航、文案、截图和图片资产。
- 用 Flask + Jinja2 + SQLAlchemy 重新实现前端页面、后端路由、搜索、登录、购物车、账户、收藏、订单等交互。
- 用 SQLite seed DB 固定初始状态，让每次 benchmark rollout 都从同一份数据开始。
- 用 Docker 把多个站点打进同一个镜像，每个站点一个独立 Flask 进程。
- 用 `control_server.py` 暴露 `/reset/<site>`，每次重置时杀掉站点进程、删除 runtime DB、从 seed DB 复制一份新的 DB，然后重新启动。

所以这里的 clone 更准确地说是“仿真式镜像”：视觉和行为要足够像真实网站，但运行时完全离线、稳定、可控。

## 2. 仓库结构和职责

核心目录：

```text
sites/<site>/
├── app.py                       Flask app: routes, SQLAlchemy models, auth, handlers
├── seed_data.py                 构造初始数据，生成 SQLite seed
├── _health.py                   站点健康检查
├── templates/                   Jinja2 页面模板
├── static/css/                  小型 CSS，进 Git
├── static/js/                   小型 JS，进 Git
├── static/icons/                小型图标，进 Git
├── static/images/               大图片资产，走 Hugging Face dataset
├── static/external_cache/       可选外部缓存资产，走 Hugging Face dataset
├── instance_seed/<site>.db      seed DB，走 Hugging Face dataset
├── instance/<site>.db           runtime DB，启动和 reset 时从 seed 复制
├── scraped_data/                采集阶段中间文件，不进入镜像
└── tasks.jsonl                  benchmark tasks
```

顶层运行文件：

```text
websyn_start.sh                  容器入口，启动所有站点和控制面
control_server.py                :8101 控制面，支持 health/reset/restart
site_runner.py                   单站点 supervisor，负责可杀进程组
Dockerfile                       构建包含所有站点的镜像
scripts/new_site.py              新站点脚手架
scripts/fetch_assets.sh          从 HF dataset 拉取大资产
scripts/extract_assets.sh        把大资产打包成 <site>.tar.gz 供 HF 上传
scripts/check_assets.sh          构建前检查 seed DB 是否存在
scripts/build.sh                 检查资产并 docker build
```

资产边界：

- Git repo 保存代码、小模板、小 CSS/JS、任务文件和文档。
- Hugging Face dataset `ChilleD/WebHarbor` 保存大资产：`instance_seed/`、`static/images/`、`static/external_cache/`。
- `.assets-revision` 决定 `fetch_assets.sh` 拉哪个 HF revision。
- `.gitignore` 会忽略 HF 管理的大资产和 runtime 中间文件。
- `.dockerignore` 不忽略 `instance_seed/` 和 `static/images/`，因为构建镜像时必须把已经拉下来的资产复制进去。

## 3. 运行和 reset 机制

容器启动时：

1. `websyn_start.sh` 读取 `SITES=(...)`。
2. 对每个站点删除 `/opt/WebSyn/<site>/instance`。
3. 从 `/opt/WebSyn/<site>/instance_seed` 复制出新的 `/opt/WebSyn/<site>/instance`。
4. 按顺序启动每个站点，端口是 `40000 + index`。
5. 启动 `control_server.py`，监听 `:8101`。

reset 单站点时：

1. `POST /reset/<site>` 进入 `control_server.py`。
2. 控制面读取 `/tmp/websyn_pids/<site>.pid`。
3. 用 process group kill 掉 `site_runner.py` 和它的 Flask child。
4. 删除 runtime `instance/`。
5. 从 `instance_seed/` 复制一份干净 DB。
6. 重新启动站点并等待首页可访问。

这就是 WebHarbor 对 RL/benchmark 友好的关键：每个任务后可以恢复到同一份初始状态。

严格要求：reset 后 runtime DB 和 seed DB 的 md5 应该一致。

```bash
docker exec wh-test md5sum \
  /opt/WebSyn/<site>/instance/<site>.db \
  /opt/WebSyn/<site>/instance_seed/<site>.db
```

如果两个 md5 不一致，通常是 `seed_*()` 函数没有做到函数级 idempotent，或者 app 启动时写入了 runtime DB。

## 4. 新增网站的端到端流程

### Step 0: 定义目标和 slug

先明确：

- 真实站点 URL，例如 `https://www.recreation.gov/`。
- 本地 slug，例如 `recreation_gov`，只能用小写字母、数字、下划线。
- 站点的核心功能面：搜索、浏览、详情、登录、账户、收藏、购物车、下单、订单管理等。
- benchmark 需要覆盖的任务类型。

不要一开始就追求全站爬取。WebHarbor 更看重可交互的核心功能和任务覆盖。

### Step 1: scaffold

```bash
./scripts/new_site.py <site>
```

脚手架会生成：

```text
sites/<site>/app.py
sites/<site>/_health.py
sites/<site>/requirements.txt
sites/<site>/templates/index.html
sites/<site>/static/{css,js,icons,images,external_cache}/
sites/<site>/instance_seed/
sites/<site>/instance/
sites/<site>/scraped_data/
```

然后把站点注册到三个地方，顺序必须一致：

- `websyn_start.sh` 的 `SITES=(...)`
- `control_server.py` 的 `SITES = [...]`
- `Dockerfile` 的 `EXPOSE 8101 40000-400NN`

端口规则是 `40000 + SITES index`。如果当前最后一个站点 index 是 15，那么本地端口就是 `40015`，Docker 测试时也要暴露到对应范围。

### Step 2: 侦察真实网站

目标是理解“需要仿什么”，不是盲目下载所有页面。

建议保存到 `sites/<site>/scraped_data/`：

- 首页 HTML、纯文本和截图。
- 搜索结果页、分类页、详情页、登录页、账户页、购物车/checkout 页。
- 主要导航结构、URL pattern、表单字段、筛选项、排序项。
- 页面视觉特征：布局、字体层级、颜色、卡片结构、按钮样式、响应式行为。
- 图片清单：logo、hero 图、商品/文章/地点图片、图标。
- `recon_summary.json`，总结站点信息架构、关键路由、实体类型和待实现功能。

`scraped_data/` 是中间材料，`.gitignore` 和 `.dockerignore` 都会排除它。运行时不能依赖它。

### Step 3: 采集并整理真实资产

图片、截图、缓存页面等大资产放到：

```text
sites/<site>/static/images/
sites/<site>/static/external_cache/
```

要求：

- 尽量使用真实网站相关资产，不用灰色 placeholder。
- 文件名稳定、可读，模板里用 `url_for("static", filename="images/...")` 引用。
- 大图和 seed DB 不直接提交到 Git，后续用 `extract_assets.sh` 打包上传到 HF dataset。
- 小型 CSS/JS/icon 可以留在 Git repo。

### Step 4: 建模和 seed DB

在 `app.py` 定义 SQLAlchemy models，在 `seed_data.py` 构造初始数据。

典型实体：

- 内容型网站：Article、Topic、Author、Bookmark、SearchHistory。
- 电商网站：Product、Category、Review、CartItem、Order、Address、PaymentMethod。
- 预订网站：Facility、Room/Campsite、Reservation、SavedItem、PaymentMethod。
- 开发者网站：User、Repository、Issue、PullRequest、Notification、Star、Watch。

原则：

- Runtime handler 只读 SQLite，不读 `scraped_data/*.json`。
- `seed_data.py` 可以读取/转化采集结果，但最后要落入 `instance_seed/<site>.db`。
- 每个主要实体至少有足够多的 distractors，不要让任务答案成为唯一结果。
- 所有 `seed_*()` 函数必须函数级 idempotent。

正确模式：

```python
def seed_database(db, Product, Category):
    if Product.query.count() > 0:
        return
    # add rows
    db.session.commit()


def seed_benchmark_users(db, User):
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    # add users
    db.session.commit()
```

反模式：

```python
def seed_database():
    for row in rows:
        if not Product.query.filter_by(slug=row["slug"]).first():
            db.session.add(Product(**row))
    db.session.commit()
```

反模式的问题是：即使没有新增行，一次空 commit 也可能改变 SQLite 元数据，导致 reset 后 md5 不一致。

### Step 5: 实现 Flask routes 和交互

`app.py` 是每个站点的核心。常见路由：

```text
GET  /
GET  /search
GET  /category/<slug>
GET  /product/<slug> 或 /facility/<slug>
GET/POST /login
GET/POST /register
GET/POST /account
GET  /saved 或 /wishlist
GET/POST /cart
GET/POST /checkout
GET  /orders 或 /reservations
POST /.../cancel
GET  /_health
```

交互要求：

- 所有重要页面都能从首页点击到，不要有孤儿页面。
- 搜索不要只做 exact match，建议做 token-overlap scoring。
- 表单提交要真实修改 DB，并给出可见反馈。
- 登录态用 Flask-Login，benchmark 用户统一使用 `TestPass123!`。
- 登录后任务要有预置状态，例如已有收藏、购物车、订单、地址、支付方式。
- 404/空状态也要有页面，不能直接报错。

### Step 6: 复刻前端

模板放在 `templates/`，样式放在 `static/css/`，少量行为放在 `static/js/`。

目标是“对 agent 来说像真实网站”：

- 导航、搜索框、筛选侧栏、详情卡、CTA 位置要接近真实网站。
- 重要文本、按钮 label、表单字段要符合真实站点习惯。
- 图片和卡片布局要足够丰富，避免所有结果长得一样。
- 移动端至少不能崩。
- 不追求像素级一致，但不能像 toy app。

Jinja 模板应从 SQLAlchemy objects 渲染，避免把答案硬编码进模板。

### Step 7: 写 benchmark tasks

任务写到：

```text
sites/<site>/tasks.jsonl
```

每行一个 JSON object，使用 WebVoyager schema：

```json
{"web_name":"My Site","id":"MySite--0","ques":"Search for ...","web":"http://localhost:40015/","upstream_url":"https://www.example.com/"}
```

建议 15-20 个任务，覆盖：

- 搜索和筛选。
- 打开详情页读取属性。
- 多结果比较。
- 登录后状态操作。
- 收藏/购物车/checkout/取消订单等写操作。
- 账户设置修改。
- 帮助页、文章页、政策页等非交易型内容。
- 3-5 个需要多步推理或消歧的 hard tasks。

任务设计要反向驱动环境完善。每个任务都应该能在本地镜像里通过真实点击和阅读完成。

### Step 8: task-driven evolution

写完 tasks 后逐个跑一遍，按任务补环境。

检查点：

- 任务提到的每个页面、按钮、表单都存在。
- 搜索结果里有足够的近似候选，而不是只有目标项。
- 需要比较的信息必须在详情页或更深层页面，不要一眼暴露在卡片标题。
- checkout、cancel、save、edit profile 等操作必须真正改变 DB。
- hard task 不能靠 URL 猜测或页面标题直接完成。

这个阶段经常会新增 route、模板、seed rows、筛选逻辑和 UI 状态。

### Step 9: hardening

WebHarbor 的难点不只是“能点通”，而是避免任务被 reward hacking。

重点审查四件事：

- De-leak：答案不要直接出现在 task 文本、卡片标题、结果摘要、页面 heading。
- Distractors：每个任务至少有多个 near-miss 结果，只差一个条件。
- Catalog breadth：搜索结果要有多个类别、价格、状态、地区、评分等维度。
- Cross-field consistency：修改产品/设施字段时，同步更新 specs、description、tags、filters。

常见坏味道：

- 搜索某个商品只返回一个结果。
- 任务问“哪一个支持 X”，结果卡片标题就写着 X。
- 详情页描述和筛选字段互相矛盾。
- 表单提交只是 redirect，没有修改 DB。
- 登录后所有用户看到同一份 cart/order。
- seed 里只有任务答案，没有自然背景数据。

### Step 10: 稳定 seed DB

本地生成 seed 的常见方式：

```bash
python3 -m py_compile sites/<site>/app.py
python3 sites/<site>/app.py
```

或通过 Docker build/run 触发 app import 和 `db.create_all()`。

最终要把稳定 DB 放到：

```text
sites/<site>/instance_seed/<site>.db
```

然后验证：

```bash
./scripts/build.sh webharbor:dev

docker run -d --rm --name wh-test \
  -p 8201:8101 -p 41000-410NN:40000-400NN \
  webharbor:dev

curl -X POST http://localhost:8201/reset/<site>

docker exec wh-test md5sum \
  /opt/WebSyn/<site>/instance/<site>.db \
  /opt/WebSyn/<site>/instance_seed/<site>.db
```

两个 md5 必须一致。

## 5. 构建、运行和检查

安装或拉取资产：

```bash
./scripts/fetch_assets.sh
```

只拉某个站点：

```bash
./scripts/fetch_assets.sh <site>
```

构建镜像：

```bash
./scripts/build.sh webharbor:dev
```

运行镜像。端口范围要覆盖当前 `SITES` 中所有站点：

```bash
docker run -d --rm --name wh-test \
  -p 8201:8101 \
  -p 41000-410NN:40000-400NN \
  webharbor:dev
```

检查控制面：

```bash
curl -s http://localhost:8201/health | python3 -m json.tool
```

检查页面是否返回 200：

```bash
for p in $(seq 41000 410NN); do
  curl -so /dev/null -w "$p:%{http_code}\n" http://localhost:$p/
done
```

检查单站点 reset：

```bash
curl -X POST http://localhost:8201/reset/<site>
```

停止测试容器：

```bash
docker stop wh-test
```

## 6. 资产提交流程

新增或更新大资产后，把 HF 管理路径打包：

```bash
./scripts/extract_assets.sh ../wh-static-pr/ <site>
```

会生成：

```text
../wh-static-pr/<site>.tar.gz
```

上传到你的 HF dataset fork：

```bash
cd ../wh-static-pr
hf upload <site>.tar.gz <your-fork>/WebHarbor <site>.tar.gz --repo-type dataset
```

在 Hugging Face 上给 `ChilleD/WebHarbor` 开 asset PR。合并后，把这个代码 repo 的 `.assets-revision` bump 到 HF merge commit，再开 GitHub PR。

如果一次打包所有站点：

```bash
./scripts/extract_assets.sh ../wh-static-pr/
```

但新增单站点时优先只打包该站点，PR 更容易 review。

## 7. PR 前 definition of done

提交前至少满足：

- `python3 -m py_compile sites/<site>/app.py` 通过。
- `./scripts/build.sh webharbor:dev` 通过。
- Docker 容器启动后所有站点 ready。
- 新站点首页、搜索页、详情页、登录页、主要写操作返回正常。
- `POST /reset/<site>` 返回 `ready: true`。
- runtime DB 和 seed DB md5 一致。
- `tasks.jsonl` 有 15-20 个任务。
- 每个任务都能通过真实 UI 操作完成。
- 任务答案没有明显泄漏。
- 搜索/筛选有足够 distractors。
- 大资产已打包并上传到 HF PR。
- GitHub PR 描述包含真实网站 URL、seed row 数、HF PR 链接、reset 输出和截图对比。

## 8. 常见问题

### 构建时报缺少 `instance_seed`

先运行：

```bash
./scripts/fetch_assets.sh
```

如果是新站点，需要先生成 `sites/<site>/instance_seed/<site>.db`。

### reset 后 md5 不一致

检查：

- 是否有 `seed_*()` 函数没有在函数开头 early return。
- 是否 app import 时写入了时间戳、访问日志、默认设置等 runtime 数据。
- 是否某个 request handler 在首页访问时修改 DB。
- 是否把 runtime `instance/<site>.db` 当成 seed 以外的可变数据源。

### 站点启动失败

进入容器看日志：

```bash
docker exec wh-test tail -n 200 /tmp/websyn_<site>.log
```

常见原因是 app import 阶段 seed 失败、模板引用不存在的字段、图片路径错误、SQLite 文件不存在。

### 新站点端口不通

检查三处是否同步：

- `websyn_start.sh`
- `control_server.py`
- `Dockerfile EXPOSE`

同时检查 `docker run -p` 的端口范围是否覆盖新站点端口。

### task 太简单

增加 near-miss distractors，把关键信息下沉到详情页或规格表，扩大 catalog，并避免把答案词直接放在标题和摘要里。

## 9. 推荐的一次性 agent prompt

如果让 coding agent 执行新增网站，可以用这个简化 prompt：

```text
Target site: <REAL_URL>
Site slug: <site_slug>

Build a WebHarbor mirror under sites/<site_slug>/.

Requirements:
- Run ./scripts/new_site.py <site_slug> if the folder does not exist.
- Register the site in websyn_start.sh, control_server.py, and Dockerfile.
- Recon the real site: navigation, core routes, page types, forms, visual style, assets.
- Save scrape intermediates under sites/<site_slug>/scraped_data/.
- Implement a self-contained Flask + SQLAlchemy app in sites/<site_slug>/app.py.
- Put runtime data in SQLite only; do not read scraped_data at request time.
- Implement idempotent seed_database() and seed_benchmark_users().
- Seed 4 benchmark users using password TestPass123!.
- Build Jinja templates and CSS/JS matching the real site's core UI.
- Add search, details, auth, account, saved/cart/order style flows as appropriate.
- Write 15-20 WebVoyager-schema tasks in sites/<site_slug>/tasks.jsonl.
- Evolve the app until every task is solvable through the UI.
- Harden tasks against answer leakage and insufficient distractors.
- Produce sites/<site_slug>/instance_seed/<site_slug>.db.
- Run py_compile, build, docker run, /reset/<site_slug>, and md5 verification.
- Stop before opening PRs. Summarize changed files, seeded row counts, task count, reset result, and required HF/GitHub PR steps.
```

## 10. Existing example to study

`sites/recreation_gov/` is a useful reference for a task-driven mirror:

- `scraped_data/` contains representative HTML/text/screenshots from reconnaissance.
- `app.py` implements models, scored search, map-ish presentation, auth, saved items, cart, checkout, reservations, account editing, API and health route.
- `seed_data.py` creates facilities, campsites, reviews, benchmark users, saved items, cart items and reservations with function-level gates.
- `tasks.jsonl` covers search, comparison, authenticated state changes, checkout, cancellation, help content and disambiguation.
- `instance_seed/recreation_gov.db` is the seed DB copied on every reset.

Use it as a pattern, not as shared code. Each site must stay self-contained.
