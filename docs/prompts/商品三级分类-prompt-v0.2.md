# Task: 商品三级分类底座实现 · 工单 v0.2

> 状态:已评审 / 可下发 Claude Code
> 作者:liujingjing
> 日期:2026-05-21
> 关联 PRD:`docs/商品三级分类-PRD-v0.2.md`(本任务的需求契约)

---

## 1. 任务上下文

请先按顺序阅读以下文档,确认理解后再开始动手:

1. `docs/商品三级分类-PRD-v0.2.md` —— **本任务的核心契约,必须完整读完**
2. `docs/MVP业务流程共识_v1.2.md` —— 关注流程 1(供应商入驻)Step 2 / 流程 3(项目+采购清单)对分类的依赖
3. `CLAUDE.md` —— 项目级强约束(技术栈、命名、红线),尤其是 §6 数据库设计约定
4. 参考工程目录 `/Users/liujingjing/Documents/overseas-pro/overseas-supply-platform/` —— **不要打开任何源码文件**;PRD §2 已对照过设计要点,实施时不需要参照

读完后跟我确认你理解了三件事:

- (1)`code` 字段是业务主键,永久不变,关联表外键引用 `code` 不引用 `id`(PRD §3.4)
- (2)灌数靠**本地人工**跑 CLI 脚本,**不自动**(无启动 seed、无 alembic 数据迁移、无任何自动化钩子)
- (3)本任务**只做业务**,不触 Docker / docker-compose / .dockerignore / entrypoint / 部署脚本 / CI 流水线

---

## 2. 任务范围

实现【商品三级分类底座】。具体范围:

- 后端:`categories` 表 + alembic 迁移 + Excel 导入 CLI 脚本 + 两个查询 API
- 前端:`CategoryCascader` 三级联动组件 + 临时 demo 页

详见 PRD §1.2(目标)/ §1.3(非目标)/ §7(任务清单)。

**不要超出 PRD 范围扩展,不要修改未提及的模块**。

---

## 3. 技术约束(必须遵守)

项目通用约束(沿用):

1. 后端:FastAPI + SQLAlchemy 2.0 async + PostgreSQL
2. 前端:Next.js 14 + TypeScript + Tailwind + shadcn/ui + SWR
3. 数据库变更通过 alembic migration,**禁止手动 ALTER**
4. API 响应格式遵循 `{ code, data, message }` 统一规范
5. 时间字段应用层强制 UTC,DB 列用 `TIMESTAMP WITHOUT TIME ZONE`(对齐 CLAUDE.md §6)
6. 主键统一 `Integer` 自增(对齐 CLAUDE.md §6)
7. 单元测试覆盖率 ≥ 80%

本任务特别强调:

8. `categories` 表外部关联键统一用 `code`(VARCHAR(16)),**不用 `id`**
9. `parent_code` FK 必须显式声明引用 `categories(code)`
10. Excel 导入逻辑**只放在 CLI 脚本里**(`backend/scripts/import_categories.py`),**不要**抽到 `app/services/`,**不要**让应用代码 import 这个脚本——为了和未来的"部署自动灌数"任务彻底解耦
11. 公开 API 不需要权限点(对齐 PRD §5.1 `权限=公开`)
12. 本任务**不涉及** RBAC / 权限点新增 / 审计日志(读接口,无写操作)

---

## 4. 实现步骤(分 Step 交付)

按以下顺序产出,**一气呵成、不设中途人工 checkpoint**(PRD §11.2),全部完成后按 §7 验收标准一次性总验收。

### Step 1:数据模型 + 迁移(对应 PRD T1)

- 新增 `backend/app/db/models/category.py`,字段、约束、索引严格对齐 PRD §3.2
- 生成 alembic 迁移文件(命名:`20260521_0005_add_categories.py` 或当日合适序号)
- 模型类加注释,引用 PRD §3.4 的 code 永久不变契约

### Step 2:Excel 导入 CLI 脚本(对应 PRD T2)

- 脚本位置:`backend/scripts/import_categories.py`
- 参数:`--file` / `--dry-run` / `--deactivate-missing`(对齐 PRD §4.3)
- 关键函数(都放在脚本文件内,不要外置到 `app/services/`):
  - `find_latest_xlsx_in_data_dir() -> Path`(扫项目根 `data/` 取 mtime 最新)
  - `validate_xlsx_path(path: Path) -> None`(校验路径在 `data/` 下,否则 fail-fast)
  - `parse_xlsx(path: Path) -> ExcelTree`(读 + 表头模糊匹配 + L3 多值拆分)
  - `import_from_xlsx(db, tree, dry_run=False, deactivate_missing=False) -> ImportStats`(核心算法)
- 算法严格按 PRD §4.5 实现"沿用已有 code"逻辑
- dry-run 打印 `新增/更新/保留不动/将停用` 差异统计(对齐 PRD §9 D4)

### Step 3:本地首次灌数 + 数据核对(对应 PRD T3)

- 确认 `data/三局产品三级分类(整合合同分类)20260516.xlsx` 在仓库内
- 跑一次 CLI 脚本灌入本地开发库
- 报告:总记录数 / L1 数 / L2 数 / L3 数 / 几个抽样 code 与名字
- 核对几个明显条目肉眼对得上

### Step 4:Service / Schema / API(对应 PRD T4-T6)

- `backend/app/services/category.py`(查全表、内存建树)
- `backend/app/schemas/category.py`(Pydantic)
- `backend/app/api/v1/categories.py`(两个 GET 接口)
- 接口参数、响应严格对齐 PRD §5.2 / §5.3
- 路由挂到 `backend/app/api/v1/router.py`

### Step 5:后端测试(对应 PRD T7)

- `backend/tests/test_categories.py` —— Service / API 层
- `backend/tests/test_import_categories.py` —— 导入算法(空库 / 重跑 / 新增节点 / 同名节点 / 路径校验)

### Step 6:前端 API + Hook + 组件(对应 PRD T8-T9)

- `frontend/src/lib/api/categories.ts`
- `frontend/src/hooks/useCategoryTree.ts`(SWR)
- `frontend/src/components/category/CategoryCascader.tsx`(对齐 PRD §6)

### Step 7:demo 页 + 手工验证(对应 PRD T10)

- `frontend/src/app/test/category/page.tsx`(临时 demo,后续轮次接入真实页面时可删)
- 完成 PRD §8 前端验收清单 5 项

---

## 5. 不要做的事(明确禁止)

直接沿用 PRD §11 所有红线 9 条,不在此重复。**特别强调禁止项**:

- ❌ 不要给关联表用 `category_id` 做外键(必须用 `category_code`)
- ❌ 不要在导入脚本里实现"改名时同步改 code"(违反 §3.4 契约)
- ❌ **不要碰任何 Docker / docker-compose / .dockerignore / docker-entrypoint.sh / deploy/ / .github/workflows/ 下的文件**
- ❌ **不要在 `app/seed.py` 里加任何分类相关代码**(本任务不预设自动灌数钩子)
- ❌ **不要在 `app/main.py` / lifespan 里加任何分类初始化逻辑**
- ❌ 不要打开 `/Users/liujingjing/Documents/overseas-pro/overseas-supply-platform/` 下任何源码文件
- ❌ 不要引入 Redis / 缓存中间件 / OCR / AI
- ❌ 不要新增 RBAC 权限点(本任务 API 全公开)
- ❌ 不要修改其他已有功能(供应商注册 / 用户认证 / 审计 / 启动流程)
- ❌ 不要为本任务新增前端导航菜单项(demo 页不入主导航)
- ❌ 不要写邮件 / 短信 / 通知逻辑

---

## 6. 输出要求

- 全部 7 个 Step 完成后,一次性输出**变更文件清单 + 关键代码片段**
- commit 粒度:**一个 Step 一个 commit**,共 7 个 commit
- commit message 格式:`feat(category): <内容> [Step N/7]`
  - 示例:`feat(category): add Category model and migration [Step 1/7]`
- PR 标题:`feat(category): 商品三级分类底座 (T1-T10)`
- PR 描述里附上:
  - 灌数报告(Step 3 的统计输出)
  - PRD §8 验收清单逐项勾选状态
  - demo 页截图(Cascader 三级联动效果)

---

## 7. 验收标准

完全沿用 PRD §8 验收清单。**所有勾选项必须满足才算完成**。

补充本任务额外要求:

- [ ] 7 个 commit 粒度清晰,可单独 revert
- [ ] 后端测试 ≥ 80% 行覆盖率(`pytest --cov=app/services/category --cov=scripts/import_categories`)
- [ ] PR 描述附带灌数报告与 demo 页截图
- [ ] git diff 确认**未触动**:Dockerfile、docker-compose.yml、.dockerignore、docker-entrypoint.sh、deploy/、.github/workflows/、app/seed.py、app/main.py

---

## 8. 异常处理协议

遇到以下情况,**停下来告诉我,不要自己继续**:

- PRD 条款解读有多种合理理解(尤其是 §3.4 契约、§4.5 算法)
- 发现 PRD 与 CLAUDE.md 或现有代码有矛盾(以 PRD 优先,但必须先报告)
- Excel 文件实际表头与 PRD §4.1 不符
- Excel 数据有 PRD §10 风险表外的异常(比如二级分类已经撞 999)
- 导入脚本在某个真实节点上跑不通
- 测试失败排查不出原因
- 实施需要超出本工单范围(发现要改 RBAC、要加导航菜单、要动 Docker、要动 seed/main/lifespan、要动其他模块)
- 时间超出预期超过 2 倍(预估 2.4 人日,超过 4.8 人日)
- **想到了 PRD 没约定的相邻功能/改进**(按既定优先级走,不扩散;有想法就停下来记录到本工单末尾的"开发日志"部分)

报告格式:**现状 + 问题 + 我的想法 + 需要拍板的点**

---

## 开发日志(Claude Code 实施期间填)

> 留白。Claude Code 在实施过程中按异常处理协议触发的报告、想到但本轮不做的改进点,都追加到这里。

---

*工单结束。请先告诉我你对 §1 末尾三件事的理解,以及 7 个 Step 的实施计划草案,等我确认后再开始 Step 1。*
