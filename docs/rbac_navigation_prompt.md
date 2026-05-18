# Claude Code 开发任务书:RBAC 基座 · 导航与侧边栏权限可视化

> **发送对象**:Claude Code
> **任务定位**:在现有 RBAC 基座(`overseas-platform-v0.1` 仓库)之上,**扩展一个完整的导航 + 侧边栏 + 占位页面骨架**,用于直观验证「前端路由守卫 / 前端 tab 显隐 / 后端 API 权限」**三级权限校验**在 4 个角色下的行为是否一致。
> **不是要做业务**——所有 tab 页面都是「权限可视化占位页」,不实现任何业务逻辑、不做表单、不做数据列表、不接业务 API。
> **预计开发时长**:30-45 分钟连续会话
> **交付标准**:用 PURCHASER / SUPPLIER / OPERATOR / ADMIN 四个种子账号分别登录,导航栏与侧边栏渲染结果不同;点击 tab 进入对应占位页,页面上**清晰展示「需要的权限点 / 当前角色是否拥有 / 实际渲染结果」**。

---

## 0. 背景与定位(必读)

现有的 RBAC 测试页(`/rbac-test` 或类似路由)只能验证**后端 API 维度**的权限——登录后看到自己有哪些权限点、调 4 个 role-only 接口看 200/403。这只覆盖了 RBAC 三级校验中的第 1 级。

本次任务是把另外两级补上:

| 级别 | 校验位置 | 现有覆盖 | 本次新增 |
|---|---|---|---|
| 1 | 后端 API 守卫 | ✅ 已有「调用 4 个角色接口」 | 不动 |
| 2 | 前端路由守卫 | ❌ 缺失 | ✅ 直接访问 URL 无权时跳走/拦截 |
| 3 | 前端 tab/按钮显隐 | ❌ 缺失 | ✅ 侧边栏按权限点动态渲染 |

**这是一个权限可视化基座,不是 MVP 业务的开始**。后续真正写业务页面时,会**复用本次的 Layout、Sidebar、权限 Hook**,但**替换**占位页内容。

---

## 1. 范围锁死(从最小可行性出发)

### 1.1 必做

- 公开区(未登录可见) + 4 套工作台(BUYER / SUPPLIER / OPERATOR / ADMIN)的 **Layout 框架**
- 每套工作台的**侧边栏**(根据当前用户权限点动态渲染可见 tab)
- 顶部 **Header**(显示当前用户 / 角色 / 切换登录 / 退出)
- 每个 tab 对应一个**占位页**——页面上展示:
  - 当前路由
  - 此页面要求的权限点
  - 当前用户是否拥有该权限点
  - 如果是「公共可见」,也要标明
- **前端路由守卫**:用户直接在地址栏输入无权访问的 URL,跳转到「无权访问」提示页(或重定向到自己的工作台)
- **调试开关**:Header 上加一个 toggle,在「线上模式(隐藏无权 tab)」和「调试模式(展示所有 tab 但置灰,hover 提示缺什么权限点)」之间切换。**调试模式是这个页面存在的意义**,默认开启。

### 1.2 不做

❌ 不实现任何业务功能(不要真的做商品列表、不要做询价表单、不要做订单详情)
❌ 不接 mock 业务数据(占位页不需要假数据)
❌ 不做按钮级显隐的具体案例(等真业务页面再做)
❌ 不动现有 RBAC 后端 API,不改 schema,不改 seed 中的权限点定义
❌ 不引入新依赖(沿用 v0.1 现有的技术栈和 UI 组件)
❌ 不做面包屑、多级折叠菜单、tab 搜索等花哨交互
❌ 不做移动端适配(桌面端优先)

### 1.3 与现有 `/rbac-test` 页面的关系

**保留** `/rbac-test`(那个调 4 个 role-only API 的页面)作为「API 层验证页」,挂在新建的 ADMIN 侧边栏的「RBAC 调试」分组下。本次任务**不重写**它。

---

## 2. 页面结构(基于 `overseas-supply-platform.md` 第十节的 MVP 页面清单)

> **重要原则**:只拉**顶层模块**,不展开子页面。每个 tab = 1 个占位页,不要建子路由树。

### 2.1 公开区(未登录可见 + 已登录可见)

| 路由 | 名称 | 可见角色 | 备注 |
|---|---|---|---|
| `/` | 平台首页 | 所有人(含未登录) | 落地页占位 |
| `/mall` | 严选商城 | 所有人 | 商城前台占位 |
| `/suppliers` | 供应商目录 | 所有人 | 占位 |
| `/countries` | 国别准入 | 所有人 | 占位 |
| `/login` | 登录 | 未登录 | 现有页面,保留 |

### 2.2 BUYER 工作台 `/buyer/*`

| 路由 | 名称 | 要求权限点(示例,以现有 seed 为准) |
|---|---|---|
| `/buyer/dashboard` | 工作台 | `buyer:dashboard:read` |
| `/buyer/projects` | 项目管理 | `project:read` |
| `/buyer/purchase-lists` | 采购清单 | `purchase_list:read` |
| `/buyer/rfqs` | 询价管理 | `rfq:read` |
| `/buyer/orders` | 订单管理 | `order:read` |
| `/buyer/documents` | 单据中心 | `document:read` |

### 2.3 SUPPLIER 工作台 `/supplier/*`

| 路由 | 名称 | 要求权限点 |
|---|---|---|
| `/supplier/dashboard` | 工作台 | `supplier:dashboard:read` |
| `/supplier/onboarding` | 入驻向导 | `supplier_org:write` |
| `/supplier/membership` | 会员中心 | `membership:read` |
| `/supplier/products` | 商品管理 | `product:read` |
| `/supplier/rfqs` | RFQ 收件箱 | `rfq:respond` |
| `/supplier/orders` | 订单管理 | `order:read` |
| `/supplier/profile` | 我的档案 | `supplier_org:read` |

### 2.4 OPERATOR 后台 `/operator/*`

| 路由 | 名称 | 要求权限点 |
|---|---|---|
| `/operator/dashboard` | 管理首页 | `operator:dashboard:read` |
| `/operator/supplier-review` | 供应商审核 | `supplier:approve` |
| `/operator/product-review` | 商品审核 | `product:approve` |
| `/operator/orders` | 订单总览 | `order:read:all` |
| `/operator/countries` | 国别数据维护 | `country:write` |
| `/operator/risk-cockpit` | 风控驾驶舱 | `risk:read` |

### 2.5 ADMIN 后台 `/admin/*`

| 路由 | 名称 | 要求权限点 |
|---|---|---|
| `/admin/users` | 用户管理 | `user:manage` |
| `/admin/roles` | 角色管理 | `role:manage` |
| `/admin/permissions` | 权限管理 | `permission:manage` |
| `/admin/config` | 系统配置 | `system:config` |
| `/admin/rbac-test` | RBAC API 调试 | 任意已登录(挂保留页) |

> **如果上述权限点 code 与现有 seed 不一致**:**优先沿用 seed 里实际存在的 code**,本表只是示意。读 seed 后做映射。如果某个 tab 在 seed 中找不到对应权限点,先在 seed 中**新增**最小定义(只加 Permission 行 + 给对应角色的 RolePermission 关联),不要凭空假设。

---

## 3. 占位页统一模板

每个 tab 进去都长一样,只有内容字段不同。建一个统一组件 `<PermissionPlaceholderPage />`,接收 props:

```tsx
<PermissionPlaceholderPage
  title="项目管理"
  route="/buyer/projects"
  requiredPermission="project:read"
  module="BUYER 工作台"
  description="(占位)未来此页面将展示项目列表、创建项目、查看项目详情"
/>
```

**渲染内容**:

```
┌─────────────────────────────────────────────┐
│  📋 项目管理                                  │
│  BUYER 工作台 · /buyer/projects               │
├─────────────────────────────────────────────┤
│                                              │
│  ✅ 你有权访问此页面                          │
│                                              │
│  要求权限点:  project:read                   │
│  当前用户:    zhang@cscec3b.com               │
│  当前角色:    [PURCHASER]                     │
│  权限点检查:  ✅ 已拥有                       │
│                                              │
│  ───────────────────────────────────────     │
│  (占位)未来此页面将展示项目列表、创建项目、    │
│  查看项目详情。                                │
│                                              │
└─────────────────────────────────────────────┘
```

**如果用户硬闯到了无权访问的 URL**(理论上路由守卫会拦,但 ADMIN 调试模式下可能进得来),占位页显示红色边框 + ❌ 标识 + 「你没有此权限点」。

---

## 4. 侧边栏(Sidebar)行为规范

### 4.1 渲染逻辑

侧边栏内的每个 tab,根据当前用户的 `permissions` 数组判断:

| 调试开关 | 用户有权 | 用户无权 |
|---|---|---|
| **线上模式(默认在生产环境用)** | ✅ 正常显示,可点击 | ❌ 完全不渲染 |
| **调试模式(默认开启,本测试页核心)** | ✅ 正常显示,可点击 | ⚠️ 显示但置灰 + 加角标「缺 `xxx:xxx`」 + 不可点击 |

### 4.2 分组

侧边栏按「业务模块」分组,组标题与 Permission 表的 `module` 字段对应:

```
┌─────────────────────┐
│  BUYER 工作台          │
│   📊 工作台            │
│   📋 项目管理          │
│   🛒 采购清单          │
│   📨 询价管理          │
│   📦 订单管理          │
│   📑 单据中心          │
└─────────────────────┘
```

每个角色登录后,**只显示该角色「应当看到」的工作台**:

- PURCHASER → 公开区 + BUYER 工作台
- SUPPLIER → 公开区 + SUPPLIER 工作台
- OPERATOR → 公开区 + OPERATOR 后台
- ADMIN → 公开区 + ADMIN 后台(+ 调试模式下可看到全部其他工作台,但 tab 都是置灰的)

### 4.3 顶部 Header

```
┌────────────────────────────────────────────────────────────┐
│  [Logo] 海外严选平台    [调试模式 ●]   zhang@... [PURCHASER]  │
│                          ↑ toggle                  ↑ 退出   │
└────────────────────────────────────────────────────────────┘
```

- **调试模式 toggle**:开启时侧边栏显示所有 tab(无权的置灰),关闭时只显示有权的
- 显示当前邮箱 + 角色徽章
- 退出按钮调现有 `/auth/logout`

---

## 5. 前端路由守卫

实现一个 `<RouteGuard requiredPermission="xxx">` 组件或对应的 middleware/hook:

- 用户访问需要权限的页面
- 检查 `session.permissions` 是否包含 `requiredPermission`
- 不包含 → 重定向到 `/no-permission?required=xxx&route=xxx`,展示「你需要权限点 `xxx`,当前角色 `[X]` 没有此权限」
- 公开区路由(`/`、`/mall`、`/suppliers`、`/countries`)不走守卫

**注意**:这是 **UX 层防护**,不是安全机制。后端 API 守卫仍然是底线,不能因为加了这个就放松后端校验。

---

## 6. 与现有代码的衔接约定

> 我没有强制规定文件路径,因为 v0.1 仓库可能已有自己的目录结构。**优先复用现有约定**,不要凭空建一套并行结构。

**必须复用**:
- 现有的 NextAuth/session 机制
- 现有的 `permissions` 数组获取方式(从 `/api/auth/me` 或 session 拿)
- 现有的 UI 组件库(看截图是浅色卡片 + 圆角 + 灰底,延续这个风格)
- 现有的 4 个种子账号

**新增建议路径**(如与现有冲突以现有为准):
```
src/components/layout/
  AppHeader.tsx              ← 新建
  AppSidebar.tsx             ← 新建,内部根据角色渲染不同分组
  PermissionPlaceholderPage.tsx  ← 新建
  RouteGuard.tsx             ← 新建
src/lib/
  permissions.ts             ← 新建或扩展现有,导出 hasPermission(perm) hook
src/config/
  navigation.ts              ← 新建,集中定义"哪个 tab 在哪个分组、要求什么权限点、占位文案是什么"
```

**`navigation.ts` 是单一可信源**——所有侧边栏渲染、占位页、路由守卫都从这里读配置。后续要加 tab 或改权限点,只动这一个文件。

---

## 7. 视觉风格(沿用 v0.1 现有风格)

从截图看,现有 RBAC 测试页风格是:
- 浅灰底(`#F5F7FA` 或类似)
- 白色卡片 + 圆角(看起来是 16-20px)+ 轻阴影
- 标题字体偏粗,正文偏淡
- 强调色用橙色(`#FF6B35` 或类似,角色徽章颜色)
- 蓝色用于深色按钮(深海军蓝)
- 等宽字体用于权限点 code 展示

**严格沿用,不要重新设计**。如果发现现有 `globals.css` 或 Tailwind config 已有色板定义,直接用变量。

---

## 8. 验收清单

**基础**:
- [ ] `npm run dev` 启动后,4 个种子账号都能登录,看到不同的侧边栏
- [ ] 顶部 Header 显示当前邮箱 + 角色徽章 + 调试模式 toggle
- [ ] 退出登录工作正常

**侧边栏(调试模式开启,默认)**:
- [ ] PURCHASER 登录 → 看到 BUYER 工作台全部 tab 可点击,看到其他工作台的 tab 但全部置灰
- [ ] SUPPLIER 登录 → 同上,反过来
- [ ] OPERATOR 登录 → OPERATOR 后台全部可点
- [ ] ADMIN 登录 → ADMIN 后台全部可点
- [ ] 鼠标 hover 置灰的 tab → 显示「需要权限点:`xxx`,当前角色未拥有」

**侧边栏(调试模式关闭)**:
- [ ] 各角色登录 → 只看到自己有权访问的 tab,其他完全不渲染

**占位页**:
- [ ] 点击任一可访问 tab → 进入占位页,正确显示路由、权限点、当前用户、是否拥有
- [ ] 占位页样式统一,信息齐全

**路由守卫**:
- [ ] PURCHASER 登录后,地址栏手动输入 `/supplier/products` → 跳到 `/no-permission`,显示缺少 `product:read`(或对应权限点)
- [ ] 公开区 `/`、`/mall`、`/suppliers`、`/countries` 在未登录状态下也可访问

**保留**:
- [ ] 原 `/rbac-test`(调 4 个 role-only API 的页面)仍可访问,挂在 ADMIN 侧边栏「RBAC 调试」分组下

**代码质量**:
- [ ] `navigation.ts` 是单一配置源,所有 tab/权限点定义集中在此
- [ ] 没有引入新的第三方依赖

---

## 9. 不确定时的优先级

如果遇到设计取舍,遵循:

> **可演示性 > 调试友好性 > 代码优雅性 > 视觉精致度**

**遇到现有 seed 权限点 code 与本任务书第 2 节不一致时**:
1. 先读 seed,列出实际存在的所有权限点 code
2. 与本任务书第 2 节做映射,**沿用 seed 中的实际 code**
3. 如果 seed 中确实缺少某个 tab 需要的权限点,**在 seed 里最小化新增**(只加 Permission + 对应 RolePermission),并在 PR description 里说明哪些是新增的
4. **不要**凭空假设权限点存在
5. **不要**因为某个权限点缺失就跳过该 tab——补全 seed 让所有 tab 都能演示完整

---

## 10. 禁止事项

❌ **不要**在占位页里加任何 mock 业务数据(不要假装商品列表,不要假装订单)
❌ **不要**重写现有 RBAC 后端 API
❌ **不要**改 RBAC 5 张表的 schema
❌ **不要**引入新的 UI 组件库或图表库
❌ **不要**做按钮级显隐的具体案例(本任务只到 tab 级别)
❌ **不要**做权限编辑后台(那是 V1.0 的事)
❌ **不要**做面包屑、多级折叠菜单、tab 搜索框
❌ **不要**做移动端响应式

---

## 11. 开始

第一步:`git pull` 同步现有代码 → 列出 `src/` 目录结构 → 找到现有 seed 文件,输出当前所有 Permission code 清单 → 与本任务书第 2 节做映射并报告差异 → **等我确认后**再开始写代码。

不要直接开干,先对齐 seed。
