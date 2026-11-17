# Questionnaire Automation

[中文](#中文) | [English](#english)

# 中文

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

浏览器打开 <http://127.0.0.1:8000/login> 完成访问确认；根路径 `/` 会跳转到 `/login`。确认后进入 `/questionnaire` 菜单，可分别打开 Questionnaire Data Upload、Questionnaire Data View 和 Questionnaire Data Analysis。旧的 `/workspace` 路径重定向到分析页；各功能页没有有效 session 时会跳回登录页。

进入前填写 work email 和 business unit (BU)，点击 **Confirm and continue**。这是使用记录，不是邮箱认证；每次确认增加一次使用次数，刷新已有会话不会重复计数。计数初始值为 66，SQLite 记录默认保存在 `output/usage.sqlite3`，也可用 `USAGE_DB_PATH` 更改路径。

运行测试：

```bash
python -m pytest -q calculation/tests backend/tests
```

## 页面定位

前端包含登录页、Questionnaire 菜单 hub、独立上传页、Questionnaire Create、数据查看页和分析页。`/` 会重定向到 `/login`；旧 `/workspace` 路径保留为分析页兼容跳转。

| 页面名称 / URL | 页面元素定位 | 修改位置 |
| --- | --- | --- |
| Login / Access：`/login` | `#access-gate`、`#access-form`、`#access-email`、`#access-bu`、`#gate-use-count` | 独立页面结构和文案在 [frontend/login.html](frontend/login.html)；确认、使用次数刷新、跳转在 [frontend/src/login.js](frontend/src/login.js)；外观在 [frontend/src/app.css](frontend/src/app.css) 的 `.access-*` / `.gate-usage` |
| Questionnaire Menu：`/questionnaire` | `.questionnaire-menu`、各模块链接 | 页面结构在 [frontend/questionnaire.html](frontend/questionnaire.html)；session 校验在 [frontend/src/hub.js](frontend/src/hub.js)；样式 `.questionnaire-menu` 在 [frontend/src/app.css](frontend/src/app.css) |
| Questionnaire Data Upload：`/questionnaire-data-upload` | `#upload-form`、`#csv-file`、`#upload-study-name`、`#upload-button`、`.standard-files` | 独立页面在 [frontend/upload.html](frontend/upload.html)；Long/Wide 上传在 [frontend/src/upload.js](frontend/src/upload.js)；模板下载仍由 [backend/src/main.py](backend/src/main.py) 的 `download_template()` 提供 |
| Questionnaire Standard Upload：`/questionnaire-standard-upload` | `#questionnaire-standard-upload-form`、`#questionnaire-standard-file`、`#questionnaire-standard-upload-button` | 独立页面在 [frontend/questionnaire-standard-upload.html](frontend/questionnaire-standard-upload.html)；文件选择、session 和上传请求在 [frontend/src/questionnaire-standard-upload.js](frontend/src/questionnaire-standard-upload.js)；后端入口为 `POST /api/questionnaire-build/upload` |
| Questionnaire Create：`/questionnaire-create` | `#questionnaire-build-table`、`#add-visit`、`#visit-dialog`、`#visit-name`、`#questionnaire-create-button`、`#download-questionnaire-excel` | 页面在 [frontend/questionnaire-create.html](frontend/questionnaire-create.html)；只读问题加载、Visit 勾选、分组预览和 Excel 下载在 [frontend/src/questionnaire-create.js](frontend/src/questionnaire-create.js) |
| Questionnaire Data View：`/questionnaire-data-view` | `#view-study`、`#data-view-table`、`#data-view-status` | 页面在 [frontend/data-view.html](frontend/data-view.html)；下拉及宽表渲染在 [frontend/src/data-view.js](frontend/src/data-view.js)；宽表转换在 [backend/src/data_view.py](backend/src/data_view.py) |
| Questionnaire Data Analysis：`/questionnaire-data-analysis` | `#analysis-form`、`#existing-study`、`#refresh-studies`、`#run-button`、`#results` | 页面在 [frontend/index.html](frontend/index.html)；Study 查询、分析请求和报告渲染在 [frontend/src/app.js](frontend/src/app.js)；旧 `/workspace` 重定向到此页 |
| Analysis Header：标题和使用次数 | `#usage-count`、`#use-count` | 分析页 HTML 在 [frontend/index.html](frontend/index.html)；计数更新在 [frontend/src/app.js](frontend/src/app.js)；菜单和上传页共用 `.topbar` / `.usage-count` 样式 |
| PR Results：报告预览（分析页） | `#results`、`#report-table`、`#database-status`、`#report-caption` | 渲染在 [frontend/src/app.js](frontend/src/app.js) 的 `renderReport()`；表格样式 `.table-scroll`、`table`、`thead`、`tbody` 在 [frontend/src/app.css](frontend/src/app.css) |

修改菜单 hub 定位 `frontend/questionnaire.html` / `frontend/src/hub.js`；普通数据上传定位 `frontend/upload.html` / `frontend/src/upload.js`；标准 questionnaire template 上传定位 `frontend/questionnaire-standard-upload.html` / `frontend/src/questionnaire-standard-upload.js`；查看页定位 `frontend/data-view.html` / `frontend/src/data-view.js`；分析页定位 `frontend/index.html` / `frontend/src/app.js`。所有页面共用 `frontend/src/app.css`，文案目前是英文。

Data View 以 `1_Study`、`2_Respondent Serial Number`、`3_Day`、`4_Leg` 为前四列，将 `5_Dqs` 展为列、`6_Value` 显示为值；同一单元格存在多条记录时显示全部值，并以逗号分隔。该页面只读取数据，不修改数据库。

Questionnaire Create 从 `consumer_questionnaire.questionnaire_build` 只读加载问题。添加 Visit / Widget 后，该列的所有问题默认勾选；用户可逐题勾选或取消。点击 Create 会在独立浏览器页签生成按 Visit 分组的 HTML 预览：Screening 优先，D1/D2/D4 等按天数排序，其他名称按添加顺序排列；每组只显示已勾选的问题。Download Excel 导出四列：Day、Question Code、Question、Answer；Question 合并英文与中文题目，Answer 使用 Options。Visit 名称与勾选关系、Excel 生成过程均只在浏览器与内存处理，不写入数据库；此模块不提供打印或 PDF 功能。

## 分析与数据流程

1. 网页提交 email 和 BU 到 `POST /api/access/confirm`。后台把访问时间、email 和 BU 写入 SQLite，并返回访问 token。
2. 上传区支持 Long 和 Wide CSV。Long 文件包含六个业务列，`1_Study` 沿用文件内值；Wide 文件必须匹配固定 65 列输入 schema，并在上传区填写 Study Name。
3. `POST /api/uploads` 检测格式；Wide 数据按 `Day{number}_{DQ_name}` 展开为数据库 Long 行，Long 数据直接校验。两种格式均在上传成功前写入 PostgreSQL 的 `consumer_questionnaire.questionnaire_data`。
4. Questionnaire Standard Upload 使用 [4_1 模板](calculation/4_1_Questionnaire%20Template.csv)，经 `POST /api/questionnaire-build/upload` 严格校验 7 列顺序、每行字段数、ID/Variable Code 唯一性及必填/可空字段后，写入 `consumer_questionnaire.questionnaire_build`。
5. 标准上传只插入数据，不自动创建或修改表。部署前先执行已批准的 `consumer_questionnaire.questionnaire_build` DDL；表列类型、顺序、可空性、主键和唯一约束必须与模板约定一致。
6. `GET /api/studies` 只从 PostgreSQL 的 `1_Study` 列读取名称。分析区选择已入库 Study Name 后，`POST /api/analyze` 从 PostgreSQL 读取该 Study 的六个业务列，并按该 Study 实际存在的 `Day_DQ` 指标重建分析 Wide 表；不要求每个 Study 都包含固定模板中的全部 DQ 列。
7. [calculation/2_2_main.py](calculation/2_2_main.py) 的 `detect_experiment_type()` 按每个受访者对应的唯一产品数分流：一个产品为 independent、两个为 paired、三个或以上为 mixed。
8. 对应算法和统计方法保持不变，仅对已存 Study 中存在且符合 `Day{number}_{DQ_name}` 的 DQ 列进行计算。报告结构不变，按产品计算均值和 N；`p < 0.05` 时，在均值后追加显著差异对手的产品缩写，例如 `64 B` 或 `69 AB`。
9. 报告写入 `Rep(All Data)` 工作表，并可下载该 Study 的六列数据库数据。PostgreSQL 不可用、列不匹配或上传失败时，接口返回错误，不会报告“已保存”。

### 统计方法

| 实验设计 | 算法文件 | 方法入口 / 说明 |
| --- | --- | --- |
| Independent | [2_2_Method_for_IndependentDesign.py](calculation/2_2_Method_for_IndependentDesign.py) | `run_significance_analysis()`；对独立产品样本计算 Welch 两样本 t-test p-value。脚本也包含 Shapiro、Levene 与 adaptive p-value 辅助方法。 |
| Paired | [2_2_Method_for_PairedDesign_PCT.py](calculation/2_2_Method_for_PairedDesign_PCT.py) | `run_significance_analysis()`；按受访者配对产品，计算差值并用单样本 t-test 检验均值差是否为 0；同时计算 Wilcoxon 相关统计量。 |
| Mixed | [2_2_Method_for_MixedDesign_SQM.py](calculation/2_2_Method_for_MixedDesign_SQM.py) | `run_significance_analysis()`；尝试拟合随机受访者截距 mixed model，并按产品对做配对 t-test；配对不足时回退到独立 Student t-test。 |

三种脚本均调用 [calculation/input_schema.py](calculation/input_schema.py) 校验输入列名、顺序、必填字段、日列命名和数值。[calculation/report_pipeline.py](calculation/report_pipeline.py) 负责分析报告；上传使用的 Wide 转 Long 转换位于 [calculation/database_format.py](calculation/database_format.py)。

## 模块边界

- 上传模块：页面 [frontend/upload.html](frontend/upload.html)、交互 [frontend/src/upload.js](frontend/src/upload.js)、格式识别 [backend/src/ingestion.py](backend/src/ingestion.py)，调用 `POST /api/uploads`。上传处理不导入分析报告模块。
- 分析模块：页面 [frontend/index.html](frontend/index.html)、交互 [frontend/src/app.js](frontend/src/app.js)、数据库数据转换 [calculation/study_data.py](calculation/study_data.py) 和 [calculation/report_pipeline.py](calculation/report_pipeline.py)，调用 `POST /api/analyze`。分析处理不导入上传格式识别模块。
- 共同依赖：两者仍通过 PostgreSQL 六列业务格式交换数据，并共享数据库连接、登录 session 和字段 schema。修改这些公共契约时，需要同时检查上传和分析；单独修改页面或模块逻辑时不应修改另一模块。此调整没有修改 PostgreSQL 表结构或现有数据。

## 页面与 API

后端入口是 [backend/src/main.py](backend/src/main.py)。主要路由：

| 路由 | 用途 |
| --- | --- |
| `GET /` | 重定向到 `/login` |
| `GET /login` | 返回访问确认页面 |
| `GET /workspace` | 兼容跳转到 `/questionnaire-data-analysis` |
| `GET /questionnaire` | 返回 Questionnaire 菜单 hub |
| `GET /questionnaire-create` | 返回只读 Questionnaire Create / Visit 配置页面 |
| `GET /questionnaire-data-upload` | 返回独立的 Questionnaire Data Upload 页面 |
| `GET /questionnaire-data-view` | 返回独立的 Questionnaire Data View 页面 |
| `GET /questionnaire-data-analysis` | 返回独立的 Questionnaire Data Analysis 页面 |
| `GET /api/health` | 服务健康检查 |
| `GET /api/usage/count` | 仅返回总使用次数，不返回用户信息 |
| `POST /api/access/confirm` | 校验并记录 email、BU，建立访问 session |
| `GET /api/access/session` | 恢复当前浏览器 session 并返回个人/总次数 |
| `GET /api/studies` | 从 PostgreSQL 查询不同的 `1_Study`；DB 不可用时返回错误 |
| `GET /api/questionnaire-build` | 只读获取 Questionnaire Create 的问题定义；需要 Bearer token |
| `POST /api/questionnaire-build/export` | 根据所选 Visit 和问题生成 Excel，不写入 PostgreSQL；需要 Bearer token |
| `GET /api/questionnaire-data?study_name=...` | 读取选定 Study 的业务数据并返回用于展示的宽表；需要 Bearer token |
| `POST /api/uploads` | 检测 Long/Wide CSV、校验或转换并立即写入 PostgreSQL；Wide 需提供 Study Name |
| `POST /api/questionnaire-build/upload` | 校验 `4_1_Questionnaire Template.csv` 并将问卷定义写入 `consumer_questionnaire.questionnaire_build`；需要 Bearer token |
| `GET /api/templates/{kind}` | 下载 `raw-input`、`pr-report` 或 `database` 标准文件 |
| `POST /api/analyze` | 按已入库 Study Name 从 PostgreSQL 读取数据并生成报告/导出文件；需要 Bearer token |
| `GET /api/runs/{run_id}` | 读取一次运行的预览和验证日志 |
| `GET /api/runs/{run_id}/artifacts/{kind}` | 下载该次运行的报告、数据库 CSV 或验证日志 |

## 关键文件

| 文件 | 职责 |
| --- | --- |
| [frontend/login.html](frontend/login.html) | `/login` 访问确认页面结构 |
| [frontend/src/login.js](frontend/src/login.js) | `/login` 表单、计数展示、访问确认和跳转 |
| [frontend/questionnaire.html](frontend/questionnaire.html) | `/questionnaire` 菜单 hub |
| [frontend/questionnaire-create.html](frontend/questionnaire-create.html) | `/questionnaire-create` 问题表与 Visit 配置页面 |
| [frontend/upload.html](frontend/upload.html) | `/questionnaire-data-upload` 上传和模板下载页 |
| [frontend/questionnaire-standard-upload.html](frontend/questionnaire-standard-upload.html) | `/questionnaire-standard-upload` 问卷标准模板上传页 |
| [frontend/data-view.html](frontend/data-view.html) | `/questionnaire-data-view` 数据查看页 |
| [frontend/src/hub.js](frontend/src/hub.js) | hub session 校验 |
| [frontend/src/questionnaire-create.js](frontend/src/questionnaire-create.js) | 只读问题表、Visit 列和临时勾选状态 |
| [frontend/src/upload.js](frontend/src/upload.js) | 上传页 session、格式上传与结果提示 |
| [frontend/src/questionnaire-standard-upload.js](frontend/src/questionnaire-standard-upload.js) | Questionnaire Standard Upload 页面交互 |
| [frontend/src/data-view.js](frontend/src/data-view.js) | 查看页 Study 选择与宽表渲染 |
| [frontend/index.html](frontend/index.html) | `/questionnaire-data-analysis` 分析和结果页 |
| [frontend/src/app.css](frontend/src/app.css) | 登录页、菜单、上传、分析页共用样式 |
| [frontend/src/app.js](frontend/src/app.js) | 分析页 session 检查、Study 查询、分析请求和报告表格渲染 |
| [backend/src/main.py](backend/src/main.py) | FastAPI 路由、访问限制及分析请求编排 |
| [backend/src/usage_store.py](backend/src/usage_store.py) | SQLite 基准计数、访问事件和 token hash |
| [backend/src/database.py](backend/src/database.py) | PostgreSQL 列检查与安全插入 |
| [backend/src/ingestion.py](backend/src/ingestion.py) | 上传文件的 Long/Wide 格式识别和校验 |
| [backend/src/questionnaire_build.py](backend/src/questionnaire_build.py) | 4_1 CSV 的字段、行结构、类型及唯一性校验 |
| [backend/src/data_view.py](backend/src/data_view.py) | 数据查看页 Long 转 Wide，保留重复答案 |
| [calculation/database_format.py](calculation/database_format.py) | 共用数据库六列定义及上传 Wide 转 Long |
| [calculation/study_data.py](calculation/study_data.py) | 已存数据库 Long 行转分析 Wide 表 |
| [calculation/input_schema.py](calculation/input_schema.py) | 原始 CSV 固定 schema 的唯一校验入口 |
| [calculation/2_2_main.py](calculation/2_2_main.py) | 实验设计识别及统计算法分发 |
| [calculation/report_pipeline.py](calculation/report_pipeline.py) | 分析调度、PR 报告构建和文件输出 |
| [calculation/2_1_Analysis Input schema.csv](calculation/2_1_Analysis%20Input%20schema.csv) | 仅含表头的原始输入列定义 |
| [calculation/3_1_Target Database schema.csv](calculation/3_1_Target%20Database%20schema.csv) | 仅含表头的 PostgreSQL 导入目标列定义 |
| [calculation/3_2_Target Result Format.xlsx](calculation/3_2_Target%20Result%20Format.xlsx) | PR Excel 工作簿模板 |

## 输出与数据库

每次分析在 `output/{run_id}/` 下生成：

- `business_report.xlsx`：业务报告。
- `database_ingestion.csv`：按 `3_1_Target Database format.csv` 六列顺序生成的平表。
- `validation_log.json`：schema、统计、输出行数和数据库结果。

设置 `DATABASE_URL` 和 `DATABASE_TABLE`（默认 `consumer_questionnaire.questionnaire_data`）后，上传会检查目标表包含六个业务列且顺序正确，再以事务插入这些列；数据库生成 `id` 和时间戳等管理字段。缺少连接或列不匹配时上传失败，不会仅保存在本地。详情见 [docs/database.md](docs/database.md)。

Questionnaire Standard Upload 另外写入 `consumer_questionnaire.questionnaire_build`，该表必须预先按批准的 4_1 schema 建立；上传接口只做结构核对和插入，不执行 DDL，也不会变更其他表。

产品缩写按产品代码排序后分配 A、B、C……；PR 输出顺序为 A 列 DQ Question、B 列 Time Point、C 列起按产品名动态扩展。输出不再包含空白分隔列或 Chinese Description 列；显著性标记规则和统计方法不变。

含有 respondent 数据行的原始 `2_1_Analysis Input Mod_PCTtest_DQ.csv` 和 `3_1_Target Database format.csv` 保留在本地并由 `.gitignore` 排除，避免将问卷明细推送到远端。代码和测试改用 header-only 的 `2_1_Analysis Input schema.csv` 与 `3_1_Target Database schema.csv` 获取固定列定义，不依赖被忽略的数据文件。

# English

## Purpose

This project accepts questionnaire data in a fixed CSV format, automatically identifies the experimental design, and compares products. It generates a PR Excel report for business users and a standardized CSV for PostgreSQL. The web application also offers template downloads and records each access and the total usage count.

The original input column names and order are defined by the [header-only input schema](calculation/2_1_Analysis%20Input%20schema.csv): respondent ID, product/Leg, and DQ metric columns named `Day{number}_{DQ_name}`. Other column names or orders are not accepted at runtime.

## Running Locally

Python 3.10 or later and PostgreSQL are required. Uploads and analysis by Study Name access PostgreSQL directly.

```bash
python -m pip install -r requirements-dev.txt
uvicorn backend.src.main:app --reload
```

Before starting the application, configure `DATABASE_URL` and `DATABASE_TABLE` (default: `consumer_questionnaire.questionnaire_data`). Do not commit real credentials to Git:

```bash
export DATABASE_URL='postgresql://...'
export DATABASE_TABLE='consumer_questionnaire.questionnaire_data'
```

To run the analysis script independently, provide the raw CSV path explicitly:

```bash
python calculation/2_2_main.py path/to/raw-input.csv
```

Open <http://127.0.0.1:8000/login> and confirm access. The root path `/` redirects to `/login`. After confirmation, the `/questionnaire` menu provides access to the application modules. The legacy `/workspace` path redirects to the analysis page; pages redirect to login when there is no valid session.

Enter a work email and business unit (BU), then select **Confirm and continue**. This records usage; it does not authenticate the email address. Each confirmation increments the usage count, while refreshing an existing session does not. The initial count is 66. SQLite records are stored in `output/usage.sqlite3` by default; set `USAGE_DB_PATH` to change the location.

Run the tests:

```bash
python -m pytest -q calculation/tests backend/tests
```

## Pages

The frontend has separate login, menu, upload, questionnaire creation, data view, and analysis pages. `/` redirects to `/login`; `/workspace` remains as a compatibility redirect to the analysis page.

| Page / URL | Page elements | Implementation |
| --- | --- | --- |
| Login / Access: `/login` | `#access-gate`, `#access-form`, `#access-email`, `#access-bu`, `#gate-use-count` | Structure and text: [frontend/login.html](frontend/login.html); confirmation, count refresh, and redirects: [frontend/src/login.js](frontend/src/login.js); styles: `.access-*` and `.gate-usage` in [frontend/src/app.css](frontend/src/app.css). |
| Questionnaire Menu: `/questionnaire` | `.questionnaire-menu`, module links | Structure: [frontend/questionnaire.html](frontend/questionnaire.html); session check: [frontend/src/hub.js](frontend/src/hub.js); `.questionnaire-menu` styles: [frontend/src/app.css](frontend/src/app.css). |
| Questionnaire Data Upload: `/questionnaire-data-upload` | `#upload-form`, `#csv-file`, `#upload-study-name`, `#upload-button`, `.standard-files` | Page: [frontend/upload.html](frontend/upload.html); Long/Wide uploads: [frontend/src/upload.js](frontend/src/upload.js); template downloads: `download_template()` in [backend/src/main.py](backend/src/main.py). |
| Questionnaire Standard Upload: `/questionnaire-standard-upload` | `#questionnaire-standard-upload-form`, `#questionnaire-standard-file`, `#questionnaire-standard-upload-button` | Page: [frontend/questionnaire-standard-upload.html](frontend/questionnaire-standard-upload.html); file selection, session, and requests: [frontend/src/questionnaire-standard-upload.js](frontend/src/questionnaire-standard-upload.js); backend: `POST /api/questionnaire-build/upload`. |
| Questionnaire Create: `/questionnaire-create` | `#questionnaire-build-table`, `#add-visit`, `#visit-dialog`, `#visit-name`, `#questionnaire-create-button`, `#download-questionnaire-excel` | Page: [frontend/questionnaire-create.html](frontend/questionnaire-create.html); read-only definitions, Visit selections, grouped preview, and Excel download: [frontend/src/questionnaire-create.js](frontend/src/questionnaire-create.js). |
| Questionnaire Data View: `/questionnaire-data-view` | `#view-study`, `#data-view-table`, `#data-view-status` | Page: [frontend/data-view.html](frontend/data-view.html); selection and rendering: [frontend/src/data-view.js](frontend/src/data-view.js); Long-to-Wide conversion: [backend/src/data_view.py](backend/src/data_view.py). |
| Questionnaire Data Analysis: `/questionnaire-data-analysis` | `#analysis-form`, `#existing-study`, `#refresh-studies`, `#run-button`, `#results` | Page: [frontend/index.html](frontend/index.html); Study lookup, analysis requests, and report rendering: [frontend/src/app.js](frontend/src/app.js). `/workspace` redirects here. |
| Analysis header | `#usage-count`, `#use-count` | Markup: [frontend/index.html](frontend/index.html); count updates: [frontend/src/app.js](frontend/src/app.js); shared `.topbar` and `.usage-count` styles: [frontend/src/app.css](frontend/src/app.css). |
| PR Results preview | `#results`, `#report-table`, `#database-status`, `#report-caption` | `renderReport()` in [frontend/src/app.js](frontend/src/app.js); table styles in [frontend/src/app.css](frontend/src/app.css). |

All pages share [frontend/src/app.css](frontend/src/app.css), and the interface text is currently in English.

Data View uses `1_Study`, `2_Respondent Serial Number`, `3_Day`, and `4_Leg` as its first four columns, expands `5_Dqs` into question columns, and displays `6_Value` as the cell value. Multiple records for a cell are all displayed, separated by commas. This page reads data without modifying the database.

Questionnaire Create reads definitions from `consumer_questionnaire.questionnaire_build`. Adding a Visit / Widget selects all questions by default; each selection can be changed individually. **Create** opens an HTML preview grouped by Visit in a separate tab: Screening first, D1/D2/D4 and similar labels in day order, then other names in the order added. Each group shows only its selected questions. **Download Excel** exports four columns: Day, Question Code, Question, and Answer. Question combines the English and Chinese question text; Answer uses Options. Visit names and selections are temporary, and Excel is generated in memory without writing to the database. Printing and PDF export are not provided by this module.

## Analysis and Data Flow

1. The browser sends the email and BU to `POST /api/access/confirm`. The backend stores the access time, email, and BU in SQLite and returns an access token.
2. The upload page accepts Long and Wide CSV files. Long files contain six business columns and retain the file's `1_Study` value. Wide files must match the fixed 65-column input schema and require a Study Name on the upload page.
3. `POST /api/uploads` detects the format. Wide data is expanded into database Long rows using `Day{number}_{DQ_name}`; Long data is validated directly. Both formats are written to `consumer_questionnaire.questionnaire_data` in PostgreSQL before an upload is reported as successful.
4. Questionnaire Standard Upload uses the [4_1 template](calculation/4_1_Questionnaire%20Template.csv). `POST /api/questionnaire-build/upload` validates the seven-column order, field count per row, ID and Variable Code uniqueness, and required/nullable fields before inserting into `consumer_questionnaire.questionnaire_build`.
5. Standard upload only inserts data; it does not create or alter the table. Run the approved DDL for `consumer_questionnaire.questionnaire_build` before deployment. Column types, order, nullability, primary key, and unique constraints must match the template contract.
6. `GET /api/studies` reads names only from PostgreSQL's `1_Study` column. For a selected stored Study Name, `POST /api/analyze` reads its six business columns and reconstructs an analysis Wide table using the `Day_DQ` metrics actually present. A study does not need every DQ column from the fixed template.
7. `detect_experiment_type()` in [calculation/2_2_main.py](calculation/2_2_main.py) dispatches by the number of unique products per respondent: one is independent, two is paired, and three or more is mixed.
8. The corresponding algorithms calculate only DQ columns present in the stored study that match `Day{number}_{DQ_name}`. The report retains its structure and includes means and N by product. When `p < 0.05`, the product letters of significantly different comparisons are appended to the mean, for example `64 B` or `69 AB`.
9. The report is written to the `Rep(All Data)` worksheet, and the study's six-column database data can also be downloaded. When PostgreSQL is unavailable, columns do not match, or an upload fails, the API returns an error instead of reporting that data was saved.

### Statistical Methods

| Design | Algorithm file | Entry point / method |
| --- | --- | --- |
| Independent | [2_2_Method_for_IndependentDesign.py](calculation/2_2_Method_for_IndependentDesign.py) | `run_significance_analysis()` calculates Welch two-sample t-test p-values for independent product samples. The script also includes Shapiro, Levene, and adaptive p-value helpers. |
| Paired | [2_2_Method_for_PairedDesign_PCT.py](calculation/2_2_Method_for_PairedDesign_PCT.py) | `run_significance_analysis()` pairs products by respondent and uses a one-sample t-test on the differences to test whether their mean is zero; it also computes Wilcoxon-related statistics. |
| Mixed | [2_2_Method_for_MixedDesign_SQM.py](calculation/2_2_Method_for_MixedDesign_SQM.py) | `run_significance_analysis()` attempts a mixed model with random respondent intercepts and performs paired t-tests for product pairs, falling back to an independent Student t-test when pairing is insufficient. |

All three scripts use [calculation/input_schema.py](calculation/input_schema.py) to validate column names and order, required fields, day-column names, and numeric values. [calculation/report_pipeline.py](calculation/report_pipeline.py) handles analysis reports. The upload Wide-to-Long conversion is in [calculation/database_format.py](calculation/database_format.py).

## Module Boundaries

- Upload: [frontend/upload.html](frontend/upload.html), [frontend/src/upload.js](frontend/src/upload.js), and [backend/src/ingestion.py](backend/src/ingestion.py) use `POST /api/uploads`. Upload processing does not import the analysis reporting module.
- Analysis: [frontend/index.html](frontend/index.html), [frontend/src/app.js](frontend/src/app.js), [calculation/study_data.py](calculation/study_data.py), and [calculation/report_pipeline.py](calculation/report_pipeline.py) use `POST /api/analyze`. Analysis processing does not import the upload format detection module.
- Shared dependencies: both use the six-column PostgreSQL business format and share the database connection, login session, and field schema. Changes to these shared contracts require checking both upload and analysis; changes confined to a page or module should not alter the other module. This separation did not change PostgreSQL table structures or existing data.

## Pages and API

The backend entry point is [backend/src/main.py](backend/src/main.py). Key routes:

| Route | Purpose |
| --- | --- |
| `GET /` | Redirect to `/login`. |
| `GET /login` | Return the access confirmation page. |
| `GET /workspace` | Compatibility redirect to `/questionnaire-data-analysis`. |
| `GET /questionnaire` | Return the Questionnaire menu. |
| `GET /questionnaire-create` | Return the read-only Questionnaire Create / Visit configuration page. |
| `GET /questionnaire-data-upload` | Return the Questionnaire Data Upload page. |
| `GET /questionnaire-data-view` | Return the Questionnaire Data View page. |
| `GET /questionnaire-data-analysis` | Return the Questionnaire Data Analysis page. |
| `GET /api/health` | Service health check. |
| `GET /api/usage/count` | Return the total usage count without user information. |
| `POST /api/access/confirm` | Validate and record email and BU, then establish an access session. |
| `GET /api/access/session` | Restore the current browser session and return personal and total counts. |
| `GET /api/studies` | Query distinct `1_Study` values from PostgreSQL; return an error if the database is unavailable. |
| `GET /api/questionnaire-build` | Read questionnaire definitions for Questionnaire Create; requires a Bearer token. |
| `POST /api/questionnaire-build/export` | Generate an Excel workbook from the selected Visits and questions without writing to PostgreSQL; requires a Bearer token. |
| `GET /api/questionnaire-data?study_name=...` | Read a selected study's data and return a Wide table for display; requires a Bearer token. |
| `POST /api/uploads` | Detect, validate or convert, and immediately insert Long/Wide CSV data into PostgreSQL; Wide requires a Study Name. |
| `POST /api/questionnaire-build/upload` | Validate `4_1_Questionnaire Template.csv` and insert definitions into `consumer_questionnaire.questionnaire_build`; requires a Bearer token. |
| `GET /api/templates/{kind}` | Download the `raw-input`, `pr-report`, or `database` standard file. |
| `POST /api/analyze` | Read a stored Study Name from PostgreSQL and generate reports and exports; requires a Bearer token. |
| `GET /api/runs/{run_id}` | Retrieve a run's preview and validation log. |
| `GET /api/runs/{run_id}/artifacts/{kind}` | Download the report, database CSV, or validation log for a run. |

## Key Files

| File | Responsibility |
| --- | --- |
| [frontend/login.html](frontend/login.html) | Access confirmation page structure. |
| [frontend/src/login.js](frontend/src/login.js) | Login form, usage count, access confirmation, and redirect. |
| [frontend/questionnaire.html](frontend/questionnaire.html) | Questionnaire menu. |
| [frontend/questionnaire-create.html](frontend/questionnaire-create.html) | Question table and Visit configuration page. |
| [frontend/upload.html](frontend/upload.html) | Data upload and template download page. |
| [frontend/questionnaire-standard-upload.html](frontend/questionnaire-standard-upload.html) | Questionnaire template upload page. |
| [frontend/data-view.html](frontend/data-view.html) | Data view page. |
| [frontend/src/hub.js](frontend/src/hub.js) | Menu session validation. |
| [frontend/src/questionnaire-create.js](frontend/src/questionnaire-create.js) | Read-only questions, Visit columns, temporary selections, preview, and Excel download. |
| [frontend/src/upload.js](frontend/src/upload.js) | Upload session, file submission, and status messages. |
| [frontend/src/questionnaire-standard-upload.js](frontend/src/questionnaire-standard-upload.js) | Questionnaire Standard Upload interactions. |
| [frontend/src/data-view.js](frontend/src/data-view.js) | Study selection and Wide table rendering. |
| [frontend/index.html](frontend/index.html) | Analysis and results page. |
| [frontend/src/app.css](frontend/src/app.css) | Shared frontend styles. |
| [frontend/src/app.js](frontend/src/app.js) | Analysis session, Study lookup, requests, and report rendering. |
| [backend/src/main.py](backend/src/main.py) | FastAPI routes, access restrictions, and analysis orchestration. |
| [backend/src/usage_store.py](backend/src/usage_store.py) | SQLite baseline count, access events, and token hashes. |
| [backend/src/database.py](backend/src/database.py) | PostgreSQL schema checks and safe inserts. |
| [backend/src/ingestion.py](backend/src/ingestion.py) | Long/Wide upload detection and validation. |
| [backend/src/questionnaire_build.py](backend/src/questionnaire_build.py) | 4_1 CSV field, row, type, and uniqueness validation. |
| [backend/src/data_view.py](backend/src/data_view.py) | Long-to-Wide conversion for Data View, preserving duplicate answers. |
| [calculation/database_format.py](calculation/database_format.py) | Shared six-column database schema and upload Wide-to-Long conversion. |
| [calculation/study_data.py](calculation/study_data.py) | Convert stored database Long rows into an analysis Wide table. |
| [calculation/input_schema.py](calculation/input_schema.py) | Central validation for the fixed raw CSV schema. |
| [calculation/2_2_main.py](calculation/2_2_main.py) | Experimental design detection and statistical algorithm dispatch. |
| [calculation/report_pipeline.py](calculation/report_pipeline.py) | Analysis dispatch, PR report construction, and file output. |
| [calculation/2_1_Analysis Input schema.csv](calculation/2_1_Analysis%20Input%20schema.csv) | Header-only raw input column definitions. |
| [calculation/3_1_Target Database schema.csv](calculation/3_1_Target%20Database%20schema.csv) | Header-only PostgreSQL import column definitions. |
| [calculation/3_2_Target Result Format.xlsx](calculation/3_2_Target%20Result%20Format.xlsx) | PR Excel workbook template. |

## Outputs and Database

Each analysis creates the following files under `output/{run_id}/`:

- `business_report.xlsx`: business report.
- `database_ingestion.csv`: flat table in the six-column order of `3_1_Target Database format.csv`.
- `validation_log.json`: schema, statistics, output row counts, and database result.

With `DATABASE_URL` and `DATABASE_TABLE` configured (default: `consumer_questionnaire.questionnaire_data`), upload checks that the target table contains the six business columns in the correct order, then inserts them in a transaction. The database generates administrative fields such as `id` and timestamps. Upload fails when the connection is missing or columns do not match; it does not silently save only locally. See [docs/database.md](docs/database.md).

Questionnaire Standard Upload also writes to `consumer_questionnaire.questionnaire_build`, which must already exist with the approved 4_1 schema. The upload endpoint only checks its structure and inserts data; it does not run DDL or modify other tables.

Product letters A, B, C, and so on are assigned by sorted product code. The PR output uses column A for DQ Question, column B for Time Point, and dynamically adds product columns from column C onward. There are no blank separator or Chinese Description columns; significance markers and statistical methods remain unchanged.

The original `2_1_Analysis Input Mod_PCTtest_DQ.csv` and `3_1_Target Database format.csv` files containing respondent data are retained locally and excluded by `.gitignore` to avoid pushing questionnaire details to a remote repository. Code and tests use the header-only `2_1_Analysis Input schema.csv` and `3_1_Target Database schema.csv` for fixed column definitions and do not depend on the ignored data files.
