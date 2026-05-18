# Claude Code 实施 Prompt 01:认证、RBAC 与审计底座

> **版本**:V1.1 · 精简版
> **目标**:本地可运行的认证、RBAC、审计日志底座,作为后续业务模块的基础
> **关联文档**:`docs/MVP业务流程共识_v1.2.md`、`docs/RBAC与组织架构设计讨论_v1.2.md`

---

## 0. 实施前必读

### 0.1 本轮交付清单

- 后端:FastAPI + SQLAlchemy 2.0(async) + Alembic + SQLite + uv
- 前端:Next.js (App Router) + TypeScript + Tailwind + shadcn 风格
- 10 张表:User / Role / Permission / UserRole / RolePermission / BuyerOrganization / SupplierOrganization / BuyerMember / SupplierMember / AuditLog
- 注册接口(BUYER / SUPPLIER 各一个,自助注册)
- 内部账号创建接口(super admin 创建 ADMIN / OPERATOR)
- 登录接口(JWT)
- `/auth/me` 接口(返回 user + roles + permissions + organization)
- 密码规则、登录限流、Trace ID、审计日志
- 前端登录页 / 注册页 / 修改密码页 / 4 个 RBAC 测试页
- pytest 用例 + curl 验证脚本 + README

### 0.2 不做的(明确砍掉)

❌ Docker、部署、CI/CD
❌ 邮件验证、找回密码、OAuth、2FA
❌ 业务流程页面(项目、采购清单、RFQ、订单等)
❌ 审计日志查询 UI、权限管理后台 UI、用户管理 UI
❌ Redis、缓存
❌ 国际化、PWA、SSG/ISR

### 0.3 必读资料

实施前 **必须阅读** `/Users/liujingjing/Documents/overseas-platform/overseas-supply-platform`(参考工程代码),特别关注:

- `src/app/(auth)/layout.tsx` — 认证页整体壳
- `src/app/(auth)/login/page.tsx` — 登录页
- `src/app/(auth)/register/page.tsx` — 注册页(单页 + 角色选择)
- `src/middleware.ts` — 前端路由守卫
- 整体的 Tailwind 色值和组件风格

**前端复用原则**:
- ✅ 复用:页面视觉风格、布局、控件、文案、动效、组件结构、功能入口
- ❌ 不复用:API 调用层(按本文档的新后端契约重写);Prisma 相关代码(用我们的后端)

---

## 1. 技术栈

### 后端

| 类目 | 选型 |
|---|---|
| 语言 | Python 3.11+ |
| 框架 | FastAPI |
| ORM | SQLAlchemy 2.0(async) |
| 迁移 | Alembic |
| 数据库 | **SQLite**(MVP 阶段) |
| 数据库驱动 | aiosqlite |
| 校验 | Pydantic v2 |
| JWT | python-jose[cryptography] |
| 密码加密 | passlib[bcrypt] |
| 配置 | pydantic-settings |
| 测试 | pytest + httpx + pytest-asyncio |
| 包管理 | **uv** |

### 前端

| 类目 | 选型 |
|---|---|
| 框架 | Next.js (App Router) + TypeScript |
| UI | Tailwind CSS + Radix UI (shadcn 风格) |
| 状态 | Zustand |
| 表单 | react-hook-form + zod |
| 数据请求 | fetch + SWR |
| 包管理 | pnpm |

---

## 2. 项目结构

```
overseas-supply-platform/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/              # config / security / dependencies / exceptions
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── models/        # 所有 ORM 模型
│   │   ├── schemas/           # Pydantic
│   │   ├── api/v1/            # 路由
│   │   ├── services/          # 业务逻辑
│   │   ├── rbac/              # constants / permissions_config / guards / sync
│   │   ├── audit/             # constants / middleware / logger
│   │   └── seed.py            # 启动种子
│   ├── alembic/
│   ├── tests/
│   ├── scripts/verify.sh
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── .env.example
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── login/page.tsx
│   │   │   │   └── register/page.tsx
│   │   │   ├── change-password/page.tsx
│   │   │   ├── test/
│   │   │   │   ├── buyer-only/page.tsx
│   │   │   │   ├── supplier-only/page.tsx
│   │   │   │   ├── operator-only/page.tsx
│   │   │   │   └── admin-only/page.tsx
│   │   │   └── page.tsx       # 落地页占位
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   └── auth/PermissionGuard.tsx
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   └── usePermissions.ts
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── auth.ts
│   │   │   └── permissions.ts
│   │   ├── stores/authStore.ts
│   │   └── middleware.ts
│   ├── package.json
│   ├── .env.local.example
│   └── README.md
│
├── docs/
│   ├── MVP业务流程共识_v1.2.md
│   ├── RBAC与组织架构设计讨论_v1.2.md
│   ├── overseas-supply-platform.md  # 参考工程代码,前端复用来源
│   └── prompts/
│       └── prompt-01-auth-rbac-foundation.md  # 本文件
│
└── README.md
```

---

## 3. 数据库 Schema

### 3.1 通用约定

- 主键统一 `Integer` 自增(SQLAlchemy `BigInteger`,SQLite 实际是 INTEGER)
- 时间字段统一 `DateTime`,**应用层强制 UTC 存储**,前端按需转时区显示
- 状态字段用 `VARCHAR` + 应用层 Enum 校验,**不用 SQLite 的 enum 类型**
- JSON 用 SQLAlchemy `JSON` 类型(SQLite 存为 TEXT,SQLAlchemy 自动序列化)
- 不引入软删字段
- **禁止使用 SQLite 特有语法**(如 `INSERT OR REPLACE`),保持 ORM 抽象,便于未来切 PG

### 3.2 表清单

#### users

| 字段 | 类型 | 约束 |
|---|---|---|
| id | Integer | PK autoincrement |
| email | String(255) | UNIQUE NOT NULL |
| name | String(100) | NOT NULL |
| phone | String(30) | NULL |
| password_hash | String(255) | NOT NULL |
| status | String(20) | NOT NULL DEFAULT 'ACTIVE'(ACTIVE / DISABLED) |
| must_change_password | Boolean | NOT NULL DEFAULT FALSE |
| created_at | DateTime | NOT NULL DEFAULT now() |
| updated_at | DateTime | NOT NULL DEFAULT now() |

#### roles

| 字段 | 类型 | 约束 |
|---|---|---|
| id | Integer | PK |
| code | String(50) | UNIQUE NOT NULL(`BUYER` / `SUPPLIER` / `OPERATOR` / `ADMIN`)|
| name | String(100) | NOT NULL |
| scope | String(20) | NOT NULL DEFAULT 'GLOBAL'(MVP 仅 GLOBAL) |
| scope_id | Integer | NULL |
| description | Text | NULL |
| created_at | DateTime | NOT NULL DEFAULT now() |

#### permissions

| 字段 | 类型 | 约束 |
|---|---|---|
| id | Integer | PK |
| code | String(100) | UNIQUE NOT NULL(如 `user:read`)|
| name | String(150) | NOT NULL |
| module | String(50) | NOT NULL |
| description | Text | NULL |
| created_at | DateTime | NOT NULL DEFAULT now() |

#### user_roles

| 字段 | 类型 | 约束 |
|---|---|---|
| id | Integer | PK |
| user_id | Integer | FK → users(id) ON DELETE CASCADE |
| role_id | Integer | FK → roles(id) ON DELETE CASCADE |
| created_at | DateTime | NOT NULL DEFAULT now() |

UNIQUE `(user_id, role_id)`

#### role_permissions

| 字段 | 类型 | 约束 |
|---|---|---|
| id | Integer | PK |
| role_id | Integer | FK → roles(id) ON DELETE CASCADE |
| permission_id | Integer | FK → permissions(id) ON DELETE CASCADE |
| created_at | DateTime | NOT NULL DEFAULT now() |

UNIQUE `(role_id, permission_id)`

#### buyer_organizations

| 字段 | 类型 | 约束 |
|---|---|---|
| id | Integer | PK |
| name | String(200) | NOT NULL |
| code | String(50) | UNIQUE |
| description | Text | NULL |
| status | String(20) | NOT NULL DEFAULT 'ACTIVE' |
| created_at / updated_at | DateTime | NOT NULL DEFAULT now() |

**种子数据**:1 条,`name='中建三局'`、`code='CSCEC3B'`

#### supplier_organizations

| 字段 | 类型 | 约束 |
|---|---|---|
| id | Integer | PK |
| name | String(200) | NOT NULL |
| business_license_no | String(100) | UNIQUE |
| status | String(20) | NOT NULL DEFAULT 'DRAFT' |
| created_at / updated_at | DateTime | NOT NULL DEFAULT now() |

> 本轮供应商组织字段最小化,详细资质字段在后续 prompt 完善。

#### buyer_members / supplier_members

均为关联表:

| 字段 | 类型 | 约束 |
|---|---|---|
| id | Integer | PK |
| user_id | Integer | FK → users(id) ON DELETE CASCADE |
| buyer_org_id / supplier_org_id | Integer | FK → 对应组织表 ON DELETE CASCADE |
| is_owner | Boolean | NOT NULL DEFAULT FALSE |
| created_at | DateTime | NOT NULL DEFAULT now() |

UNIQUE `(user_id, org_id)`

#### audit_logs

| 字段 | 类型 | 约束 |
|---|---|---|
| id | Integer | PK |
| trace_id | String(36) | NOT NULL,INDEX |
| user_id | Integer | NULL,INDEX |
| user_email | String(255) | NULL |
| resource_type | String(50) | NOT NULL |
| resource_id | String(100) | NULL |
| action | String(50) | NOT NULL |
| method | String(10) | NULL |
| path | String(500) | NULL |
| ip | String(50) | NULL |
| user_agent | Text | NULL |
| status | String(20) | NOT NULL(SUCCESS / FAILED) |
| error_message | Text | NULL |
| extra | JSON | NULL |
| created_at | DateTime | NOT NULL,INDEX |

复合索引 `(resource_type, action)`

---

## 4. RBAC 设计

### 4.1 角色清单(种子数据,全部 `scope='GLOBAL'`)

| code | name |
|---|---|
| BUYER | 项目部采购员 |
| SUPPLIER | 供应商 |
| OPERATOR | 平台运营 |
| ADMIN | 系统管理员 |

### 4.2 权限点清单(本轮范围)

```python
# backend/app/rbac/constants.py

class Permissions:
    # auth
    AUTH_LOGIN = "auth:login"
    AUTH_LOGOUT = "auth:logout"
    AUTH_ME = "auth:me"

    # user
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DISABLE = "user:disable"

    # role / permission
    ROLE_READ = "role:read"
    ROLE_MANAGE = "role:manage"
    PERMISSION_READ = "permission:read"

    # rbac
    USER_ROLE_ASSIGN = "user_role:assign"
    USER_ROLE_REVOKE = "user_role:revoke"

    # org
    BUYER_ORG_READ = "buyer_org:read"
    SUPPLIER_ORG_READ = "supplier_org:read"

    # system
    AUDIT_LOG_READ = "audit:read"
```

### 4.3 角色 → 权限点分配

```python
# backend/app/rbac/permissions_config.py

# TODO(Q22): 角色-权限关系定义方式待团队拍板。
# 当前实现:配置文件 + 启动同步到数据库(预倾向方案 C)。

ROLE_PERMISSIONS = {
    "BUYER": [
        Permissions.AUTH_LOGIN,
        Permissions.AUTH_LOGOUT,
        Permissions.AUTH_ME,
        Permissions.BUYER_ORG_READ,
    ],
    "SUPPLIER": [
        Permissions.AUTH_LOGIN,
        Permissions.AUTH_LOGOUT,
        Permissions.AUTH_ME,
        Permissions.SUPPLIER_ORG_READ,
    ],
    "OPERATOR": [
        Permissions.AUTH_LOGIN,
        Permissions.AUTH_LOGOUT,
        Permissions.AUTH_ME,
        Permissions.USER_READ,
        Permissions.BUYER_ORG_READ,
        Permissions.SUPPLIER_ORG_READ,
    ],
    "ADMIN": [
        Permissions.AUTH_LOGIN,
        Permissions.AUTH_LOGOUT,
        Permissions.AUTH_ME,
        Permissions.USER_READ,
        Permissions.USER_CREATE,
        Permissions.USER_UPDATE,
        Permissions.USER_DISABLE,
        Permissions.ROLE_READ,
        Permissions.ROLE_MANAGE,
        Permissions.PERMISSION_READ,
        Permissions.USER_ROLE_ASSIGN,
        Permissions.USER_ROLE_REVOKE,
        Permissions.AUDIT_LOG_READ,
    ],
}
```

### 4.4 启动同步逻辑

应用启动时(FastAPI lifespan):
1. 遍历 `Permissions` 类常量,对比数据库 `permissions` 表:新增的 INSERT,变更的 UPDATE,**配置中删除的不删数据库**(只警告)
2. 遍历 `ROLE_PERMISSIONS`,对比 `role_permissions` 表:不存在的 INSERT,配置已删除的 DELETE,**完全镜像配置**
3. 输出同步日志:`Permissions: +X synced, RolePermissions: +Y / -Z synced`

### 4.5 后端权限守卫

```python
# backend/app/rbac/guards.py

def require_permission(code: str):
    async def checker(current_user = Depends(get_current_user)):
        if code not in current_user.permissions:
            raise HTTPException(403, f"Permission denied: {code}")
        return current_user
    return checker

# 使用
@router.post("/admin/users")
async def create_user(
    body: UserCreate,
    current_user = Depends(require_permission("user:create")),
):
    ...
```

### 4.6 前端权限三级校验

- **路由守卫**(`middleware.ts`):未登录访问受保护路由 → 跳 `/login`
- **路由层**:进入页面时,如检测到 `must_change_password=true` 强制跳 `/change-password`
- **按钮显隐**:`<PermissionGuard required="xxx:yyy">...</PermissionGuard>` 或 `usePermissions().hasPermission('xxx:yyy')`

---

## 5. 接口规范

### 5.1 统一响应格式

**成功**:
```json
{ "code": 0, "message": "ok", "data": { ... } }
```

**失败**:
```json
{ "code": 40001, "message": "Invalid credentials", "data": null, "trace_id": "abc-123" }
```

- HTTP 状态码同步设置(200/400/401/403/404/422/429/500)
- `trace_id` 仅失败时进 body;成功时通过响应头 `X-Trace-Id` 返回
- 所有响应都带 `X-Trace-Id` 响应头

### 5.2 接口清单

#### 公开接口

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/auth/register/buyer` | BUYER 自助注册 |
| POST | `/api/v1/auth/register/supplier` | SUPPLIER 自助注册 |
| POST | `/api/v1/auth/login` | 登录,返回 JWT |
| GET | `/healthz` | 健康检查 |

#### 已登录

| Method | Path | 所需权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/auth/me` | `auth:me` | 当前用户+roles+permissions+organization |
| POST | `/api/v1/auth/logout` | `auth:logout` | 登出(前端清 token) |
| POST | `/api/v1/auth/change-password` | `auth:me` | 修改自己密码 |

#### 内部账号管理

| Method | Path | 所需权限 | 说明 |
|---|---|---|---|
| POST | `/api/v1/admin/users` | `user:create` | 创建 ADMIN/OPERATOR |
| GET | `/api/v1/admin/users` | `user:read` | 用户列表 |

#### RBAC 测试接口(本轮临时)

| Method | Path | 所需 |
|---|---|---|
| GET | `/api/v1/test/buyer-only` | role=BUYER |
| GET | `/api/v1/test/supplier-only` | role=SUPPLIER |
| GET | `/api/v1/test/operator-only` | role=OPERATOR |
| GET | `/api/v1/test/admin-only` | role=ADMIN |
| GET | `/api/v1/test/all-roles` | 任意登录 |

### 5.3 关键接口契约

#### POST `/api/v1/auth/register/buyer`

**Request**:
```json
{
  "email": "zhang@cscec3b.com",
  "name": "张三",
  "phone": "13800138000",
  "password": "Abcd1234"
}
```

**业务逻辑**:
1. 校验 email 唯一、密码规则
2. 事务:
   - 创建 User
   - 关联中建三局 BuyerOrganization
   - 创建 BuyerMember(is_owner=false)
   - 分配 BUYER 角色
3. 写审计日志(REGISTER)
4. **不自动登录**,返回成功 200

**Response 200**:
```json
{
  "code": 0,
  "message": "ok",
  "data": { "user_id": 42, "email": "zhang@cscec3b.com" }
}
```

#### POST `/api/v1/auth/register/supplier`

**Request**:
```json
{
  "email": "li@huajian.com",
  "name": "李四",
  "phone": "13800138001",
  "password": "Abcd1234",
  "company_name": "华建供应链有限公司",
  "business_license_no": "91110000XXXXXXXXXX"
}
```

**业务逻辑**:
1. 校验 email、营业执照号唯一、密码规则
2. 事务:
   - 创建 User
   - 创建 SupplierOrganization(status='DRAFT')
   - 创建 SupplierMember(is_owner=true)
   - 分配 SUPPLIER 角色
3. 写审计日志(REGISTER)
4. **不自动登录**,返回成功 200

#### POST `/api/v1/auth/login`

**Request**:
```json
{ "email": "xxx@xxx.com", "password": "Abcd1234" }
```

**业务逻辑**:
1. 限流检查(email+IP)→ 锁定中返回 429
2. 查 user → 不存在或密码错 → 限流计数+1 → 写审计 LOGIN_FAILED → 401
3. user.status='DISABLED' → 写审计 LOGIN_FAILED → 403
4. 通过 → 清限流计数 → 签 JWT → 写审计 LOGIN_SUCCESS → 200

**Response 200**(**不含 permissions**):
```json
{
  "code": 0,
  "data": {
    "access_token": "...",
    "refresh_token": "...",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

#### GET `/api/v1/auth/me`(权限权威接口)

**Response 200**:
```json
{
  "code": 0,
  "data": {
    "id": 42,
    "email": "zhang@cscec3b.com",
    "name": "张三",
    "phone": "13800138000",
    "status": "ACTIVE",
    "must_change_password": false,
    "roles": ["BUYER"],
    "permissions": ["auth:login", "auth:logout", "auth:me", "buyer_org:read"],
    "organization": {
      "type": "BUYER_ORG",
      "id": 1,
      "name": "中建三局",
      "is_owner": false
    }
  }
}
```

> ADMIN/OPERATOR 用户的 `organization` 字段返回 `null`。

#### POST `/api/v1/admin/users`

**Request**:
```json
{
  "email": "ops@platform.com",
  "name": "王五",
  "password": "TempPass123",
  "role": "OPERATOR",
  "must_change_password": true
}
```

**业务逻辑**:
1. 校验 `user:create` 权限
2. role 仅允许 `OPERATOR` / `ADMIN`(BUYER/SUPPLIER 走自助注册,不能从此接口创建)
3. 创建 User + 分配角色
4. 写审计日志(CREATE)

---

## 6. 业务规则

### 6.1 密码规则

- 长度 8-32 位
- 必须包含至少 1 个字母 + 至少 1 个数字
- 正则:`^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&^_-]{8,32}$`
- **前后端都校验**

### 6.2 登录失败限流

- 维度:`email + IP` 组合
- 窗口:1 分钟滚动
- 阈值:5 次失败
- 锁定时长:5 分钟
- 存储:**进程内 dict**(MVP 单机够用)
- 触发锁定时写审计 `LOGIN_LOCKED`,返回 429

### 6.3 JWT 配置

- 算法 HS256,Secret 通过环境变量 `JWT_SECRET_KEY`
- Access Token:15 分钟
- Refresh Token:7 天
- payload:`{ sub, email, type: "access"|"refresh", iat, exp }`
- **permissions 不放 JWT**,通过 `/auth/me` 实时获取

### 6.4 初始超级管理员(种子)

环境变量配置:
```bash
SUPER_ADMIN_EMAIL=superadmin@platform.local
SUPER_ADMIN_INITIAL_PASSWORD=ChangeMe123
```

启动种子逻辑:
- 检查 super admin 是否存在,不存在则创建,`must_change_password=true`,分配 ADMIN 角色
- 已存在则跳过,**绝不覆盖**
- 输出明显提示日志

---

## 7. Trace ID 与审计日志

### 7.1 Trace ID 中间件

```python
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request.state.trace_id = trace_id
        trace_id_var.set(trace_id)  # contextvar
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
```

所有 Python logger 配 filter,自动从 `trace_id_var` 取值,日志格式:
```
[2026-05-17T10:23:45Z] [trace=abc-123] [INFO] auth.login: user=xxx@xxx success
```

### 7.2 审计日志记录范围

**只记敏感写操作 + 登录相关**,不记普通 GET。

| 操作 | resource_type | action |
|---|---|---|
| 登录成功 | auth | LOGIN_SUCCESS |
| 登录失败 | auth | LOGIN_FAILED |
| 登录锁定 | auth | LOGIN_LOCKED |
| 登出 | auth | LOGOUT |
| 注册 | user | REGISTER |
| 创建内部用户 | user | CREATE |
| 修改密码 | auth | PASSWORD_CHANGE |
| 修改用户 | user | UPDATE |
| 禁用用户 | user | DISABLE |
| 角色分配 | user_role | ROLE_ASSIGN |
| 角色撤销 | user_role | ROLE_REVOKE |

### 7.3 Enum 定义

```python
# backend/app/audit/constants.py

class AuditResourceType(str, Enum):
    AUTH = "auth"
    USER = "user"
    ROLE = "role"
    PERMISSION = "permission"
    USER_ROLE = "user_role"
    BUYER_ORG = "buyer_org"
    SUPPLIER_ORG = "supplier_org"
    BUYER_MEMBER = "buyer_member"
    SUPPLIER_MEMBER = "supplier_member"

class AuditAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DISABLE = "DISABLE"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGIN_LOCKED = "LOGIN_LOCKED"
    LOGOUT = "LOGOUT"
    REGISTER = "REGISTER"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    ROLE_ASSIGN = "ROLE_ASSIGN"
    ROLE_REVOKE = "ROLE_REVOKE"
```

### 7.4 命名约定

- 权限点:`resource:action` 小写冒号
- AuditResourceType:小写下划线,与表名单数对齐
- AuditAction:大写下划线
- 数据库表:复数小写下划线
- API 路径:`/api/v1/<resource>/...`,小写连字符

---

## 8. 关键流程图

### 8.1 登录流程

```
[POST /auth/login]
  ↓
限流检查 ──锁定──→ 写审计 LOGIN_LOCKED → 429
  ↓
查 user
  ├─ 不存在/密码错 → 限流+1 → 写审计 LOGIN_FAILED → 401
  ├─ status=DISABLED → 写审计 LOGIN_FAILED → 403
  └─ 通过 ↓
清限流 → 签 JWT → 写审计 LOGIN_SUCCESS → 200
                   (只返回 token,不返回 permissions)
  ↓
[前端拿到 token]
  ↓
[GET /auth/me]
  ↓
返回完整 user + roles + permissions + organization
```

### 8.2 权限校验流程

```
[请求到达]
  ↓
RequestIDMiddleware 设置 trace_id
  ↓
JWT 解析 → user_id
  ├─ 无效 → 401
  └─ 有效 ↓
DB 查 user
  ├─ DISABLED → 401
  └─ ACTIVE ↓
DB 查 roles 和 permissions
  ↓
require_permission Guard 检查
  ├─ 缺失 → 403
  └─ 通过 ↓
进入业务逻辑
  ↓
[写操作] → 写审计日志
  ↓
返回响应(带 X-Trace-Id 头)
```

### 8.3 初始超级管理员引导

```
[首次部署]
  ↓
配置 .env 中 SUPER_ADMIN_EMAIL / SUPER_ADMIN_INITIAL_PASSWORD
  ↓
alembic upgrade head → uvicorn 启动
  ↓
[lifespan startup]
  ├─ 同步 Role / Permission / RolePermission
  ├─ 确保中建三局 BuyerOrg 存在
  └─ 确保初始 super admin 存在(否则创建,must_change_password=true)
  ↓
[运维登录前端]
  ↓
登录响应携带 token → 前端调 /auth/me
  ↓
检测到 must_change_password=true → 强制跳 /change-password
  ↓
修改密码后 → 跳测试页 /test/admin-only
  ↓
super admin 可通过 POST /admin/users 创建其他 ADMIN/OPERATOR
```

---

## 9. 前端实施要点

### 9.1 复用与改造

**完全复用参考工程**(`docs/overseas-supply-platform.md` 中的代码):
- `src/app/(auth)/layout.tsx` — 整体壳
- `src/app/(auth)/login/page.tsx` — 登录页 HTML 结构、Tailwind 类、组件、文案、动效
- `src/app/(auth)/register/page.tsx` — 注册页(单页 + 角色选择)
- 按钮、表单、错误提示等视觉元素

**必须改造的部分**:

| 项 | 参考工程 | 本项目 |
|---|---|---|
| 登录方式 | NextAuth Credentials | 直接 fetch 新后端 `/api/v1/auth/login` |
| 注册接口 | 单接口 `/api/auth/register` body 带 role | **双接口** `/api/v1/auth/register/buyer` 和 `/api/v1/auth/register/supplier`,前端按 role 选用 |
| 注册成功跳转 | 自动登录 → dashboard | **不自动登录**,跳 `/login?registered=1`(登录页显示"注册成功,请登录") |
| 登录响应处理 | NextAuth session | 存 token 到 localStorage → 立即调 `/auth/me` 拿完整 user 信息 → 存 Zustand |
| 路由守卫 | `middleware.ts` 基于 NextAuth token | 基于 localStorage token 存在性 |
| 角色名 | BUYER / SUPPLIER | **保持** BUYER / SUPPLIER |
| 品牌名占位 | "基建严选 JIJIAN SELECT" | **品牌名暂留空**,文字部分用 TODO 注释占位(保留布局位置) |
| 公司类型字段 | 注册时有 SOE/PRIVATE 等 | **不要这个字段**(后端 schema 没有) |

### 9.2 路由清单

| 路径 | 说明 |
|---|---|
| `/` | 落地页(本轮简单占位) |
| `/login` | 登录页 |
| `/register` | 注册页(单页 + 角色选择) |
| `/change-password` | 修改密码页(强制改密必经) |
| `/test/buyer-only` | RBAC 测试页 |
| `/test/supplier-only` | RBAC 测试页 |
| `/test/operator-only` | RBAC 测试页 |
| `/test/admin-only` | RBAC 测试页 |

### 9.3 登录后流程

```
登录成功 → 拿到 token → 存 localStorage
  ↓
立即调 /auth/me → 完整 user 信息存 authStore
  ↓
检查 must_change_password
  ├─ true → 跳 /change-password(强制)
  └─ false ↓
根据 roles 跳测试页:
  BUYER    → /test/buyer-only
  SUPPLIER → /test/supplier-only
  OPERATOR → /test/operator-only
  ADMIN    → /test/admin-only
```

### 9.4 Token 管理

- access_token、refresh_token 存 localStorage
- `lib/api.ts` 请求拦截器自动注入 `Authorization: Bearer <token>`
- 401 时自动尝试用 refresh_token 续期一次,失败则清 token 跳 `/login`

### 9.5 RBAC 测试页内容

每个测试页统一展示:

- 当前用户信息(name / email / role)
- 我的权限点列表(全部展示)
- 4 个测试按钮,每个调对应后端接口,显示返回结果或错误码 + trace_id
- 按钮用 `<PermissionGuard>` 或基于 roles 包裹决定显隐

直观验证:**登录什么角色 → 能看到什么按钮 → 点了能拿到 200 还是 403**。

---

## 10. 测试要求

### 10.1 pytest 必须覆盖

**test_auth.py**
- BUYER 注册成功 / email 重复 / 密码不合规
- SUPPLIER 注册成功 / 营业执照号重复
- 注册成功后 **不应自动登录**(无 token 返回)
- 登录:成功(4 个角色都测)/ 密码错 / 用户不存在 / 用户已禁用
- 限流:连续 5 次失败后第 6 次返回 429
- 限流 5 分钟后自动解除
- `/auth/me` 未登录 401,已登录返回完整 user 数据
- 修改密码:旧密码错 / 新密码不合规 / 成功后 must_change_password=false

**test_rbac.py**
- 4 个角色访问各自测试接口 → 200
- 跨角色访问 → 403
- super admin 调 `POST /admin/users` 成功
- 非 ADMIN 调 `POST /admin/users` → 403
- `POST /admin/users` 创建 BUYER → 400(角色不允许)
- 启动同步:数据库手动删除一条 role_permission 后重启,**自动恢复**

**test_audit.py**
- 登录成功/失败/锁定 → 对应记录写入
- 注册 / 创建内部用户 / 改密 / 角色分配 → 写入
- 所有审计 trace_id 非空
- GET 请求 **不写**审计日志

### 10.2 curl 验证脚本(`backend/scripts/verify.sh`)

至少覆盖:
1. `/healthz` 200
2. 注册 BUYER 成功
3. 错误密码登录 → 401
4. 正确登录拿 token
5. 用 token 调 `/auth/me` 拿完整 user
6. 调 `/test/buyer-only` → 200
7. 调 `/test/admin-only` → 403
8. 验证响应头 `X-Trace-Id` 存在

---

## 11. 本地启动

### 前置

- Python 3.11+
- Node.js 20+
- uv
- pnpm

### 后端

```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -e .

cp .env.example .env
# 编辑 .env(JWT_SECRET_KEY / SUPER_ADMIN_*)

alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 访问 http://localhost:8000/docs
```

### 前端

```bash
cd frontend
pnpm install
cp .env.local.example .env.local
# NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

pnpm dev
# 访问 http://localhost:3000
```

### 验证清单

- [ ] 后端 `/docs` 可访问
- [ ] 后端 `/healthz` 200
- [ ] 前端首页可访问
- [ ] super admin 登录 → 强制改密 → 进 admin 测试页
- [ ] super admin 创建一个 OPERATOR,OPERATOR 能登录
- [ ] BUYER 自助注册 → 跳登录页 → 登录 → 进 buyer 测试页
- [ ] SUPPLIER 同上
- [ ] 每个角色访问自己角色测试 API 成功,跨角色 403
- [ ] 连续 5 次错误密码后被锁
- [ ] `audit_logs` 表能查到完整记录
- [ ] 任一响应头取到 X-Trace-Id,搜后端日志和审计表都能找到

---

## 12. 禁止事项(避免常见踩坑)

❌ **不要**用 PostgreSQL / MySQL / MongoDB —— 锁死 SQLite
❌ **不要**用 mock 数据替代真实 DB —— 所有列表必须从数据库查
❌ **不要**用 SQLite 特有语法(如 `INSERT OR REPLACE`)—— 保持 ORM 抽象
❌ **不要**在登录响应里塞 permissions —— 必须通过 `/auth/me` 拿
❌ **不要**在 JWT payload 里塞 permissions —— 权限变更需即时生效
❌ **不要**把权限判断写死在业务代码里(`if role == 'BUYER'`)—— 必须走 `require_permission`
❌ **不要**让 ADMIN 拥有业务数据权限 —— 严格职责分离
❌ **不要**让注册接口自动登录 —— 注册和登录是两个独立动作
❌ **不要**让 `POST /admin/users` 能创建 BUYER/SUPPLIER —— 业务用户走自助注册
❌ **不要**引入 NextAuth、Prisma —— 后端是 FastAPI,前端只做轻量 token 管理
❌ **不要**引入 i18n / next-intl 等库 —— MVP 不做国际化
❌ **不要**做用户头像生成、邮件、短信、OAuth、2FA、找回密码
❌ **不要**做 PWA / SSG / ISR —— 一律动态渲染
❌ **不要**把品牌名硬编码 —— 暂留 TODO 占位
❌ **不要**写测试代码以外的次要功能 —— 不在本文档清单的一律不做

---

## 13. 待团队拍板的决策(代码中需 TODO 标注)

| 决策点 | 当前落地方案 | TODO 位置 |
|---|---|---|
| Q22 角色-权限关系定义方式 | 配置文件 + 启动同步 | `app/rbac/permissions_config.py` |
| Q23 Role.scope 字段 | 引入 scope,MVP 仅用 GLOBAL | `app/db/models/role.py` |
| Q24 OPERATOR 细分 | 不细分 | `app/rbac/permissions_config.py` |
| Q25 ADMIN 业务数据访问 | 严格分离 | `app/rbac/permissions_config.py` |
| Q26 super admin 密码策略 | 环境变量注入 + 强制改密 | `app/seed.py` |
| Q27 何时切换 PostgreSQL | MVP 用 SQLite,等业务起量再评估 | `backend/README.md` |

---

## 14. 验收标准

完成本轮的硬指标:

1. 按 README 步骤,**15 分钟内本地启动成功**(前后端)
2. **4 个角色**全部能登录并访问自己的 RBAC 测试页
3. super admin 首次登录被强制改密,改密后才能继续
4. super admin 能通过 API 创建 OPERATOR/ADMIN,且不能创建 BUYER/SUPPLIER
5. BUYER/SUPPLIER 自助注册成功后跳登录页,**不自动登录**
6. 5 次错误密码触发锁定 5 分钟
7. **pytest 全绿**
8. 任一请求的 `X-Trace-Id` 响应头可在日志和 `audit_logs` 表中关联检索
9. 启动后查 `audit_logs` 表可见 super admin 创建记录(REGISTER 类)

---

## 15. 遇到设计未覆盖时的回滚顺序

1. 查 `docs/RBAC与组织架构设计讨论_v1.2.md` 的"已闭环决策汇总"章节
2. 查 `docs/MVP业务流程共识_v1.2.md`
3. 都没覆盖 → **选最简方案** + 代码标注 `TODO: 设计未覆盖,采用最简实现`
4. **不要**自行扩展功能或发明新规则

---

