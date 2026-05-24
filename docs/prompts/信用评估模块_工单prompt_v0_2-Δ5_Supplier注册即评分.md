# Task: Supplier 注册即评分闭环 · 增量工单 prompt v0.2-Δ5

> 状态:可下发 Claude Code
> 日期:2026-05-23
> 类型:**增量功能扩展**,信用评估模块产品定位变更后的实施
> 关联文档:
> - 上一轮工单:`docs/prompts/信用评估模块_工单prompt_v0_2-Δ4_RBAC_scope接入.md`(已合入)
> - 技术方案:`docs/architecture/信用评估模块技术方案设计-v0_2.md`(本工单完成后另行升 v0.3,本工单不修文档)
> - PRD:`docs/prd/信用评估模块 PRD v0.3_四维评分模型版.md.docx`
> 当前分支:`feat/credit-supplier-register-scoring`(基于 main 切出)

---

## 1. 任务上下文

### 1.1 信用评估模块定位变更(关键)

旧定位:海外工程领域企查查,评估对象 = 任意目标公司(可平台外)。

**新定位**:**评估对象 = 平台已注册 Supplier**,不再支持评估"平台外目标公司"。

定位变更触发的核心实施:

1. Supplier 注册成功后,系统**异步自动生成一份评分**(本期用 mock 数据填充,等真实数据源接入后替换)
2. BUYER / OPERATOR 在信用评估页搜索时,只能看到平台已注册 Supplier
3. 现有 4 家 demo "平台外公司"需要改造为"已注册 Supplier"

### 1.2 当前代码状态

v0.2-Δ4 已合入:
- 信用评估模块完整功能已就绪(评分引擎、规则、AI 评价、AI 对话、详情页)
- RBAC scope 机制已落地
- SUPPLIER / ADMIN 均不持有 credit 权限点
- 4 家 demo 数据当前是"平台外公司"形态(`credit_company.linked_supplier_org_id` 全为 NULL)

### 1.3 本次任务目标

实施 Supplier "注册即评分"闭环,使产品定位变更落地。包含:

1. seed 改造(展示用)
2. 注册流程注入异步评分(现场注册演示用)
3. 搜索接口对齐新定位
4. 简化版 mock 数据生成器

### 1.4 阅读顺序

1. 本工单 §3 实现步骤
2. 现有 seed 代码(`backend/app/seed.py`)中信用评估部分,了解当前 4 家 demo 数据结构
3. 现有 supplier_organizations 注册接口与状态机
4. 现有 ScoringEngine 入口(`backend/app/services/credit/scoring_engine.py`)

---

## 2. 范围

**做**:

- seed 改造:删除 4 家"平台外公司",新建 4 家"已注册 demo Supplier" + 关联 credit_company 镜像 + mock 数据 + 评分快照 + AI 评价
- 注册流程注入:Supplier 注册成功的代码路径中,通过 FastAPI BackgroundTasks 触发异步评分初始化
- mock 数据生成器:简化版工具函数,按 supplier_org.id 决定档位(A/B/C/D 循环)
- 搜索接口改造:`GET /credit/companies/search` 改为 JOIN supplier_organizations,只返已注册 Supplier 范围内的结果
- 异步任务的异常容错与详情页降级展示

**不做**:

- 不修改 credit_company 表约束(`linked_supplier_org_id` 保持 nullable=True,UNIQUE 也不加;新数据写入由业务层保证 1:1 关联。表约束加固作为独立后续工单 Δ6 处理)
- 不引入 Celery / RQ 等任务队列(FastAPI BackgroundTasks 进程内执行已够 MVP)
- 不实施"按 Supplier 审批状态过滤"(本期 BUYER/OPERATOR 能看到所有 Supplier 评分,不区分 DRAFT/APPROVED;状态过滤作为 TODO)
- 不删除 `ensure_company_scored` stub(残留代码不影响功能,后续清理)
- 不更新技术方案文档(本期工单跑完后,另行升技术方案 v0.3 时统一更新)
- 不动 RBAC、不动 AI 服务、不动评分引擎与规则
- 不实施 SUPPLIER 自己看评分

---

## 3. 实现步骤

### Step 1:Mock 数据生成器

新建 `backend/app/services/credit/mock_data_generator.py`,提供 `generate_mock_credit_data_for_supplier(supplier_org)` 工具函数:

**职责**:基于 supplier_organizations 实例,生成一套"合理的 mock 信用数据",含 basic_data、finance_data、legal_data、certifications 四类。

**档位策略**:按 `supplier_org.id % 4` 循环出现 A/B/C/D 四档:

| id % 4 | 预期等级 | mock 数据特征 |
|---|---|---|
| 0 | A | 工商完整 / 多张有效证书 / 营收增长 / 无诉讼 / 现金流正 / 无负面 |
| 1 | B | 工商完整 / 1-2 张证书 / 营收波动盈利 / 少量已结诉讼 / 现金流为负但融资正常 / 偶发负面已澄清 |
| 2 | C | 缺 1 项工商字段 / 1 张证书 / 亏损 / 5-20 起诉讼 / 持续负现金流 / 持续负面 |
| 3 | D | 缺 2 项工商字段 / 证书过期 / **失信被执行未结案 >0**(触发维度4 一票否决)/ 负面舆情 |

**注意事项**:

- mock 数据的 `company_id` 字段用调用方传入的 `credit_company.id`,不在生成器里查
- 数据生成器**只负责返回数据结构**,不写库;由调用方落库
- mock 数据的 `data_source` 字段填 `'mock'`
- 等级仅是预期,实际评分由 ScoringEngine 跑出来确定;只需保证 mock 数据触发的子项规则与预期档位大致对齐

**示例签名**:

```python
@dataclass
class MockCreditDataBundle:
    basic_data: dict   # 用于建 credit_company_basic_data
    finance_data: dict
    legal_data: dict
    certifications: list[dict]

def generate_mock_credit_data_for_supplier(supplier_org: SupplierOrganization) -> MockCreditDataBundle:
    ...
```

### Step 2:Seed 改造

改造 `backend/app/seed.py` 中信用评估相关 seed 函数:

**删除**:原 4 家"平台外公司"的 seed 代码段(原沙特/印尼/巴基斯坦/摩洛哥)。

**新增**:4 家"已注册 demo Supplier"。每家执行以下步骤:

1. 在 supplier_organizations 表 seed 一条 Supplier 记录(name / country_code / registration_no / status='APPROVED')。如对应账号已存在(通过 username 或 email 判断),复用,不重复创建
2. 在 credit_company 表建一条镜像,linked_supplier_org_id = supplier_org.id,name / country_code / registration_no 与 supplier_org 一致
3. 调 `generate_mock_credit_data_for_supplier(supplier_org)` 拿到 mock 数据
4. 写入 credit_company_basic_data / finance_data / legal_data / certifications 四张表
5. 调 `ScoringEngine.compute(company_id, trigger_type='INITIAL', trigger_detail={'source': 'seed'})`,生成 score_snapshot + score_detail + score_audit_log
6. 调 `AISummaryGenerator.generate()` 生成 ai_summary 并回写到 snapshot(若 DashScope API Key 未配置,跳过 AI 生成,ai_summary 保持 NULL,不阻断 seed)

**4 家 demo Supplier**:

| supplier_org_id | name | country | 预期档位 |
|---|---|---|---|
| (自增 1) | Al-Rashid Industrial Co. | SA | A |
| (自增 2) | PT Cahaya Sentosa | ID | B |
| (自增 3) | Karachi Steel Works Ltd. | PK | C |
| (自增 4) | Atlas Construction SARL | MA | D |

注意 `id % 4` 顺序与档位的对应——如果 supplier_organizations 表已存在其他 seed 数据(如 demo 用户),需要让这 4 家的 id 满足"% 4 = 0/1/2/3"或调整生成器档位逻辑使之对齐。**简单方案**:不依赖 id 取模,直接在 seed 中给每家指定档位参数,改 `generate_mock_credit_data_for_supplier(supplier_org, target_tier='A')` 签名。

**Seed 幂等**:每步先检查目标记录是否存在,存在则跳过,不存在则创建。

### Step 3:注册流程注入异步评分

定位现有 Supplier 注册接口(可能位于 `backend/app/api/v1/supplier_registration.py` 或类似路径),在注册成功的代码路径中注入异步任务:

```python
@router.post("/suppliers/register")
async def register_supplier(
    data: SupplierRegistrationIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # 原有注册逻辑(写 supplier_organizations、用户、审计日志等)
    supplier_org = await create_supplier_organization(db, data)
    await db.commit()
    
    # 注入异步评分初始化
    background_tasks.add_task(
        initialize_credit_for_new_supplier,
        supplier_org_id=supplier_org.id,
    )
    
    # 返回原有 success response
    return SuccessResponse(supplier_org)
```

**异步任务函数** `initialize_credit_for_new_supplier` 新建于 `backend/app/services/credit/registration_hook.py`:

```python
async def initialize_credit_for_new_supplier(supplier_org_id: int):
    """
    异步任务:新 Supplier 注册成功后,自动生成信用评分。
    使用独立 DB session,失败不影响注册本身。
    """
    try:
        async with async_session_factory() as db:
            # 1. 加载 supplier_org
            supplier_org = await db.get(SupplierOrganization, supplier_org_id)
            if supplier_org is None:
                logger.warning(f"Supplier {supplier_org_id} not found for credit init")
                return
            
            # 2. 幂等:如 credit_company 镜像已存在,跳过
            existing = await db.execute(
                select(CreditCompany).where(
                    CreditCompany.linked_supplier_org_id == supplier_org_id
                )
            )
            if existing.scalar_one_or_none() is not None:
                logger.info(f"Credit company for supplier {supplier_org_id} already exists, skip")
                return
            
            # 3. 建 credit_company 镜像
            credit_company = CreditCompany(
                name=supplier_org.name,
                country_code=supplier_org.country_code,
                registration_no=supplier_org.registration_no,
                linked_supplier_org_id=supplier_org_id,
            )
            db.add(credit_company)
            await db.flush()  # 拿到 credit_company.id
            
            # 4. 生成 mock 数据并落库
            mock_bundle = generate_mock_credit_data_for_supplier(supplier_org)
            # 写入四张数据表,company_id = credit_company.id
            ...
            
            # 5. 调 ScoringEngine
            await scoring_engine.compute(
                company_id=credit_company.id,
                trigger_type='INITIAL',
                trigger_detail={'source': 'supplier_registration'},
            )
            
            # 6. 调 AISummaryGenerator(失败不抛)
            try:
                await ai_summary_generator.generate(credit_company.id)
            except LLMUnavailableError:
                logger.info(f"AI summary skipped for supplier {supplier_org_id}, LLM unavailable")
            
            await db.commit()
            logger.info(f"Credit initialized for supplier {supplier_org_id}")
    
    except Exception as e:
        logger.exception(f"Credit init failed for supplier {supplier_org_id}: {e}")
        # 不抛异常——异步任务失败不影响注册主流程
```

**关键约束**:

- 异步任务**用独立 DB session**(不复用注册请求的 session),避免事务边界混乱
- 失败时**只记日志,不抛异常**,保证注册请求始终成功
- 失败的 Supplier 可后续通过 `POST /credit/companies/{id}/recompute` 手动补救(但需要先有 credit_company 镜像;如镜像都没建成,需要 OPERATOR 走管理界面或脚本补建——本期不实现该补救工具,作为已知限制)

### Step 4:搜索接口改造

`GET /credit/companies/search` 改为 INNER JOIN supplier_organizations:

```python
@router.get("/companies/search")
async def search_companies(
    country: str | None = None,
    q: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_permission(user, "credit:read")
    scope = get_scope(user, "credit:read")
    
    # INNER JOIN 保证只返回有 supplier_organizations 关联的 credit_company
    query = (
        select(CreditCompany, ScoreSnapshot)
        .join(
            SupplierOrganization,
            CreditCompany.linked_supplier_org_id == SupplierOrganization.id,
            isouter=False,  # INNER JOIN
        )
        .outerjoin(
            ScoreSnapshot,
            (ScoreSnapshot.company_id == CreditCompany.id) & (ScoreSnapshot.is_current == True)
        )
    )
    
    if country:
        query = query.where(CreditCompany.country_code == country)
    if q:
        # 模糊匹配 name 或 registration_no
        query = query.where(
            or_(
                CreditCompany.name.ilike(f'%{q}%'),
                CreditCompany.registration_no.ilike(f'%{q}%'),
            )
        )
    
    # scope=ALL 不加额外条件;scope=OWN 不存在(因为 SUPPLIER 已无 credit:read)
    
    query = query.limit(20)
    # 装配返回结构(含分数与等级)
    ...
```

**响应字段**:每条返回 `{ id, name, country_code, registration_no, current_score, grade }`,grade 在 score_snapshot 为 NULL 时(异步评分未完成)返回 `null` 或字符串 `"PENDING"`。前端据此显示"评分生成中"或"暂无评分"。

### Step 5:详情接口的优雅降级

`GET /credit/companies/{id}`:

如果 credit_company 存在但 score_snapshot 为 NULL(异步评分尚未完成或失败),接口仍正常返回 credit_company 基础信息,score 部分返回 null,前端展示"评分生成中,请稍后刷新"。

### Step 6:Demo 验证场景

启动后:

1. 自动 seed 4 家 demo Supplier,每家立即有完整评分(因 seed 是同步执行 ScoringEngine,不走 BackgroundTasks)
2. BUYER 登录 → 搜索"沙特",返回 Al-Rashid Industrial(A 级);搜索"印尼"返回 PT Cahaya Sentosa(B 级)等等
3. OPERATOR 登录 → 同上
4. **现场注册新 Supplier**:用注册接口(API 或前端表单)创建一家新公司,几秒后(异步任务完成)用 BUYER 账号搜索能看到这家,并有完整评分

---

## 4. 验收标准

### 后端

- `uv run alembic upgrade head` 无新增迁移(本期不动表结构)
- `uv run uvicorn app.main:app` 启动成功,seed 完成日志输出 "4 家 demo Supplier credit 初始化完成"
- 数据库:`supplier_organizations` 表至少有 4 家 demo Supplier;`credit_company` 表每家对应一条镜像,`linked_supplier_org_id` 非空且唯一
- 4 家 demo Supplier 的 grade 分布:A=1 / B=1 / C=1 / D=1
- D 档 Supplier(Atlas Construction)`dimension_overrides` 数组非空,触发 `DIM4_UNRESOLVED_DEFAULTER`

### 接口

- `GET /credit/companies/search?country=SA&q=`(BUYER 调用)→ 返回 Al-Rashid Industrial 一条,带 grade='A'
- `GET /credit/companies/search?q=Al`(BUYER 调用)→ 返回 Al-Rashid Industrial 一条
- `GET /credit/companies/{atlas_id}` → 返回完整数据,dimension_overrides 含失信触发记录
- **现场注册新 Supplier 测试**:用 supplier 注册接口创建新公司,等 5-10 秒,再调 search 能搜到这家,grade 非空

### 前端

- BUYER / OPERATOR 信用评估页搜索功能正常,4 家 demo 数据可见
- 列表项展示 grade 徽章颜色(A 绿 / B 黄 / C 橙 / D 红)
- 详情页正常展示评分快照、雷达图、明细表、AI 评价(如 DashScope API Key 未配置,AI 评价区显示占位文案)
- 如某 Supplier 评分快照为 NULL(异步任务失败 / 进行中),列表展示"评分生成中"或灰色徽章,详情页降级展示

### 代码

- `pnpm tsc --noEmit` + `pnpm build` 通过
- 后端 `uv run pytest` 通过(如有相关单测,补充 BackgroundTasks 调用路径单测)
- BackgroundTasks 注入位置代码注释清晰,提到"异步评分初始化"
- mock 数据生成器代码内加注释:`# TODO(T-2): 本生成器在真实数据源接入后弃用`

---

## 5. 严格不做的事

1. 不修改 credit_company 表约束(NOT NULL / UNIQUE 等)
2. 不引入 Celery / RQ / APScheduler 等新组件
3. 不实施 SUPPLIER 看自己评分的功能
4. 不修改 RBAC 配置(ADMIN / SUPPLIER 仍不持有 credit 权限点)
5. 不修改 ScoringEngine 内部逻辑(只调用,不重构)
6. 不修改前端任何已有 UI 元素(仅"评分生成中"占位为新增,严格小灰字,不加图标/卡片/警示色)
7. 不实施按 Supplier 审批状态过滤(本期 BUYER/OPERATOR 能看到所有状态的 Supplier;状态过滤作为 TODO 记录)
8. 不修改 PRD / 不更新技术方案文档(本期工单后另行升技术方案 v0.3 统一更新)
9. 不实施"批量为已存在 Supplier 补建评分"功能(本期只针对新注册触发;现有 seed 阶段的 4 家 demo 直接 seed,不走 BackgroundTasks)

如遇方案未覆盖的细节,选最简实现 + 代码标注 `TODO: 方案未覆盖,采用最简实现`,**不自行扩展功能**。

---

## 6. 提交规范

- commit message:`Ref: docs/prompts/信用评估模块_工单prompt_v0_2-Δ5_Supplier注册即评分.md`
- 性质标注:`feat(credit): supplier registration triggers async credit scoring`

---

*工单 v0.2-Δ5(增量) · 基线 v0.2-Δ4 · 信用评估模块定位变更落地 · 注册即评分异步闭环*
