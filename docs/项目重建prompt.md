# 央企海外工程供应链平台 · 项目重建 Prompt

> **用法**:把本文件**整份**复制粘贴给 Claude / GPT-4 / Cursor / 任何 LLM 编码工具,作为系统级指令。AI 会按规格逐文件生成代码。
>
> **同事使用建议**:粘贴前在末尾加一句"先列你的实现假设给我看,我确认后再开始写文件",避免一上来就跑飞。

---

## 1. 项目背景

实现一个 **「央企海外工程供应链平台」** 的 MVP 第一阶段(认证 / RBAC / 审计底座)。

- **业务定位**:面向中国央企海外 EPC 项目的 B2B 供应链平台,前期主要业主中建三局
- **当前阶段交付物**:用户注册登录 · 基于角色的访问控制(RBAC)· 数据归属隔离 · 操作审计 · 多组织模型
- **不在范围**:业务功能(项目/采购清单/RFQ/订单/履约/风控/商品/供应商档案审核)、邮件 / 找回密码 / OAuth / 2FA、消息推送、PWA、i18n

---

## 2. 技术栈(**锁定,禁止替换**)

### 后端

| 类目 | 选型 |
|---|---|
| 语言 | Python 3.11+ |
| Web 框架 | FastAPI(0.115+) |
| ORM | SQLAlchemy 2.0 async |
| 数据库 | PostgreSQL 16(本机 brew @16 端口 5433,asyncpg + psycopg)|
| 迁移 | Alembic(每个迁移 upgrade/downgrade 必须可逆) |
| 校验 | Pydantic v2 |
| JWT | python-jose[cryptography] |
| 密码 | passlib[bcrypt] |
| 配置 | pydantic-settings |
| 测试 | pytest + pytest-asyncio + httpx |
| 包管理 | uv |

### 前端

| 类目 | 选型 |
|---|---|
| 框架 | Next.js 14 App Router + TypeScript 5 |
| UI | Tailwind CSS + Radix UI(shadcn 风格,自建,不引整套 shadcn) |
| 状态 | Zustand(access token 内存存储) |
| 表单 | react-hook-form + zod(简单表单可手写) |
| 数据请求 | fetch + 自封装 ApiClient + SWR |
| 图标 | lucide-react |
| 包管理 | pnpm 或 npm 二选一(保持一个 lockfile) |

### 不允许引入

- ❌ MySQL / MongoDB / SQLite(已选 PostgreSQL)
- ❌ NextAuth.js(自管 token)
- ❌ Prisma(后端是 SQLAlchemy)
- ❌ Redis(MVP 内存够用,但限流抽 interface 留扩展口)
- ❌ Docker 进生产架构(本地演示打包可用)
- ❌ i18n / next-intl
- ❌ OAuth / SSO / 2FA / 邮件 / 短信库

---

## 3. 项目结构

```
overseas-platform-v0.1/
├── backend/
│   ├── app/
│   │   ├── main.py                FastAPI app + 中间件 + 启动钩子
│   │   ├── core/                  config / security / dependencies / exceptions
│   │   ├── db/
│   │   │   ├── base.py            Base + TimestampMixin
│   │   │   ├── session.py         async engine + get_db dependency
│   │   │   └── models/            一个表一个文件
│   │   ├── schemas/               Pydantic IO 模型
│   │   ├── api/v1/                路由(按业务模块拆文件)
│   │   ├── services/              业务逻辑(纯函数 + AsyncSession)
│   │   ├── rbac/                  权限常量 / 配置 / Guard / 启动同步
│   │   ├── audit/                 审计常量 / 中间件 / 写入工具
│   │   └── seed.py                启动种子(super admin 始终种 + demo 受开关控制)
│   ├── alembic/                   迁移
│   ├── tests/
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/            login / register(公共布局)
│   │   │   ├── (marketing)/       首页 / 商城 / 供应商目录 / 国别(公开)
│   │   │   ├── buyer/             采购方工作台
│   │   │   ├── supplier/          供应商工作台
│   │   │   ├── operator/          平台运营后台
│   │   │   ├── admin/             系统管理后台
│   │   │   ├── account/           个人账户设置
│   │   │   ├── change-password/   首次强制改密页
│   │   │   ├── no-permission/     无权限页
│   │   │   └── test/              RBAC 测试调试页(MVP 临时)
│   │   ├── components/
│   │   │   ├── ui/                基础原子组件(Button / Input / Label / Card)
│   │   │   ├── auth/              RouteGuard / PermissionGuard
│   │   │   └── layout/            AppShell / AppHeader / AppSidebar / PublicLayout
│   │   ├── config/
│   │   │   ├── navigation.ts      路由 + 侧边栏配置
│   │   │   └── permission-matrix.ts  4×15 权限矩阵权威源
│   │   ├── hooks/
│   │   ├── lib/                   api / auth / adminUsers / adminAudit / debugApi / permissions / validators / utils
│   │   ├── stores/                authStore(Zustand)
│   │   └── middleware.ts          路由级守卫
│   └── package.json
└── README.md
```

---

## 4. 数据模型(共 10 张表)

### 4.1 RBAC 五件套

- `users`(id / email UNIQUE / username UNIQUE NULL / name / phone VARCHAR(30) UNIQUE NULL / password_hash bcrypt / status ACTIVE|DISABLED / must_change_password / created_at / updated_at)
- `roles`(id / code UNIQUE / name / description / scope VARCHAR(20) DEFAULT 'GLOBAL')
- `permissions`(id / code UNIQUE 形如 `resource:action` / name / module)
- `user_roles`(user_id, role_id PK 组合)
- `role_permissions`(role_id, permission_id PK 组合)

### 4.2 组织模型(双表,不合一)

- `buyer_organizations`(id / name / code UNIQUE NULL / unified_social_credit_code VARCHAR(18) UNIQUE NULL / description / status ACTIVE|DISABLED)
- `supplier_organizations`(id / name / business_license_no VARCHAR(100) UNIQUE NULL / status DRAFT|UNDER_REVIEW|APPROVED|REJECTED)
- `buyer_members`(user_id, buyer_org_id, is_owner, created_at)
- `supplier_members`(user_id, supplier_org_id, is_owner, created_at)

### 4.3 审计

- `audit_logs`(id / trace_id UUID / user_id NULL / user_email NULL / resource_type / resource_id NULL / action / method NULL / path NULL / ip NULL / user_agent NULL / status SUCCESS|FAILED / error_message NULL / extra JSON NULL / created_at)
- 索引:`(resource_type, action)` · `created_at` · `trace_id` · `user_id`

### 4.4 通用约定

- 主键 Integer 自增
- 时间字段统一 `TIMESTAMP WITHOUT TIME ZONE`,应用层强制 UTC 写入(`datetime.now(timezone.utc).replace(tzinfo=None)`)
- 状态字段 `VARCHAR` + 应用层 Enum 校验
- JSON 字段用 SQLAlchemy `JSON`(PG 自动落 JSONB)
- 表名:**复数小写下划线**(`users`、`buyer_organizations`)
- 禁止数据库特有/厂商私有语法(保持 ORM 抽象,不用 PG 私有函数)
- 不做软删

---

## 5. RBAC 设计(核心)

### 5.1 4 个角色(MVP 固定)

| code | 用户类型 | 业务定位 |
|---|---|---|
| BUYER | external | 采购方:能做所有采购操作,挂 BuyerOrganization |
| SUPPLIER | external | 供应商:档案/上架/响应询价/履约,挂 SupplierOrganization |
| OPERATOR | internal | 平台运营:全业务审核与监控,**不触系统配置** |
| ADMIN | internal | 系统管理员:用户/角色/系统配置,**不触业务数据** |

### 5.2 ~35 个权限点(`resource:action` 命名)

**auth 底层**:`auth:login` `auth:logout` `auth:me`(所有角色都有)

**业务-档案**:`supplier:read/write/approve/reject` · `product:read/write/approve/reject` · `country:read/write`

**业务-交易**:`project:read/write` · `purchase_list:read/write` · `cart:read/write` · `rfq:read/create/respond` · `quote:read/write` · `order:read/write/checkin`

**业务-供应商**:`membership:read/write`

**业务-运营**:`risk:read`

**系统**:`user:manage` · `role:manage` · `permission:manage` · `system:config` · `system:audit`

### 5.3 配置即代码 + 启动同步

- `app/rbac/permissions_config.py` 定义 `ROLE_PERMISSIONS: dict[role_code, list[permission_code]]`(单一可信源)
- `app/rbac/scope_config.py` 定义 `ROLE_RESOURCE_SCOPE: dict[(role, resource), Scope]`,Scope ∈ `OWN / OWN_ORG / ALL / NONE`
- `app/rbac/constants.py` 定义所有权限码常量 + meta(name, module)
- `app/rbac/sync.py` 启动时把配置同步到 DB(`permissions` / `roles` / `role_permissions`),支持 `PERMISSION_SYNC_MODE=dry_run`
- **永远不要在业务代码里写死 `if role == 'BUYER'`**

### 5.4 权限校验三级

1. **后端 API Guard**(`require_permission(code)`,**安全底线,必做**)
2. **前端路由守卫**(`middleware.ts` + `RouteGuard`)
3. **前端按钮显隐**(`<PermissionGuard>` / `usePermissions().hasPermission()`)

后端权限点判定:**实时查 DB**,不放 JWT。JWT 只带 `user_id`。

### 5.5 数据归属过滤(scope)

- 权限点回答"**能不能做**"
- scope 回答"**对哪些数据做**"
- 公开池(已上架商品、已审核供应商等):无 WHERE 过滤
- 私有池(项目/询价/订单等):service 层强制按归属字段过滤

---

## 6. 认证流程

### 6.1 注册 — 自助

**POST `/api/v1/auth/register/buyer`** (BUYER 自助)

```
{ email, username?, name, phone?(中国 11 位), password,
  company_name, unified_social_credit_code(18 位大写字母+数字) }
```

逻辑:校验密码强度(8-32 位 + 至少 1 字母 1 数字) + email/username/phone 唯一性 → 按 USC 查 BuyerOrg:
- **不存在** → 创建新 BuyerOrg + 用户为 owner(`is_owner=true`)
- **已存在** → 加入该 BuyerOrg(`is_owner=false`),company_name 与 DB 不一致 → warn 后沿用 DB 名字

→ 创建 User + BuyerMember + 赋 BUYER 角色 → 写审计 REGISTER(extra 含 buyer_org_id / is_owner / org_created / USC)

**POST `/api/v1/auth/register/supplier`** (SUPPLIER 自助)

```
{ email, username?, name, phone?, password, company_name, business_license_no }
```

营业执照号撞 → 409,文案:**"该供应商已在平台注册。如需加入该企业,请联系企业管理员。"**(不创建任何 user / org / 审计)

否则创建 User + 创建 SupplierOrganization(status=DRAFT)+ SupplierMember(is_owner=true)+ 赋 SUPPLIER 角色 → 写审计

### 6.2 登录

**POST `/api/v1/auth/login`** `{ identifier, password }`

identifier 三选一识别:
- 含 `@` → email
- 11 位纯数字且 1 开头 → phone
- 否则 → username

限流:`(identifier, ip)` 维度,60s 内 5 次失败锁 5 分钟。**抽象成 RateLimiter 接口**,实现层 in-memory dict(为将来换 Redis 留口)。

成功:签发 JWT access(15min,载荷只含 user_id)+ refresh token(7d)。
**access token** 在响应 body(前端存 Zustand 内存)。
**refresh token** 走 **httpOnly cookie**(secure 生产必须 true,samesite=lax,path=`/api/v1/auth`)。

写审计 LOGIN_SUCCESS / LOGIN_FAILED / LOGIN_LOCKED(extra 含 identifier_used: email/phone/username)。

### 6.3 Refresh

**POST `/api/v1/auth/refresh`**:从 cookie 拿 refresh token → 校验 + Origin header 白名单(CSRF 防御)→ 轮换 refresh + 签新 access。

### 6.4 自助资料

- `GET /api/v1/auth/me` → 返回 `{id, email, username, name, phone, status, must_change_password, roles[], permissions[], organization{type, id, name, is_owner}|null}`
- `PATCH /api/v1/auth/me/profile`(改 name,无需密码)
- `POST /api/v1/auth/me/email`(需 current_password)
- `POST /api/v1/auth/me/username`(需 current_password,可清空)
- `POST /api/v1/auth/me/phone`(需 current_password,可清空)
- `POST /api/v1/auth/change-password`(需 old_password)

每个改动写审计:EMAIL_CHANGE / USERNAME_CHANGE / PHONE_CHANGE / PASSWORD_CHANGE / PROFILE_UPDATE,extra 含 old/new 值。

### 6.5 强制改密

`must_change_password=true` 用户登录可成功,**但其他业务接口被拦** → 必须先 `/auth/change-password`。
拦点放**后端中间件**(白名单:auth/me, auth/change-password, auth/logout, auth/refresh),前端守卫只是 UX 层。

---

## 7. 内部账号管理

**POST `/api/v1/admin/users`** 守卫 `user:manage` — 创建 ADMIN / OPERATOR(BUYER/SUPPLIER 走自助注册,**禁止**走这个接口)

**GET `/api/v1/admin/users`** 守卫 `user:manage` — 列表(分页 page/page_size,page_size ≤ 200,默认 50)

**POST `/api/v1/admin/users/{id}/disable`** 守卫 `user:manage` — 停用,红线:
- 不能停自己(400)
- 不能停 super admin(`email == SUPER_ADMIN_EMAIL`,400)
- 不能停最后一个可用 ADMIN(400)
- 已 DISABLED 幂等返回,不重复审计

**POST `/api/v1/admin/users/{id}/enable`** 守卫 `user:manage` — 启用,幂等

写审计 USER_DISABLE / USER_ENABLE(extra: target_user_id, target_email)。

---

## 8. 审计日志查询

**GET `/api/v1/admin/audit-logs`** 守卫 `system:audit` — 多条件筛选:
- page, page_size(≤200) / resource_type / action / status / user_email(LIKE 模糊) / trace_id(精确) / start_at / end_at
- 排序 `created_at DESC, id DESC`
- 响应 `{items, total, page, page_size}`

**GET `/api/v1/admin/audit-logs/{id}`** 守卫 `system:audit` — 单条详情含完整 extra

**GET `/api/v1/admin/audit-logs/_options`** 守卫 `system:audit` — 返回 `{resource_types[], actions[], statuses[]}` 给前端下拉用

**GET 类查询本身不写审计**(避免日志爆炸)。

---

## 9. 统一响应 + 异常

### 成功
```json
{ "code": 0, "message": "ok", "data": { ... } }
```

### 失败
```json
{ "code": 40001, "message": "Invalid credentials", "data": null, "trace_id": "uuid" }
```

HTTP 状态码与业务码并行设置(200 / 400 / 401 / 403 / 404 / 409 / 422 / 429 / 500)。

### 异常映射(`app/core/exceptions.py`)

| Exception | HTTP | code |
|---|---|---|
| `InvalidCredentialsError` | 401 | 40001 |
| `NotAuthenticatedError` | 401 | 40001 |
| `TooManyAttemptsError` | 429 | 40029 |
| `PermissionDeniedError` | 403 | 40003 |
| `AccountDisabledError` | 403 | 40005 |
| `ValidationFailedError` | **400** | 40006(业务校验,**与 pydantic 422 区分**)|
| `ConflictError` | 409 | 40009 |
| `NotFoundError` | 404 | 40400 |

### Trace ID

- 中间件每请求生成 UUID,写 `request.state.trace_id` + contextvar
- 所有日志格式带 `[trace=xxx]`
- 响应头 `X-Trace-Id` 始终携带
- 失败响应 body 含 `trace_id`

### 审计写入

- **写**:登录成功/失败/锁定/登出/注册/创建内部用户/改密/角色变更/任何业务写操作 / 失败的权限校验
- **不写**:GET 查询
- 写入失败**不阻断主流程**(catch + logger.error)

---

## 10. 前端架构要点

### 10.1 工作台导航

四个工作台 + 公开区,见 `config/navigation.ts`。`Workspace` 数据结构:`{code, label, pathPrefix, themeColor, groups: NavGroup[]}`。

主题色:BUYER `#003366` · SUPPLIER `#FF6B35` · OPERATOR `#0F4C81` · ADMIN `#475569`。

### 10.2 权限矩阵权威源

`config/permission-matrix.ts`:
- `RESOURCES` — 15 个资源域 metadata
- `ROLE_RESOURCE_SCOPE` — `Record<RoleCode, Record<ResourceCode, Scope>>`,**前端是后端的镜像**
- `deriveCell(role, resource)` — 计算 (scope, dominantAction) 矩阵符号

### 10.3 守卫

- `middleware.ts` — 路由级守卫(检查 cookie 状态)
- `<RouteGuard requiredPermissions={[...]}>` — 页面级,从 authStore 读 user.permissions
- `<PermissionGuard>` 与 `usePermissions().hasPermission(code)` — 按钮显隐

权限不通过 → 跳 `/no-permission`。

### 10.4 token 管理

- `useAuthStore`(Zustand)持有 `{user, accessToken}` 全内存
- `lib/api.ts` 封装 fetch:`credentials:"include"`,401 自动 `/auth/refresh` 重试一次,并发去重
- 启动钩子 `hooks/useAuth.ts` `bootstrap()`:静默 refresh + `/auth/me`,失败 → 未登录状态

### 10.5 表单 onBlur 校验

- `lib/validators.ts` 集中规则(EMAIL_RE / PHONE_RE / USERNAME_RE / USC_RE / PASSWORD_RE)
- 每字段:`onBlur` 跑校验 → 失败红框 + 红字 → `onChange` 清错
- 提交时跑全量校验,首错填顶部 banner 兜底
- 应用于:register / login / account 各 Card / admin/users 创建模态 / change-password

### 10.6 注册→登录自动填充

- 注册成功前 `sessionStorage.setItem("prefill_login", {identifier, password})`(identifier 优先 username > phone > email)
- `/login` 页 `useEffect` 一次性消费(读完立刻 removeItem)
- 只填充不自动登录

### 10.7 占位页

业务模块未实装时,页面用 `<PermissionPlaceholderPage>`,展示 4 个维度(页面访问 / 权限点 / scope / 后端 _debug 调试),供前期可视化验证 RBAC 链路。

---

## 11. seed 与配置

### `app/core/config.py`

```python
class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://liujingjing@localhost:5433/overseas_supply_dev"
    JWT_SECRET_KEY: str   # 必填,≥16 字符
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SUPER_ADMIN_EMAIL: str = "superadmin@platform.local"
    SUPER_ADMIN_INITIAL_PASSWORD: str = "ChangeMe123"
    SEED_DEMO_ACCOUNTS: bool = False     # 默认关,生产安全
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str]              # 逗号分隔
    CORS_ALLOW_CREDENTIALS: bool = True
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_RATE_LIMIT_MAX_FAILURES: int = 5
    LOGIN_RATE_LIMIT_LOCK_SECONDS: int = 300
    ENABLE_DEBUG_API: bool = True        # 生产应关
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_PATH: str = "/api/v1/auth"
    REFRESH_COOKIE_MAX_AGE: int = 604800
    REFRESH_COOKIE_SECURE: bool = False  # 生产 https 必须 true
    REFRESH_COOKIE_SAMESITE: str = "strict"  # strict/lax/none
```

### `app/seed.py` 启动种子

- **super_admin** 始终种入(env 注入,`must_change_password=true`)
- **demo 内容**仅当 `SEED_DEMO_ACCOUNTS=true` 时种:
  - 中建三局 BuyerOrg(`code=CSCEC3B`, USC 占位 `91420100MA4KXXXX01`)
  - `admin@platform.local` / `admin` (ADMIN, 密码 `12345678a`, must_change=false)
  - `operator@platform.local` / `operator` (OPERATOR, 同上)
  - `buyer@cscec3b.local` / `buyer` (BUYER, 挂中建三局, is_owner=false)

幂等:已存在则跳过,绝不覆盖。

---

## 12. 测试约定

- pytest + pytest-asyncio + httpx + ASGITransport 直连 app
- 共用 test DB `overseas_supply_test`,每测试前 `Base.metadata.drop_all + create_all`,完全隔离 `_dev`
- conftest 默认 `SEED_DEMO_ACCOUNTS=true`(让 fixture 拿到 demo 数据)
- 不依赖 alembic 跑测试 — 直接 `create_all`,更快
- 覆盖目标:每个新接口至少 1 个 happy path + 1-2 个红线 + 审计断言

---

## 13. 命名约定

| 对象 | 规则 | 例子 |
|---|---|---|
| 权限点 | `resource:action` 小写冒号 | `user:manage` |
| AuditResourceType | 小写下划线,与表名单数对齐 | `user` `buyer_org` |
| AuditAction | 大写下划线 | `LOGIN_SUCCESS` `USER_DISABLE` |
| 数据库表 | 复数小写下划线 | `users` `buyer_organizations` |
| Python 类 | 大驼峰 | `User` `BuyerOrganization` |
| Python 函数/变量 | 小写下划线 | `get_current_user` |
| API 路径 | `/api/v1/<resource>/...` 小写连字符 | `/api/v1/admin/audit-logs` |
| TS 组件 | 大驼峰 | `PermissionGuard` |
| TS Hook | `use` 前缀小驼峰 | `usePermissions` |

---

## 14. 不允许的实现错误(常见踩坑)

- ❌ 把 permissions 塞进 JWT(权限变更需即时生效,必须 `/auth/me` 实时查)
- ❌ 登录响应里返回 permissions(同上)
- ❌ 注册自动登录(必须分两步)
- ❌ `POST /admin/users` 创建 BUYER/SUPPLIER
- ❌ 业务代码写死 `if role == 'BUYER'`
- ❌ ADMIN 接触业务数据接口
- ❌ GET 写审计
- ❌ 裸 SQL(必须 ORM)
- ❌ 数据库特有语法(`INSERT OR REPLACE` 等)
- ❌ ENABLE_DEBUG_API 生产泄露
- ❌ 任何 i18n / 国际化框架
- ❌ NextAuth / Prisma / Redis / Docker

---

## 15. 启动命令

### 后端
```bash
cd backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env  # 改 JWT_SECRET_KEY:openssl rand -hex 32
alembic upgrade head
uvicorn app.main:app --reload --port 8000
# /docs 看 OpenAPI · /healthz 看健康
```

### 前端
```bash
cd frontend
pnpm install   # 或 npm ci
pnpm dev       # http://localhost:3000
```

### 测试
```bash
cd backend && pytest -q
```

---

## 16. 给 AI 实现者的硬约束

1. **先列假设给我看,再开始写文件** —— 任何模糊点先提问或注释 `TODO: 设计未覆盖,采用最简实现`,**绝不自行扩展**
2. **每个文件**:头部加 docstring 说明职责。**Python 用类型注解,TypeScript 禁用 any**
3. **关键业务逻辑写中文注释**,只解释 **WHY** 不解释 WHAT
4. **错误处理显式**:fail-fast,不吞异常,映射到统一异常类
5. **每个新接口配套**:Pydantic schema + Service 单测 + Route 集成测
6. **每个 alembic 迁移**:upgrade + downgrade 都实写,本地跑往返通过
7. **顺序产出**:`core / db.base / models → schemas → rbac.constants / permissions_config / scope_config / sync → audit → services → api/v1 → main.py → seed → 测试 → 前端`

---

## 17. 验收清单

完成后下面场景必须全过:

- [ ] `pytest -q` 全绿
- [ ] `SEED_DEMO_ACCOUNTS=true` 启动,4 个 demo 账号 + 中建三局齐全
- [ ] `SEED_DEMO_ACCOUNTS=false` 启动,只有 super admin
- [ ] 4 个 demo 账号都能登录 + `/auth/me` 返回正确 roles+permissions+organization
- [ ] 采购方注册:同 USC 第二个用户加入同组织,is_owner=false
- [ ] 用 phone(13800138000)注册 + 登录全链路通
- [ ] 改邮箱/用户名/手机号都需当前密码
- [ ] ADMIN 在 `/admin/users` 创建 OPERATOR → 停用 → 该 OPERATOR 立刻无法登录
- [ ] OPERATOR 访问 `/admin/audit-logs` → 403
- [ ] 全链路 trace_id:响应头 `X-Trace-Id` + 日志 `[trace=xxx]` + audit_logs 表能对得上
- [ ] 权限矩阵全景页(`/admin/permission-matrix`)展示 4×15 网格

---

*Prompt 结束。粘贴时请保留完整结构,不要节选。*
