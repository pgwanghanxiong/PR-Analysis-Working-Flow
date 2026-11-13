# Questionnaire Automation

## 项目用途

本项目接收符合固定 CSV 模板的问卷数据，自动判断实验设计并进行产品比较，生成供业务人员预览的 PR Excel 报告和供 PostgreSQL 使用的标准化 CSV。网页还提供模板下载、访问计数及每次访问的后台记录。

原始输入列名和列顺序以 [header-only 输入 schema](calculation/2_1_Analysis%20Input%20schema.csv) 为准：受访者编号、产品/Leg，以及 `Day{number}_{DQ_name}` 格式的 DQ 指标列。运行时不接受其他列名或列顺序。

## 本地运行

需要 Python 3.10 或更高版本。PostgreSQL 仅在需要直接写库时需要配置。

```bash
python -m pip install -r requirements-dev.txt
uvicorn backend.src.main:app --reload
```

独立运行分析脚本时，必须显式传入原始 CSV 路径，例如：

```bash
python calculation/2_2_main.py path/to/raw-input.csv
```

浏览器打开 <http://127.0.0.1:8000/login> 完成访问确认；根路径 `/` 会跳转到 `/login`。确认后进入 <http://127.0.0.1:8000/workspace>，该页面用于分析和模板下载。直接访问工作区但没有有效 session 时会跳回登录页。

进入前填写 work email 和 business unit (BU)，点击 **Confirm and continue**。这是使用记录，不是邮箱认证；每次确认增加一次使用次数，刷新已有会话不会重复计数。计数初始值为 66，SQLite 记录默认保存在 `output/usage.sqlite3`，也可用 `USAGE_DB_PATH` 更改路径。

运行测试：

```bash
python -m pytest -q calculation/tests backend/tests
```

## 页面定位

前端拆成两个独立 URL，名称采用常见的 login/workspace 约定。`/` 不是页面，会重定向到 `/login`。

| 页面名称 / URL | 页面元素定位 | 修改位置 |
| --- | --- | --- |
| Login / Access：`/login` | `#access-gate`、`#access-form`、`#access-email`、`#access-bu`、`#gate-use-count` | 独立页面结构和文案在 [frontend/login.html](frontend/login.html)；确认、使用次数刷新、跳转在 [frontend/src/login.js](frontend/src/login.js)；外观在 [frontend/src/app.css](frontend/src/app.css) 的 `.access-*` / `.gate-usage` |
| Analysis Workspace：`/workspace` | `#app-shell`、`#usage-count`、`#analysis-form`、`.upload-section`、`.analysis-section`、`#results`、`.standard-files` | 页面结构在 [frontend/index.html](frontend/index.html)；session 检查、Study Name 查询、分析请求和报告渲染在 [frontend/src/app.js](frontend/src/app.js)；工作区和报告样式在 [frontend/src/app.css](frontend/src/app.css) |
| Workspace Header：工作区标题和计数 | `#usage-count`、`#use-count` | HTML 在 [frontend/index.html](frontend/index.html)；计数更新在 [frontend/src/app.js](frontend/src/app.js) 的 `updateUsageCount()`；样式 `.topbar` / `.usage-count` 在 [frontend/src/app.css](frontend/src/app.css) |
| Upload Questionnaire File：上传区（`/workspace` 上方） | `.upload-section`、`#csv-file`、`#file-name`、`#upload-status` | HTML 在 [frontend/index.html](frontend/index.html)；文件选择状态在 [frontend/src/app.js](frontend/src/app.js)；样式 `.upload-section` / `.file-picker` 在 [frontend/src/app.css](frontend/src/app.css) |
| Analysis Setup：分析区（`/workspace` 下方） | `.analysis-section`、`#existing-study`、`#study-name`、`#refresh-studies`、`#run-button`、`#status` | Study Name 下拉、手动输入及提交在 [frontend/src/app.js](frontend/src/app.js)；列表由 `GET /api/studies` 提供；HTML 在 [frontend/index.html](frontend/index.html)；样式 `.analysis-section` / `.study-fields` 在 [frontend/src/app.css](frontend/src/app.css) |
| PR Results：报告预览（`/workspace`） | `#results`、`#report-table`、`#database-status`、`#report-caption` | 渲染在 [frontend/src/app.js](frontend/src/app.js) 的 `renderReport()`；表格样式 `.table-scroll`、`table`、`thead`、`tbody` 在 [frontend/src/app.css](frontend/src/app.css) |
| Standard Files：标准文件下载（`/workspace`） | `.standard-files`、`.standard-grid`、`.standard-file` | 链接在 [frontend/index.html](frontend/index.html)；样式 `.standard-*` 在 [frontend/src/app.css](frontend/src/app.css)；下载路由在 [backend/src/main.py](backend/src/main.py) 的 `download_template()` |

修改登录页只需定位 `frontend/login.html`、`frontend/src/login.js` 和共享样式 `frontend/src/app.css`；修改工作区定位 `frontend/index.html`、`frontend/src/app.js` 和同一份共享样式。所有页面文案目前是英文。

## 分析与数据流程

1. 网页提交 email 和 BU 到 `POST /api/access/confirm`。后台把访问时间、email 和 BU 写入 SQLite，并返回访问 token、个人使用次数和总使用次数。
2. `/workspace` 使用 `GET /api/studies` 加载数据库中已有的 Study Name；数据库未配置或查询失败时，可以手动填写。
3. 用户在上方上传 CSV、在下方选择或填写 Study Name 后，`POST /api/analyze` 检查访问 token 和固定输入 schema。
4. [calculation/2_2_main.py](calculation/2_2_main.py) 的 `detect_experiment_type()` 按每个受访者对应的唯一产品数分流：一个产品为 independent、两个为 paired、三个或以上为 mixed。
5. 对应算法返回各 DQ 和产品对的 p-value。报告按产品计算均值和 N；`p < 0.05` 时，在均值后追加显著差异对手的产品缩写，例如 `64 B` 或 `69 AB`。
6. 报告写入 `Rep(All Data)` 工作表；宽表同时转换成固定六列的数据库 CSV。数据库连接配置存在时，只有数据库表列名和顺序完全匹配才写入，否则只输出文件并记录 warning。

### 统计方法

| 实验设计 | 算法文件 | 方法入口 / 说明 |
| --- | --- | --- |
| Independent | [2_2_Method_for_IndependentDesign.py](calculation/2_2_Method_for_IndependentDesign.py) | `run_significance_analysis()`；对独立产品样本计算 Welch 两样本 t-test p-value。脚本也包含 Shapiro、Levene 与 adaptive p-value 辅助方法。 |
| Paired | [2_2_Method_for_PairedDesign_PCT.py](calculation/2_2_Method_for_PairedDesign_PCT.py) | `run_significance_analysis()`；按受访者配对产品，计算差值并用单样本 t-test 检验均值差是否为 0；同时计算 Wilcoxon 相关统计量。 |
| Mixed | [2_2_Method_for_MixedDesign_SQM.py](calculation/2_2_Method_for_MixedDesign_SQM.py) | `run_significance_analysis()`；尝试拟合随机受访者截距 mixed model，并按产品对做配对 t-test；配对不足时回退到独立 Student t-test。 |

三种脚本均调用 [calculation/input_schema.py](calculation/input_schema.py) 校验输入列名、顺序、必填字段、日列命名和数值。报告与 CSV 转换集中在 [calculation/report_pipeline.py](calculation/report_pipeline.py)。

## 页面与 API

后端入口是 [backend/src/main.py](backend/src/main.py)。主要路由：

| 路由 | 用途 |
| --- | --- |
| `GET /` | 重定向到 `/login` |
| `GET /login` | 返回访问确认页面 |
| `GET /workspace` | 返回分析工作区；前端检查 session，无有效 token 时跳回 `/login` |
| `GET /api/health` | 服务健康检查 |
| `GET /api/usage/count` | 仅返回总使用次数，不返回用户信息 |
| `POST /api/access/confirm` | 校验并记录 email、BU，建立访问 session |
| `GET /api/access/session` | 恢复当前浏览器 session 并返回个人/总次数 |
| `GET /api/studies` | 根据 `DATABASE_TABLE` 查询已有的不同 `1_Study`；数据库不可用时返回手动输入提示 |
| `GET /api/templates/{kind}` | 下载 `raw-input`、`pr-report` 或 `database` 标准文件 |
| `POST /api/analyze` | 上传 CSV、运行分析并生成报告/数据库文件/验证日志；需要 Bearer token |
| `GET /api/runs/{run_id}` | 读取一次运行的预览和验证日志 |
| `GET /api/runs/{run_id}/artifacts/{kind}` | 下载该次运行的报告、数据库 CSV 或验证日志 |

## 关键文件

| 文件 | 职责 |
| --- | --- |
| [frontend/login.html](frontend/login.html) | `/login` 访问确认页面结构 |
| [frontend/src/login.js](frontend/src/login.js) | `/login` 表单、计数展示、访问确认和跳转 |
| [frontend/index.html](frontend/index.html) | `/workspace` 分析、结果和模板下载结构 |
| [frontend/src/app.css](frontend/src/app.css) | 登录页和工作区共用的桌面/移动端样式 |
| [frontend/src/app.js](frontend/src/app.js) | `/workspace` session 检查、分析请求和报告表格渲染 |
| [backend/src/main.py](backend/src/main.py) | FastAPI 路由、访问限制及分析请求编排 |
| [backend/src/usage_store.py](backend/src/usage_store.py) | SQLite 基准计数、访问事件、按 email 统计及 token hash |
| [backend/src/database.py](backend/src/database.py) | PostgreSQL 列检查与安全插入 |
| [calculation/input_schema.py](calculation/input_schema.py) | 原始 CSV 固定 schema 的唯一校验入口 |
| [calculation/2_2_main.py](calculation/2_2_main.py) | 实验设计识别及统计算法分发 |
| [calculation/report_pipeline.py](calculation/report_pipeline.py) | PR 报告构建、数据库平表转换、文件输出 |
| [calculation/2_1_Analysis Input schema.csv](calculation/2_1_Analysis%20Input%20schema.csv) | 仅含表头的原始输入列定义 |
| [calculation/3_1_Target Database schema.csv](calculation/3_1_Target%20Database%20schema.csv) | 仅含表头的 PostgreSQL 导入目标列定义 |
| [calculation/3_2_Target Result Format.xlsx](calculation/3_2_Target%20Result%20Format.xlsx) | PR Excel 工作簿模板 |

## 输出与数据库

每次分析在 `output/{run_id}/` 下生成：

- `business_report.xlsx`：业务报告。
- `database_ingestion.csv`：按 `3_1_Target Database format.csv` 六列顺序生成的平表。
- `validation_log.json`：schema、统计、输出行数和数据库结果。

直接写 PostgreSQL 时设置 `DATABASE_URL` 和 `DATABASE_TABLE`（默认 `consumer_questionnaire.questionnaire_data`）。当前仓库定义的该表还包含管理列，因此与六列目标格式不匹配，系统会跳过插入并记录 warning，不会自动修改表结构。详情见 [docs/database.md](docs/database.md)。

产品缩写按产品代码排序后分配 A、B、C，最多支持三个产品；参考文件没有独立产品全名映射或中文描述，因此显示产品代码，中文描述留空。

含有 respondent 数据行的原始 `2_1_Analysis Input Mod_PCTtest_DQ.csv` 和 `3_1_Target Database format.csv` 保留在本地并由 `.gitignore` 排除，避免将问卷明细推送到远端。代码和测试改用 header-only 的 `2_1_Analysis Input schema.csv` 与 `3_1_Target Database schema.csv` 获取固定列定义，不依赖被忽略的数据文件。
