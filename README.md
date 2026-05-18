# 央企海外工程供应链平台 · v0.1

> MVP 第一轮:认证、RBAC、审计底座(后续业务模块在 `docs/prompts/` 中陆续上线)。

## 一键启动(开发模式)

### 0. PostgreSQL(本机 brew @16,端口 5433)

```bash
brew install postgresql@16
# 改 /opt/homebrew/var/postgresql@16/postgresql.conf 中 port=5433(避 EnterpriseDB pg13 占的 5432)
brew services start postgresql@16
/opt/homebrew/opt/postgresql@16/bin/createdb -p 5433 overseas_supply_dev
/opt/homebrew/opt/postgresql@16/bin/createdb -p 5433 overseas_supply_test
```

### 1. 后端

```bash
cd backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env       # 务必生成 JWT_SECRET_KEY:openssl rand -hex 32
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- API 文档:http://localhost:8000/docs
- 健康检查:http://localhost:8000/healthz

启动会自动同步 RBAC、创建中建三局组织,以及 super admin(`must_change_password=true`)。

### 2. 前端

```bash
cd frontend
pnpm install
cp .env.local.example .env.local
pnpm dev    # http://localhost:3000
```

### 3. 端到端验证

```bash
cd backend
bash scripts/verify.sh
```

也可以直接走 UI:

1. 打开 http://localhost:3000
2. super admin 登录 → 强制改密 → 进 `/test/admin-only`
3. 自助注册 BUYER → 跳登录页 → 登录 → 进 `/test/buyer-only`
4. 自助注册 SUPPLIER → 同上

## 本轮交付清单

| 维度 | 完成项 |
|---|---|
| 后端 | FastAPI + SQLAlchemy 2.0 async + Alembic + PostgreSQL 16 + uv |
| 表 | 10 张(User / Role / Permission / UserRole / RolePermission / BuyerOrg / SupplierOrg / BuyerMember / SupplierMember / AuditLog)|
| 接口 | 注册(BUYER/SUPPLIER 各一个)/ 登录 / `/auth/me` / 改密 / 登出 / 内部账号创建+列表 / 4 个 RBAC 测试 |
| 安全 | 密码 8-32 位 1 字母 1 数字、登录限流 60s 内 5 次锁 5 分钟、JWT 不带 permissions、`/auth/me` 实时权威 |
| 审计 | Trace ID 全链路、敏感操作写库、GET 不写、错误也写 |
| 前端 | Next.js + TS + Tailwind + shadcn 风格,登录/注册/改密/4 个 RBAC 测试页 |
| 测试 | pytest 33 用例全绿 |

## 不在本轮范围

- ❌ Docker / 部署 / CI/CD
- ❌ 邮件、找回密码、OAuth、2FA
- ❌ 业务页面(项目、采购清单、RFQ、订单等)
- ❌ 审计日志查询 UI / 权限管理 UI / 用户管理 UI
- ❌ Redis、缓存、国际化、PWA

## 目录结构

```
overseas-platform-v0.1/
├── backend/              FastAPI 后端(详见 backend/README.md)
├── frontend/             Next.js 前端(详见 frontend/README.md)
├── docs/                 设计文档
│   ├── MVP业务流程共识_v1.2.md
│   └── RBAC与组织架构设计讨论_v1.2.md
├── RBAC与组织架构设计_v0.1.md   本轮实施 prompt
├── CLAUDE.md             给 Claude Code 的项目级指令
└── README.md             本文件
```

## 设计文档

每次开发前必读(顺序):

1. `docs/MVP业务流程共识_v1.2.md` —— 整体业务范围、5 条主流程、AI 占位约定
2. `docs/RBAC与组织架构设计讨论_v1.2.md` —— RBAC 设计、组织模型、已闭环决策汇总
3. `RBAC与组织架构设计_v0.1.md` —— 本轮实施 prompt(细到接口契约)

## 待团队拍板(代码中已 TODO 标注)

| 编号 | 决策 | 当前方案 |
|---|---|---|
| Q22 | 角色-权限关系定义方式 | 配置文件 + 启动同步 |
| Q23 | Role.scope 字段 | 引入字段,MVP 仅 GLOBAL |
| Q24 | OPERATOR 是否细分 | 不细分 |
| Q25 | ADMIN 能否访问业务数据 | 严格分离 |
| Q26 | super admin 密码策略 | 环境变量注入 + 强制改密 |
| Q27 | 何时切 PostgreSQL | ✅ 已切(2026-05-18,brew @16 端口 5433) |
