# Task: 柬埔寨去 Mock 占位评分 + AI 评语按需触发

> 状态:可下发 Claude Code
> 版本:v0.3-Δ8
> 类型:基线之上的行为调整(无新表、无新枚举,部分代码删除 + 部分接口新增)
> 基线:Δ7 v0.3 已实施完成的代码
> 当前分支:沿用 `feat/credit-cambodia-public-harvest` 或新建 `feat/credit-cambodia-no-mock`

---

## 1. 背景

Δ5 / Δ7 阶段为了让评分流程的"骨架"先跑通,所有国家(含柬埔寨)注册后都先写一份 mock 占位评分,柬埔寨之后再追加一次真实抓取并覆盖。

实测后两个问题:

- **柬埔寨场景下,mock 占位与真实抓取并存语义混乱**:列表先看到一个假分,过 30 秒~2 分钟变成真分,运营/采购方易误判
- **AI 评语自动生成消耗 LLM Token 较多**:注册即评分链路里同步触发 AI 评语,在 mock 占位评分上跑一次、真实评分上再跑一次,Token 消耗与 AI 评语实际使用率不匹配

调整方向:

| 维度 | 调整后行为 |
|---|---|
| 柬埔寨 mock 占位评分 | **取消**,不写假数据、不算假分 |
| 柬埔寨真实抓取 | 注册链尾保留,前置守卫调整 |
| 其他 8 国 mock 占位评分 | **保留不变** |
| AI 评语 | **取消自动生成**,改为详情页按钮触发(同步生成,有 loading 态) |

---

## 2. 改动范围

### 2.1 做

| 项 | 说明 |
|---|---|
| **A. 柬埔寨去 mock 占位** | |
| 注册 BackgroundTask 链调整 | `initialize_credit_for_new_supplier` 内对 KH 提前 return,仅建空 `credit_company` 行(无 mock 数据、无 snapshot) |
| `harvest_after_register` 守卫调整 | 删除"必须有 snapshot 才继续"的判断 |
| 已落库的 KH mock 数据清理迁移 | alembic 迁移:删除 KH 国别下所有 `data_source=MOCK` 的 4 张 credit_company_*_data 行 + 对应 mock 来源的 snapshot |
| **B. AI 评语按需触发** | |
| 删除 `registration_hook.py` 中 AI 评语自动生成 | 删除第 132-139 行整段 try/except |
| 删除 `harvest_task.py` 中 AI 评语自动生成 | 删除第 413-422 行整段 try/except + 相关 import |
| 新增 API:POST `/api/v1/credit/companies/{company_id}/ai-summary/generate` | 同步调 `AISummaryGenerator.generate_for_snapshot`,返回生成文本或 null |
| 详情接口 `ai_summary` 字段语义不变 | 仍是"已生成则展示、未生成则返回 null",前端据此判断按钮可见性 |
| **C. 详情页评估状态语义收紧** | |
| `_evaluation_status` 调整 | 柬埔寨场景下"无 snapshot + 无 harvest_run"视为 `pending`(注册刚完成、Task 还没启动);"无 snapshot + 有 RUNNING run"视为 `pending`;"无 snapshot + 有 FAILED run"视为 `failed`;"无 snapshot + 有 SUCCEEDED 但 0 字段命中"视为 `empty`(新增) |
| `evaluation_status` 枚举新增 `empty` | 表示"抓取成功完成但未命中任何数据" |

### 2.2 不做

| 项 | 状态 |
|---|---|
| `credit_company` / `credit_data_harvest_run` 表结构 | 不改 |
| `HarvestRunStatus` 枚举 | 不改(仍是 pending/running/succeeded/partial_succeeded/failed/cached_hit) |
| 其他 8 国注册后行为 | 保留 mock 占位评分 |
| `AISummaryGenerator` 内部逻辑 | 不动(已有的"成功回写、失败返回 None"机制复用) |
| 手动 API `manual_harvest` | 不动(运营重试入口已存在) |
| Tavily search_depth | 不在本工单调整(advanced 升级走单独的小补丁,见 §11) |

---

## 3. 业务流程对照

### 3.1 柬埔寨供应商注册

| 步骤 | 调整前 | 调整后 |
|---|---|---|
| 1. POST /auth/register-supplier 同步返回 | ✅ 不变 | ✅ 不变 |
| 2. Task1: `initialize_credit_for_new_supplier` | 建 credit_company + 写 mock 4 表 + 算 mock 分 + 写 mock snapshot + 调 AI 评语 | **仅建 credit_company(空数据),立即 return** |
| 3. Task2: `harvest_after_register` | 守卫"必须有 snapshot",否则跳过;有则调 `run_harvest_for_company` | **删除守卫**,直接调 `run_harvest_for_company` |
| 4. `run_harvest_for_company` 内部 | 抓数据→落 4 表→算分→写 snapshot→调 AI 评语 | 抓数据→落 4 表→算分→写 snapshot(**删除 AI 评语自动生成**) |
| 5. 评分快照状态 | 先有 mock snapshot,后被真实 snapshot 覆盖(is_current 切换) | **仅有真实 snapshot**(抓取成功时);失败/无数据时 **无 snapshot** |
| 6. AI 评语 | 自动跑两次(mock 一次、真实一次) | **不自动跑,由用户点详情页按钮触发** |

### 3.2 其他 8 国供应商注册

完全不变:仍走 mock 占位评分,Task2 在 `if country_code != "KH": return` 处提前退出。

AI 评语调整对其他 8 国生效:注册不再自动生成 AI 评语,改按需触发。

### 3.3 详情页评估状态

| 后端状态 | 详情接口返回 `evaluation_status` | 前端展示文案 |
|---|---|---|
| KH 注册后 Task2 还没启动 | `pending` | "数据抓取进行中,请稍后刷新" |
| KH harvest_run.status = RUNNING | `pending` | 同上 |
| KH harvest_run.status = SUCCEEDED / PARTIAL_SUCCEEDED / CACHED_HIT 且有 snapshot | `ready` | 正常展示评分 |
| KH harvest_run.status = SUCCEEDED 但无 snapshot 且 dimensions_status 全为 missing | `empty` | "公开数据源未匹配到该企业信息" |
| KH harvest_run.status = FAILED | `failed` | "数据抓取失败,请联系运营手动重试"(运营按钮入口已有) |
| 非 KH | `ready` | 正常展示(mock 评分) |

---

## 4. 代码改动清单

### 4.1 `app/services/credit/registration_hook.py`

**调整 `create_credit_for_supplier`**:

```python
async def create_credit_for_supplier(
    db: AsyncSession,
    supplier_org: SupplierOrganization,
    *,
    target_tier: str | None = None,
    source: str = "supplier_registration",
    run_ai: bool = True,  # ← 保留参数兼容 seed,但内部不再调 AI
) -> CreditCompany | None:
    # 收编/新建 credit_company 逻辑保留

    company = (await db.execute(...)).scalar_one_or_none()
    if company is not None:
        # 收编逻辑保留不变
        ...
    else:
        company = CreditCompany(
            name=supplier_org.name,
            legal_name_en=None,
            country_code=supplier_org.country_code,
            registration_no=supplier_org.registration_no,
            linked_supplier_org_id=supplier_org.id,
            data_status=None,  # KH 不带 expected_grade,非 KH 走下方分支
        )
        db.add(company)
        await db.flush()

    # === Δ8 新增分支 ===
    # 柬埔寨:不写 mock 数据、不算 mock 分,仅保留 credit_company 行,留待 Task2 抓真实数据
    if supplier_org.country_code == "KH":
        logger.info(
            "credit init: KH supplier_org=%s company=%s 跳过 mock 占位,等待 harvest",
            supplier_org.id, company.id,
        )
        return company

    # === 其他 8 国保留原 mock 流程 ===
    bundle = generate_mock_credit_data_for_supplier(supplier_org, target_tier)
    # 注:expected_grade 仅非 KH 场景写入,KH 已在上面 return
    company.data_status = {"expected_grade": bundle.expected_grade}

    _persist_bundle(db, company.id, bundle)
    await db.flush()

    engine = ScoringEngine(MockDataSource())
    snapshot = await engine.compute(...)

    # === Δ8 删除:不再自动生成 AI 评语 ===
    # 原 if run_ai: ... 整段删除

    logger.info(...)
    return company
```

**清理点**:

- `from app.services.credit.ai_summary_generator import AISummaryGenerator` 删除
- `from app.services.llm import LLMUnavailableError, QwenChatService` 删除
- 函数签名 `run_ai` 参数保留(兼容 seed/测试调用方),但函数体内不使用

### 4.2 `app/services/credit/harvester/harvest_task.py`

**调整 `harvest_after_register`**:

```python
async def harvest_after_register(supplier_org_id: int) -> None:
    """注册链尾触发抓取。仅柬埔寨。"""
    try:
        async with AsyncSessionLocal() as db:
            company = (await db.execute(
                select(CreditCompany)
                .where(CreditCompany.linked_supplier_org_id == supplier_org_id)
                .limit(1)
            )).scalar_one_or_none()
            if company is None:
                logger.warning("harvest skip: supplier_org=%s 无 credit_company", supplier_org_id)
                return
            if company.country_code != "KH":
                return

            # === Δ8 删除:不再检查 snapshot 前置存在 ===
            # 原 if has_snap is None: return 整段删除

            await run_harvest_for_company(
                db, company.id, triggered_by=HarvestTriggeredBy.SUPPLIER_REGISTER
            )
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("注册触发抓取失败 supplier_org=%s", supplier_org_id)
```

**调整 `run_harvest_for_company` 末尾**:

```python
# === Δ8 删除:不再自动生成 AI 评语 ===
# 原 try: AISummaryGenerator(...).generate_for_snapshot(...) 整段删除

logger.info(
    "harvest done company=%s run=%s status=%s dims=%s",
    company_id, run.id, run.status, dim_status,
)
return run
```

**清理点**:

- `from app.services.credit.ai_summary_generator import AISummaryGenerator` 删除
- `from app.services.llm import LLMUnavailableError, QwenChatService` 删除(如不再被本文件其他位置使用)
- `from app.core.config import settings` 若仅被 AI 评语用,同步检查并删除

### 4.3 `app/api/v1/credit.py`

**新增 API**:

```python
@router.post(
    "/companies/{company_id}/ai-summary/generate",
    summary="按需触发 AI 评语生成(同步)",
)
async def generate_ai_summary(
    company_id: int = Path(..., ge=1),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """同步生成 AI 评语并写库。前端展示 loading 态,完成后刷新详情。

    - 该公司无 current snapshot → 400 业务错误"评分未就绪,无法生成 AI 评语"
    - 已生成过(snapshot.ai_summary 非空)→ 直接返回已生成的文本,不重复调 LLM
    - LLM 调用失败 → 503 业务错误"AI 评语暂时不可用,请稍后重试"
    """
    company = await _verify_company_access(db, current, company_id)

    snapshot = (await db.execute(
        select(ScoreSnapshot).where(
            ScoreSnapshot.company_id == company.id,
            ScoreSnapshot.is_current.is_(True),
        )
    )).scalar_one_or_none()

    if snapshot is None:
        raise BusinessError(
            http_status=400, biz_code=40001,
            message="评分未就绪,无法生成 AI 评语",
        )

    if snapshot.ai_summary:
        return success({
            "ai_summary": snapshot.ai_summary,
            "generated_at": (
                snapshot.ai_summary_generated_at.isoformat()
                if snapshot.ai_summary_generated_at else None
            ),
            "cached": True,
        })

    text = await AISummaryGenerator(QwenChatService(settings)).generate_for_snapshot(
        db, snapshot.id
    )
    await db.commit()

    if text is None:
        raise BusinessError(
            http_status=503, biz_code=50301,
            message="AI 评语暂时不可用,请稍后重试",
        )

    return success({
        "ai_summary": text,
        "generated_at": (
            snapshot.ai_summary_generated_at.isoformat()
            if snapshot.ai_summary_generated_at else None
        ),
        "cached": False,
    })
```

**写审计**:本接口属于"写操作"(回写 ai_summary),按项目硬约束写 `audit_log`。`action` 建议 `credit.ai_summary.generate`,`resource` 为 `credit_company:{id}`,`status` 区分 `success` / `failed`。重复调用命中 cached 分支也写一条,避免后续追溯缺失。

### 4.4 `app/api/v1/credit.py` 中的 `_evaluation_status`

```python
async def _evaluation_status(
    db: AsyncSession, company: CreditCompany
) -> tuple[str, dict | None]:
    """Δ8:KH 场景下细化状态映射,新增 empty 态。"""
    if company.country_code != "KH":
        return "ready", None

    run = (await db.execute(
        select(CreditDataHarvestRun)
        .where(CreditDataHarvestRun.company_id == company.id)
        .order_by(CreditDataHarvestRun.started_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if run is None:
        return "pending", None  # 注册刚完成,Task 还没启动

    latest = {
        "id": run.id, "status": run.status, "triggered_by": run.triggered_by,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }

    # === Δ8 新增:succeeded 但全维度 missing → empty ===
    if run.status in ("succeeded", "partial_succeeded", "cached_hit"):
        # 看是否有 current snapshot,无则视为 empty
        has_snap = (await db.execute(
            select(ScoreSnapshot.id).where(
                ScoreSnapshot.company_id == company.id,
                ScoreSnapshot.is_current.is_(True),
            )
        )).scalar_one_or_none()
        if has_snap is None:
            return "empty", latest
        return "ready", latest

    if run.status == "failed":
        return "failed", latest
    # pending / running
    return "pending", latest
```

### 4.5 `app/schemas/credit.py`

`evaluation_status` 字段值域文档说明里追加 `empty`(若字段是 str 类型则只需更新注释/示例;若是 Literal/Enum 需扩值)。

### 4.6 数据库迁移

新建 alembic 迁移文件 `20260526_0009_cambodia_drop_mock_credit_data.py`:

```python
"""Drop mock credit data for Cambodia companies (Δ8).

柬埔寨改为不写 mock 占位评分。已存量的 KH mock 数据需清除,
避免列表/详情展示残留假数据。

清理顺序(子→父,避免 FK 约束失败):
1. score_detail(关联 score_snapshot)
2. score_audit_log
3. score_snapshot(KH + trigger_type=INITIAL + 来源是 mock 的)
4. credit_company_basic_data / finance_data / legal_data / certification
   (data_source=MOCK 且 company 是 KH)
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 找出所有 KH credit_company 的 id
    op.execute("""
        CREATE TEMP TABLE _kh_companies AS
        SELECT id FROM credit_company WHERE country_code = 'KH';
    """)

    # 子表先删
    op.execute("""
        DELETE FROM score_detail
        WHERE snapshot_id IN (
            SELECT s.id FROM score_snapshot s
            WHERE s.company_id IN (SELECT id FROM _kh_companies)
              AND s.trigger_type = 'INITIAL'
        );
    """)
    op.execute("""
        DELETE FROM score_audit_log
        WHERE snapshot_id IN (
            SELECT s.id FROM score_snapshot s
            WHERE s.company_id IN (SELECT id FROM _kh_companies)
              AND s.trigger_type = 'INITIAL'
        );
    """)
    op.execute("""
        DELETE FROM score_snapshot
        WHERE company_id IN (SELECT id FROM _kh_companies)
          AND trigger_type = 'INITIAL';
    """)
    # 4 张数据表删 mock 来源
    for tbl in (
        "credit_company_basic_data",
        "credit_company_finance_data",
        "credit_company_legal_data",
        "credit_company_certification",
    ):
        op.execute(f"""
            DELETE FROM {tbl}
            WHERE company_id IN (SELECT id FROM _kh_companies)
              AND data_source = 'MOCK';
        """)

    op.execute("DROP TABLE _kh_companies;")


def downgrade() -> None:
    # 不可逆(mock 数据本就是生成出来的,无业务价值)
    pass
```

注意点:

- 实施时先在本地用 `alembic upgrade head` 跑通,不要直接上生产
- 表名/字段名以实际 schema 为准(若有偏差按本地实际改)
- `data_source` 枚举字面量(MOCK / PUBLIC_WEB)按实际枚举类的 value 字段填

### 4.7 已实施测试调整

修改影响以下测试,需同步更新:

| 测试文件 | 影响点 |
|---|---|
| `tests/test_harvest_task_integration.py` | 删去"前置 mock snapshot"的 setup,改为只建 credit_company |
| `tests/test_harvest_failure_fallback.py` | 同上,失败场景下断言 snapshot 为 None |
| `tests/test_register_buyer_usc.py` 等涉及 KH 注册的 | 断言"KH 注册后 credit_company 存在但 snapshot 不存在(在 harvest 跑完前)" |

### 4.8 新增测试

| 测试文件 | 用例 |
|---|---|
| `tests/test_cambodia_no_mock.py`(新建) | KH 注册后 credit_company 已建、4 张数据表无 MOCK 行、无 snapshot |
| `tests/test_ai_summary_api.py`(新建) | 1) 无 snapshot → 400;2) 已生成 → cached=true 不调 LLM;3) 未生成 → 调 LLM 并回写;4) LLM 失败 → 503 |
| `tests/test_evaluation_status.py`(新建或扩展) | 5 种状态映射断言:无 run → pending,RUNNING → pending,SUCCEEDED+snapshot → ready,SUCCEEDED+无 snapshot → empty,FAILED → failed |

### 4.9 前端改动(参考说明,不强制)

前端不在本工单实施范围(本工单仅后端 + DB),但需要前端对齐如下接口契约,避免上线后阻塞:

- 详情接口 `evaluation_status` 字段新增 `empty` 值,需要新加文案"公开数据源未匹配到该企业信息"
- AI 评语按钮的可见性:`snapshot != null && ai_summary == null` → 显示"生成 AI 评语"按钮;`ai_summary != null` → 直接展示文本,无按钮
- 按钮点击 → POST `/companies/{id}/ai-summary/generate` → loading 态(预计 5-15 秒)→ 刷新详情或就地渲染
- 503 → 提示"AI 评语暂时不可用,请稍后重试"
- 400(评分未就绪)→ 按钮不应被点击,前端做防御

---

## 5. 配置项

无新增。

---

## 6. 数据契约

无新增字段。`evaluation_status` 字段值域扩展(从 4 值 → 5 值)。

---

## 7. 验收点

| # | 项 | 期望 |
|---|---|---|
| 1 | KH 供应商注册 | 同步返回 200;数据库 credit_company 已建、4 张数据表无 mock 行、score_snapshot 无行 |
| 2 | KH 抓取完成且命中数据 | snapshot 已建,evaluation_status=ready |
| 3 | KH 抓取完成但 0 字段 | 无 snapshot,evaluation_status=empty |
| 4 | KH 抓取失败 | 无 snapshot,evaluation_status=failed |
| 5 | KH 抓取进行中 | 无 snapshot,evaluation_status=pending,latest_harvest_run.status=running |
| 6 | 其他 8 国供应商注册 | 与改动前一致:mock 占位评分立即生成,evaluation_status=ready |
| 7 | AI 评语按钮点击(snapshot 存在,首次) | 同步调 LLM,生成后回写,返回 cached=false |
| 8 | AI 评语按钮点击(已生成过) | 直接返回 cached=true,不调 LLM |
| 9 | AI 评语点击(无 snapshot) | 400 业务错误 |
| 10 | AI 评语点击(LLM 失败) | 503 业务错误 |
| 11 | 注册流程整体耗时(KH) | 与改动前持平或更快(去掉 mock 生成步骤) |
| 12 | alembic 迁移可重放 | 本地 reset_db + 重新 upgrade head 不报错 |

---

## 8. 实施顺序

1. 后端代码改动(registration_hook / harvest_task / credit API / schemas)
2. alembic 迁移
3. 现有测试调整 + 新增测试
4. 本地 reset_db + 跑 verify.sh + 注册 1 个 KH + 1 个其他国别供应商,人工核验数据库与详情接口
5. 提交 PR

---

## 9. 风险与处理

| 风险 | 处理 |
|---|---|
| AI 评语接口同步调 LLM,响应时间 5-15 秒,可能超 nginx 默认超时 | 部署时确认 nginx / uvicorn 超时配置 ≥ 30 秒;接口本身设 25 秒 timeout |
| AI 评语接口被刷(用户连点多次)| 已通过 `if snapshot.ai_summary: return cached` 防御;若需限频,后续在 rate_limit.py 加策略,不在本工单范围 |
| 历史 KH 数据迁移可能存在脏数据 | 迁移前在 staging 上 dry-run;若生产已有真实评分快照(非 mock),迁移条件 `trigger_type='INITIAL' AND data_source='MOCK'` 不会误删 |
| 老的 seed 脚本 `seed_credit.py` 仍可能为 KH 生成 mock | 同步检查 `seed_credit.py`,若有 KH mock 生成逻辑,加 `country_code != 'KH'` 跳过条件 |

---

## 10. 范围之外

| 项 | 说明 |
|---|---|
| AI 评语生成的限频 / 计费追溯 | 后续工单 |
| AI 评语支持手动重新生成(覆盖现有) | 后续工单 |
| KH harvest 失败后的自动重试 | 后续工单(目前依赖运营手动触发 manual_harvest) |
| Tavily search_depth basic → advanced | 后续小补丁(本工单不耦合) |
| 前端实施 | 后续前端工单 |

---

## 11. 备注

- Tavily search_depth 升级到 advanced 的小补丁,与本工单解耦,可单独提一个 2 行改动的 PR
- 本工单不引入新依赖、不改硬约束、不破坏 RBAC scope 模型
