# Questionnaire Automation

## 项目用途

本项目接收符合固定 CSV 模板的问卷数据，自动判断实验设计并进行产品比较，生成供业务人员预览的 PR Excel 报告和供 PostgreSQL 使用的标准化 CSV。网页还提供模板下载、访问计数及每次访问的后台记录。

原始输入列名和列顺序以 [header-only 输入 schema](calculation/2_1_Analysis%20Input%20schema.csv) 为准：受访者编号、产品/Leg，以及 `Day{number}_{DQ_name}` 格式的 DQ 指标列。运行时不接受其他列名或列顺序。

## 本地运行

需要 Python 3.10 或更高版本，并配置 PostgreSQL。上传数据和按 Study Name 分析都直接访问 PostgreSQL。

```bash
python -m pip install -r requirements-dev.txt
uvicorn backend.src.main:app --reload
```

启动前配置 `DATABASE_URL` 和 `DATABASE_TABLE`（默认 `consumer_questionnaire.questionnaire_data`），不要把真实凭据提交到 Git：

```bash
export DATABASE_URL='postgresql://...'
export DATABASE_TABLE='consumer_questionnaire.questionnaire_data'
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
| Upload Questionnaire File：上传区（`/workspace` 上方） | `#upload-form`、`#csv-file`、`#upload-study-name`、`#upload-button`、`#upload-status` | Long/Wide CSV 上传和 Wide 格式 Study Name 在 [frontend/index.html](frontend/index.html)；POST `/api/uploads` 与反馈在 [frontend/src/app.js](frontend/src/app.js)；样式 `.upload-section` / `.upload-fields` 在 [frontend/src/app.css](frontend/src/app.css) |
| Analysis Setup：分析区（`/workspace` 下方） | `#analysis-form`、`#existing-study`、`#refresh-studies`、`#run-button`、`#status` | 只选择 PostgreSQL 已有 Study Name 并提交分析；交互在 [frontend/src/app.js](frontend/src/app.js)，名称来自 `GET /api/studies` |
| PR Results：报告预览（`/workspace`） | `#results`、`#report-table`、`#database-status`、`#report-caption` | 渲染在 [frontend/src/app.js](frontend/src/app.js) 的 `renderReport()`；表格样式 `.table-scroll`、`table`、`thead`、`tbody` 在 [frontend/src/app.css](frontend/src/app.css) |
| Standard Files：标准文件下载（`/workspace`） | `.standard-files`、`.standard-grid`、`.standard-file` | 链接在 [frontend/index.html](frontend/index.html)；样式 `.standard-*` 在 [frontend/src/app.css](frontend/src/app.css)；下载路由在 [backend/src/main.py](backend/src/main.py) 的 `download_template()` |

修改登录页只需定位 `frontend/login.html`、`frontend/src/login.js` 和共享样式 `frontend/src/app.css`；修改工作区定位 `frontend/index.html`、`frontend/src/app.js` 和同一份共享样式。所有页面文案目前是英文。

## 分析与数据流程

1. 网页提交 email 和 BU 到 `POST /api/access/confirm`。后台把访问时间、email 和 BU 写入 SQLite，并返回访问 token。
2. 上传区支持 Long 和 Wide CSV。Long 文件包含六个业务列，`1_Study` 沿用文件内值；Wide 文件必须匹配固定 65 列输入 schema，并在上传区填写 Study Name。
3. `POST /api/uploads` 检测格式；Wide 数据按 `Day{number}_{DQ_name}` 展开为数据库 Long 行，Long 数据直接校验。两种格式均在上传成功前写入 PostgreSQL 的 `consumer_questionnaire.questionnaire_data`。
4. `GET /api/studies` 只从 PostgreSQL 的 `1_Study` 列读取名称。分析区选择已入库 Study Name 后，`POST /api/analyze` 从 PostgreSQL 读取该 Study 的六个业务列，并按该 Study 实际存在的 `Day_DQ` 指标重建分析 Wide 表；不要求每个 Study 都包含固定模板中的全部 DQ 列。
5. [calculation/2_2_main.py](calculation/2_2_main.py) 的 `detect_experiment_type()` 按每个受访者对应的唯一产品数分流：一个产品为 independent、两个为 paired、三个或以上为 mixed。
6. 对应算法和统计方法保持不变，仅对已存 Study 中存在且符合 `Day{number}_{DQ_name}` 的 DQ 列进行计算。报告结构不变，按产品计算均值和 N；`p < 0.05` 时，在均值后追加显著差异对手的产品缩写，例如 `64 B` 或 `69 AB`。
7. 报告写入 `Rep(All Data)` 工作表，并可下载该 Study 的六列数据库数据。PostgreSQL 不可用、列不匹配或上传失败时，接口返回错误，不会报告“已保存”。

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
| `GET /api/studies` | 从 PostgreSQL 查询不同的 `1_Study`；DB 不可用时返回错误 |
| `POST /api/uploads` | 检测 Long/Wide CSV、校验或转换并立即写入 PostgreSQL；Wide 需提供 Study Name |
| `GET /api/templates/{kind}` | 下载 `raw-input`、`pr-report` 或 `database` 标准文件 |
| `POST /api/analyze` | 按已入库 Study Name 从 PostgreSQL 读取数据并生成报告/导出文件；需要 Bearer token |
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
| [backend/src/usage_store.py](backend/src/usage_store.py) | SQLite 基准计数、访问事件和 token hash |
| [backend/src/database.py](backend/src/database.py) | PostgreSQL 列检查与安全插入 |
| [backend/src/ingestion.py](backend/src/ingestion.py) | Long/Wide 格式识别、Wide 转 Long、Long 转分析 Wide |
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

设置 `DATABASE_URL` 和 `DATABASE_TABLE`（默认 `consumer_questionnaire.questionnaire_data`）后，上传会检查目标表包含六个业务列且顺序正确，再以事务插入这些列；数据库生成 `id` 和时间戳等管理字段。缺少连接或列不匹配时上传失败，不会仅保存在本地。详情见 [docs/database.md](docs/database.md)。

产品缩写按产品代码排序后分配 A、B、C……；PR 输出顺序为 A 列 DQ Question、B 列 Time Point、C 列起按产品名动态扩展。输出不再包含空白分隔列或 Chinese Description 列；显著性标记规则和统计方法不变。

含有 respondent 数据行的原始 `2_1_Analysis Input Mod_PCTtest_DQ.csv` 和 `3_1_Target Database format.csv` 保留在本地并由 `.gitignore` 排除，避免将问卷明细推送到远端。代码和测试改用 header-only 的 `2_1_Analysis Input schema.csv` 与 `3_1_Target Database schema.csv` 获取固定列定义，不依赖被忽略的数据文件。
