# Claude Code 开发任务书:RBAC 基座 · 导航与权限可视化(v3)

> **发送对象**:Claude Code
> **任务定位**:在现有 RBAC 基座(`overseas-platform-v0.1` 仓库)之上,扩展**完整的导航 + 侧边栏 + 占位页骨架 + 权限矩阵全景页 + scope 调试接口 + 启动同步机制**,直观验证四层权限校验机制在 4 个角色下的行为。
> **不是要做业务**——所有 tab 页面都是「权限可视化占位页」,不实现任何业务逻辑、不做表单、不做数据列表、不接业务数据。
> **预计开发时长**:45-60 分钟连续会话
> **交付标准**:用 BUYER / SUPPLIER / OPERATOR / ADMIN 四个种子账号分别登录,导航栏与侧边栏渲染结果不同;点击 tab 进入占位页清晰展示「权限点 / scope / 当前角色是否拥有 / 后端 scope 过滤决策」;ADMIN 后台的「权限矩阵」全景页可视化 4 角色 × N 资源的权限分布。

---

## 0. 背景

### 0.1 现状

现有 RBAC 基座(`/rbac-test` 或类似路由)只验证了**后端 API 权限点**这一层——登录后看到自己有哪些权限点、调几个 role-only 接口看 200/403。

### 0.2 本次补齐:四层校验完整覆盖

| 层 | 校验位置 | 现有 | 本次 |
|---|---|---|---|
| 1. 后端 API 权限点 | `@RequirePermission` | ✅ | 不动 |
| 2. 后端服务层 scope 过滤 | service 层查表 | ❌ | ✅ 新增 |
| 3. 前端路由守卫 | 前端 middleware | ❌ | ✅ 新增 |
| 4. 前端 tab 显隐 | 侧边栏渲染 | ❌ | ✅ 新增 |

1+2 是安全底线,3+4 是 UX。

### 0.3 关键设计原则:权限点 vs scope 两层独立

**这是本次任务最核心的设计约定,所有代码必须遵循:**

- **权限点**:回答「能不能做某个动作」,如 `project:read`
- **scope**:回答「能看/改哪些数据」,取值 `ALL` / `ORG` / `OWN` / `NONE`

**权限点 code 不带 scope 后缀**。`project:read` 就是 `project:read`,**4 个角色拿到的是同一个 code**。差异由后端服务层根据角色查表决定。

| 形式 | 是否采用 |
|---|---|
| `project:read` | ✅ |
| `project:read:own` | ❌ 禁止 |
| `project:read:all` | ❌ 禁止 |

### 0.4 这不是 MVP 业务的开始

这是个**权限可视化基座**。后续真正写业务页面时,会复用本次的 Layout / Sidebar / `<RouteGuard>` / `usePermission` hook / `permission-matrix.ts` 配置 / 后端 `get_scope()` 函数,但**会替换**占位页内容。本次绝不实现任何业务逻辑。

---

## 1. 范围锁死

### 1.1 必做

**前端**:
- 公开区 + 4 套工作台(BUYER / SUPPLIER / OPERATOR / ADMIN)的 Layout
- 每套工作台的**动态侧边栏**(根据权限点 + scope 决定 tab 显隐)
- 顶部 Header(当前用户 / 角色 / 调试模式 toggle / 退出)
- 每个 tab 一个**占位页**,展示 4 个维度信息(详见 §5)
- **前端路由守卫**:无权访问 URL → 跳「无权访问」页
- **调试开关**:Header 上的 toggle 切换「线上模式(隐藏无权 tab)」/「调试模式(显示但置灰)」,默认调试模式开启
- **ADMIN 新增「权限矩阵」全景页**(详见 §6)

**后端**:
- **启动同步机制**:服务启动时根据配置文件自动同步 Permission / RolePermission 表(详见 §10)
- **scope 调试接口** `/api/_debug/scope?resource={resource}`:返回当前用户对该资源的权限点检查 + scope + 模拟 SQL 过滤条件,**不返回真实业务数据**
- 后端 `get_scope(user, permission)` 查表函数

### 1.2 不做

❌ 不实现任何业务功能
❌ 不接 mock 业务数据
❌ 不做按钮级显隐的具体业务案例
❌ 不做权限管理后台 UI
❌ 不动 RBAC 5 张表 schema
❌ 不引入新的 UI 组件库或图表库
❌ 不做面包屑、多级折叠菜单、tab 搜索框
❌ 不做移动端响应式

### 1.3 与现有 `/rbac-test` 的关系

保留 `/rbac-test` 作为「API 层权限点验证页」,挂在 ADMIN 侧边栏「RBAC 调试」分组下。不重写它。

---

## 2. MVP 资源域定义(权威清单)

| 资源域 code | 中文名 | 所属 module | 说明 |
|---|---|---|---|
| `supplier` | 供应商档案 | 业务-档案 | 供应商基础信息、资质 |
| `product` | 商品 SKU | 业务-档案 | 商品基础信息、阶梯报价 |
| `country` | 国别准入 | 业务-档案 | 8 国 × 品类准入规则 |
| `project` | 项目 | 业务-交易 | 采购方项目 |
| `purchase_list` | 采购清单 | 业务-交易 | 项目下的采购清单 |
| `cart` | 购物车 | 业务-交易 | 采购方购物车 |
| `rfq` | 询价单 | 业务-交易 | RFQ 主体 |
| `quote` | 报价 | 业务-交易 | 供应商对 RFQ 的报价 |
| `order` | 订单 | 业务-交易 | 含订单主体 + 12 节点履约 + 单据 |
| `membership` | 会员/缴费 | 业务-供应商 | 供应商会员状态、缴费记录 |
| `risk` | 风控驾驶舱 | 业务-运营 | 马甲图谱、价格异常、合规雷达 |
| `user` | 用户管理 | 系统 | ADMIN 管理用户 |
| `role` | 角色管理 | 系统 | ADMIN 管理角色 |
| `permission` | 权限管理 | 系统 | ADMIN 管理权限点 |
| `system` | 系统配置/审计 | 系统 | 系统配置、操作日志 |

**合计 15 个资源域**。

---

## 3. 完整权限点 × 角色矩阵(写入配置文件)

权限点 code 形式固定为 `<resource>:<action>`,**不带 scope 后缀**。

| 资源域 | 权限点 code | BUYER | SUPPLIER | OPERATOR | ADMIN |
|---|---|---|---|---|---|
| supplier | `supplier:read` | ✅ | ✅ | ✅ | ❌ |
| supplier | `supplier:write` | ❌ | ✅ | ❌ | ❌ |
| supplier | `supplier:approve` | ❌ | ❌ | ✅ | ❌ |
| supplier | `supplier:reject` | ❌ | ❌ | ✅ | ❌ |
| product | `product:read` | ✅ | ✅ | ✅ | ❌ |
| product | `product:write` | ❌ | ✅ | ❌ | ❌ |
| product | `product:approve` | ❌ | ❌ | ✅ | ❌ |
| product | `product:reject` | ❌ | ❌ | ✅ | ❌ |
| country | `country:read` | ✅ | ✅ | ✅ | ❌ |
| country | `country:write` | ❌ | ❌ | ✅ | ❌ |
| project | `project:read` | ✅ | ❌ | ✅ | ❌ |
| project | `project:write` | ✅ | ❌ | ❌ | ❌ |
| purchase_list | `purchase_list:read` | ✅ | ❌ | ✅ | ❌ |
| purchase_list | `purchase_list:write` | ✅ | ❌ | ❌ | ❌ |
| cart | `cart:read` | ✅ | ❌ | ❌ | ❌ |
| cart | `cart:write` | ✅ | ❌ | ❌ | ❌ |
| rfq | `rfq:read` | ✅ | ✅ | ✅ | ❌ |
| rfq | `rfq:create` | ✅ | ❌ | ❌ | ❌ |
| rfq | `rfq:respond` | ❌ | ✅ | ❌ | ❌ |
| quote | `quote:read` | ✅ | ✅ | ✅ | ❌ |
| quote | `quote:write` | ❌ | ✅ | ❌ | ❌ |
| order | `order:read` | ✅ | ✅ | ✅ | ❌ |
| order | `order:write` | ✅ | ✅ | ❌ | ❌ |
| order | `order:checkin` | ❌ | ✅ | ❌ | ❌ |
| membership | `membership:read` | ❌ | ✅ | ✅ | ❌ |
| membership | `membership:write` | ❌ | ✅ | ❌ | ❌ |
| risk | `risk:read` | ❌ | ❌ | ✅ | ❌ |
| user | `user:manage` | ❌ | ❌ | ❌ | ✅ |
| role | `role:manage` | ❌ | ❌ | ❌ | ✅ |
| permission | `permission:manage` | ❌ | ❌ | ❌ | ✅ |
| system | `system:config` | ❌ | ❌ | ❌ | ✅ |
| system | `system:audit` | ❌ | ❌ | ❌ | ✅ |

**合计 32 个权限点**。每个权限点的 `module` 字段对应所属资源域(用于侧边栏分组)。

### 3.1 关键约束

- **OPERATOR 不访问系统资源**(user/role/permission/system 全 ❌)
- **ADMIN 不访问业务资源**(所有 supplier/product/order 等业务域全 ❌)
- 业务审核审批(approve / reject)归 OPERATOR,不归 ADMIN
- 公开池资源(supplier/product/country)给业务相关三角色都开放 read,差异在 scope 不在权限点

---

## 4. scope 映射(写入配置文件)

| 资源域 | BUYER | SUPPLIER | OPERATOR | ADMIN |
|---|---|---|---|---|
| supplier | ALL | OWN | ALL | NONE |
| product | ALL | OWN | ALL | NONE |
| country | ALL | ALL | ALL | NONE |
| project | ORG | NONE | ALL | NONE |
| purchase_list | ORG | NONE | ALL | NONE |
| cart | OWN | NONE | NONE | NONE |
| rfq | ORG | OWN | ALL | NONE |
| quote | ORG | OWN | ALL | NONE |
| order | ORG | OWN | ALL | NONE |
| membership | NONE | OWN | ALL | NONE |
| risk | NONE | NONE | ALL | NONE |
| user | NONE | NONE | NONE | ALL |
| role | NONE | NONE | NONE | ALL |
| permission | NONE | NONE | NONE | ALL |
| system | NONE | NONE | NONE | ALL |

### 4.1 scope 含义

| scope | 含义 | SQL 行为 |
|---|---|---|
| `ALL` | 全平台数据 | 无 WHERE 过滤 |
| `ORG` | 本组织数据 | `WHERE buyer_organization_id = current_user.organization_id` |
| `OWN` | 本人/本企业数据 | `WHERE supplier_id = current_user.supplier_id` 或 `WHERE user_id = current_user.id` |
| `NONE` | 无访问权(权限点已拦截,不应走到这里) | — |

### 4.2 scope 实现边界

**scope 是简单查表函数,不是策略引擎**。明确不做:

- 多条 scope 规则按优先级匹配
- scope 值支持自定义表达式或 DSL
- 运行时动态变更 scope 映射
- 通用 SQL 过滤条件生成器

实现形式即:`(角色, 权限点) → scope 值` 的静态映射 + 三五个 if/else 分支组装 WHERE。

---

## 5. 单一可信源:`permission-matrix.ts`

**所有权限相关的展示、校验、过滤,都从这一个文件读**。建议路径 `src/config/permission-matrix.ts`(以现有项目约定为准)。

```typescript
// 资源域定义
export const RESOURCES = {
  supplier:       { code: 'supplier',       name: '供应商档案',  module: '业务-档案' },
  product:        { code: 'product',        name: '商品 SKU',   module: '业务-档案' },
  country:        { code: 'country',        name: '国别准入',   module: '业务-档案' },
  project:        { code: 'project',        name: '项目',       module: '业务-交易' },
  purchase_list:  { code: 'purchase_list',  name: '采购清单',   module: '业务-交易' },
  cart:           { code: 'cart',           name: '购物车',     module: '业务-交易' },
  rfq:            { code: 'rfq',            name: '询价单',     module: '业务-交易' },
  quote:          { code: 'quote',          name: '报价',       module: '业务-交易' },
  order:          { code: 'order',          name: '订单',       module: '业务-交易' },
  membership:     { code: 'membership',     name: '会员',       module: '业务-供应商' },
  risk:           { code: 'risk',           name: '风控驾驶舱', module: '业务-运营' },
  user:           { code: 'user',           name: '用户管理',   module: '系统' },
  role:           { code: 'role',           name: '角色管理',   module: '系统' },
  permission:     { code: 'permission',     name: '权限管理',   module: '系统' },
  system:         { code: 'system',         name: '系统配置',   module: '系统' },
} as const;

// 角色 × 资源 → scope 映射(来自 §4)
export const ROLE_RESOURCE_SCOPE = {
  BUYER: {
    supplier: 'ALL', product: 'ALL', country: 'ALL',
    project: 'ORG', purchase_list: 'ORG', cart: 'OWN',
    rfq: 'ORG', quote: 'ORG', order: 'ORG',
    membership: 'NONE', risk: 'NONE',
    user: 'NONE', role: 'NONE', permission: 'NONE', system: 'NONE',
  },
  SUPPLIER: {
    supplier: 'OWN', product: 'OWN', country: 'ALL',
    project: 'NONE', purchase_list: 'NONE', cart: 'NONE',
    rfq: 'OWN', quote: 'OWN', order: 'OWN',
    membership: 'OWN', risk: 'NONE',
    user: 'NONE', role: 'NONE', permission: 'NONE', system: 'NONE',
  },
  OPERATOR: {
    supplier: 'ALL', product: 'ALL', country: 'ALL',
    project: 'ALL', purchase_list: 'ALL', cart: 'NONE',
    rfq: 'ALL', quote: 'ALL', order: 'ALL',
    membership: 'ALL', risk: 'ALL',
    user: 'NONE', role: 'NONE', permission: 'NONE', system: 'NONE',
  },
  ADMIN: {
    supplier: 'NONE', product: 'NONE', country: 'NONE',
    project: 'NONE', purchase_list: 'NONE', cart: 'NONE',
    rfq: 'NONE', quote: 'NONE', order: 'NONE',
    membership: 'NONE', risk: 'NONE',
    user: 'ALL', role: 'ALL', permission: 'ALL', system: 'ALL',
  },
} as const;

// 角色 × 资源 → 持有的权限点列表(来自 §3)
export const ROLE_RESOURCE_PERMISSIONS = {
  BUYER: {
    supplier: ['supplier:read'],
    product: ['product:read'],
    country: ['country:read'],
    project: ['project:read', 'project:write'],
    purchase_list: ['purchase_list:read', 'purchase_list:write'],
    cart: ['cart:read', 'cart:write'],
    rfq: ['rfq:read', 'rfq:create'],
    quote: ['quote:read'],
    order: ['order:read', 'order:write'],
  },
  // SUPPLIER / OPERATOR / ADMIN 按 §3 表格完整填充
  // ...
} as const;
```

### 5.1 四处使用

- **前端**:渲染侧边栏 / 矩阵全景页 / 占位页信息
- **后端 scope resolver**:`get_scope(user, permission)` 读 `ROLE_RESOURCE_SCOPE`
- **启动同步**:服务启动时读 `ROLE_RESOURCE_PERMISSIONS`,自动同步到 Permission / RolePermission 表
- **调试接口**:`/api/_debug/scope` 基于此配置返回响应

**改一次,四处同步**。

---

## 6. 占位页统一模板

每个 tab 进去都长一样,只有字段不同。统一组件 `<PermissionPlaceholderPage />`:

```tsx
<PermissionPlaceholderPage
  title="项目管理"
  route="/buyer/projects"
  resource="project"
  requiredPermissions={['project:read']}
  description="(占位)未来此页面将展示项目列表、创建项目、查看项目详情"
/>
```

### 6.1 占位页 4 个维度

```
┌──────────────────────────────────────────────────────────┐
│  📋 项目管理                                                │
│  业务-交易 · /buyer/projects                                │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  【维度 1:页面访问】 ✅ 你有权访问此页面                       │
│                                                            │
│  【维度 2:权限点】(动作许可)                                │
│      要求权限点:    project:read                            │
│      当前用户:      zhang@cscec3b.com                       │
│      当前角色:      BUYER                                    │
│      权限点检查:    ✅ 已拥有                                 │
│                                                            │
│  【维度 3:数据范围】(数据边界 / scope)                      │
│      数据范围:      ORG                                     │
│      矩阵图符号:    ◎ 己(对应权限矩阵图中的"仅本组织数据")    │
│      范围说明:      仅本采购组织的项目                         │
│                                                            │
│  【维度 4:后端验证】(点击调试)                              │
│      [ 🔧 调用 scope 调试接口 ]                              │
│      ↓ 点击后展示后端返回的 JSON                              │
│                                                            │
│  ─────────────────────────────────────────                 │
│  (占位)未来此页面将展示项目列表、创建项目、查看项目详情。       │
│                                                            │
└──────────────────────────────────────────────────────────┘
```

### 6.2 调试按钮行为

点击「调用 scope 调试接口」→ 前端调 `GET /api/_debug/scope?resource=project` → 后端返回:

```json
{
  "user": "zhang@cscec3b.com",
  "role": "BUYER",
  "resource": "project",
  "permission_check": {
    "required": "project:read",
    "passed": true
  },
  "scope_resolved": "ORG",
  "would_apply_filter": "WHERE buyer_organization_id = 'org_xxx'",
  "explanation": "你是 BUYER,根据 ROLE_RESOURCE_SCOPE 配置,project 域的 scope 是 ORG,后端服务层会自动按你所属的 BuyerOrganization 过滤"
}
```

前端把这段 JSON **格式化显示在按钮下方**(不要弹 alert,要内嵌展示,方便截图)。

### 6.3 无权访问的占位页

如果用户硬闯到了无权 URL(调试模式下可能进得来),占位页显示**红色边框 + ❌ 标识**:

- 维度 1 显示 ❌ 你没有此权限点
- 维度 3 数据范围显示 `NONE`,矩阵符号 `× 无`
- 调试按钮仍可点,后端返回 `permission_check.passed: false`

---

## 7. 权限矩阵全景页(ADMIN 后台新增)

### 7.1 路由

`/admin/permission-matrix`

### 7.2 页面内容

**4 行(角色) × 15 列(资源域)的网格**,每个格子根据 `ROLE_RESOURCE_SCOPE` + `ROLE_RESOURCE_PERMISSIONS` 显示符号:

| 符号 | 含义 | 触发条件 |
|---|---|---|
| ✓ 全 | 完全权限(CRUD) | 拥有 read + write/create/update/delete + scope = ALL |
| 📖 读 | 只读 | 仅有 read 权限点 + scope = ALL |
| ◎ 己 | 仅自己/本组织 | 任意权限点 + scope = OWN 或 ORG |
| ★ 管 | 管理权限(审核/配置) | 拥有 approve/reject/manage/config 类权限点 |
| × 无 | 无权限 | scope = NONE |

### 7.3 配色

- 「全」绿色背景
- 「读」浅蓝色背景
- 「己」橙色背景
- 「管」紫色背景
- 「无」浅红色背景

### 7.4 交互

- **点击任一格** → 弹窗显示该角色对该资源的:
  - 完整权限点列表
  - scope 值
  - 数据范围说明
- 顶部图例栏说明 5 种符号
- 底部文字框,列出 RBAC 三条核心原则

---

## 8. 侧边栏行为规范

### 8.1 渲染逻辑

| 调试开关 | 该资源 scope ≠ NONE | 该资源 scope = NONE |
|---|---|---|
| **线上模式** | ✅ 正常显示,可点击 | ❌ 完全不渲染 |
| **调试模式(默认)** | ✅ 正常显示,可点击 | ⚠️ 显示但置灰 + 角标「scope=NONE」+ 不可点击 |

### 8.2 侧边栏分组

按 `module` 字段分组,组标题与 Permission 表的 `module` 一致。

不同角色登录看到的「主要工作台」不同,**调试模式下能看到所有工作台**(无权部分置灰):

- BUYER → 公开区 + BUYER 工作台(高亮)+ 其他工作台(置灰)
- SUPPLIER → 公开区 + SUPPLIER 工作台(高亮)+ 其他(置灰)
- OPERATOR → 公开区 + OPERATOR 后台(高亮)+ 其他(置灰)
- ADMIN → 公开区(只读)+ ADMIN 后台(高亮)+ 其他(置灰)

### 8.3 顶部 Header

```
┌──────────────────────────────────────────────────────────────┐
│  [Logo] 海外严选平台   [调试模式 ●]   zhang@... [BUYER] [退出]  │
└──────────────────────────────────────────────────────────────┘
```

---

## 9. 完整路由表

### 9.1 公开区

| 路由 | 名称 | 占位 resource |
|---|---|---|
| `/` | 平台首页 | (无,落地页) |
| `/mall` | 严选商城 | `product` |
| `/suppliers` | 供应商目录 | `supplier` |
| `/countries` | 国别准入 | `country` |
| `/login` | 登录 | (保留现有) |

### 9.2 BUYER 工作台 `/buyer/*`

| 路由 | 名称 | resource | 主要权限点 |
|---|---|---|---|
| `/buyer/dashboard` | 工作台 | - | (无,只看登录) |
| `/buyer/projects` | 项目管理 | `project` | `project:read` |
| `/buyer/purchase-lists` | 采购清单 | `purchase_list` | `purchase_list:read` |
| `/buyer/cart` | 购物车 | `cart` | `cart:read` |
| `/buyer/rfqs` | 询价管理 | `rfq` | `rfq:read` |
| `/buyer/orders` | 订单管理 | `order` | `order:read` |

### 9.3 SUPPLIER 工作台 `/supplier/*`

| 路由 | 名称 | resource | 主要权限点 |
|---|---|---|---|
| `/supplier/dashboard` | 工作台 | - | - |
| `/supplier/onboarding` | 入驻向导 | `supplier` | `supplier:write` |
| `/supplier/membership` | 会员中心 | `membership` | `membership:read` |
| `/supplier/products` | 商品管理 | `product` | `product:read` |
| `/supplier/rfqs` | RFQ 收件箱 | `rfq` | `rfq:respond` |
| `/supplier/quotes` | 我的报价 | `quote` | `quote:read` |
| `/supplier/orders` | 订单管理 | `order` | `order:read` |
| `/supplier/profile` | 我的档案 | `supplier` | `supplier:read` |

### 9.4 OPERATOR 后台 `/operator/*`

| 路由 | 名称 | resource | 主要权限点 |
|---|---|---|---|
| `/operator/dashboard` | 管理首页 | - | - |
| `/operator/supplier-review` | 供应商审核 | `supplier` | `supplier:approve` |
| `/operator/product-review` | 商品审核 | `product` | `product:approve` |
| `/operator/orders` | 订单总览 | `order` | `order:read` |
| `/operator/countries` | 国别数据维护 | `country` | `country:write` |
| `/operator/risk-cockpit` | 风控驾驶舱 | `risk` | `risk:read` |

### 9.5 ADMIN 后台 `/admin/*`

| 路由 | 名称 | resource | 主要权限点 |
|---|---|---|---|
| `/admin/users` | 用户管理 | `user` | `user:manage` |
| `/admin/roles` | 角色管理 | `role` | `role:manage` |
| `/admin/permissions` | 权限管理 | `permission` | `permission:manage` |
| `/admin/config` | 系统配置 | `system` | `system:config` |
| `/admin/permission-matrix` | **权限矩阵全景**(新建) | - | (任意已登录) |
| `/admin/rbac-test` | RBAC API 调试(保留) | - | (任意已登录) |

---

## 10. 启动同步机制

### 10.1 角色-权限关系的可信源

**角色-权限关联(RolePermission 表数据)的可信源是 `permission-matrix.ts`,不是数据库。**

数据库中的 Permission 表 + RolePermission 表照常存在,但表中数据由程序在**服务启动时**根据配置文件自动同步。任何在数据库中手动修改的关联,下次启动会被覆盖。

### 10.2 同步函数行为

服务启动时执行 `syncPermissionsToDB()`,行为:

| 比对结果 | 同步动作 |
|---|---|
| 配置有,DB 无 | INSERT |
| 配置有,DB 有 | 跳过(已一致) |
| 配置无,DB 有 | DELETE |

#### 同步约束

- **作用对象限定**:仅 Permission 表 + RolePermission 表。**不触碰任何其他表**(User、UserRole、Role、业务数据均不受影响)。
- **幂等**:连续执行 N 次,结果一致。
- **可观测**:输出差异统计 + 耗时。

启动日志输出格式:

```
[Permission Sync] permissions: +5 / -1 / 27 unchanged
[Permission Sync] role_permissions: +12 / -3 / 89 unchanged
[Permission Sync] done in 142ms
```

### 10.3 dry-run 模式

通过环境变量 `PERMISSION_SYNC_MODE=dry_run` 启用。

启用后,启动同步只输出差异报告,不执行 INSERT / DELETE。dry-run 模式下服务正常启动并对外提供请求(DB 中现有权限数据继续生效),仅同步动作被跳过。

```
[Permission Sync] DRY RUN - no changes will be applied
[Permission Sync] would add: product:export, product:import
[Permission Sync] would remove: product:legacy_action
[Permission Sync] would add 4 role_permissions for OPERATOR
```

### 10.4 seed 与启动同步的职责分工

| 数据 | 由谁创建 |
|---|---|
| Role 表(4 个角色定义) | seed |
| Permission 表 | **启动同步** |
| RolePermission 表 | **启动同步** |
| BuyerOrganization 占位 | seed |
| 初始 super admin 账号 | seed |
| UserRole(种子账号) | seed |

**seed 不再写 Permission / RolePermission 数据**。

---

## 11. 前端路由守卫

实现 `<RouteGuard requiredPermissions={['xxx']}>` 或 middleware:

- 检查 session.permissions 是否包含全部 `requiredPermissions`
- 不包含 → 重定向到 `/no-permission?required=xxx&route=xxx`
- 公开区路由不走守卫

**注意**:这是 UX 层防护,不是安全机制。后端 API 守卫 + 服务层 scope 过滤仍是底线。

---

## 12. scope 调试接口(后端)

### 12.1 接口定义

```
GET /api/_debug/scope?resource={resource_code}

Header: Authorization: Bearer {token}

Response 200:
{
  "user": "zhang@cscec3b.com",
  "role": "BUYER",
  "resource": "project",
  "permission_check": {
    "required": "project:read",
    "passed": true,
    "explanation": "BUYER 角色拥有 project:read 权限点"
  },
  "scope_resolved": "ORG",
  "would_apply_filter": "WHERE buyer_organization_id = 'org_xxx'",
  "explanation": "你是 BUYER,根据 ROLE_RESOURCE_SCOPE 配置,project 域的 scope 是 ORG,后端服务层会自动按你所属的 BuyerOrganization 过滤数据"
}
```

### 12.2 实现要求

- **不返回任何业务数据**,只返回 scope 决策信息
- `permission_check` 字段返回该资源的「主要 read 权限点」是否拥有(如 `project:read`)
- `would_apply_filter` 是**字符串展示**,不真正执行 SQL
- 接口需要登录(401 未登录),但**所有已登录用户都能调**(无权限点要求,因为这是调试接口)

### 12.3 路径约定

`/api/_debug/*` 前缀的接口在生产环境**默认禁用**,通过环境变量 `ENABLE_DEBUG_API=true` 开启。本任务在 dev 环境默认开启。

---

## 13. 视觉风格

沿用现有 v0.1 风格(浅色卡片 + 圆角 + 灰底):

- 背景 `#F5F7FA`
- 卡片白色 + 圆角 16-20px + 轻阴影
- 标题深色加粗,正文偏淡
- 角色徽章用橙色(`#FF6B35`)
- 深色按钮用海军蓝
- 权限点 code 用等宽字体(monospace)

**严格沿用,不要重新设计**。

---

## 14. 验收清单

### 14.1 基础

- [ ] `npm run dev` 启动后,4 个种子账号都能登录
- [ ] Header 显示当前邮箱 + 角色徽章 + 调试模式 toggle
- [ ] 启动日志包含 `[Permission Sync]` 输出

### 14.2 启动同步

- [ ] 首次启动(空 DB)→ Permission 表 + RolePermission 表被自动填满
- [ ] 删除 `permission-matrix.ts` 中一个权限点 → 重启 → DB 中对应记录自动删除
- [ ] 给某角色加一个权限点 → 重启 → DB 中对应 RolePermission 自动新增
- [ ] 连续启动 3 次,DB 状态一致(幂等性)
- [ ] `PERMISSION_SYNC_MODE=dry_run` 启动 → 输出差异报告但不修改 DB

### 14.3 侧边栏(调试模式开启,默认)

- [ ] BUYER 登录 → BUYER 工作台 tab 可点击;其他工作台 tab 置灰
- [ ] SUPPLIER 登录 → SUPPLIER 工作台 tab 可点击;其他置灰
- [ ] OPERATOR 登录 → OPERATOR 后台 tab 可点击;其他置灰
- [ ] ADMIN 登录 → ADMIN 后台 tab 可点击;业务工作台全部置灰
- [ ] hover 置灰 tab → 显示「scope=NONE,缺 `xxx:xxx` 权限点」

### 14.4 侧边栏(调试模式关闭)

- [ ] 各角色只看到自己有权访问的 tab,其他完全不渲染

### 14.5 占位页(4 维度齐全)

- [ ] 点击任一可访问 tab → 进入占位页,显示路由、权限点、用户、是否拥有、scope、矩阵符号
- [ ] 点击「调用 scope 调试接口」→ 后端返回 JSON 渲染在按钮下方
- [ ] 同一占位页 4 个角色登录看到的 scope 不同:
  - BUYER 访问 `/buyer/projects` → scope=ORG
  - OPERATOR 访问 `/operator/orders` → scope=ALL
  - SUPPLIER 访问 `/supplier/orders` → scope=OWN

### 14.6 路由守卫

- [ ] BUYER 登录后访问 `/admin/users` → 跳 `/no-permission`,提示缺 `user:manage`
- [ ] BUYER 登录后访问 `/supplier/onboarding` → 跳 `/no-permission`,提示缺 `supplier:write`
- [ ] 公开区 `/`、`/mall`、`/suppliers`、`/countries` 未登录可访问

### 14.7 权限矩阵全景页

- [ ] `/admin/permission-matrix` 仅 ADMIN 可访问,其他角色跳 `/no-permission`
- [ ] 矩阵图渲染 4 角色 × 15 资源域,符号与配置一致
- [ ] 点击任一格弹窗,显示权限点列表 + scope 值 + 范围说明

### 14.8 scope 调试接口

- [ ] `GET /api/_debug/scope?resource=project` 在 BUYER 登录下返回 scope=ORG
- [ ] 同接口 OPERATOR 登录返回 scope=ALL
- [ ] 同接口 ADMIN 登录返回 scope=NONE + permission_check.passed=false
- [ ] 未登录调用返回 401

### 14.9 保留

- [ ] 原 `/rbac-test` 仍可访问,挂在 ADMIN 侧边栏「RBAC 调试」分组下
- [ ] ADMIN 侧边栏「RBAC 调试」分组包含两项:`/admin/rbac-test` + `/admin/permission-matrix`

### 14.10 代码质量

- [ ] `permission-matrix.ts` 是单一可信源,前端 + 后端 + 启动同步 + 调试接口都从此读取
- [ ] 没有引入新的第三方依赖
- [ ] 权限点 code 100% 不带 scope 后缀(grep `:own` `:all` `:org` 应无匹配)
- [ ] seed 中不包含 Permission / RolePermission 数据(由启动同步管理)

---

## 15. 开发顺序

### Phase 1:配置 + seed + 启动同步(25 分钟)

1. 创建 `permission-matrix.ts` 单一可信源
2. 读现有 seed,列出当前所有 Permission code → 与 §3 做差异对比,**报告给用户并等待确认**
3. **改造 seed**:移除 Permission / RolePermission 写入,只保留 Role / User / UserRole / BuyerOrganization
4. 实现 `syncPermissionsToDB()` 同步函数 + dry-run 模式
5. 实现后端 `get_scope(user, permission)` 查表函数
6. **首次验证**:清空 DB → 启动服务 → 检查 Permission / RolePermission 表被正确填充

### Phase 2:前端骨架(20 分钟)

7. 实现 `<RouteGuard>` 组件 + `usePermission` hook
8. 实现 `<AppHeader>` + `<AppSidebar>`(动态渲染 + 置灰逻辑)
9. 4 套 Layout 接入 Header + Sidebar
10. 实现 `<PermissionPlaceholderPage>` 组件(4 维度展示)
11. 创建 §9 列出的所有 tab 路由 + 占位页

### Phase 3:scope 调试与矩阵全景(15 分钟)

12. 实现 `/api/_debug/scope` 调试接口
13. 占位页接入「调用 scope 调试接口」按钮 + JSON 渲染
14. 实现 `/admin/permission-matrix` 全景页 + 弹窗交互

### Phase 4:验收(5 分钟)

15. 跑一遍验收清单
16. 修明显 bug

---

## 16. 禁止事项

❌ **不要**在权限点 code 里加 scope 后缀(`:own` / `:all` / `:org`)
❌ **不要**在占位页或调试接口里返回 mock 业务数据
❌ **不要**改 RBAC 5 张表的 schema
❌ **不要**引入新的 UI 组件库或图表库
❌ **不要**做权限编辑后台(创建/修改角色权限的 UI)
❌ **不要**做按钮级显隐的具体业务案例
❌ **不要**做移动端响应式
❌ **不要**把 `ROLE_RESOURCE_SCOPE` 散落在多处定义,必须只在 `permission-matrix.ts` 一处
❌ **不要**在 seed 中写 Permission / RolePermission 数据,这两张表由启动同步管理
❌ **不要**实现「策略引擎」类的 scope 系统(多规则、优先级、表达式、DSL),scope 只是简单查表

---

## 17. 开始指引

第一步:

1. `git pull` 同步现有代码
2. 列出 `src/` 目录结构
3. 读现有 seed 文件,输出当前所有 Permission code 清单
4. 与本任务书 §3 做映射并报告差异(哪些是现有的、哪些需要新增、哪些需要删除/重命名)
5. **等用户确认 seed 改造方案后**,再开始写代码

**不要直接开干,先对齐 seed**。

如果遇到设计取舍:**可演示性 > 调试友好性 > 代码优雅性 > 视觉精致度**

如果发现本任务书与现有代码冲突,**先报告,不强行覆盖**。
