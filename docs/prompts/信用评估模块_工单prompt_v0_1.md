# Task: 信用评估模块第一阶段实施 · 工单 prompt v0.1

> 状态:可下发 Claude Code
> 日期:2026-05-23
> 关联文档:
> - PRD:`docs/prd/信用评估模块 PRD v0.3_四维评分模型版.md.docx`
> - 技术方案:`docs/architecture/信用评估模块技术方案设计-v0_1.md`
> - ADR:`docs/adr/ADR-0001-OCR模型选型.md`、`docs/adr/ADR-0003-信用评估LLM选型.md`
> 当前分支:`feat/credit-assessment-mvp1`(基于 main 切出)

---

## 1. 任务上下文

按顺序阅读以下文档后开始动手:

1. `docs/architecture/信用评估模块技术方案设计-v0_1.md` —— **本任务核心契约,必须完整读完**
2. `docs/prd/信用评估模块 PRD v0.3_四维评分模型版.md.docx` —— 产品需求
3. `docs/adr/ADR-0003-信用评估LLM选型.md` —— LLM 选型
4. `CLAUDE.md` —— 项目级强约束(技术栈、命名、红线)
5. 参考工程前端样式:用户本地路径 `~/Documents/overseas-platform/overseas-supply-platform/`,仅参考 `/credit` 相关页面的**布局与视觉风格**,不参考其评分维度内容(参考工程是 9 维,本期是 4 维)

读完后按本工单顺序一气呵成,不设中途 checkpoint。

---

## 2. 任务范围

实现信用评估模块第一阶段,定位为"海外工程领域专业版企查查"。**数据全部为 mock,通过 seed 写入**。

**做**:
- 13 张表 alembic 迁移(详见技术方案 §二)
- 评分模型骨架 seed:4 维度 + 12 子项 + ~35 规则(严格按 PRD v0.3 §4.3)
- 4 家 demo 企业 seed:覆盖 A/B/C/D 各档,含工商/财务/司法/证书完整 mock 数据
- 后端 4 个抽象层:DataSource / ScoringEngine / Evaluators / LLMService
- 9 个 REST 接口(详见技术方案 §四)
- 前端 2 个页面:`/credit` 入口页 + `/credit/companies/[id]` 详情页
- RBAC 新增 3 个权限点
- AI 综合评价 + AI 对话追问(SSE 流式)

**不做**:
- 真实外部数据源接入(企查查/天眼查等,标记 TODO T-2)
- T+1 自动调度(标记 TODO T-1)
- 规则配置化 / Excel 导入(标记 TODO T-3)
- PDF 导出(标记 TODO T-4)
- 评分历史趋势图(标记 TODO T-5)
- 运营录入页

---

## 3. 技术约束

通用约束(沿用 CLAUDE.md):

1. 后端:FastAPI + SQLAlchemy 2.0 async + Alembic + Pydantic v2 + uv 包管理
2. 前端:Next.js 14 + TypeScript + Tailwind + SWR + Zustand
3. API 响应格式 `{ code, message, data, trace_id }`
4. 主键 `Integer` 自增;时间字段 `TIMESTAMP WITHOUT TIME ZONE` 存 UTC;复用 `TimestampUpdateMixin`
5. 所有写操作写平台 `audit_logs`
6. 迁移走 alembic,禁止手动 ALTER/DROP

本任务特别约束:

7. **数据全部 mock**:不引入任何真实外部 API SDK(企查查/天眼查/OpenCorporates 等都不装)
8. **千问 SDK**:仅装 `openai` 一个新依赖,实现 `QwenChatService`
   (原工单写 dashscope,C2 实施时改为 openai + DashScope OpenAI 兼容端点;
   理由是 OpenAI Chat Completions 已是国内外 LLM 事实标准,后续切其他模型只需改 base_url;
   ADR-0003 §二已同步更新)
9. **前端新增依赖**:`recharts`(雷达图);其他不引入
10. **不动现有模块**:auth / RBAC sync 流程 / supplier_organizations / categories 这些不要改
11. **RBAC 同步**:新增权限点通过 `rbac/constants.py` 注册,启动同步会自动落库
12. **代码内 TODO 标记**:所有第一阶段简化处必须加 `# TODO(T-x): xxx` 注释,T-x 编号对齐技术方案 §九
13. **求值函数命名**:`evaluator_key` 字符串严格对应 `EVALUATORS` 字典的 key,无映射错位

---

## 4. 实现步骤(分 Step 交付)

### Step 1:alembic 迁移 - 13 张表一次性建好

在 `backend/alembic/versions/` 新增一个迁移文件 `20260523_0006_credit_assessment_init.py`,**单文件**建出技术方案 §二的全部 13 张表:

- `score_dimension` / `score_subitem` / `score_rule`
- `credit_company` / `credit_company_basic_data` / `credit_company_finance_data` / `credit_company_legal_data` / `credit_company_certification`
- `score_snapshot` / `score_detail` / `score_audit_log`
- `credit_search_history`
- `credit_ai_conversation` / `credit_ai_message`

字段、约束、索引严格按技术方案 §二。注意:

- `score_snapshot` 加部分唯一索引 `(company_id) WHERE is_current = true`
- 外键引用 supplier_organizations.id 时使用 nullable=True
- jsonb 字段在 PG 用 `postgresql.JSONB`,不要用通用 JSON

`downgrade()` 也写完整,按建表反序 drop。

### Step 2:ORM 模型 - 一表一文件

在 `backend/app/db/models/` 新增 13 个 ORM 模型文件,命名与表名对应(去掉前缀 `score_` 或 `credit_` 视情况)。每个文件遵循现有规范:

- 继承 `Base, TimestampUpdateMixin`(或 `TimestampMixin` 若只需 created_at)
- 字段类型对齐迁移
- 状态/枚举值通过类常量定义(参考 `SupplierOrgStatus`、`AuditStatus` 现有写法)

在 `__init__.py` 导出新模型。

### Step 3:RBAC 权限点

`backend/app/rbac/constants.py` 增加:

```python
CREDIT_READ = "credit:read"
CREDIT_WRITE = "credit:write"
CREDIT_RECOMPUTE = "credit:recompute"
```

`PERMISSION_META` 加对应元数据(模块 `BIZ_ARCHIVE` 或新增 `BIZ_CREDIT`,建议复用 `BIZ_ARCHIVE`)。

`permissions_config.py` 把权限点授予:
- `credit:read` → BUYER / SUPPLIER / OPERATOR / ADMIN
- `credit:write` → OPERATOR / ADMIN
- `credit:recompute` → OPERATOR / ADMIN

### Step 4:LLM 服务抽象 + 千问实现

新建 `backend/app/services/llm/`:

- `base.py`:`LLMService` 抽象基类,定义 `generate()` 和 `stream_chat()`
- `qwen_chat_service.py`:基于 `dashscope` SDK 实现

DashScope API Key 从环境变量 `DASHSCOPE_API_KEY` 读取,在 `app/core/config.py` 添加 settings 字段。

千问模型:`qwen-plus`。

调用方式:`openai.AsyncOpenAI(base_url=settings.QWEN_BASE_URL, api_key=settings.DASHSCOPE_API_KEY)`。

接口签名严格遵循技术方案 §3.4。流式输出适配 FastAPI SSE 响应。

异常处理:LLM 调用失败抛 `LLMUnavailableError`,调用方决定如何处理。

### Step 5:DataSource 抽象 + Mock 实现

新建 `backend/app/services/credit/data_source/`:

- `base.py`:`DataSource` 抽象基类,定义 `fetch_basic_data` / `fetch_finance_data` / `fetch_legal_data` / `fetch_certifications`
- `mock_data_source.py`:实现就是直接 SELECT 最新一条 `credit_company_*_data` 表记录

返回类型用 Pydantic 模型或 dataclass,定义在 `backend/app/services/credit/types.py`。

### Step 6:Evaluators 求值函数集

`backend/app/services/credit/evaluators.py`:

- 实现 ~35 个求值函数,严格对应 PRD v0.3 §4.3 各子项的计分档位
- 函数签名统一:`def fn_name(data: dict) -> bool`,`data` 包含该公司四类数据
- 文件末尾导出 `EVALUATORS: dict[str, Callable]` 字典
- 每个函数加 docstring 标注对应 PRD 哪个子项哪一档

参考实现示例(技术方案 §3.3 已给):

```python
def basic_reg_info_full(data: dict) -> bool:
    """维度1·子项1·档位1:注册时间/资本金/经营范围齐全 → 5分"""
    fields = [data.get('established_date'), 
              data.get('registered_capital'), 
              data.get('business_scope')]
    return sum(1 for f in fields if f) == 3
```

注意 PRD v0.3 中"数据不可查"档位也要实现,通过判断 `data_status` 字段。

### Step 7:ScoringEngine

`backend/app/services/credit/scoring_engine.py`:

- 实现技术方案 §3.2 的完整流程
- 依赖注入 `DataSource`,便于单测时换 mock
- 主入口方法 `async def compute(company_id: int, trigger_type: str, trigger_detail: dict | None) -> ScoreSnapshot`
- 内部步骤 1-9 严格执行,事务边界对应技术方案 §5.2
- ai_summary 生成走 Step 8 的 AISummaryGenerator,**同步调用**(第一阶段简化,后续可改异步)

### Step 8:AISummaryGenerator

`backend/app/services/credit/ai_summary_generator.py`:

- 基于 snapshot + detail 拼装 prompt(模板见技术方案 §3.5)
- 调用 `LLMService.generate()`
- 失败时返回 None,不抛异常
- ScoringEngine 调用后,如果返回非空,回写 snapshot 的 `ai_summary` 和 `ai_summary_generated_at`

### Step 9:Seed 数据 - 评分模型骨架

`backend/app/seed.py` 新增 `seed_credit_score_model()`:

- 4 个维度 seed(按 PRD v0.3 §4.3 §6.1)
- 12 个子项 seed(每维度 3 个,满分严格对齐 PRD)
- ~35 个规则 seed:每条 rule 含 subitem_id、code、description、score、evaluator_key、priority
- 所有规则的 `evaluator_key` 必须在 Step 6 的 EVALUATORS 字典中存在,启动时校验(如不一致直接报错日志,但不阻断启动)

幂等:每条记录用 code 字段判断是否已存在。

### Step 10:Seed 数据 - 4 家 demo 企业

`backend/app/seed.py` 新增 `seed_credit_demo_companies()`:

- 4 家企业:Al-Rashid(沙特,预期 A)/ PT Cahaya Sentosa(印尼,预期 B)/ Karachi Steel Works(巴基斯坦,预期 C)/ Atlas Construction(摩洛哥,预期 D)
- 每家 seed:
  - 1 条 credit_company
  - 1 条 credit_company_basic_data
  - 1 条 credit_company_finance_data
  - 1 条 credit_company_legal_data
  - 3-5 条 credit_company_certification
- mock 数据要让评分计算结果符合"预期等级":
  - A 档:基础工商完整、有多项有效证书、财务健康、无司法风险
  - B 档:大部分良好,1-2 项扣分
  - C 档:多项中等档位,关键项不缺
  - D 档:**触发司法子项"失信未结案"一票否决**

seed 完所有数据后,**调用 ScoringEngine 给每家算一次分**,生成 score_snapshot + score_detail + score_audit_log(首次评分)。

seed 时**不调 LLM 生成 ai_summary**(节约启动时间),ai_summary 留 null,用户首次访问详情页时再生成(详见 Step 11 接口逻辑)。

挂到 `run_all_seeds()`,放在现有 demo seed 后面,在 `SEED_DEMO_ACCOUNTS=true` 时执行。

### Step 11:后端接口

新建 `backend/app/api/v1/credit.py`,实现技术方案 §四的 9 个接口:

- `GET /credit/companies/search?country=xx&q=xxx` —— 模糊查询,返回最多 20 条,含当前分/等级
- `GET /credit/companies/{id}` —— 详情,**如果 ai_summary 为 null,实时生成并回写**(同步)
- `POST /credit/companies/{id}/recompute` —— 单家重算
- `POST /credit/recompute-all` —— 全平台重算(占位接口,第一阶段实际可用,ADMIN 限定)
- `GET /credit/search-history` —— 当前用户最近 5 条(同 company 去重)
- `DELETE /credit/search-history/{id}` —— 删除单条
- `POST /credit/ai/conversations` —— 创建会话(body: company_id)
- `POST /credit/ai/conversations/{id}/messages` —— **SSE 流式响应**,流完后落库
- `GET /credit/ai/conversations/{id}` —— 含全部消息

所有接口:
- 权限守卫用 `Depends(require_permission(...))`
- 响应统一 `{code, message, data, trace_id}`
- 业务异常用 `BusinessError`,trace_id 自动带入
- 写操作前后写平台 audit_logs(评分变动还要写 score_audit_log)

在 `app/api/v1/router.py` 挂载新 router。

### Step 12:前端 `/credit` 入口页

`frontend/src/app/credit/page.tsx`:

- 移除现有 PublicLayout 占位,改为登录可见(参考 `/operator/*` 路由的权限保护写法)
- 顶部:国别下拉(9 国,数据来自现有 country-registration-rules 或新增 country options)+ 关键词输入框
- 搜索结果列表:卡片样式,每张卡片显示 企业名 + 注册号 + 经营状态 + 当前分/等级徽章
- 近期搜索区域:从 `/credit/search-history` 拉,展示 5 条,可单条删除
- 输入防抖 300ms 后自动搜索
- 视觉风格参考用户提供的截图(深蓝 hero + 卡片列表)

### Step 13:前端 `/credit/companies/[id]` 详情页

`frontend/src/app/credit/companies/[id]/page.tsx`:

- 进入时调 `/credit/companies/{id}` 拿完整数据
- 布局参考截图:
  - 顶部:企业名 + 国别 + 等级大标签(A/B/C/D 颜色按 PRD §8.2)
  - 左侧:四维雷达图(recharts `<RadarChart>`,4 轴对应 4 维度,数据为各维度得分/满分百分比)
  - 右侧:基本信息卡(成立日期/注册资本/法定代表人/经营范围摘要等)
  - 下方:资质认证 chip 标签(有效绿色 / 过期灰色 / 可疑红色)
  - 可展开的"12 子项明细"表格:
    - 4 列:维度 / 子项 / 得分 / 命中规则
    - **"维度"列按维度跨行合并(rowspan)**,每个维度只显示一次,旁边带维度合计分(score/max_score)
    - 维度级 override 折叠展示:若同维度内 3 个子项命中相同规则(如"维度清零" / "一票否决" / "整维度数据缺失"),把这条描述提到维度名旁边以高亮 chip 形式展示,3 个子项行的"命中规则"列显示 "—"
    - 走默认分(is_default_score=true)的子项命中规则列显示 "(默认分)" 提示
  - 底部:AI 评价对话框
- AI 对话框:
  - 初次进入显示 ai_summary(直接渲染 markdown)
  - 下方对话区:用户输入框 + 历史消息
  - 用户发送消息:`POST /credit/ai/conversations/{id}/messages`,**fetch + ReadableStream 处理 SSE 流**,逐字渲染
  - 多轮对话:发送时拼装当前会话的所有历史消息(从 conversation API 拿)

进入页面时若无对话会话,先调 `POST /credit/ai/conversations` 创建一个。

### Step 14:依赖与配置

后端:
- `backend/pyproject.toml` 加 `dashscope` 依赖
- `backend/app/core/config.py` 加 `DASHSCOPE_API_KEY` settings 字段
- `.env.production.example` 同步加该 key

前端:
- `frontend/package.json` 加 `recharts`
- 跑 `pnpm install`

### Step 15:自测脚本

`backend/scripts/credit_smoke_test.py`(本地手动跑,不进 CI):

- 启动后调用 `GET /credit/companies/search?country=SA&q=Al`,验证返回 1 条结果且分数为 A
- 调用 `GET /credit/companies/{id}`,验证含完整 snapshot 数据
- 调用 `POST /credit/companies/{id}/recompute`,验证生成新 snapshot,旧的 is_current=false
- 调用 AI 对话流式接口,验证 SSE 输出正常

---

## 5. 验收标准

完成所有 Step 后一次性验收:

### 后端

- `cd backend && uv run alembic upgrade head` 成功执行,13 张新表创建
- `uv run uvicorn app.main:app` 启动成功,seed 完成日志输出 "评分模型骨架 + 4 家 demo 企业 seed 完成"
- 启动日志无 EVALUATORS 校验报错
- `psql` 直连查 `score_snapshot WHERE is_current=true` 应有 4 条(每家一条)
- `score_detail` 应有 4×12 = 48 条
- 4 家企业的 grade 分别为 A、B、C、D

### 接口

- `curl -H "Cookie: ..." "http://localhost:8000/api/v1/credit/companies/search?country=SA&q=Al"` 返回结果
- 详情接口返回完整数据结构(含 dimension scores、12 条 detail、ai_summary 可能为 null)
- 重算接口可调用,新快照生成,旧的 is_current 切为 false
- AI 对话接口能流式返回内容(取决于 DASHSCOPE_API_KEY 是否配置;无配置时返回 LLM 不可用错误)
- 所有接口返回 `{code, message, data, trace_id}` 格式

### 前端

- `pnpm tsc --noEmit` 通过
- `pnpm build` 通过
- `/credit` 页面:登录后访问,可选国别 + 搜索 + 点击进入详情
- `/credit/companies/[id]`:雷达图展示正确,4 个维度,等级标签颜色对应 PRD §8.2
- AI 对话:可发送消息,流式渲染响应

### 权限

- 未登录访问 `/credit` 跳转登录
- BUYER / SUPPLIER 账号可访问 `/credit` 全部页面
- 重算接口仅 OPERATOR / ADMIN 可调,其他角色 403

### TODO 标记

- 代码内搜索 `# TODO(T-` 应能看到至少 7 处标记,覆盖 T-1 到 T-7

---

## 6. 提交规范

按 step 拆 commit,或单个大 commit 也接受,但 commit message 需包含:

- 关联文档:`Ref: docs/architecture/信用评估模块技术方案设计-v0_1.md`
- 列出涉及的表/接口/页面

PR 描述包含:已实现功能清单 / TODO 清单 / 已知限制(数据全 mock)。

---

## 7. 已知边界 / 不要做的事

1. 不要接入任何真实外部数据源 API,即使代码里看到 `TODO(T-2)` 也不要顺手实现
2. 不要实现 T+1 自动调度,即使 cron 容易加也不要做
3. 不要实现 PDF 导出
4. 不要实现规则的 condition_expr DSL 解析(score_rule.condition_expr 字段建好就留空)
5. 不要新增运营录入页面
6. 不要修改 supplier_organizations / categories / auth 等现有模块
7. **不要为评分维度数量纠结**:本期就是 4 维,参考工程是 9 维仅供样式参考
8. 不要把 ai_summary 的生成做异步队列;第一阶段同步调用足够

如遇方案未覆盖的细节,选最简实现 + 代码标注 `TODO: 方案未覆盖,采用最简实现`,**不自行扩展功能**。

---

*工单 v0.1 · 关联 PRD v0.3 · 关联技术方案 v0.1*