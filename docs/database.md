# Consumer Questionnaire 数据库

## 范围与要求

本次提供 PostgreSQL 14 及以上版本的数据库脚本，未连接数据库，未实现前端或后端。
数据库名称严格为 `Consumer Questionnaire`，业务表位于 `consumer_questionnaire` schema。
SQL 中包含空格、数字前缀或大写字母的名称必须用双引号引用。

## 数据表

`consumer_questionnaire.questionnaire_data` 的六个业务字段均不能为空：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `1_Study` | `text` | 研究编号或名称 |
| `2_Respondent Serial Number` | `text` | 受访者编号，保留前导零 |
| `3_Day` | `integer` | 第几天；允许 0 表示基线，不允许负数 |
| `4_Leg` | `text` | 产品名称 |
| `5_Dqs` | `text` | 问卷的问题 |
| `6_Value` | `numeric` | 数值答案，不限定小数位数，禁止 NaN 和无穷值 |

额外管理字段为 `id`、`created_by`、`updated_by`、`created_at`、`updated_at`。
时间使用带时区类型，更新时间由触发器维护。后端须填写操作用户，不得信任前端传入的用户编号。
操作用户允许为空，以支持初始化及历史数据导入；删除用户时保留数据并清空对应引用。
日常应优先停用用户，避免丢失操作人员关联。

文本业务字段禁止空字符串及仅含普通空格的字符串；后端还应统一处理其他空白字符。
允许同一研究、受访者、天数、产品和问题出现多条记录，不自动去重或覆盖。
主键保证每条记录可单独修改，复合索引支持按研究、受访者和天数筛选。
若后续业务要求去重，应先确定唯一性规则再新增迁移。

示例查询：

```sql
SELECT id, "1_Study", "2_Respondent Serial Number", "3_Day",
       "4_Leg", "5_Dqs", "6_Value"
FROM consumer_questionnaire.questionnaire_data
WHERE "1_Study" = 'DEMO_STUDY'
ORDER BY "2_Respondent Serial Number", "3_Day", id;
```

## 权限模型

用户通过 `user_roles` 获得角色，角色通过 `role_permissions` 获得权限。
`users` 保存账号和密码哈希，`roles` 保存角色，`permissions` 保存权限定义。
角色及权限编码区分大小写；用户名当前也区分大小写，后续登录接口应保持一致。
初始脚本不创建任何用户，不提供默认密码。

| 角色编码 | 默认权限 |
| --- | --- |
| `administrator` | 全部 10 项初始权限 |
| `data_editor` | 查看、录入、修改、导入数据 |
| `analyst` | 查看、导出数据及查看统计 |
| `viewer` | 查看数据 |

权限编码为 `data:view`、`data:create`、`data:update`、`data:import`、
`data:delete`、`data:export`、`analytics:view`、`users:manage`、
`roles:manage`、`audit:view`。增加权限定义应通过数据库迁移，
运行时管理角色及其权限关联，不开放任意修改权限定义的数据库权限。

本次角色权限是全库操作级权限，**尚不包含按 Study 的数据隔离**。
如果研究间需要隔离，必须在开放真实数据前补充研究授权表和所有相关接口的过滤。

后续后端必须：

- 验证登录状态和 `users.is_active`，从数据库获取权限；默认拒绝未授权操作。
- 使用 Argon2id 等成熟密码哈希库，不存明文，不自行实现密码算法。
- 校验每个接口的权限，包括批量导入、导出、统计和管理接口；前端按钮隐藏不能代替授权。
- 为导入等多操作流程检查所有必要权限，不把导入权限当作修改、覆盖或删除权限。
- 以事务同时写入业务修改和 `audit_logs`，审计失败时回滚操作并明确报错。
- 记录用户管理、权限变更、数据修改和导出；审计内容不得包含密码哈希、令牌或不必要的个人信息。
- 使用参数化 SQL；凭据通过安全的运行环境配置，不写入代码或命令行。

`audit_logs` 包含操作用户、操作类型、对象类型、对象编号、JSON 对象详情和时间。
它是审计存储结构，不会自动识别网页用户；本次尚未实现后端审计写入。

## 脚本与执行顺序

使用 `psql`，不要将带有反斜杠元命令的入口脚本直接交给普通 SQL 驱动。
先通过安全方式配置 `PGHOST`、`PGPORT`、`PGUSER` 和凭据。
密码可使用权限为 `0600` 的 `.pgpass` 或部署环境的秘密管理，不放在命令参数里。
以下命令在项目根目录执行。

### 1. 创建数据库

```bash
psql -X --dbname=postgres --file=database/create_database.sql
```

由有 `CREATEDB` 权限的部署账号执行，新数据库归该账号所有。
如果数据库已经存在，创建脚本会报错，不会删除或覆盖；核实归属及内容后再决定后续操作。

### 2. 初始化表和角色权限

```bash
psql -X --dbname='Consumer Questionnaire' --file=database/migrations/001_initial.sql
```

使用数据库所有者或经授权的迁移账号。该入口通过相对文件路径加载
[表结构](../database/schema/consumer_questionnaire.sql) 和
[初始角色权限](../database/seeds/initial_permissions.sql)，在同一事务中执行。
不单独执行这两个被包含文件；任一步失败会回滚整个初始化。
这是一次性初始迁移，重复执行会明确报错，不会静默覆盖现有结构或权限。
后续新增编号迁移，不修改已经应用的初始迁移；部署时记录已应用的迁移编号。

### 3. 配置应用数据库权限（独立、可选步骤）

```bash
psql -X --dbname='Consumer Questionnaire' --file=database/setup_application_access.sql
```

由有创建 PostgreSQL 角色权限的数据库所有者执行。
此脚本创建集群级、不能直接登录的 `consumer_questionnaire_app` 权限角色；
这是 PostgreSQL 账号权限，不是网页的管理员、分析员等业务角色。
该名称须在集群内未被占用，重复执行会报错并回滚。

脚本取消 PUBLIC 对本数据库和 `public` schema 的默认权限。
因此仅应对本项目的新数据库执行，不应直接套用在共享业务数据库上。
实际应用登录账号应由部署管理员另行创建，使用独立密码并且不具有所有者、
超级用户、建库或管理角色权限，然后授予该权限角色：

```sql
GRANT consumer_questionnaire_app TO your_application_login;
```

`your_application_login` 是需要替换的账号标识，不是脚本创建的账号。
迁移使用所有者账号，应用仅使用受限登录账号，两者不得混用。
应用角色可读写业务和权限关联表、只读权限定义、读取及追加审计，
不能更新或删除审计、TRUNCATE 表、创建或删除表、管理数据库角色。
数据库所有者仍能改变审计，因此这不是针对所有者的防篡改审计系统。
未来新增表不会自动获得应用权限，须在对应迁移中显式授权。

### 4. 执行后的检查

```sql
SELECT current_database();

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'consumer_questionnaire'
  AND table_name = 'questionnaire_data'
ORDER BY ordinal_position;

SELECT r.code, count(rp.permission_id) AS permission_count
FROM consumer_questionnaire.roles AS r
LEFT JOIN consumer_questionnaire.role_permissions AS rp ON rp.role_id = r.id
GROUP BY r.code
ORDER BY r.code;
```

应看到数据库名称 `Consumer Questionnaire`，数据表共 11 列，以及
`administrator = 10`、`analyst = 3`、`data_editor = 4`、`viewer = 1`。
初始用户数和数据记录数应为 0。
部署时还应以真实受限应用账号确认能读写业务数据，
但不能修改审计记录、建表或管理数据库角色，并通过后端测试验证业务权限。

初始化后、业务数据投入使用前，可由数据库所有者执行自动检查：

```bash
psql -X --dbname='Consumer Questionnaire' --file=database/tests/001_initial_checks.sql
```

检查覆盖精确列名和类型、初始权限分配、编号前导零、数值精度、更新时间、
非法输入拒绝和删除用户后保留数据。失败会明确报错，测试记录在事务结束时回滚；
PostgreSQL 自增序列分配的编号不会随事务回滚，因此测试后编号可能不从 1 开始。
此检查针对初始角色配置，不适用于已经自定义角色和权限的生产数据库。
