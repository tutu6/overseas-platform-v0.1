# Task: 信用评估模块 RBAC scope 接入 · 工单 prompt v0.3

> 状态:可下发 Claude Code
> 日期:2026-05-23
> 类型:基于现有已实现代码,为信用评估模块接入 RBAC 规范要求的 scope 数据范围控制
> 关联文档:
> - 技术方案:`docs/architecture/信用评估模块技术方案设计-v0_2.md`(§六 RBAC 已更新)
> - RBAC 规范:`docs/architecture/RBAC设计规范_v1_0.md`(§8 数据权限设计原则,**必读**)
> - PRD:`docs/prd/信用评估模块 PRD v0.1.md` §8.1 隔离规则
> 当前分支:`feat/credit-rbac-scope`(基于 main 切出)

---

## 1. 任务上下文

### 1.1 当前代码状态

信用评估模块功能完整。RBAC 层面当前实施情况:

- `credit:read` / `credit:write` / `credit:recompute` 三个权限点已落库
- **SUPPLIER 角色被授予了 `credit:read`**(技术方案早期版本如此规定)
- **接口层无任何 scope 数据范围过滤**——任何拥有 `credit:read` 的用户都能看到全部 credit_company 数据

### 1.2 问题

PRD v0.1 §8.1 明确规定:

> 供应商只能查看**本企业**的信用得分与报告,绝对不可查看平台内其他供应商的分数。

当前实现违反这条规则——SUPPLIER 登录后可以看到所有平台数据,包括其他公司的评分。

### 1.3 本次任务目标

按照 `RBAC设计规范_v1_0.md` §8 的"权限点 + scope 两层独立"模型,为信用评估模块接入 scope 数据范围控制。完成后:

- BUYER / OPERATOR:scope=ALL,行为不变
- ADMIN:按 RBAC 规范 §4.3 + §8.6 职责分离原则,**不持有任何 credit 权限点**,接口层在 require_permission 阶段被 403 拦截
- SUPPLIER:scope=OWN,只能看 `credit_company.linked_supplier_org_id = 自身 supplier_org_id` 的数据
- 由于本期 `credit_company` 表无 SUPPLIER 镜像数据,SUPPLIER 实际看到的数据为空(列表空 / 详情 404)

### 1.4 阅读顺序

1. **`docs/architecture/RBAC设计规范_v1_0.md` §8 整章**——必读,本工单严格遵循该规范
2. 本工单 §3 实现步骤
3. 技术方案 §六(已更新为 scope 模型)
4. PRD v0.1 §8.1

---

## 2. 范围

**做**:

- 在 RBAC 配置中将 SUPPLIER 角色的 `credit:read` scope 设为 OWN(其他角色 ALL)
- 在统一的 scope 决策函数中加入信用评估模块的映射
- 改造 4 个查询类接口,加 scope 过滤
- 编写 / 复用 "取 user 的 supplier_org_id" 工具函数

**不做**:

- 不实施"SUPPLIER 注册→建 credit_company 镜像→触发首次评分"链路(产品决策未定,见技术方案 §10.6)
- 不改前端任何 UI(SUPPLIER 登录后看到空列表是预期结果,不展示"无数据"以外的提示)
- 不动 credit_company / 评分引擎 / AI 服务
- 不删除 SUPPLIER 的 `credit:read` 权限(scope=OWN 已足够隔离)
- 不修改 BUYER / OPERATOR 已有行为
- 不让 ADMIN 持有任何 credit 权限点(职责分离原则)

---

## 3. 实现步骤

### Step 1:确认 / 实现统一 scope 决策函数

按 RBAC 规范 §8.5.3,scope 由后端服务层统一查表函数决策。

检查仓库现有实现:

- 如已存在 `get_scope(user, permission_code) -> str` 或类似函数 → 复用,跳到 Step 2
- 如不存在 → 在 `app/rbac/scope.py` 新建该函数

函数签名与行为:

```python
def get_scope(user: User, permission_code: str) -> str:
    """
    返回当前 user 对该权限点的数据范围。
    返回值:'ALL' | 'ORG' | 'OWN' | 'NONE'
    若 user 未持有该权限点,返回 'NONE'(理论不会被调用方使用,因为已被 require_permission 拦截)。
    """
```

实现形式严格按规范 §8.5.6:**静态映射表 + if/else,不是策略引擎**。

### Step 2:配置信用评估模块的 scope 映射

在 scope 映射配置(同 `permissions_config.py` 同级或同位置)中,加入信用评估模块的映射:

| 角色 | credit:read | credit:write | credit:recompute |
|---|---|---|---|
| BUYER | ALL | — | — |
| OPERATOR | ALL | ALL | ALL |
| ADMIN | — | — | — |
| SUPPLIER | OWN | — | — |

**ADMIN 不持有任何 credit 权限点**——按 RBAC 规范 §4.3 业务管理 vs 系统管理职责分离 + §8.6 系统管理角色不进入数据权限矩阵。**实施时严格按仓库已有 scope 配置文件的格式,不另起一套**。

### Step 3:编写 / 复用 "取 user 的 supplier_org_id" 工具函数

新增工具函数(位置建议:`app/services/rbac/membership.py` 或仓库已有的同类工具文件):

```python
async def get_user_supplier_org_id(user: User) -> int | None:
    """
    取当前 user 所属的 supplier_organizations.id。
    通过 Membership 表查询 user_id → organization_id,组织类型为 SupplierOrg。
    若 user 未关联任何 SupplierOrg,返回 None。
    """
```

如仓库已有该函数(或类似名称如 `get_supplier_org_by_user`)直接复用,不重写。

### Step 4:改造 `GET /credit/companies/search` 加 scope 过滤

`backend/app/api/v1/credit.py`(或对应文件)的搜索接口:

```python
@router.get("/companies/search")
async def search_companies(
    country: str,
    q: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_permission(user, "credit:read")
    scope = get_scope(user, "credit:read")
    
    query = select(CreditCompany).where(
        CreditCompany.country_code == country,
        # 原有模糊查询条件
    )
    
    if scope == "OWN":
        supplier_org_id = await get_user_supplier_org_id(user)
        if supplier_org_id is None:
            return []  # user 未关联 SupplierOrg,直接返回空
        query = query.where(CreditCompany.linked_supplier_org_id == supplier_org_id)
    # scope == "ALL" 时不加额外条件
    
    # 后续 LIMIT 20 + 装配评分数据等逻辑保持不变
```

### Step 5:改造 `GET /credit/companies/{id}` 加 scope 过滤

详情接口按规范 §8.3:**未命中返回 404,不暴露存在性**。

```python
@router.get("/companies/{company_id}")
async def get_company_detail(
    company_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_permission(user, "credit:read")
    scope = get_scope(user, "credit:read")
    
    company = await db.get(CreditCompany, company_id)
    if company is None:
        raise NotFound("企业不存在")
    
    if scope == "OWN":
        supplier_org_id = await get_user_supplier_org_id(user)
        if supplier_org_id is None or company.linked_supplier_org_id != supplier_org_id:
            raise NotFound("企业不存在")  # 注意:文案与"真正不存在"一致,不暴露存在性
    
    # 后续装配 snapshot / detail / certifications / ai_summary 等逻辑保持不变
```

### Step 6:改造 AI 对话相关接口加 scope 过滤

`POST /credit/ai/conversations`、`POST /credit/ai/conversations/{id}/messages`、`GET /credit/ai/conversations/{id}` 三个接口。

逻辑:对话关联 company_id,如 scope=OWN 且 company 不属于该 user 的 SupplierOrg → 404。

实现思路:在每个接口入口加同样的 scope 检查,或抽取一个 `verify_company_access(user, company_id)` 工具函数复用。

### Step 7:`GET /credit/search-history` 与 `DELETE /credit/search-history/{id}`

历史搜索记录的 scope 处理:

- 这两个接口的 scope 永远是 OWN(任何角色都只看自己的搜索历史),由 user_id 过滤
- 与本次 credit:read scope 机制**独立**——历史搜索是基于 user_id 自然隔离,无需走 scope 决策函数
- 接口实现保持现状即可,本次不动

### Step 8:重算类接口无 scope 改造

`POST /credit/companies/{id}/recompute` 与 `POST /credit/recompute-all`:

- 这两个接口要求 `credit:recompute` 权限点
- SUPPLIER 无 `credit:recompute`,在 require_permission 阶段已被 403 拦截
- 因此**无需加 scope 过滤**,保持现状

### Step 9:验证 demo 数据

启动后:

- 使用 BUYER demo 账号登录 → 信用评估页能搜到 4 家 demo 企业,详情正常
- 使用 OPERATOR demo 账号登录 → 同上
- 使用 SUPPLIER demo 账号登录(若 seed 中有,如 supplier-cn-001 之类):
  - 进入 `/credit` 页面正常,可以搜索
  - 搜索结果为空(因为 4 家 demo 企业的 `linked_supplier_org_id` 全部为 NULL)
  - 尝试直接访问 `/credit/companies/1` 等任意 id → 404

### Step 10:权限同步执行

按 RBAC 规范 §9,角色-权限关联的可信源是配置文件,启动时自动同步到数据库。

确保:

- 本次新增的 scope 映射通过启动同步函数生效
- 数据库 `role_permissions` 表(或同类表)内容与配置文件一致
- 启动日志中能看到同步过程(已有日志格式)

---

## 4. 验收标准

### 后端

- `cd backend && uv run uvicorn app.main:app` 启动成功,权限同步完成
- `get_scope(user, 'credit:read')`:
  - BUYER 用户返回 `'ALL'`
  - OPERATOR 用户返回 `'ALL'`
  - ADMIN 用户返回 `'NONE'`(或调用方在 require_permission 阶段已被 403 拦截,理论不会走到 get_scope)
  - SUPPLIER 用户返回 `'OWN'`
- BUYER 调 `GET /credit/companies/search?country=SA&q=`:返回沙特 Al-Rashid 一条
- ADMIN 调相同接口:返回 **403**(无 credit:read 权限)
- SUPPLIER 调相同接口:返回空数组
- SUPPLIER 调 `GET /credit/companies/1`(假设 id=1 是平台外目标公司):返回 404
- ADMIN 调相同接口:返回 **403**
- SUPPLIER 调 `POST /credit/companies/1/recompute`:返回 403
- ADMIN 调相同接口:返回 **403**
- SUPPLIER 调 `POST /credit/ai/conversations`(body 含 company_id=1):返回 404

### 前端

- BUYER / OPERATOR 登录后,信用评估页面行为与现状完全一致
- ADMIN 登录后,信用评估菜单**不可见**,直接访问 `/credit` URL 跳转到无权限页或登录页(按现有"无权限"处理逻辑)
- SUPPLIER 登录后:
  - 信用评估菜单可见(SUPPLIER 拥有 credit:read)
  - 进入 `/credit` 页面正常加载,无 403 错误
  - 搜索任何国别+关键词,结果列表为空
  - 不展示额外的"功能未上线"提示——按规范"假装不存在"

### 文档与代码

- `pnpm tsc --noEmit` + `pnpm build` 通过
- 后端 `uv run pytest` 通过(如涉及 RBAC 单测,补充 SUPPLIER scope 路径的单测)
- scope 映射配置易读,新增条目与现有条目格式一致

---

## 5. 严格不做的事

1. 不实施 SUPPLIER 评分镜像逻辑(注册时不建 credit_company 镜像,不触发评分)
2. 不在前端添加"功能未上线""敬请期待"等提示文案——按规范 §8.3"假装不存在"
3. 不删除 SUPPLIER 的 `credit:read` 权限点(scope=OWN 已实现隔离)
4. **不创建新的权限点**(如 `credit:read:own`)——禁止 scope 进权限点 code(规范 §8.5.1)
5. 不修改 BUYER / OPERATOR 任何已有行为
6. **不给 ADMIN 授予任何 credit 权限点**——按 RBAC 规范 §4.3 + §8.6 职责分离
7. 不实施"用户可见字段过滤""AI 评价对 SUPPLIER 脱敏"等产品政策内容
8. 不动 credit_company 表结构与现有数据

---

## 6. 提交规范

- commit message:`Ref: docs/prompts/信用评估模块_工单prompt_v0_3_RBAC调整.md`
- 性质标注:`feat(credit): apply rbac scope filtering for credit module`

---

*工单 v0.3 · 仅后端、RBAC scope 数据范围控制*