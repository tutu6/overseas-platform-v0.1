# Task: 供应商目录列表页(MVP)· 工单 prompt v0.1

> 状态:待审 → 可下发 Claude Code
> 日期:2026-05-24
> 类型:新功能 · BUYER / OPERATOR 浏览已注册 Supplier 列表
> 关联:
> - 视觉参考:`/Users/liujingjing/Documents/overseas-platform/overseas-supply-platform`(认证供应商目录页)+ 用户截图
> - 占位页(将被替换):`frontend/src/app/suppliers/page.tsx`
> - 顶部入口(已加):`PUBLIC_NAV` 的「供应商目录」→ `/suppliers`(#31)
> 当前分支:`feat/supplier-directory-page`(基于 main 切出)

---

## 1. 任务上下文

### 1.1 目标

把 `/suppliers` 占位页换成真实的「认证供应商目录」列表页:

- **谁能看**:BUYER / OPERATOR(后端 `supplier:read`,两者都持有);访客 / SUPPLIER 不在本期范围(SUPPLIER 顶部 nav 已整体隐藏)
- **看什么**:平台已注册的 Supplier 列表,每家带综合评分 + 等级徽章 + 国别
- **本期不做状态限制**:只要注册了(`supplier_organizations` 有记录)就能查到,**不区分 DRAFT / APPROVED**(状态过滤作为 TODO)

### 1.2 数据现状与缺口(关键 —— 决定本期能交付到哪)

当前 `supplier_organizations` 表字段极简:

| 字段 | 有无 |
|---|---|
| name(中文名) | ✅ |
| country_code(单一国别,9 国之一) | ✅ |
| registration_no | ✅ |
| status(DRAFT/APPROVED/...) | ✅ |
| 综合评分 / grade | ⚠️ 间接:`credit_company.linked_supplier_org_id` → `score_snapshot.total_score / grade`(Δ5 注册即评分后,新注册 Supplier 都有) |
| 英文名 | ❌ 无字段 |
| tier(T1/T2/T3) | ❌ 无字段 → **本期由 grade 映射**(见下) |
| 主营品类(铝单板/幕墙/机电…) | ❌ 无 supplier-品类 关联(`category` 表是商品三级分类,非供应商主营) |
| 多国覆盖(export countries) | ❌ 只有单一注册国 country_code |

**结论**:参考工程/截图里的「品类 chip」「多国覆盖」「英文名」本期**无数据支撑,先不做**;tier 用 grade 映射保留视觉。

### 1.3 grade → tier 映射(本期约定)

| credit grade | 目录 tier | 徽章文案 | 颜色 |
|---|---|---|---|
| A | T1 | T1 头部供应商 | 黄/金 |
| B | T2 | T2 优质供应商 | 灰 |
| C | T3 | T3 认证供应商 | 棕 |
| D | —(不评级) | 暂未评级 | 浅灰 |
| 无 snapshot(评分中) | —(不评级) | 评分生成中 | 浅灰 |

> 注:tier 是展示层从 grade 推导,**不落库、不引入新字段**。

---

## 2. 范围

**做**:

- 后端新增 `GET /api/v1/suppliers` 列表接口(`supplier:read` 守卫)
- 接口返回:id / name / country_code / status / total_score / grade
- 筛选:关键词 `q`(模糊匹配 name)、国别 `country`、级别 `grade`(可选)
- 前端 `/suppliers` 占位页替换为真实列表页(参考截图风格)
- 头部 banner + 搜索框 + 国别 chips + 级别 chips + 供应商卡片网格
- 卡片:名称 + 评分圆环(total_score)+ tier 徽章(grade 映射)+ 国别 + 「查看详情」占位
- banner 右上角统计:总数 + T1/T2/T3 计数(从列表数据算)

**不做**:

- ❌ 不加表字段 / 不做迁移(英文名 / tier / 品类 / 多国覆盖 全部不落库)
- ❌ 不做品类筛选(无 supplier-品类 数据)
- ❌ 不做供应商详情页(「查看详情」先留占位 `# TODO`,不跳转或跳到占位)
- ❌ 不做按审批状态过滤(本期全状态可见,TODO 记录)
- ❌ 不做分页(MVP 用 `limit` 上限,默认 50)
- ❌ 不动 credit 模块 / RBAC / 注册流程
- ❌ 不做多维评分雷达(目录列表不需要)

---

## 3. 实现步骤

### Step 1:后端列表接口

新建 `backend/app/api/v1/suppliers.py`(并在 `router.py` 注册):

```
GET /api/v1/suppliers
  query: q?(name 模糊)、country?(ISO-2)、grade?(A/B/C/D)
  权限: require_permission("supplier:read")
  逻辑:
    - LEFT JOIN credit_company (linked_supplier_org_id) → score_snapshot (is_current)
      取 total_score / grade(无评分则 None)
    - 不做状态过滤(全状态返回)
    - q → name ilike;country → country_code==;grade → snapshot.grade==
    - order by total_score desc nulls last,limit 50
  返回 SupplierListItem[]: { id, name, country_code, status, total_score|null, grade|null }
```

- schema 放 `backend/app/schemas/supplier.py`(新建)
- 评分关联参照 credit.py 现有 `ScoreSnapshot.is_current.is_(True)` 写法
- **不暴露内部细节**;无评分的 supplier 正常返回(分数 null,前端显示"评分生成中")

### Step 2:前端 API 客户端

`frontend/src/lib/api/suppliers.ts`(新建):
- `suppliersApi.list({ q, country, grade })` → `SupplierListItem[]`
- 类型与后端 schema 对齐

### Step 3:前端列表页

替换 `frontend/src/app/suppliers/page.tsx`:
- 外层 `PublicLayout` + `RouteGuard requiredPermissions={[Permissions.SUPPLIER_READ]}`
- 复用截图/参考工程视觉(品牌色 `#003366`,辅色 `#FF6B35`)
- 结构:
  1. 头部 banner:标题「认证供应商目录」+ 总数徽章 + 右上 T1/T2/T3 统计
  2. 搜索框(回车 / 点击「搜索」触发)
  3. 国别 chips:全部 + 9 国(从 `country-registration-rules` COUNTRIES 取)
  4. 级别 chips:全部 / T1 / T2 / T3
  5. 卡片网格 `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`
- 卡片元素(参考截图):
  - 公司名(中文)
  - 评分圆环(total_score,≥80 绿 / ≥60 橙 / <60 红;null 时灰圈 + "评分中")
  - tier 徽章(grade 映射,D / null → "暂未评级")
  - 国别(单个 country_code 中文名)
  - 「查看详情 ›」(本期占位,`# TODO: 详情页待实现`,不跳转或 disabled)

### Step 4:评分圆环组件

复用或新建 `frontend/src/components/supplier/ScoreCircle.tsx`(SVG 圆环),
若 credit 模块已有类似组件(`CreditRadarChart` 不合适,那是雷达)可新建一个简单圆环。

### Step 5:筛选交互

- chips 单选(国别一组、级别一组),点选即重新请求
- 搜索 + 筛选组合:都作为 query 传给 `GET /api/v1/suppliers`
- 空结果:显示"未找到匹配供应商"

---

## 4. 验收标准

### 后端
- `GET /api/v1/suppliers`(BUYER / OPERATOR token)→ 200,返回已注册 Supplier 列表(含 Δ5 seed 的 4 家 + 注册的)
- `?q=Al` → 命中 Al-Rashid
- `?country=SA` → 只返沙特
- `?grade=A` → 只返 A 级
- ADMIN / SUPPLIER token → 403(无 supplier:read?需确认:ADMIN 无 supplier:read,SUPPLIER 有 supplier:read 但本期 UI 不暴露;**接口层 SUPPLIER 调用返回什么需在实现时确认**——见待确认项)
- 无评分的 Supplier 正常返回,total_score / grade 为 null
- `uv run pytest` 通过(补列表接口单测:权限 + 筛选)

### 前端
- BUYER / OPERATOR 点顶部「供应商目录」→ 列表正常渲染,卡片含评分圆环 + tier 徽章 + 国别
- 搜索 / 国别 / 级别筛选生效
- D 级 / 无评分显示"暂未评级 / 评分生成中",不报错
- `pnpm tsc --noEmit` + `pnpm build` 通过

---

## 5. 严格不做的事

1. 不加任何表字段 / 迁移
2. 不做供应商详情页(本期只列表)
3. 不做品类筛选 / 多国覆盖 / 英文名(无数据)
4. 不做审批状态过滤(全状态可见)
5. 不动 credit / RBAC / 注册流程
6. 不引入分页组件(limit 50 够用)
7. 方案未覆盖的细节 → 最简实现 + `TODO: 方案未覆盖` 标注,不自行扩展

---

## 6. 待确认项(实现前需拍板)

1. **SUPPLIER 调 `/api/v1/suppliers` 返回什么?**
   SUPPLIER 持有 `supplier:read`(scope=OWN,用于自家档案)。供应商目录是"看别人",语义上 SUPPLIER 不该用。
   - 方案 A:接口不特殊处理,SUPPLIER 调也能列全部(但前端无入口)——最简
   - 方案 B:接口对 SUPPLIER 按 scope=OWN 只返自家——与目录语义矛盾
   - **倾向 A**(本期前端不给 SUPPLIER 入口,接口不做角色特判)
2. **「查看详情」**:本期占位不可点,还是预留路由 `/suppliers/[id]`(404 占位)?倾向不可点 + TODO。

---

## 7. 提交规范

- commit:`feat(supplier): supplier directory list page (MVP)`
- Ref:`docs/prompts/供应商目录-列表页-prompt-v0.1.md`

---

*工单 v0.1 · BUYER/OPERATOR 浏览已注册 Supplier · 不做状态限制 · 品类/多国/英文名因无数据降级*
