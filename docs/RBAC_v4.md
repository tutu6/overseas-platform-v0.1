# 第二阶段开发任务书 · RBAC 与认证底座收尾

> **阶段定位**:不进业务模块。把第一轮 RBAC 基础设施"开口子但没做完"的部分补齐,完成《后端技术方案设计 v0.1》在 main 分支上的全部 gap。
> **前置文档**:《后端技术方案设计 v0.1》《MVP 业务流程共识 v1.2》《RBAC 设计规范 v1.0》
> **不在范围**:任何业务模块(项目/采购清单/RFQ/订单/履约/风控/商品/供应商档案审核)、邮件/OAuth/2FA、Redis、容器化

---

## 0. 阶段目标(一句话)

把"4 角色 × 35 权限点"的底座**完整闭环到 ADMIN 可见可用**——采购方按信用代码识别企业、手机号成为正式登录凭证、ADMIN 能在后台真正管账号 + 看审计日志、demo seed 不污染生产。

---

## 1. 当前 main 分支已实现状态(只读理解,不要重复造)

### 1.1 已交付(无需改动)

- **10 张表**已建:users / roles / permissions / user_roles / role_permissions / buyer_organizations / supplier_organizations / buyer_members / supplier_members / audit_logs
- **RBAC 启动同步**完整:`permissions_config.py` + `scope_config.py` 为单一可信源,启动时同步到 DB,支持 `PERMISSION_SYNC_MODE=dry_run`
- **4 角色 × 35 权限点**矩阵完整(含 3 个 `auth:*` 底层权限)
- **认证接口**已实现:`/auth/register/buyer`、`/auth/register/supplier`、`/auth/login`、`/auth/me`、`/auth/logout`、`/auth/refresh`(httpOnly cookie + 轮转 + Origin 校验)、`/auth/change-password`
- **自助资料**已实现:`PATCH /auth/me/profile`(改 name)、`POST /auth/me/email`、`POST /auth/me/username`
- **管理接口**部分实现:`POST /admin/users`(创建 ADMIN/OPERATOR)、`GET /admin/users`(列表)
- **调试接口**:`/_debug/scope`、`/_debug/matrix`
- **审计日志**:trace_id 全链路 + 失败操作也写入
- **前端**:4 工作台导航骨架 + RouteGuard + Sidebar 显隐 + 矩阵全景页 + 调试模式开关 + 占位页四维度

### 1.2 不一致的 gap(本阶段要补完)

| Gap | 当前状态 | 方案要求 |
|---|---|---|
| G1 采购方按信用代码识别企业 | `register_buyer` 硬编码取 `CSCEC3B` 组织 | 按 `unified_social_credit_code` 查/建 BuyerOrg |
| G2 手机号作登录凭证 | phone 只是选填字段,不唯一,不可登录 | phone 唯一约束 + 中国大陆 11 位校验 + identifier 三选一 |
| G3 改手机号接口 | 未实现 | `POST /auth/me/phone`(需当前密码) |
| G4 内部账号禁用 | 后端无 disable 接口,前端 /admin/users 是占位页 | `POST /admin/users/{id}/disable` + 真实 UI |
| G5 审计日志查询 | ADMIN 有 `system:audit` 权限但无接口/页面 | `GET /admin/audit-logs` + ADMIN 后台审计页 |
| G6 demo seed 生产隐患 | seed 无条件创建 admin/operator/buyer demo 账号 + 中建三局组织 | `SEED_DEMO_ACCOUNTS` 开关控制,默认关闭 |

---

## 2. 任务清单(按依赖顺序排列,严格按顺序做)

### T1 · 数据库迁移:phone 唯一 + buyer_org 信用代码

**目标**:为 G1 / G2 准备表结构。

**改动**:
1. 新建 alembic 迁移 `20260520_0003_phone_unique_and_buyer_usc.py`,内容:
   - `users.phone`:增加 `UNIQUE` 约束(`uq_users_phone`)+ `INDEX`(`ix_users_phone`)。注意:NULL 值在 PG 中默认不参与唯一约束,符合预期(允许多个 NULL)。
   - `buyer_organizations`:
     - 新增 `unified_social_credit_code VARCHAR(18) NULL` 字段(18 位国标长度)
     - 加 `UNIQUE` 约束(`uq_buyer_org_usc`)
     - 加 `INDEX`(`ix_buyer_org_usc`)
   - 同时为现有中建三局 seed 数据回填一个占位信用代码(下面 T2 同步处理)。
2. 同步修改 ORM 模型 `app/db/models/user.py` 和 `app/db/models/buyer_organization.py`。

**校验**:
- `alembic upgrade head` 干净通过
- `alembic downgrade -1` 能干净回滚
- 已有数据不丢

**约束**:
- 迁移必须可逆。`downgrade` 必须实现,删除新增字段与索引。
- 字段长度严格按方案(`unified_social_credit_code` = 18 位)。

---

### T2 · 改造采购方注册:按统一社会信用代码识别企业(G1)

**目标**:采购方注册改为"按信用代码查 BuyerOrg,无则创建,有则加入"。

**改动**:

#### 2.1 Schema(`app/schemas/auth.py`)
- `BuyerRegisterIn` 增加两个必填字段:
  - `company_name: str`(1-200 字符)
  - `unified_social_credit_code: str`(严格 18 位:`^[0-9A-Z]{18}$`,大写字母+数字)

#### 2.2 Service(`app/services/auth_service.py`)
- 删掉 `CSCEC3B_CODE` 硬编码常量及其依赖逻辑。
- `register_buyer` 新流程:
  ```
  校验密码 + email/username/phone 唯一性
  ↓
  按 unified_social_credit_code 查 BuyerOrganization:
    ├─ 不存在 → 创建 BuyerOrg(name=company_name, unified_social_credit_code=...,
    │                         status=ACTIVE)
    │           → 新用户成为 owner(is_owner=true)
    └─ 已存在 → company_name 与现有不一致时,采用 DB 中已有名字
                (输出 warn 日志,不阻断;新用户 is_owner=false)
  ↓
  创建 User + BuyerMember + 赋 BUYER 角色
  ↓
  写审计(extra 中记录 buyer_org_id、is_owner、是否新建组织)
  ```
- 注意:`unified_social_credit_code` 唯一约束冲突的 race condition 用 try/except + DB 约束兜底。

#### 2.3 路由(`app/api/v1/auth.py`)
- `register_buyer` 路由接收新字段,透传给 service。

#### 2.4 前端注册页(`frontend/src/app/(auth)/register/page.tsx`)
- BUYER 选项下也展示"公司名称 + 统一社会信用代码"字段(与 SUPPLIER 字段结构对称)。
- 信用代码前端 regex 校验:`^[0-9A-Z]{18}$`,提示文案"18 位大写字母与数字"。
- 删除当前页面 BUYER 分支下"默认隶属中建三局"的提示文案。
- 提交时把这两个字段传给 `/auth/register/buyer`。

#### 2.5 seed.py
- `seed_buyer_org` 改为:**仅当 `SEED_DEMO_ACCOUNTS=true` 时**才种入中建三局,且写入占位信用代码(例如 `91420100MA4KXXXX01`,18 位假数据)。
- 不再以"组织缺失"为运维问题—register_buyer 不再依赖任何预置组织。

**校验**:
- 新建采购方账号 A 填信用代码 X → 创建新 BuyerOrg + A 为 owner
- 新建采购方账号 B 填同一信用代码 X → 加入同一 BuyerOrg + B 非 owner
- 信用代码格式错误 → 422,文案明确
- 单元测试覆盖以上三个路径

---

### T3 · 手机号作登录凭证(G2 + G3)

**目标**:phone 升级为正式登录凭证之一,与 email/username 三选一。

**改动**:

#### 3.1 phone 格式校验(`app/schemas/auth.py` 新增 util)
- 加 `PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")`(中国大陆 11 位手机号)
- `BuyerRegisterIn` / `SupplierRegisterIn`:`phone` 字段保留可选但若提供必须匹配 regex。
- 新增 util `_validate_phone_optional(v)`。

#### 3.2 注册唯一性校验(`app/services/auth_service.py`)
- `register_buyer` / `register_supplier` 增加 phone 唯一性预校验函数 `_phone_exists`,逻辑同 email/username。
- DB 唯一约束兜底竞态。

#### 3.3 登录 identifier 解析(`app/services/auth_service.py::_find_user_by_identifier`)
改造识别逻辑:
```python
ident = identifier.strip()
if "@" in ident:
    # 当 email 查
elif ident.isdigit() and len(ident) == 11 and ident.startswith("1"):
    # 当 phone 查
else:
    # 当 username 查
```
- login 接口的 `identifier_used` 审计字段加 `"phone"` 取值。

#### 3.4 me 接口审计字段
- `auth_service.login` 的 audit extra `identifier_used` 三选一:`email` / `username` / `phone`。

#### 3.5 新接口 `POST /auth/me/phone`
- Schema:`ChangePhoneIn { new_phone: str | None, current_password: str }`(`new_phone=None` 或 `""` 表示清空)
- Service `me_service.change_phone`:
  - 同 `change_email` 模板
  - 二次密码校验
  - phone 唯一性校验
  - 写审计 `PHONE_CHANGE`(extra 含 old_phone / new_phone)
- 新审计 Action 常量:`AuditAction.PHONE_CHANGE = "PHONE_CHANGE"`

#### 3.6 前端
- 登录页 identifier 输入框提示文案改为"邮箱 / 用户名 / 手机号"。
- 注册页 phone 字段加 11 位 regex 校验(用 `/^1[3-9]\d{9}$/`)和实时提示。
- 账户设置页(`frontend/src/app/account/page.tsx`)增加"修改手机号"操作行,UI 与改邮箱对称。
- `frontend/src/lib/auth.ts` 增加 `authApi.changePhone(...)`。

**校验**:
- 用 phone 登录可成功;phone 错或格式不符返 401
- 注册时同一手机号二次注册返 409
- 改手机号:旧密码错返 401;新号被占返 409;清空 → 后续不能再用 phone 登录

---

### T4 · 内部账号禁用接口(G4)

**目标**:ADMIN 能停用 ADMIN/OPERATOR 账号(BUYER/SUPPLIER 自助账号也允许停用,作为风控手段)。

**改动**:

#### 4.1 后端

**新路由** `POST /api/v1/admin/users/{user_id}/disable`:
- 守卫:`require_permission(Permissions.USER_MANAGE)`
- Service `user_service.disable_user`:
  - 不允许停用自己(`actor_user_id == target_id` → 422)
  - 不允许停用最后一个 ADMIN(查询 ADMIN 角色 + ACTIVE 状态用户数,若 ≤1 且 target 是 ADMIN → 422,文案"系统至少保留一个可用 ADMIN")
  - 不允许停用 super admin(`email == settings.SUPER_ADMIN_EMAIL` → 422)
  - 已 DISABLED 直接幂等返回
  - 改 status,写审计 `USER_DISABLE`
- 新审计 Action:`AuditAction.USER_DISABLE = "USER_DISABLE"`

**新路由** `POST /api/v1/admin/users/{user_id}/enable`(对称):
- 同样 ADMIN 权限,写审计 `USER_ENABLE`

#### 4.2 前端 `/admin/users/page.tsx`
- 删除占位页,做真实 UI:
  - 顶部"新建账号"按钮 → 模态框(填 email/username/name/password/role 单选 ADMIN/OPERATOR/must_change_password 勾选)
  - 表格列:ID / 邮箱 / 用户名 / 姓名 / 角色 / 状态(ACTIVE/DISABLED 徽标) / 操作(停用/启用)
  - 分页(后端已支持 page/page_size)
  - 停用按钮 → 二次确认 → 调 disable 接口
- 视觉风格沿用项目已有 admin layout 的卡片样式

**校验**:
- 创建 OPERATOR → 列表出现 → 停用 → 状态变为 DISABLED → 该用户登录即返 403
- 自己停自己返 422
- 最后一个 ADMIN 停用尝试返 422

---

### T5 · 审计日志查询接口与 ADMIN 后台审计页(G5)

**目标**:让 ADMIN 持有的 `system:audit` 权限点真正可用。

**改动**:

#### 5.1 后端 `app/api/v1/admin_audit.py`(新文件)

**`GET /api/v1/admin/audit-logs`**:
- 守卫:`require_permission(Permissions.SYSTEM_AUDIT)`
- Query 参数(全部可选):
  - `page: int = 1, page_size: int = 50`(上限 200)
  - `resource_type: str | None`(精确匹配)
  - `action: str | None`(精确匹配)
  - `status: str | None`(SUCCESS / FAILED)
  - `user_email: str | None`(LIKE %xxx% 模糊匹配)
  - `trace_id: str | None`(精确)
  - `start_at: datetime | None` / `end_at: datetime | None`(created_at 范围)
- 响应字段:`items: [...] + total`
- 排序:`created_at DESC`
- 返回字段含 `created_at` 的 ISO 字符串(已有 naive UTC,转 ISO 时不加 Z 后缀,留前端转)

**`GET /api/v1/admin/audit-logs/{id}`**:
- 单条详情,展开 `extra` JSON
- 同样 `system:audit` 守卫

#### 5.2 Service `app/services/audit_query_service.py`(新文件)
- `list_audit_logs(db, *, filters, page, page_size)`:动态拼 WHERE,标准分页
- `get_audit_log(db, *, log_id)`:返回单条

#### 5.3 前端

**新增 nav item**(`frontend/src/config/navigation.ts` ADMIN 工作台):
```
{ path: "/admin/audit-logs", label: "审计日志",
  icon: ScrollText, resource: "system",
  requiredPermissions: [Permissions.SYSTEM_AUDIT],
  description: "全平台敏感操作审计记录,支持按资源类型/动作/状态/邮箱/Trace ID 筛选" }
```

**新增页面** `frontend/src/app/admin/audit-logs/page.tsx`:
- 顶部筛选区(横向 flex):resource_type 下拉 / action 下拉 / status 下拉 / user_email 输入 / trace_id 输入 / 时间范围
- 表格列:created_at / trace_id(短显示+悬浮全 ID) / user_email / resource_type / action / status / 操作(点击查看详情)
- 点击行展开抽屉,显示完整 JSON(`extra`)
- 分页

下拉选项的值来自后端常量,由后端额外提供一个 `GET /api/v1/admin/audit-logs/_options` 返回 `{ resource_types: [...], actions: [...] }`,前端启动时一次拉取缓存。

#### 5.4 调试
- 该页面有 `system:audit` 守卫,OPERATOR/BUYER/SUPPLIER 直接 URL 访问 → 跳 `/no-permission`
- 该页本身写审计?**不写**,GET 类查询不写审计(避免日志爆炸,与方案 §6.3 一致)

**校验**:
- ADMIN demo 账号 → 看到完整日志流
- 用 trace_id 检索能定位到具体登录失败记录
- OPERATOR 直访路径返 403

---

### T6 · demo seed 开关化(G6)

**目标**:`SEED_DEMO_ACCOUNTS` 开关控制 demo 内容,生产默认关闭。

**改动**:

#### 6.1 `app/core/config.py`
- 增加 `SEED_DEMO_ACCOUNTS: bool = False`(默认关闭)。
- 增加 `SUPER_ADMIN_EMAIL`、`SUPER_ADMIN_INITIAL_PASSWORD`(已存在则跳过)。

#### 6.2 `app/seed.py`
- `run_all_seeds` 改为:
  ```python
  if settings.SEED_DEMO_ACCOUNTS:
      await seed_buyer_org(db)        # 中建三局 demo BuyerOrg
      await seed_demo_internal_accounts(db)  # admin@platform.local / operator@platform.local
      # 演示 BUYER 账号 buyer@cscec3b.local(如方案 §7.2 表所示) - 也加进来
      await seed_demo_buyer_account(db)
  await seed_super_admin(db)  # 始终种,生产唯一保留项
  ```
- 新增 `seed_demo_buyer_account`:在中建三局 BuyerOrg 下种 `buyer@cscec3b.local`(密码 `12345678a`,must_change=false,角色 BUYER,is_owner=false)。
- demo seed 函数全部在创建时 logger.warning 输出"**仅开发演示,生产务必删除**"。

#### 6.3 `.env.example`(根目录或 backend 目录,以现有惯例为准)
- 新增:
  ```
  SEED_DEMO_ACCOUNTS=true   # 本地开发推荐 true;生产必须 false
  SUPER_ADMIN_EMAIL=superadmin@platform.local
  SUPER_ADMIN_INITIAL_PASSWORD=Change_Me_Immediately_1
  ```

#### 6.4 README(`backend/README.md`)
- 启动步骤章节加入说明:
  - 本地开发:`SEED_DEMO_ACCOUNTS=true`
  - 生产部署:`SEED_DEMO_ACCOUNTS=false`,并提供"如已被误种入,如何手工删除 demo 数据"的清理 SQL

**校验**:
- `SEED_DEMO_ACCOUNTS=false` 启动 → 数据库只有 super admin + 4 个 roles + N 个 permissions,无中建三局组织、无 demo 账号
- `SEED_DEMO_ACCOUNTS=true` 启动 → 4 个 demo 账号 + 中建三局组织齐全

---

## 3. 测试要求

每个任务必须配 pytest 用例。文件组织:
- `tests/test_register_buyer_usc.py`(T1+T2)
- `tests/test_phone_login.py`(T3)
- `tests/test_admin_users_disable.py`(T4)
- `tests/test_audit_query.py`(T5)
- `tests/test_seed_demo_switch.py`(T6,可用 monkeypatch + 调 seed 函数测试)

**目标**:本阶段结束 `pytest` 全绿,新增用例不少于 25 个。

---

## 4. 不在本阶段范围(明确拒绝)

| 想做 | 拒绝理由 |
|---|---|
| 角色管理后台(增删改 Role) | 角色由配置文件 + 启动同步管;运行时无写需求 |
| 权限点管理后台(增删改 Permission) | 同上,代码即可信源 |
| 找回密码 / 邮件验证 | 方案明确不在范围 |
| 6 角色升级(PURCHASER + OVERSEAS_LEADER) | Q28 待团队拍板,本阶段不动 |
| 采购方注册引入 OPERATOR 审核 | Q27 待拍板,本阶段保持自助 |
| Redis / 容器化 / K8s | MVP 单机够用 |
| service 层 scope WHERE 真过滤 | 业务表未上线,无意义;调试接口已示意 |
| 任何业务表(project / supplier 资质 / rfq 等) | 进入业务模块就是第三阶段了 |

---

## 5. 验收清单

完成本阶段后,以下场景必须全部通过:

- [ ] `pytest` 全绿
- [ ] `SEED_DEMO_ACCOUNTS=true` 启动,种子完整
- [ ] `SEED_DEMO_ACCOUNTS=false` 启动,只有 super admin
- [ ] 采购方 A 用信用代码 X + 公司名 Y 注册 → 创建新 BuyerOrg,A 为 owner
- [ ] 采购方 B 用同一信用代码 X 注册 → 加入同一 BuyerOrg,B 非 owner
- [ ] 用手机号 `13800138000` 注册 + 登录全链路通
- [ ] 同一手机号二次注册 → 409
- [ ] 改手机号需当前密码,改完用新手机号能登录、旧的不能
- [ ] ADMIN 在 `/admin/users` 页面创建 OPERATOR → 停用 → OPERATOR 立即无法登录(403)
- [ ] ADMIN 不能停用自己,不能停用最后一个 ADMIN,不能停用 super admin
- [ ] ADMIN 在 `/admin/audit-logs` 看到完整审计流,可按 trace_id / user_email / action 等筛选
- [ ] OPERATOR 访问 `/admin/audit-logs` → 跳 no-permission
- [ ] 35 个权限点矩阵全景页(`/admin/permission-matrix`)显示不变(本阶段不动权限点)
- [ ] 全链路 trace_id 在响应头 / 日志 / audit_logs 三方位置可对得上

---

## 6. 实施顺序与时间预估

| 顺序 | 任务 | 预估 |
|---|---|---|
| 1 | T1 迁移 | 0.5 天 |
| 2 | T2 信用代码改造 | 1 天 |
| 3 | T3 手机号登录 | 1 天 |
| 4 | T6 demo seed 开关(可以提前到这里,避免后面 T4/T5 调试时种子混乱) | 0.5 天 |
| 5 | T4 账号禁用 + UI | 1 天 |
| 6 | T5 审计查询 + UI | 1.5 天 |
| 7 | 联调 + 测试补全 | 1 天 |
| **合计** | | **约 6.5 天** |

注:T6 的优先级提前,因为它影响所有后续测试的 fixture 设计。

---

## 7. 给 Claude Code 的硬约束

1. **不要动 `permissions_config.py` 和 `scope_config.py` 的权限点 / scope 配置**——本阶段权限矩阵保持 4×35 不变。
2. **不要新增前端业务页面**——只动 `account` / `admin/users` / `admin/audit-logs` / 注册页 / 登录提示。
3. **不要引入新依赖**(尤其禁止:Redis、Celery、SMTP 客户端、OAuth 库、Docker 配置文件、i18n 库)。
4. **每个任务独立提交**(T1 一个 PR、T2 一个 PR …),便于 review。
5. **测试与代码同 PR 提交**——不接受"代码先合,测试后补"。
6. **任何"设计未覆盖"的细节**,严格按 `CLAUDE.md` 第 33 行规则:选最简方案 + 注释 `TODO: 设计未覆盖,采用最简实现`,**不自行扩展**。
7. **数据库迁移必须可逆**(`downgrade()` 不留 `pass`)。
8. **审计写入失败不阻断主流程**——`write_audit` 已遵守此原则,新增审计点继续沿用。

---

*文档结束 · 第二阶段开发任务书 v1.0 · 与《后端技术方案设计 v0.1》对齐*
