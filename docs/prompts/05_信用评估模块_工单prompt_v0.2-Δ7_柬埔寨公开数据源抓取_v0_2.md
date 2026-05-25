# Task: 柬埔寨公开数据源抓取与 LLM 抽取 · 增量工单 prompt v0.2-Δ7

> 状态:可下发 Claude Code
> 日期:2026-05-25
> 类型:**增量功能扩展**,信用评估模块真实数据源接入第一步
> 关联文档:
> - 上一轮工单:`docs/prompts/信用评估模块_工单prompt_v0_2-Δ5_Supplier注册即评分.md`(已合入)
> - 技术方案:`docs/architecture/信用评估模块技术方案设计-v0_2.md`(本工单完成后另行升 v0.3)
> - PRD:`docs/prd/信用评估模块 PRD v0.3_四维评分模型版.md.docx`
> - 评分规则清单:`docs/architecture/评分规则清单-v0_1.md`
> 当前分支:`feat/credit-cambodia-public-harvest`(基于 Δ5 已合入的 main 切出)

---

## 1. 任务上下文

### 1.1 信用评估模块当前状态

- Δ4 已合入:信用评估模块完整功能就绪(评分引擎、规则、AI 评价、AI 对话、详情页),RBAC scope 落地
- Δ5 已合入:Supplier 注册即评分闭环,`initialize_credit_for_new_supplier` 已挂在 `auth.py` 注册成功 BackgroundTask
- Δ6 待办:credit_company 表约束加固,本工单不依赖

### 1.2 本工单目标

为已注册柬埔寨 (`country_code='KH'`) Supplier,从**公开网络渠道**抓取四维评分所需数据,经 LLM 结构化抽取后落入 `credit_company_*_data` 四张表,触发 ScoringEngine 跑真实数据评分。

实施"评分进行中 → 数据抓取 → 评分刷新"两阶段链路,详情接口在抓取未完成时返回 `evaluation_status=pending`。

### 1.3 阅读顺序

1. 本工单 §3 实现步骤
2. Δ5 工单(`docs/prompts/信用评估模块_工单prompt_v0_2-Δ5_Supplier注册即评分.md`)
3. 现有 DataSource 抽象层(`backend/app/services/credit/data_source/`)
4. 现有 QwenChatService(`backend/app/services/llm/qwen_chat_service.py`)与 LLMService 基类(`backend/app/services/llm/base.py`)
5. RBAC 权限点定义(`backend/app/rbac/constants.py`)

---

## 2. 范围

### 2.1 做

| 项 | 说明 |
|---|---|
| `CambodiaDataSource` 实现 | `app/services/credit/data_source/cambodia_data_source.py`,读 4 张快照表最新一条(与 MockDataSource 模式一致) |
| `PublicWebHarvester` 通用工具 | `app/services/credit/harvester/`,封装 Tavily 搜索 + qwen-plus 结构化抽取 + 反幻觉机制 |
| 4 维度 prompt 模板 | `app/services/credit/harvester/prompts/kh/`(柬埔寨专属) |
| `TavilyClient` 搜索 API 封装 | 走 httpx,环境变量 `TAVILY_API_KEY` |
| `LLMService.generate_json()` 新增方法 + `QwenChatService` 实现 | 结构化抽取专用,固定 `temperature=0.0` + `response_format={"type":"json_object"}` |
| 抓取异步触发(Δ5 链路接入) | 注册成功 BackgroundTask 链尾追加 harvest_task |
| 手动抓取 API | `POST /api/v1/credit/companies/{id}/harvest`,支持 `force_refresh=true` |
| 24 小时抓取结果缓存 | 按 `company_id` 缓存,命中跳过 Tavily + LLM,沿用最新快照 |
| `credit_data_harvest_run` 审计表 | 抓取过程审计,与 `audit_logs` / `score_audit_log` 分工见 §4.7 |
| 4 张快照表加 `raw_data` + `harvest_run_id` 字段 | 通过 alembic 迁移(`raw_data` 在 finance/legal 已有,仅 basic/cert 新增) |
| 详情接口 `evaluation_status` 字段 | `pending / ready / failed`,前端骨架屏依赖 |
| 反幻觉机制 | LLM 输出强制要求 `_evidence.<field>` 含 source_quote(≥10 字),无引用字段后处理置 null |
| 抓取失败兜底 | 维度级隔离,落 `data_source='missing'` 评一次分;run.status 准确反映成败 |
| 单测覆盖 | 见 §6 |

### 2.2 不做

| 项 | 落到哪 |
|---|---|
| T+1 定时刷新 | 后续独立工单 |
| 规则更新自动触发重评 | 后续独立工单 |
| OCR / 证书图片识别 | Δ9 或更后 |
| 商业 API 接入(OpenCorporates / D&B / 海外征信厂商) | Δ8 或更后 |
| 自建爬虫直连 MOC 官网 | 不做(合规风险) |
| 前端注册号正则 bug 修复 | 独立小工单先发(本工单不含) |
| 其他 8 国真实数据源接入 | 柬埔寨上线、Harvester 抽象稳定后逐国 |
| 评分规则或 evaluator 改动 | 不在本工单 |
| AI 评价文案改造 | 不在本工单 |
| 抓取结果人工复核工作流 | 后续工单 |
| `TriggerType` 枚举新增 | **不新增**。沿用 `REAL_TIME_ONBOARD`(注册场景) + `MANUAL_RECALC`(手动场景) |
| 新增权限点 | **不新增**。手动 API 复用 `Permissions.CREDIT_RECOMPUTE` |

---

## 3. 实现步骤

### Step 1:Alembic 迁移 — 4 张快照表加字段 + 新增审计表

迁移文件:`alembic/versions/XXXXXXXX_credit_harvest_infrastructure.py`

#### 改动 4 张快照表

```sql
-- credit_company_basic_data 首次新增 raw_data
ALTER TABLE credit_company_basic_data
    ADD COLUMN raw_data JSONB NULL,
    ADD COLUMN harvest_run_id INTEGER NULL REFERENCES credit_data_harvest_run(id);

-- credit_company_certification 首次新增 raw_data
ALTER TABLE credit_company_certification
    ADD COLUMN raw_data JSONB NULL,
    ADD COLUMN harvest_run_id INTEGER NULL REFERENCES credit_data_harvest_run(id);

-- finance/legal_data 已有 raw_data,仅加 harvest_run_id
ALTER TABLE credit_company_finance_data
    ADD COLUMN harvest_run_id INTEGER NULL REFERENCES credit_data_harvest_run(id);
ALTER TABLE credit_company_legal_data
    ADD COLUMN harvest_run_id INTEGER NULL REFERENCES credit_data_harvest_run(id);
```

#### 新增审计表

```sql
CREATE TABLE credit_data_harvest_run (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES credit_company(id),
    status VARCHAR(20) NOT NULL,
    -- pending / running / succeeded / partial_succeeded / failed / cached_hit
    triggered_by VARCHAR(50) NOT NULL,
    -- supplier_register / manual
    operator_user_id INTEGER NULL REFERENCES users(id),
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP NULL,
    dimensions_status JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- {basic: succeeded, finance: missing, legal: succeeded, qualification: missing}
    cache_source_run_id INTEGER NULL REFERENCES credit_data_harvest_run(id),
    -- cached_hit 时引用源 run
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

> 迁移顺序注意:`credit_data_harvest_run` 表先建,然后 4 张快照表才能加 `harvest_run_id` 外键。alembic upgrade 内部按 SQL 顺序执行即可。

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

# 抓取调用上限(单家公司单次)
CREDIT_HARVEST_TAVILY_CALLS_PER_HARVEST: int = 10
CREDIT_HARVEST_LLM_TIMEOUT_SECONDS: int = 30
CREDIT_HARVEST_LLM_RETRY: int = 1
```

`.env.example` 同步加上述变量(注释中标注 TAVILY_API_KEY 不入仓库)。

### Step 3:`LLMService` 基类扩展 + `QwenChatService.generate_json()`

`app/services/llm/base.py`(扩抽象方法):

```python
class LLMService(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str: ...

    @abstractmethod
    async def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]: ...

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        *,
        timeout_seconds: int | None = None,
    ) -> str:
        """结构化 JSON 输出。

        实现需保证:
        - 固定 temperature=0.0
        - 启用 response_format={"type": "json_object"}
        - 返回原始 JSON 字符串(调用方负责 schema 校验与解析)
        - 失败抛 LLMUnavailableError
        """
        ...
```

`app/services/llm/qwen_chat_service.py`(新增方法,不动既有 `generate` / `stream_chat`):

```python
async def generate_json(
    self,
    prompt: str,
    *,
    timeout_seconds: int | None = None,
) -> str:
    self._check_configured()
    try:
        # 注意:openai SDK 的 timeout 是客户端级,这里通过 with_options 临时覆盖
        client = (
            self._client.with_options(timeout=timeout_seconds)
            if timeout_seconds is not None
            else self._client
        )
        resp = await client.chat.completions.create(
            model=self._model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
    except (APIConnectionError, APITimeoutError, AuthenticationError, APIError) as exc:
        logger.warning("LLM generate_json 失败: %s", exc)
        raise LLMUnavailableError(str(exc)) from exc
    except Exception as exc:
        logger.exception("LLM generate_json 未知错误")
        raise LLMUnavailableError(str(exc)) from exc

    content = resp.choices[0].message.content if resp.choices else None
    return (content or "").strip()
```

> 说明:DashScope OpenAI 兼容端点已支持 `response_format={"type":"json_object"}`(qwen-plus 自 2024Q3 起支持)。如发现兼容性问题,降级方案为 prompt 末尾追加 "仅输出 JSON,不要任何其他文本" 强约束 + 调用方加强 JSON 解析容错。

### Step 4:`TavilyClient`

`app/services/credit/harvester/tavily_client.py`:

```python
class TavilySearchResult(BaseModel):
    title: str
    url: str
    content: str       # Tavily 摘要
    score: float | None = None  # 相关性分数

class TavilyClient:
    """Tavily 搜索 API 封装。httpx 异步。"""

    def __init__(self, api_key: str, base_url: str, timeout: int = 15) -> None: ...

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: list[str] | None = None,
    ) -> list[TavilySearchResult]: ...
```

Tavily API 细节:
- Endpoint: `POST {TAVILY_API_URL}/search`
- Body: `{api_key, query, max_results, search_depth, include_answer: false, include_raw_content: false}`
- 解析 `response.results` 映射到 `TavilySearchResult`
- 异常:超时 / 401 / 配额限制 抛 `TavilyError`(模块内自定义异常类)

### Step 5:`PublicWebHarvester`

`app/services/credit/harvester/public_web_harvester.py`:

```python
class HarvestResult(BaseModel):
    """单维度抓取结果。"""
    status: str  # ok / partial / missing / failed
    data_source: str  # public / media / missing
    extracted: dict[str, Any]  # LLM 抽取的字段
    raw_llm_response: str
    evidence: dict[str, str | None]  # 每字段 source_quote
    confidence: str | None
    tavily_calls: int
    llm_calls: int
    error: str | None = None

class PublicWebHarvester:
    """通用工具:Tavily + LLM 结构化抽取 + 反幻觉。国别无关。"""

    def __init__(
        self,
        tavily: TavilyClient,
        llm: LLMService,
        prompts_root: Path,
    ) -> None: ...

    async def harvest_basic(
        self, company_name: str, country_code: str, registration_no: str | None,
    ) -> HarvestResult: ...

    async def harvest_finance(self, ...) -> HarvestResult: ...
    async def harvest_legal(self, ...) -> HarvestResult: ...
    async def harvest_qualifications(self, ...) -> list[HarvestResult]: ...
```

每个 `harvest_xxx` 内部:

1. **构造搜索 query**(维度差异化):
   - 基础: `"{company_name}" {registration_no} {country_name} company registration`
   - 财务: `"{company_name}" {country_name} annual report revenue financial`
   - 司法: `"{company_name}" {country_name} lawsuit court litigation`
   - 资质: `"{company_name}" {country_name} ISO certification standard`

2. 调 Tavily 取 top-N,拼成 `search_context`

3. 加载 prompt 模板:`prompts/{country_code}/{dimension}.txt`,做 `{company_name}` / `{registration_no}` / `{search_context}` 替换

4. 调 `llm.generate_json(prompt, timeout_seconds=30)`,重试 1 次

5. JSON Schema 校验(§Step 6)

6. **反幻觉后处理**:
   - 遍历 `_evidence.<field>`,source_quote 为 null / 空 / 长度<10 字符 → 强制将对应字段置 null
   - 统计 `_confidence`,写入 raw_data

7. 返回 `HarvestResult`

### Step 6:LLM 输出 Schema

`app/services/credit/harvester/schemas.py`:

```python
class BasicExtractedSchema(BaseModel):
    established_date: str | None
    registered_capital: str | None
    business_scope: str | None
    legal_representative: str | None
    shareholders: str | None
    status_text: str | None  # 正常/异常/注销/吊销
    address: str | None
    website: str | None
    evidence: dict[str, str | None] = Field(alias="_evidence")
    confidence: str | None = Field(default=None, alias="_confidence")
    notes: str | None = Field(default=None, alias="_notes")

    model_config = ConfigDict(populate_by_name=True)

class FinanceExtractedSchema(BaseModel):
    revenue_trend: str | None
    debt_ratio: float | None
    cash_flow_status: str | None
    evidence: dict[str, str | None] = Field(alias="_evidence")
    confidence: str | None = Field(default=None, alias="_confidence")

class LegalExtractedSchema(BaseModel):
    litigation_count: int | None
    defaulter_unresolved_count: int | None
    defaulter_resolved_count: int | None
    negative_news_level: str | None  # none/occasional/persistent/major_scandal/unknown
    evidence: dict[str, str | None] = Field(alias="_evidence")
    confidence: str | None = Field(default=None, alias="_confidence")

class CertificationExtractedSchema(BaseModel):
    has_iso_9001: bool | None
    has_iso_14001: bool | None
    has_iso_45001: bool | None
    has_isc_certification: bool | None
    other_certifications: list[str] = Field(default_factory=list)
    evidence: dict[str, str | None] = Field(alias="_evidence")
    confidence: str | None = Field(default=None, alias="_confidence")
```

### Step 7:Prompt 模板

`app/services/credit/harvester/prompts/kh/basic.txt`(其他维度同结构):

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
    "registered_capital": "原文引用片段 或 null"
    /* 每个非 null 字段必须提供 */
  },
  "_confidence": "low / medium / high",
  "_notes": "任何不确定性说明(可选)"
}

铁律:
1. 任何字段如无明确证据,必须填 null
2. _evidence 中的 source_quote 必须是原文片段(不少于 10 字),不是总结
3. 不要输出 JSON 之外的任何文本
```

> 实施时:`{company_name}` / `{registration_no}` / `{search_context}` 由代码在加载模板后做字符串替换。其他三个维度(`finance.txt` / `legal.txt` / `qualification.txt`)字段对齐 §Step 6 Schema。

### Step 8:`CambodiaDataSource`

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
    # 其余三个 fetch_xxx 同
```

实现可直接 copy MockDataSource 框架,本期 SQL 逻辑相同。差异在未来——CambodiaDataSource 可能需要"按 harvest_run_id 优先级排序"等定制逻辑,本期不引入。

### Step 9:`registry.py` 路由更新

```python
def resolve_data_source(country_code: str) -> DataSource:
    if country_code == "KH":
        return CambodiaDataSource()
    return MockDataSource()  # 其他 8 国仍 mock
```

### Step 10:抓取任务实现

`app/services/credit/harvester/harvest_task.py`:

```python
async def run_harvest_for_company(
    session: AsyncSession,
    company_id: int,
    triggered_by: str,             # 'supplier_register' / 'manual'
    operator_user_id: int | None = None,
    force_refresh: bool = False,
) -> CreditDataHarvestRun:
    """完整抓取流程。

    1. 缓存检查(force_refresh=false 时):
       查 CREDIT_HARVEST_CACHE_TTL_HOURS 内是否有 status ∈ (succeeded, partial_succeeded) 的 run
       命中 → 写新 run(status=cached_hit, cache_source_run_id=源 id, tavily_calls=0, llm_calls=0)
              不写新快照,不触发评分,直接返回
    2. 写 run(status=running, started_at=now)
    3. 加载 company,取 name + registration_no
    4. 依次 harvest 四维度:
       - ok / partial:落新快照(带 raw_data + harvest_run_id)
       - missing:落 data_source='missing' 占位快照(带 raw_data 留 LLM 应答)
       - failed:不落快照,run.dimensions_status 标 failed
    5. 更新 run(status, finished_at, dimensions_status, tavily_calls, llm_calls, error_detail)
    6. 触发评分:
       - trigger_type = REAL_TIME_ONBOARD(注册触发) 或 MANUAL_RECALC(手动触发)
       - trigger_detail = {"harvest_run_id": run.id, "triggered_by": triggered_by}
       - ScoringEngine.compute(...)
    """
```

调用方:
- Δ5 注册成功 BackgroundTask 链尾(在 `initialize_credit_for_new_supplier` 之后追加)
- 手动 API

### Step 11:Δ5 链路接入

修改 `app/api/v1/auth.py` 中 supplier 注册成功后的 BackgroundTask 链:

```python
# Δ5 已有
background_tasks.add_task(initialize_credit_for_new_supplier, supplier_org_id=...)

# Δ7 追加(独立 BackgroundTask,链尾)
background_tasks.add_task(
    _harvest_after_register,
    company_id=...,  # 由 initialize_credit_for_new_supplier 创建的 credit_company.id 取得
)
```

**关键约束**:`_harvest_after_register` 必须先确认 Δ5 占位评分已完成(查 credit_company 存在 + 至少一条 score_snapshot),再调 `run_harvest_for_company(triggered_by='supplier_register')`。

实现路径建议:`_harvest_after_register` 内部:
1. 用独立 AsyncSession
2. 查 credit_company 是否存在(防御:Δ5 可能因异常未建)
3. 调 `run_harvest_for_company(...)`
4. 失败只记日志不抛(注册主流程不受影响,与 Δ5 风格一致)

### Step 12:手动触发 API

`app/api/v1/credit.py` 新增:

```python
@router.post(
    "/companies/{company_id}/harvest",
    summary="手动触发数据抓取(运营用)",
)
async def trigger_harvest(
    company_id: int = Path(..., ge=1),
    force_refresh: bool = Query(False, description="强制刷新(绕过 24h 缓存)"),
    background_tasks: BackgroundTasks = ...,
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_RECOMPUTE)),
    db: AsyncSession = Depends(get_db),
):
    # 1. 校验 company 存在
    company = await db.get(CreditCompany, company_id)
    if company is None:
        raise BusinessError(http_status=404, biz_code=40404, message="企业不存在")

    # 2. 仅柬埔寨支持(本期)
    if company.country_code != "KH":
        raise BusinessError(
            http_status=400, biz_code=40001,
            message="当前仅支持柬埔寨企业抓取真实数据源",
        )

    # 3. 提交后台任务
    background_tasks.add_task(
        _manual_harvest,
        company_id=company_id,
        operator_user_id=current.user_id,
        force_refresh=force_refresh,
    )

    return {"code": 0, "message": "已加入抓取队列", "data": {"company_id": company_id}}
```

> 权限点复用 `CREDIT_RECOMPUTE`(已挂在 `/recompute` 和 `/recompute-all` 接口,语义匹配)。

### Step 13:详情接口 `evaluation_status`

修改 `app/api/v1/credit.py` 中 company detail 接口:

```python
class CompanyDetailOut(BaseModel):
    ...(原字段)
    evaluation_status: str  # pending / ready / failed
    latest_harvest_run: dict | None  # {id, status, triggered_by, started_at, finished_at}
```

`evaluation_status` 判定:
- 查公司最近一条 `credit_data_harvest_run`
- run.status in (pending, running) → `pending`
- run.status in (succeeded, partial_succeeded, cached_hit) → `ready`
- run.status = failed → `failed`
- 无 run(KH 公司)→ `pending`(防御)
- 非 KH 公司无 harvest 概念 → `ready`(直接走 mock 数据)

前端按此渲染骨架屏或评分内容。

---

## 4. 关键约束

### 4.1 反幻觉

| 约束 | 实施 |
|---|---|
| LLM 必须为每个非 null 字段提供 source_quote(≥10 字) | prompt 强制 + 后处理校验 |
| source_quote 缺失或过短 → 字段强制置 null | 统一后处理 |
| `_confidence` 写入 raw_data | 后续运营观察 |

### 4.2 数据来源标记

| 维度 | 主标记 |
|---|---|
| 基础工商 | `public`(LLM 抽取) |
| 资质认证 | `public`(LLM 识别"是否拥有") |
| 财务 | `public`(上市可得)/ `missing` |
| 司法 | `media`(舆情)+ `missing`(litigation/defaulter) |

### 4.3 raw_data 留存

每张快照表 raw_data 结构:

```json
{
  "llm_response": "原始 JSON 字符串",
  "evidence": {"established_date": "原文片段", ...},
  "confidence": "high",
  "tavily_results": [{"url": "...", "title": "...", "content": "..."}],
  "harvest_run_id": 123
}
```

### 4.4 缓存语义

- key:`company_id`
- 命中条件:`CREDIT_HARVEST_CACHE_TTL_HOURS` 内存在 `status ∈ (succeeded, partial_succeeded)` 的 run
- 命中行为:写新 run(`status=cached_hit, cache_source_run_id=源 id, tavily_calls=0, llm_calls=0`);**不写新快照**;**不触发评分**
- `force_refresh=true` 绕过缓存

### 4.5 不触发评分场景

| 场景 | 是否触发 ScoringEngine.compute |
|---|---|
| 缓存命中 | 不触发(快照不变,评分结果必然不变) |
| 全部 4 维度 failed | 触发(走 missing 路径,与 Δ5 占位评分逻辑一致) |
| 部分维度成功 | 触发 |

### 4.6 失败兜底

| 失败类型 | 处理 |
|---|---|
| Tavily 调用失败 | 该维度 status=failed,不落快照,run.dimensions_status 记 failed,继续下一维度 |
| LLM 调用失败 | 重试 1 次后仍失败 → failed |
| LLM 返回非合法 JSON | Schema 校验失败 → failed |
| LLM 返回字段全为 null | status=missing,落 data_source='missing' 快照(raw_data 留应答) |
| 全 4 维度 failed | run.status=failed, error_detail 汇总,评分仍跑(走 missing) |
| 部分维度成功 | run.status=partial_succeeded |

### 4.7 三张审计表的分工

| 表 | 职责 | 一条记录代表 |
|---|---|---|
| `audit_logs` | 操作审计(谁做了什么) | 一次用户/系统操作 |
| `score_audit_log` | 评分变动审计(分数为什么变) | 一次评分相对上次的差异 |
| `credit_data_harvest_run`(本工单新增) | 抓取过程审计(数据从哪来) | 一次抓取任务 |

链路打通:
- 触发 harvest 时,**额外**写一条 `audit_logs`,resource_type='credit_harvest_run', resource_id=run.id, action='trigger', extra={triggered_by, force_refresh}
- 评分完成后写 `score_audit_log`,关联到 score_snapshot
- `score_snapshot.trigger_detail` 落 `{"harvest_run_id": X}` → 评分追溯到抓取批次

### 4.8 trigger_type 枚举沿用

| Δ7 场景 | trigger_type |
|---|---|
| 注册触发抓取后评分 | `REAL_TIME_ONBOARD`(已有) |
| 手动触发抓取后评分 | `MANUAL_RECALC`(已有) |

**不新增枚举值**。

### 4.9 不修改既有评分链路

| 模块 | 改动 |
|---|---|
| `ScoringEngine` | 不动 |
| `evaluators.py` | 不动 |
| `data_source/base.py` | 不动 |
| `MockDataSource` | 不动(其他 8 国仍使用) |
| `QwenChatService.generate()` / `stream_chat()` | 不动 |

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
backend/app/services/llm/base.py                           # LLMService 加 generate_json 抽象方法
backend/app/services/llm/qwen_chat_service.py              # 实现 generate_json
backend/app/services/credit/data_source/registry.py        # KH 路由到 CambodiaDataSource
backend/app/api/v1/auth.py                                 # 注册成功 BackgroundTask 链尾追加 harvest
backend/app/api/v1/credit.py                               # 新增手动 API + 详情接口加 evaluation_status
backend/app/core/config.py                                 # 新增 Tavily / 抓取配置
backend/app/db/models/credit_company_basic_data.py         # 加 raw_data + harvest_run_id
backend/app/db/models/credit_company_certification.py      # 加 raw_data + harvest_run_id
backend/app/db/models/credit_company_finance_data.py       # 加 harvest_run_id
backend/app/db/models/credit_company_legal_data.py         # 加 harvest_run_id
backend/app/db/models/__init__.py                          # 导出 CreditDataHarvestRun
backend/app/services/credit/types.py                       # BasicData 加 raw_data 可选字段
backend/.env.example                                       # 加 TAVILY_API_KEY 等
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
backend/tests/llm/test_qwen_generate_json.py
```

---

## 6. 验收标准

### 6.1 功能验收

| 场景 | 期望 |
|---|---|
| 柬埔寨大型公开企业(如 Kampot Cement)注册 | 维度 1 至少 5/8 字段有值;维度 4 negative_news_level 非 null;维度 2/3 多为 missing |
| 柬埔寨 CSX 上市企业(如 JS Land Plc)注册 | 维度 1/3/4 多字段有值;维度 2 部分识别 |
| 柬埔寨小微企业(注册号正确但网络无信息) | 全维度 missing,run.status=partial_succeeded 或 failed,评分走降级路径 |
| 24h 内重复手动触发(无 force_refresh) | 新 run.status=cached_hit, cache_source_run_id 指向上次,无 Tavily/LLM 调用 |
| 24h 内重复手动触发(force_refresh=true) | 跳过缓存,真实调用,新写快照 + 新评分 |
| Tavily API 返回 0 结果 | 该维度 status=missing |
| LLM 抛错(模拟 timeout) | 该维度 status=failed,继续下一维度 |
| LLM 返回字段无 source_quote | 后处理强制置 null |
| 详情接口在评分进行中查询 | 返回 `evaluation_status='pending'`,前端骨架屏 |
| 非 KH 公司调用 `/harvest` | 返回 400 错误 |
| SUPPLIER 角色调用 `/harvest` | 403(权限点 CREDIT_RECOMPUTE 不持有) |

### 6.2 数据验收

| 表 | 校验 |
|---|---|
| credit_data_harvest_run | 每次触发必有记录;status 枚举正确;dimensions_status 4 维度齐 |
| credit_company_basic_data | raw_data 含 llm_response/evidence/confidence/tavily_results |
| 4 张快照表 | data_source ∈ {public, media, missing};harvest_run_id 指向有效 run |
| score_snapshot | trigger_detail 含 harvest_run_id |
| audit_logs | 触发 harvest 时有一条 resource_type='credit_harvest_run' 记录 |

### 6.3 安全验收

- TAVILY_API_KEY 仅在 env 文件,不进代码库
- 手动 API 必须通过 `CREDIT_RECOMPUTE` 权限校验
- 抓取产生的 raw_data 不含敏感凭证

### 6.4 单测覆盖

- `test_qwen_generate_json.py`:验证 temperature=0 + response_format 正确传入
- `test_cambodia_data_source.py`:与 MockDataSource 行为对齐
- `test_public_web_harvester.py`:mock Tavily + mock LLM,字段映射正确
- `test_harvest_anti_hallucination.py`:缺 evidence 强制 null
- `test_harvest_cache.py`:命中 / force_refresh 绕过
- `test_harvest_task_integration.py`:完整闭环
- `test_harvest_failure_fallback.py`:各类失败状态正确
- `test_evaluation_status_field.py`:三态判定
- `test_manual_harvest_api.py`:权限 + 参数校验 + 非 KH 公司拒绝

---

## 7. 风险与缓解

| 风险 | 严重性 | 缓解 |
|---|---|---|
| LLM 幻觉 | 高 | source_quote 约束 + 后处理 null 化 + raw_data 留存 |
| 搜索命中错公司 | 中 | query 带 registration_no + country_name;prompt 强调"目标公司" |
| Tavily 配额耗尽(1000/月) | 中 | 24h 缓存 + 单家 ≤10 次调用 + 配额监控 |
| qwen-plus Token 消耗 | 中 | 缓存 + search_depth=basic + JSON 强约束减少冗余输出 |
| qwen-plus response_format 兼容性 | 中 | 已确认 DashScope 兼容端点支持;降级方案为 prompt 强约束 |
| 抓取在 demo 现场未完成 | 中 | evaluation_status=pending + 骨架屏;Δ5 占位评分先出 |
| BackgroundTasks 进程内执行 | 中 | MVP 阶段串行可接受;并发高时考虑切 Celery(后续工单) |
| force_refresh 被误用浪费 Token | 低 | 权限点限制;后端可加最小间隔限制(可选) |

---

## 8. 实施前置依赖

- [x] Δ5 已合入(`initialize_credit_for_new_supplier` 已在 auth.py BackgroundTask)
- [x] Tavily 账号已申请,API Key 待注入 demo 环境
- [x] qwen-plus DashScope 账号本地可用
- [ ] 前端柬埔寨注册号正则 bug(`^[A-Z0-9]{10,12}$` → `^[0-9]{6,12}$`)已修(独立小工单)
- [ ] 工作区无未提交改动(切分支前自行确认)

---

## 9. 与后续工单的关系

```
Δ5 (Supplier 注册即评分) ──→ Δ7 (本工单 · 柬埔寨公开数据源)
                                  │
                                  ├──→ T+1 定时刷新 / 规则更新触发重评(独立工单)
                                  ├──→ 商业 API:OpenCorporates / D&B(独立工单)
                                  ├──→ OCR + 用户上传补全(独立工单)
                                  └──→ 其他 8 国(逐国独立工单)
```

---

## 10. v0.2 相对 v0.1 的变更

| # | 变更 | 原因 |
|---|---|---|
| 1 | 手动 API 权限点改为 `Permissions.CREDIT_RECOMPUTE` | v0.1 误写 `credit.operate`,该权限点不存在;现有 `CREDIT_RECOMPUTE` 语义匹配 |
| 2 | trigger_type 沿用 `REAL_TIME_ONBOARD` + `MANUAL_RECALC`,不新增 | v0.1 拟新增 `harvest_refresh`;现有枚举已覆盖语义 |
| 3 | 新增 `LLMService.generate_json()` + `QwenChatService` 实现,补到改动清单 | v0.1 误以为现有 `generate()` 支持 temperature 覆盖与 response_format |
| 4 | 删除"新增依赖 httpx"项 | httpx 已是依赖 |
| 5 | §4.7 明确三张审计表分工 | 评审反馈 harvest_run 与现有审计表职责待澄清 |
| 6 | 触发 harvest 时同步写 `audit_logs` 入口记录 | 让"谁触发了 harvest"在通用审计表中可查 |
| 7 | `score_snapshot.trigger_detail` 落 harvest_run_id | 评分追溯到抓取批次 |

---

*工单 v0.2 定稿。可下发 Claude Code。*
