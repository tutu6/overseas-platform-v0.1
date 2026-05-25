# Task: 柬埔寨公开数据源抓取与 LLM 抽取 · 增量工单 prompt v0.2-Δ7

> 状态:可下发 Claude Code
> 日期:2026-05-25
> 类型:**增量功能扩展**,信用评估模块真实数据源接入第一步
> 关联文档:
> - 上一轮工单:`docs/prompts/信用评估模块_工单prompt_v0_2-Δ5_Supplier注册即评分.md`(需先完成)
> - 技术方案:`docs/architecture/信用评估模块技术方案设计-v0_2.md`(本工单完成后另行升 v0.3)
> - PRD:`docs/prd/信用评估模块 PRD v0.3_四维评分模型版.md.docx`
> - 评分规则清单:`docs/architecture/评分规则清单-v0_1.md`
> 当前分支:`feat/credit-cambodia-public-harvest`(基于 Δ5 完成后的 main 切出)

---

## 1. 任务上下文

### 1.1 信用评估模块当前状态

Δ4 已合入:信用评估模块完整功能已就绪(评分引擎、规则、AI 评价、AI 对话、详情页),RBAC scope 落地。

Δ5 实施中:Supplier 注册即评分闭环,4 家 demo 改造为已注册 Supplier 形态。本工单以 Δ5 合入为前提。

Δ6 待办:credit_company 表约束加固。本工单不依赖 Δ6。

### 1.2 本工单目标

为已注册柬埔寨 (`country_code='KH'`) Supplier,从**公开网络渠道**抓取四维评分所需数据,经 LLM 结构化抽取后落入 `credit_company_*_data` 四张表,触发 ScoringEngine 跑真实数据评分。

实施"评分进行中→数据抓取→评分刷新"两阶段链路,详情接口在抓取未完成时返回 `evaluation_status=pending`。

### 1.3 阅读顺序

1. 本工单 §3 实现步骤
2. Δ5 工单(`docs/prompts/信用评估模块_工单prompt_v0_2-Δ5_Supplier注册即评分.md`),了解注册→评分异步链路
3. 现有 DataSource 抽象层(`backend/app/services/credit/data_source/`)
4. 现有 QwenChatService(`backend/app/services/llm/qwen_chat_service.py`)

---

## 2. 范围

### 2.1 做

| 项 | 说明 |
|---|---|
| `CambodiaDataSource` 实现 | 落在 `app/services/credit/data_source/cambodia_data_source.py`,读 4 张快照表最新一条(与 MockDataSource 模式一致) |
| `PublicWebHarvester` 通用工具 | 落在 `app/services/credit/harvester/`,封装 Tavily 搜索 + qwen-plus 结构化抽取 + 反幻觉机制 |
| 4 维度 prompt 模板 | 柬埔寨专属 prompts,落在 `app/services/credit/harvester/prompts/kh/` |
| `TavilyClient` 搜索 API 封装 | 走 httpx,环境变量 `TAVILY_API_KEY` |
| 抓取异步触发(Δ5 链路接入) | Supplier 注册成功后,Δ5 已触发占位评分;本工单在其后**额外**触发抓取任务,完成后**再触发一次评分** |
| 手动抓取 API | `POST /api/v1/credit/companies/{id}/harvest`,支持 `force_refresh=true` 绕过缓存 |
| 24 小时抓取结果缓存 | 按 `(company_id)` 缓存,7×24 小时内重复触发跳过 Tavily + LLM,沿用最新快照 |
| `credit_data_harvest_run` 审计表 | 记录每次抓取触发,含触发源 / 状态 / 缓存命中 / 4 维度结果 |
| 4 张快照表加 `raw_data` + `harvest_run_id` 字段 | 通过 alembic 迁移 |
| 详情接口 `evaluation_status` 字段 | `pending / ready / failed` 三态,前端据此渲染骨架屏 |
| 反幻觉机制 | LLM 输出强制要求 `_evidence.<field>` 含 `source_quote`,无引用字段后处理置 null |
| 抓取失败兜底 | 落 `data_source='missing'` 评一次分;`harvest_run.status='failed'` + error_detail 留存 |
| 单测覆盖 | 见 §6 |

### 2.2 不做

| 项 | 落到哪 |
|---|---|
| T+1 定时刷新 | 移出本工单,后续独立工单 |
| 规则更新自动触发重评 | 移出本工单,后续独立工单 |
| OCR / 证书图片识别 | 移出本工单,Δ9 或更后 |
| 商业 API 接入(OpenCorporates / D&B / 海外征信厂商) | 移出本工单,Δ8 或更后 |
| 自建爬虫直连 MOC 官网 | 不做(合规风险) |
| 前端注册号正则 bug 修复 | 独立小工单先发(本工单不含) |
| 其他 8 国(巴基斯坦/摩洛哥/...)真实数据源接入 | 待柬埔寨上线、Harvester 抽象稳定后逐国 |
| 评分规则或 evaluator 改动 | 不在本工单 |
| AI 评价文案改造 | 不在本工单 |
| 抓取结果人工复核工作流 | 移出本工单 |

---

## 3. 实现步骤

### Step 1:Alembic 迁移 — 4 张快照表加字段 + 新增审计表

迁移文件:`alembic/versions/XXXXXXXX_credit_harvest_infrastructure.py`

#### 改动 4 张快照表

`credit_company_basic_data` / `credit_company_finance_data` / `credit_company_legal_data` / `credit_company_certification` 各加两个字段:

```sql
ALTER TABLE <table_name>
    ADD COLUMN raw_data JSONB NULL,
    ADD COLUMN harvest_run_id INTEGER NULL REFERENCES credit_data_harvest_run(id);
```

注:`finance_data` 和 `legal_data` 已有 `raw_data` 字段,跳过;`basic_data` 和 `certification` 是首次新增。

#### 新增审计表

```sql
CREATE TABLE credit_data_harvest_run (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES credit_company(id),
    status VARCHAR(20) NOT NULL,
    -- pending / running / succeeded / partial_succeeded / failed / cached_hit
    triggered_by VARCHAR(50) NOT NULL,
    -- supplier_register / manual / cache_hit_fallback
    operator_user_id INTEGER NULL REFERENCES users(id),
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP NULL,
    dimensions_status JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- {basic: succeeded, finance: missing, legal: succeeded, qualification: missing}
    cache_source_run_id INTEGER NULL REFERENCES credit_data_harvest_run(id),
    -- cached_hit 状态时引用的源 run
    error_detail TEXT NULL,
    tavily_calls INTEGER NOT NULL DEFAULT 0,
    llm_calls INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
CREATE INDEX ix_harvest_run_company_started
    ON credit_data_harvest_run (company_id, started_at DESC);
CREATE INDEX ix_harvest_run_status_started
    ON credit_data_harvest_run (status, started_at DESC);
```

> 注:`triggered_by` 仅枚举本工单两种值;后续工单(T+1/规则更新)新增枚举值时,扩 `triggered_by` 不改表。

### Step 2:配置项

`app/core/config.py` 新增:

```python
# Tavily 搜索 API
TAVILY_API_KEY: str = ""
TAVILY_API_URL: str = "https://api.tavily.com"
TAVILY_TIMEOUT_SECONDS: int = 15
TAVILY_MAX_RESULTS_PER_QUERY: int = 5

# 抓取缓存
CREDIT_HARVEST_CACHE_TTL_HOURS: int = 24

# 抓取并发与限速
CREDIT_HARVEST_LLM_TIMEOUT_SECONDS: int = 30
CREDIT_HARVEST_LLM_RETRY: int = 1

# 抓取调用上限(单家公司单次)
CREDIT_HARVEST_TAVILY_CALLS_PER_HARVEST: int = 10
```

`.env.example` 同步加上述变量。

### Step 3:`TavilyClient`

`app/services/credit/harvester/tavily_client.py`:

```python
class TavilySearchResult(BaseModel):
    title: str
    url: str
    content: str  # Tavily 返回的摘要
    score: float | None = None  # Tavily 相关性分数

class TavilyClient:
    """Tavily 搜索 API 封装。使用 httpx 异步调用。"""

    def __init__(self, api_key: str, base_url: str, timeout: int = 15) -> None: ...

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",  # basic / advanced
        include_domains: list[str] | None = None,
    ) -> list[TavilySearchResult]: ...
```

Tavily API 调用细节:
- Endpoint: `POST {TAVILY_API_URL}/search`
- Body: `{api_key, query, max_results, search_depth, include_answer: false, include_raw_content: false}`
- 解析 response.results,映射到 `TavilySearchResult`

### Step 4:`PublicWebHarvester`

`app/services/credit/harvester/public_web_harvester.py`:

```python
class HarvestResult(BaseModel):
    """单维度抓取结果。"""
    status: str  # ok / partial / missing / failed
    data_source: str  # public / media / missing
    extracted: dict[str, Any]  # LLM 抽取的结构化字段
    raw_llm_response: str  # LLM 完整应答
    evidence: dict[str, str | None]  # 每字段的 source_quote
    confidence: str | None  # low / medium / high
    tavily_calls: int
    llm_calls: int
    error: str | None = None

class PublicWebHarvester:
    """通用工具:Tavily 搜索 + qwen-plus 结构化抽取 + 反幻觉。

    设计为国别无关;按 country_code 选择 prompt 模板路径。
    """

    def __init__(
        self,
        tavily: TavilyClient,
        llm: QwenChatService,
        prompts_root: Path,  # 指向 prompts/ 目录
    ) -> None: ...

    async def harvest_basic(
        self,
        company_name: str,
        country_code: str,
        registration_no: str | None,
    ) -> HarvestResult: ...

    async def harvest_finance(self, ...) -> HarvestResult: ...
    async def harvest_legal(self, ...) -> HarvestResult: ...
    async def harvest_qualifications(self, ...) -> list[HarvestResult]: ...
        # 证书可能多张,返回 list
```

每个 `harvest_xxx` 内部流程:

1. **构造搜索 query**(按维度差异化):
   - 基础: `"{company_name}" {registration_no} {country_name} company registration`
   - 财务: `"{company_name}" {country_name} annual report revenue financial`
   - 司法: `"{company_name}" {country_name} lawsuit court litigation`
   - 资质: `"{company_name}" {country_name} ISO certification standard`

2. **调 Tavily** 取 top-N 摘要 + URL,拼成 `search_context`

3. **加载 prompt 模板**:`prompts/{country_code}/{dimension}.txt`

4. **调 qwen-plus**(JSON Schema 强约束):
   - `temperature=0.0`
   - `response_format={"type": "json_object"}`
   - timeout 30s,重试 1 次

5. **JSON 校验**(`schemas.py` 里的 pydantic 模型)

6. **反幻觉后处理**:
   - 遍历 `_evidence.<field>`,如 source_quote 为 null/空,强制将对应字段置 null
   - source_quote 长度 < 10 字符同样视为无效
   - 后处理统计 _confidence

7. **返回 HarvestResult**

### Step 5:LLM 输出 Schema(`schemas.py`)

每个维度对应一个 pydantic 模型,用于 JSON 校验:

```python
class BasicExtractedSchema(BaseModel):
    established_date: str | None  # "YYYY-MM-DD" 字符串,后续 parse
    registered_capital: str | None
    business_scope: str | None
    legal_representative: str | None
    shareholders: str | None
    status_text: str | None  # 正常/异常/注销/吊销
    address: str | None
    website: str | None
    _evidence: dict[str, str | None]
    _confidence: str | None  # low/medium/high
    _notes: str | None = None

class FinanceExtractedSchema(BaseModel):
    revenue_trend: str | None  # growing/fluctuating/loss/unknown
    debt_ratio: float | None
    cash_flow_status: str | None  # positive/negative_with_funding/persistent_negative/unknown
    _evidence: ...
    _confidence: ...
    _notes: ...

class LegalExtractedSchema(BaseModel):
    litigation_count: int | None  # 柬埔寨场景多为 null
    defaulter_unresolved_count: int | None  # 柬埔寨场景多为 null
    defaulter_resolved_count: int | None
    negative_news_level: str | None  # none/occasional/persistent/major_scandal/unknown
    _evidence: ...
    _confidence: ...

class CertificationExtractedSchema(BaseModel):
    has_iso_9001: bool | None
    has_iso_14001: bool | None
    has_iso_45001: bool | None
    has_isc_certification: bool | None  # 柬埔寨 ISC
    other_certifications: list[str] = []  # 文本描述,不细化字段
    _evidence: ...
    _confidence: ...
```

### Step 6:Prompt 模板

`app/services/credit/harvester/prompts/kh/basic.txt`(示例,其他维度同结构):

```
你是企业工商信息抽取专家。
分析柬埔寨企业 "{company_name}"(注册号 {registration_no}) 的公开网络资料。

输入(Tavily 搜索结果):
---
{search_context}
---

输出严格的 JSON,结构如下(任何字段拿不到必须填 null,不要猜测):
{
  "established_date": "YYYY-MM-DD 或 null",
  "registered_capital": "原文表述如 'USD 5,000,000' 或 null",
  "business_scope": "经营范围描述 或 null",
  "legal_representative": "法人姓名 或 null",
  "shareholders": "股东与持股比例描述 或 null",
  "status_text": "正常 / 异常 / 注销 / 吊销 之一 或 null",
  "address": "完整注册地址 或 null",
  "website": "官网 URL 或 null",
  "_evidence": {
    "established_date": "原文引用片段(不少于 10 字)或 null",
    "registered_capital": "原文引用片段 或 null",
    ...(每个非 null 字段必须提供)
  },
  "_confidence": "low / medium / high",
  "_notes": "任何不确定性说明(可选)"
}

铁律:
1. 任何字段如无明确证据,必须填 null
2. _evidence 中的 source_quote 必须是原文片段(不少于 10 字),不是你的总结
3. 不要输出 JSON 之外的任何文本
```

其他三个维度模板(`finance.txt` / `legal.txt` / `qualification.txt`)结构对应,字段对齐 §Step 5 Schema。

### Step 7:`CambodiaDataSource`

`app/services/credit/data_source/cambodia_data_source.py`:

```python
class CambodiaDataSource(DataSource):
    """柬埔寨数据源(Δ7)。

    fetch_xxx 仍是从数据库读最新一条(与 MockDataSource 模式一致)。
    抓取由异步任务驱动,与 fetch_xxx 解耦。
    """

    async def fetch_basic_data(self, session, company_id) -> BasicData:
        # 与 MockDataSource 行为一致:读最新一条
        # 没有数据返回 data_source='missing' stub
        ...
    # 其他三个 fetch_xxx 同
```

### Step 8:`registry.py` 路由更新

```python
def resolve_data_source(country_code: str) -> DataSource:
    if country_code == "KH":
        return CambodiaDataSource()
    return MockDataSource()  # 其他 8 国仍 mock
```

### Step 9:抓取任务实现

`app/services/credit/harvester/harvest_task.py`:

```python
async def run_harvest_for_company(
    session: AsyncSession,
    company_id: int,
    triggered_by: str,
    operator_user_id: int | None = None,
    force_refresh: bool = False,
) -> CreditDataHarvestRun:
    """完整抓取流程。

    1. 缓存检查(force_refresh=false 时):
       查 24 小时内是否有 status=succeeded 或 partial_succeeded 的 run
       命中 → 写新 run(status=cached_hit, cache_source_run_id=源 id),返回
    2. 写 run(status=running)
    3. 加载 company,取 name + registration_no
    4. 依次 harvest 四维度,每维度结果:
       - status=ok / partial: 落新快照(带 raw_data + harvest_run_id)
       - status=missing: 落 data_source='missing' 占位快照(带 raw_data 留 LLM 应答)
       - status=failed: 不落快照,run dimensions_status 标 failed
    5. 更新 run(status, finished_at, dimensions_status, tavily_calls, llm_calls, error_detail)
    6. 触发评分:ScoringEngine.compute(trigger_type='harvest_refresh')
    """
```

调用方:
- Δ5 注册成功后的 BackgroundTask(在 Δ5 占位评分之后追加触发)
- 手动 API

### Step 10:Δ5 链路接入

修改 `app/api/v1/auth.py` 中 supplier 注册成功后的 BackgroundTask:

```python
# Δ5 已有(伪代码)
background_tasks.add_task(initialize_credit_for_new_supplier, ...)

# Δ7 追加(在同一个 BackgroundTask 链尾追加,或单独追加一个)
background_tasks.add_task(
    run_harvest_for_company,
    company_id=company.id,
    triggered_by="supplier_register",
)
```

**关键约束**:Δ7 触发的抓取任务必须在 Δ5 占位评分**之后**执行。Δ5 占位评分负责写第一条 score_snapshot(全 missing → 各维度降级),Δ7 抓取完成后追加第二条 snapshot。

### Step 11:手动触发 API

`app/api/v1/credit.py` 新增:

```python
@router.post(
    "/companies/{company_id}/harvest",
    summary="手动触发数据抓取(运营用)",
    dependencies=[Depends(require_permission("credit.operate"))],
)
async def trigger_harvest(
    company_id: int,
    force_refresh: bool = Query(False, description="强制刷新(绕过 24h 缓存)"),
    background_tasks: BackgroundTasks,
    operator: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # 1. 校验 company 存在且 country_code='KH'
    # 2. 触发 BackgroundTask
    # 3. 返回 {harvest_run_id, status: 'queued'}
    ...
```

权限点 `credit.operate` 沿用 Δ4 已建立的 RBAC,无需新建。

### Step 12:详情接口 `evaluation_status`

修改 `app/api/v1/credit.py` 中的 company detail 接口,新增字段:

```python
class CompanyDetailOut(BaseModel):
    ...(原字段)
    evaluation_status: str  # pending / ready / failed
    latest_harvest_run: dict | None  # {id, status, started_at, finished_at}
```

`evaluation_status` 判定逻辑:
- 查公司最近一条 `credit_data_harvest_run`
- run.status in (pending, running) → `pending`
- run.status in (succeeded, partial_succeeded, cached_hit) → `ready`
- run.status = failed → `failed`
- 无 run(理论上不出现,Δ5 注册时会触发) → `pending`(防御)

前端按此渲染骨架屏或评分内容。

---

## 4. 关键约束

### 4.1 反幻觉

| 约束 | 实施 |
|---|---|
| LLM 必须为每个非 null 字段提供 source_quote(不少于 10 字) | prompt 强制 + 后处理校验 |
| source_quote 缺失或过短的字段强制置 null | 后处理统一处理 |
| `_confidence` 字段强制落库到 `raw_data._confidence` | 后续运营可观察可靠性 |

### 4.2 数据来源标记

| 维度 | 主标记 |
|---|---|
| 基础工商 | `public`(LLM 抽取 + 多源融合) |
| 资质认证 | `public`(LLM 识别"是否拥有"类证书) |
| 财务 | `public`(上市企业可得) / `missing`(私企居多) |
| 司法 | `media`(舆情子项) + `missing`(litigation/defaulter 字段) |

### 4.3 raw_data 留存

| 表 | raw_data 内容 |
|---|---|
| `credit_company_basic_data` | `{llm_response: str, evidence: dict, confidence: str, tavily_results: list[{url, title, content}]}` |
| `credit_company_finance_data` | 同上结构 |
| `credit_company_legal_data` | 同上结构 |
| `credit_company_certification` | 同上结构(每张证书一条记录,raw_data 关联到来源 LLM 应答) |

### 4.4 缓存语义

- key:`company_id`
- 命中条件:24 小时内存在 `status ∈ (succeeded, partial_succeeded)` 的 run
- 命中行为:写新 run(`status=cached_hit, cache_source_run_id=源 id, tavily_calls=0, llm_calls=0`);**不写新快照**;**不重新调评分**(因为快照没变,评分结果也不会变)
- `force_refresh=true` 时绕过缓存

### 4.5 缓存命中时是否触发评分

不触发。理由:
- 快照没变(沿用旧 run 的快照)
- ScoringEngine 输入相同 → 评分结果相同
- 重复写 score_snapshot 仅引入噪声
- 详情接口拿到的 evaluation_status='ready'(因为 run.status=cached_hit ∈ ready 类)

### 4.6 失败兜底

| 失败类型 | 处理 |
|---|---|
| Tavily 调用失败(超时/限流/无 key) | 该维度 status=failed,不写快照,run.dimensions_status 记 failed,继续下一维度 |
| LLM 调用失败 | 同上,重试 1 次后仍失败则 failed |
| LLM 返回非合法 JSON | Schema 校验失败 → 该维度 failed |
| LLM 返回字段全为 null | status=missing,落 data_source='missing' 快照(raw_data 留 LLM 应答) |
| 全部 4 维度都 failed | run.status='failed', error_detail 汇总;评分仍跑(走 missing 路径) |
| 部分维度成功 | run.status='partial_succeeded' |

### 4.7 不修改既有评分链路

| 模块 | 改动 |
|---|---|
| `ScoringEngine` | 不动 |
| `evaluators.py` | 不动 |
| `data_source/base.py` | 不动 |
| `MockDataSource` | 不动(其他 8 国仍使用) |

---

## 5. 文件清单

### 5.1 新增

```
backend/app/services/credit/data_source/cambodia_data_source.py
backend/app/services/credit/harvester/__init__.py
backend/app/services/credit/harvester/public_web_harvester.py
backend/app/services/credit/harvester/tavily_client.py
backend/app/services/credit/harvester/schemas.py
backend/app/services/credit/harvester/harvest_task.py
backend/app/services/credit/harvester/prompts/kh/basic.txt
backend/app/services/credit/harvester/prompts/kh/finance.txt
backend/app/services/credit/harvester/prompts/kh/legal.txt
backend/app/services/credit/harvester/prompts/kh/qualification.txt
backend/app/db/models/credit_data_harvest_run.py
backend/alembic/versions/XXXXXXXX_credit_harvest_infrastructure.py
```

### 5.2 改动

```
backend/app/services/credit/data_source/registry.py        # KH 路由到 CambodiaDataSource
backend/app/api/v1/auth.py                                 # supplier 注册成功 BackgroundTask 追加 harvest
backend/app/api/v1/credit.py                               # 新增手动触发 API + 详情接口加 evaluation_status
backend/app/core/config.py                                 # 新增 Tavily / 抓取相关配置
backend/app/db/models/credit_company_basic_data.py         # 加 raw_data + harvest_run_id
backend/app/db/models/credit_company_certification.py      # 加 raw_data + harvest_run_id
backend/app/db/models/credit_company_finance_data.py       # 加 harvest_run_id(raw_data 已有)
backend/app/db/models/credit_company_legal_data.py         # 加 harvest_run_id(raw_data 已有)
backend/app/services/credit/types.py                       # BasicData 加 raw_data 可选字段
backend/.env.example                                       # 加 TAVILY_API_KEY 等环境变量
backend/pyproject.toml                                     # 新增依赖 httpx(若未引入)
```

### 5.3 测试

```
backend/tests/credit/test_cambodia_data_source.py
backend/tests/credit/test_public_web_harvester.py
backend/tests/credit/test_tavily_client.py
backend/tests/credit/test_harvest_anti_hallucination.py
backend/tests/credit/test_harvest_cache.py
backend/tests/credit/test_harvest_task_integration.py
backend/tests/credit/test_harvest_failure_fallback.py
backend/tests/credit/test_evaluation_status_field.py
backend/tests/credit/test_manual_harvest_api.py
```

---

## 6. 验收标准

### 6.1 功能验收

| 场景 | 期望 |
|---|---|
| 柬埔寨大型公开企业(如 Kampot Cement)注册 | 维度 1 至少 5/8 字段有值;维度 4 negative_news_level 非 null;维度 2/3 多为 missing |
| 柬埔寨 CSX 上市企业(如 JS Land Plc)注册 | 维度 1/3/4 多字段有值;维度 2 部分识别 |
| 柬埔寨小微企业(注册号正确但网络无信息) | 全维度 missing,run.status=partial_succeeded 或 failed,评分走降级路径 |
| 24 小时内重复手动触发(不带 force_refresh) | 新 run.status=cached_hit, cache_source_run_id 指向上次 run,无 Tavily/LLM 调用 |
| 24 小时内重复手动触发(带 force_refresh=true) | 跳过缓存,真实调用 Tavily + LLM,新写快照 + 新评分 |
| Tavily API 返回 0 结果 | 该维度 status=missing,落 missing 快照 |
| LLM 抛错(模拟 timeout) | 该维度 status=failed,run.dimensions_status 标 failed,继续下一维度 |
| LLM 返回字段无 source_quote | 后处理强制置 null,落库字段为 null |
| 详情接口在评分进行中查询 | 返回 `evaluation_status='pending'`,前端骨架屏 |

### 6.2 数据验收

| 表 | 校验 |
|---|---|
| credit_data_harvest_run | 每次触发必有记录;状态枚举正确;dimensions_status 4 维度齐 |
| credit_company_basic_data | raw_data 非空时含 llm_response/evidence/confidence/tavily_results |
| 所有 4 张快照表 | data_source 仅取 {public, media, missing};harvest_run_id 非空指向有效 run |

### 6.3 安全验收

- Tavily API Key 仅出现在 env 文件,不进代码库
- 手动触发 API 必须通过 `credit.operate` 权限校验
- 抓取产生的 raw_data 不暴露 Tavily 中间结果之外的内部信息

### 6.4 单测覆盖

- `test_cambodia_data_source.py`:与 MockDataSource 行为对齐
- `test_public_web_harvester.py`:mock TavilyClient + mock LLM,验证字段映射
- `test_harvest_anti_hallucination.py`:LLM 应答缺 evidence 字段时强制置 null
- `test_harvest_cache.py`:24h 内重复触发命中 / force_refresh 绕过
- `test_harvest_task_integration.py`:完整闭环(写 run + 写快照 + 触发评分)
- `test_harvest_failure_fallback.py`:Tavily / LLM 失败时 run 状态正确
- `test_evaluation_status_field.py`:三态判定逻辑
- `test_manual_harvest_api.py`:权限校验 + 参数校验

---

## 7. 风险与缓解

| 风险 | 严重性 | 缓解 |
|---|---|---|
| LLM 幻觉(编造字段) | 高 | source_quote 强制约束 + 后处理 null 化 + raw_data 留存供溯源 |
| 搜索结果命中错公司(重名/子公司) | 中 | query 中带 registration_no + country_name;LLM prompt 强调"目标公司" |
| Tavily 免费层配额耗尽(1000 次/月) | 中 | 缓存 24 小时 + 单家公司单次 ≤10 次调用 + 配额监控告警 |
| qwen-plus Token 消耗超预期 | 中 | 缓存机制 + 限制 Tavily search_depth=basic(摘要短) |
| 抓取任务在 demo 现场触发但未完成 | 中 | evaluation_status=pending + 前端骨架屏 + 注册时同步出占位评分 |
| 抓取异步任务积压(进程内执行,峰值多家公司同时注册) | 中 | FastAPI BackgroundTasks 进程内串行,MVP 阶段可接受;若并发高再切 Celery |
| force_refresh 被误用导致 Token 浪费 | 低 | 权限点限制 + 后端做最小间隔限制(可选) |

---

## 8. 实施前置依赖

- [ ] Δ5 工单已合入(supplier_register BackgroundTask 已就位)
- [ ] Tavily 账号已申请(已确认),API Key 已注入 demo 环境
- [ ] qwen-plus DashScope 账号本地可用(已确认)
- [ ] 前端柬埔寨注册号正则 bug(`^[A-Z0-9]{10,12}$` → `^[0-9]{6,12}$`)已修(独立小工单)

---

## 9. 与后续工单的关系

```
Δ5 (Supplier 注册即评分) ──→ Δ7 (本工单 · 柬埔寨公开数据源)
                                  │
                                  ├──→ Δ8 ?(T+1 定时刷新 / 规则更新触发重评 / 批量重评)
                                  ├──→ Δ9 ?(商业 API:OpenCorporates / D&B)
                                  ├──→ Δ10 ?(OCR + 用户上传补全)
                                  └──→ 其他 8 国(巴基斯坦/摩洛哥/...)
```

---

## 10. v0.1 相对 v0.0 的变更

| # | 变更 | 原因 |
|---|---|---|
| 1 | 移除 T+1 定时刷新 | 温总:T+1 先不做,Δ7 先跑通注册+手动 |
| 2 | 移除规则更新触发重评 | 同上,与抓取链路解耦 |
| 3 | 移除变更检测机制 | T+1 移除后该机制不再需要 |
| 4 | 缓存从"7 天 + 变更检测"改为"24 小时" | 温总:更保守,只避免同日反复探索 |
| 5 | 缓存方案明确为 A(外层缓存抓取结果) | 温总:遵循 MVP 务实 |
| 6 | 详情接口新增 evaluation_status=pending 友好提示 | 温总:注册到评分完成之间需友好提示 |
| 7 | 明确移出 OCR / 证书图片识别 | 温总:本期仅文本/HTML |
| 8 | 搜索 API 明确选 Tavily | PM:账号已申请 |
| 9 | LLM 明确用 qwen-plus(不切 qwen3-max) | 千问 enable_search 仅 qwen3-max 支持,模型切换成本大;两步分离更可控 |

---

*工单 v0.1 定稿。Δ5 合入后启动。*
