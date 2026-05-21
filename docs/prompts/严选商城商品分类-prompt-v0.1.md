# Task: 严选商城商品分类导航实施 · 工单 v0.1

> 状态:已评审 / 可下发 Claude Code
> 作者:liujingjing
> 日期:2026-05-21
> 关联 PRD:`docs/商品管理/商品三级分类-PRD-v2.0.md`(本任务的需求契约)
> 当前分支:`feat/mall-category-nav`(已基于 main 最新 `ee382a2` 切出)

---

## 1. 任务上下文

请先按顺序阅读以下文档,确认理解后再开始动手:

1. `docs/商品管理/商品三级分类-PRD-v2.0.md` —— **本任务的核心契约,必须完整读完**(4 个决策点已确认)
2. `docs/商品管理/商品三级分类-PRD-v1.0.md` —— v1.0 分类底座 PRD,本轮所有数据/API/组件契约的源(尤其 §3.4 code 永久不变契约)
3. `CLAUDE.md` —— 项目级强约束(技术栈、命名、红线)
4. **参考工程 mall/page.tsx**:`/Users/liujingjing/Documents/overseas-pro/overseas-supply-platform/src/app/(marketing)/mall/page.tsx`(556 行,本轮**核心复用源**)
5. **参考工程 Header.tsx**:`/Users/liujingjing/Documents/overseas-pro/overseas-supply-platform/src/components/layout/Header.tsx`(L12 有"严选商城" tab 样式)

读完后**默认按 PRD §10 红线一气呵成,不设中途人工 checkpoint**。

---

## 2. 任务范围

实现【严选商城页面 + 左侧分类侧边栏导航】。具体范围:

- 前端:`/mall` 路由从占位 → 真实页面(Hero + 分类 sidebar + Filter bar UI + 占位主区)
- 数据来源:复用 v1.0 已交付的 `GET /api/v1/categories/tree`
- 视觉/交互:**直接搬参考工程** `mall/page.tsx`,做 PRD §2.2 列的 6 个改造点
- URL 同步:`?cat=` 单查询参数

详见 PRD §1.2(目标)/ §1.3(非目标)/ §5(前端实施)/ §6(任务清单)。

**不要超出 PRD 范围扩展,不要修改未提及的模块**。

---

## 3. 技术约束(必须遵守)

项目通用约束(沿用):

1. 前端:Next.js 14 App Router + TypeScript + Tailwind + SWR
2. API 响应格式 `{ code, data, message }`,`apiRequest` 已自动剥 `data`,所以 `api.get<T>` 拿到的就是 `T`
3. lucide-react 已装 0.408.0,直接用
4. `pnpm tsc --noEmit` / `pnpm lint` / `pnpm build` 必须全过

本任务特别强调:

5. **纯前端工作**,不动 backend / data / scripts / alembic / docker / deploy / .github
6. **不新增 npm 依赖**(ProductCard / Badge 都不引入)
7. **不修改 v1.0 已交付的**:`categoriesApi` / `useCategoryTree` / `CategoryCascader` / `categories` 后端 API
8. **遵守 PRD v1.0 §3.4 "code 永久不变"契约**:本轮只读用 code 作为 URL 参数,不存任何 code → 关联表
9. **字段名严格 snake_case**:`name_zh / name_en / sort_order / parent_code / is_active`(对齐 v1.0 API 返回)
10. **`category.id` 是 number**(v1.0 后端是 Integer 自增),不是参考工程的 string CUID

---

## 4. 实现步骤(分 Step 交付)

按以下顺序产出,**一气呵成、不设中途人工 checkpoint**(PRD §10),全部完成后按 §7 验收标准一次性总验收。

### Step 1:拷贝 mall/page.tsx + 字段改造 + API 调用替换(对应 PRD T1-T3)

- 把参考工程 `mall/page.tsx` 整体拷到 `frontend/src/app/mall/page.tsx`(覆盖现有占位)
- 全文 sed 替换字段名:
  - `nameZh` → `name_zh`
  - `nameEn` → `name_en`
  - `sortOrder` → `sort_order`
- `CategoryNode` interface 改:`id: string` → `id: number`
- `fetch('/api/categories/tree')` → 改用 `categoriesApi.tree()`(import 自 `@/lib/api/categories`),拿到的就是数组(已剥 `data`)
- `loadingCategories` / `categoryTree` 状态可用 `useCategoryTree()` hook 一键替换,或保留原 fetch 逻辑(择优)
- 跑 `pnpm tsc --noEmit`,看完整错误清单驱动后续 Step

### Step 2:干掉 products + 主区占位(对应 PRD T4-T5)

- 删除 `Product` interface、`Pagination` interface、`products` / `pagination` / `loading` / `searchInput` 这些跟 products 强相关的 state
- 删除 `fetchProducts` useCallback + `useEffect(fetchProducts)`
- 删除 `<ProductCard>` 渲染逻辑(原 473-502 行附近)
- 删除 `import { ProductCard }`
- 主区按 PRD §5.3 改成**占位卡片**:
  - 有 `selectedCategory`:显示"商品功能开发中,当前选中分类:**{selectedCategoryName}** code = `{selectedCategory}`"
  - 无 `selectedCategory`:显示"商品功能开发中,左侧选择分类查看品类结构"
- `selectedCategoryName` 用 `findCategoryNode` 取出来(参考工程已有这个函数,保留)

### Step 3:URL 同步 ?cat=(对应 PRD T6)

- 用 `useSearchParams()` + `useRouter().replace()` 实现 URL ↔ `selectedCategory` 双向绑定
- 初次加载:从 URL `?cat=XXX` 读 → 初始化 state
- 用户点击分类:`setSelectedCategory(code)` 同时 `router.replace(?cat=code)`(用 `replace` 不入栈)
- 点击"全部分类"(code = ""):URL 移除 `cat` 参数
- 直接访问 `?cat=01.001.001`:页面打开就高亮完整路径
- 注意 Next.js 14 `useSearchParams` 在 client component 需 Suspense 包裹,看是否需要(参考 PRD §9 风险表)

### Step 4:Filter bar / 分页 UI 保留但禁用(对应 PRD T7-T8 / Q2)

- 出口国家 / 供应商级别 chip UI **完整保留**
- `selectedCountry / selectedTier` state 保留(用于 chip 可视觉切换 active 态),但**不**触发任何 fetch
- 分页按钮 UI 保留,加 `disabled` + 透明度降低
- "清除筛选"按钮:只清 selectedCountry / selectedTier / search 这些前端 state,不动后端

### Step 5:Header tab "严选商城" verify / 补(对应 PRD T9 / Q4)

- 先看 `frontend/src/components/layout/Header.tsx`:是否已有"严选商城" tab + 高亮当前路径
- 已有 + 高亮 OK → **不动**,记录到 commit message
- 缺 → 按参考工程 `Header.tsx:12` 样式补:`{ label: "严选商城", en: "Mall", href: "/mall" }`,接入当前的 `nav` 数组,样式跟其他 tab 一致
- 高亮逻辑:用 `usePathname()` 判断当前路径以 `/mall` 开头

### Step 6:工程验收 + 浏览器手动验证(对应 PRD T10)

- `pnpm tsc --noEmit` 通过
- `pnpm lint` 无 warning
- `pnpm build` 通过
- `uvicorn` + `pnpm dev` 双启,浏览器开 `http://localhost:3000/mall`,按 PRD §7.2 交互清单逐项手验:
  - hover 一级 → 飞出二级面板
  - 点击一/二/三级 → URL `?cat=` 同步 + 高亮路径
  - 点"全部分类" → URL 移除 `cat`
  - 直接访问 `?cat=01.001.001` → 高亮完整路径
  - 后退键状态恢复
- **不能交互的部分(SSR 不能跑)用说明文字补充**,但其他都要实测

---

## 5. 不要做的事(明确禁止)

直接沿用 PRD v2.0 §10 所有红线 9 条,不在此重复。**特别强调禁止项**:

- ❌ 不要碰任何后端代码(`backend/` 目录全员免疫)
- ❌ 不要碰 Docker / docker-compose / Dockerfile / `.dockerignore` / `docker-entrypoint.sh`
- ❌ 不要碰 `deploy/` / `.github/workflows/`
- ❌ 不要碰 `data/` / `backend/scripts/`
- ❌ 不要新增任何 npm 依赖(`package.json` 只能改 `version` 等无关字段)
- ❌ 不要引入 ProductCard / shadcn Badge / Avatar / DropdownMenu 等
- ❌ 不要修改 v1.0 已交付的:
  - `frontend/src/lib/api/categories.ts`
  - `frontend/src/hooks/useCategoryTree.ts`
  - `frontend/src/components/category/CategoryCascader.tsx`(本轮跟 Cascader 并存,不动它)
  - `backend/app/db/models/category.py` / `backend/app/services/category.py` / `backend/app/api/v1/categories.py`
- ❌ 不要修改其他已有功能(供应商注册 / 用户认证 / 审计 / 启动流程)
- ❌ 不要新增 RBAC 权限点(本轮 mall 全公开)
- ❌ 不要为分类侧边栏拆出独立组件(`<CategorySidebar />` 等),内联在 `mall/page.tsx` 里就行,跟参考工程结构一致

---

## 6. 输出要求

- 全部 6 个 Step 完成后,**一次性输出**变更文件清单 + 关键代码片段
- commit 粒度:**一个 Step 一个 commit**,共 6 个 commit(Step 1 含拷贝 + 字段改 + API 替换,允许);若 Step 5 verify 后无需改,Step 5 可合并到 Step 6
- commit message 格式:`feat(mall): <内容> [Step N/6]`
  - 示例:`feat(mall): copy reference page + snake_case fields + use categoriesApi [Step 1/6]`
- PR 标题:`feat(mall): 严选商城商品分类导航 (PRD v2.0, T1-T10)`
- PR 描述里附上:
  - PRD §7 验收清单逐项勾选状态
  - 浏览器截图(至少 3 张:`/mall` 首屏 / hover 一级展开二级 / `?cat=01.001.001` 直达高亮)
  - 红线核查(git diff main..HEAD 对 backend/ / Docker / deploy/ / .github/ 全部为空)

---

## 7. 验收标准

完全沿用 PRD v2.0 §7 验收清单(视觉 8 + 交互 7 + 工程 5 共 20 项)。**所有勾选项必须满足才算完成**。

补充本任务额外要求:

- [ ] 6 个 commit 粒度清晰,可单独 revert
- [ ] PR 描述附带 3 张截图 + PRD §7 完整勾选状态
- [ ] git diff main..HEAD 确认**未触动**:`backend/` / `data/` / Dockerfile / docker-compose.yml / `.dockerignore` / `docker-entrypoint.sh` / `deploy/` / `.github/workflows/` / `package.json` 的 dependencies
- [ ] 未引入新 npm 依赖(`pnpm-lock.yaml` 不应有新增条目)

---

## 8. 异常处理协议

遇到以下情况,**停下来告诉我,不要自己继续**:

- PRD 条款解读有多种合理理解(尤其是 §5.3 占位规范、§5.4 URL 同步、§2.2 改造点)
- 发现 PRD 与 CLAUDE.md 或现有代码有矛盾(以 PRD 优先,但必须先报告)
- 参考工程文件位置/字段与 PRD §2 描述不符
- `useSearchParams` 在 Next.js 14 App Router 报错 / 需要 Suspense 包裹(直接包,但报告)
- 字段改造后 tsc 仍有遗漏的 camelCase 残留
- Header verify 发现"严选商城" tab 已存在但**链到了不同路径**或样式不一致(可能需调整)
- 测试失败排查不出原因
- 实施需要超出本工单范围(发现要改 RBAC、要加导航菜单结构、要动后端、要动 deploy、要动其他模块)
- 时间超出预期超过 2 倍(预估 1.2 人日,超过 2.4 人日)
- **想到了 PRD 没约定的相邻功能/改进**(按既定优先级走,不扩散;有想法就停下来记录到本工单末尾的"开发日志"部分)

报告格式:**现状 + 问题 + 我的想法 + 需要拍板的点**

---

## 开发日志(Claude Code 实施期间填)

> 留白。Claude Code 在实施过程中按异常处理协议触发的报告、想到但本轮不做的改进点,都追加到这里。

---

*工单结束。**默认按 §10 红线一气呵成执行 Step 1 → Step 6**,完工后输出变更清单 + PR。*
