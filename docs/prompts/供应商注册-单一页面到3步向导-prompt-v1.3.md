# Task: 供应商入驻 · 供应商注册(3 步向导)实现

> **工单版本** v1.1 · **PRD 依据** `docs/prd/供应商注册_v1.3.md`
> **状态** 待 Claude Code 接单
> **交付节奏** **5 个 Step 一气呵成,不停下等 review**;每个 Step 完成后**必须立即自测**,自测全绿才能进下一步;**只有自测失败时才停下报告**
>
> **v1.1 相对 v1.0 的变更**
> - 取消"每步停下等 review",改为"自测驱动,一气呵成"
> - 加 §4.0 **自测协议**(每个 Step 的自动验收命令)
> - §5.3 文案/常量边界收窄(参 PRD v1.3 §5.3)
> - §7 grep 校验改成"精准规则",不再泛 grep 中文

---

## 1. 任务上下文

请先阅读以下文档(在仓库中):

- `CLAUDE.md`(项目级协作约定)
- `docs/MVP业务流程共识_v1.2.md`(关注**流程 1 · 供应商入驻**)
- `docs/RBAC与组织架构设计讨论_v1.2.md`(关注 SupplierOrganization / SupplierMember 模型)
- `docs/prd/供应商注册_v1.3.md`(**本任务核心契约,所有疑问优先在此找答案**)
- `docs/微调任务_供应商重复入驻提示.md`(已落地的前序微调,作为现状参考)

**熟悉文档后,在响应开头先复述以下 5 条关键决议**(每条 1-2 句话证明你理解了),**复述完毕立即进入 Step 1 实现,不要等我 review**。

1. 3 步向导 = 前端 UI 编排,**仅 Step 3 提交时调用一次** `POST /api/v1/auth/register/supplier`,Step 1/2/3 间切换**不调后端**
2. 跨 Step 数据存 **sessionStorage**(`register_supplier_draft`),**密码不存**,关 tab 即清
3. 9 国凭证规则 + **仅前后端要对齐的字符串**集中在 `frontend/src/config/country-registration-rules.ts`(后端对应 `backend/app/constants/country_registration.py`);一次性展示文案直接写组件 JSX 里(PRD v1.3 §5.3)
4. 唯一性约束改为 **(country_code, registration_no) 复合唯一**,不同国家可撞号
5. 重复注册错误文案:`"当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。"`(**不暴露**任何 owner / 公司名信息)

**如果复述后发现 PRD 真的存在矛盾或多种合理理解**,这是唯一允许停下来问我的时机;否则一律继续。

---

## 2. 任务范围

实现 **SUPPLIER 自助注册(3 步向导)+ 后端 schema 适配 + dashboard 待完善资料 banner + `/supplier/members` 占位路由**。详见 PRD §1-§5。

**不要超出 PRD 范围扩展,不要修改未提及的模块**。

---

## 3. 技术约束(必须遵守)

### 3.1 项目级(沿用 CLAUDE.md)

1. 后端:FastAPI + SQLAlchemy 2.0 async + PostgreSQL 16 + alembic + uv
2. 前端:Next.js App Router + TS + Tailwind + shadcn 风格 + Zustand + pnpm
3. 数据库变更通过 **alembic migration**,**禁止手动 ALTER**
4. API 响应遵循 `{ code, message, data, [trace_id] }` 统一格式
5. 所有写操作必须写 `audit_log`(注册成功写、注册失败重复时**不写**——沿用现行为)
6. trace_id 全链路;成功响应不重复 trace_id,失败响应 body 带 trace_id
7. 时间字段应用层 UTC,DB 列 `TIMESTAMP WITHOUT TIME ZONE`
8. 主键统一 `Integer` 自增

### 3.2 本任务特别强调

- **常量化边界**(按 PRD v1.3 §5.3):
  - 进常量:9 国数据、凭证规则、`language_preference` 值域、**重复注册错误文案**(前后端逐字一致)、状态字符串
  - 直接硬编码:Step 标题/副标题/字段 label/placeholder/按钮文字/Dashboard banner
- **TODO 注释带编号**:`TODO(I18N-PHONE)` / `TODO(REG-RULE)` / `TODO(T-LANG-CHANGE)` 等(对应 PRD §8 的待办编号)
- **复合唯一**:`UNIQUE(country_code, registration_no)`,不是单字段唯一。原 `business_license_no` 字段的 UNIQUE 必须删除
- **phone 正则放宽**:`^[+0-9\s\-]{6,20}$`(占位规则,覆盖中国 11 位),**前后端保持一致**
- **密码不进 sessionStorage**:前端任何持久化路径都不能落 `password` / `confirmPassword`
- **3 步向导的 Step 1/2 不调后端**。整个注册流程后端接口数量净增 = **0**

### 3.3 视觉规范

- 沿用现有 `(auth)/layout.tsx` 的深蓝渐变背景 + 白卡片 + 橙色顶边
- 步骤条用项目色(深蓝 `#003366` 填充态,灰色待选态),**不用截图的紫色/纯蓝**
- 主按钮:SUPPLIER 流程用 `#FF6B35`,次按钮用现有 secondary 风格
- 文案严格按 PRD §5.3 的措辞,不要自由发挥

---

## 4. 实现步骤(一气呵成 + 自测驱动)

### 4.0 总流程

**核心规则**:**5 个 Step 一气呵成完成,中途不停下等 review**。每个 Step 内部完成后**必须立即跑自测**;自测全绿才进下一步,自测红立即停下报告。

```
复述 5 条决议
    ↓
Step 1: 写代码 → 自测 → 绿 → 进 Step 2
                     ↘ 红 → 停下报告 ❌
    ↓
Step 2: 写代码 → 自测 → 绿 → 进 Step 3
                     ↘ 红 → 停下报告 ❌
    ↓
... Step 3 / Step 4 / Step 5 同上 ...
    ↓
全部完成 → 跑 §7 验收清单 → 一次性给我看完整结果
```

### 4.0.1 每个 Step 的自测命令(必须跑,全绿才往下)

| Step | 自测命令 | 通过标准 |
|---|---|---|
| Step 1 | `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` | 三连无报错;`\d supplier_organizations` 显示新约束 |
| Step 2 | `cd backend && pytest tests/test_auth.py -v` | 全绿;新增用例 ≥ 4 个(成功 / 复合唯一 / 缺字段 / 非法 country_code)|
| Step 3 | `cd frontend && pnpm build && pnpm lint` | 0 error;`country-registration-rules.ts` 类型导出正确(`tsc --noEmit`)|
| Step 4 | `cd frontend && pnpm build && pnpm lint` + 手工启动 `pnpm dev` 跑通 3 步流程 | build 通过;**至少**用 CN 和 MY 两个国家各跑通一遍 |
| Step 5 | `cd backend && pytest` + `cd frontend && pnpm build` + §7 全部 grep 校验 | 后端全绿;前端 build 通过;grep 校验全过 |

### 4.0.2 失败时的硬规则

**任何自测红 → 立即停下报告,不要做以下任何事情**:

- ❌ 修改测试断言以"绕过"失败
- ❌ 删除失败的测试用例
- ❌ try/except 吞异常让代码"看起来"通过
- ❌ 跳过失败的 Step,继续下一步
- ❌ 自己尝试"快速修复"超过 2 次还不成

**报告格式**(按 §8):
```
[Step N 自测失败]
跑的命令:<command>
失败输出:<paste 关键报错>
我的判断:<问题在 X,可能原因 Y>
建议:<选项 A / B / C>
需要拍板:<明确的问题>
```

---

### Step 1 · 数据库 schema + alembic migration

**目标**:落地 PRD §4.1 的全部 DB 改动,**一个 migration 文件搞定**。

**改动**:

- `supplier_organizations`:
  - 加列 `country_code VARCHAR(2) NOT NULL`(因表里目前可能已有测试数据,先 `ADD COLUMN NULL` → `UPDATE ... SET country_code='CN'` 兜底回填 → `ALTER COLUMN ... SET NOT NULL`,3 步在同一 migration 内)
  - 重命名 `business_license_no` → `registration_no`(`alter_column ... new_column_name=...`)
  - **删除**旧 `UNIQUE(business_license_no)`
  - **新增** `UNIQUE(country_code, registration_no)`
- `users`:
  - 加列 `language_preference VARCHAR(10) NULL`(nullable,无回填需要)
- ORM 模型同步更新:`SupplierOrganization`(改字段名 + 加 `country_code`)、`User`(加 `language_preference`)

**交付物**:
1. migration 文件(`backend/alembic/versions/<timestamp>_supplier_register_country_code.py`)
2. ORM 模型代码更新到位
3. `downgrade()` 必须可逆(改回原列名 + 删 country_code + 删 language_preference + 还原旧 UNIQUE)
4. **跑自测**(见 §4.0.1):`alembic upgrade head && downgrade -1 && upgrade head` 三连必须无报错;之后进入 Step 2,**不停下等 review**

**注意**:CLAUDE.md 第 397-400 行约束含 `drop_column` 会被 CI 拦截。本 migration 含 `drop_constraint(old_unique)` 与 `alter_column(new_column_name=...)`,**不含 drop_column**,正常通过。如果脚本检测误报,**这是允许暂停的例外**:停下报告,等我拍板是否加 `[allow-destructive-migration]`。

---

### Step 2 · 后端 schema + service + 单元测试

**目标**:落地 PRD §4.2 §4.3,改造 `SupplierRegisterIn` 和 `auth_service.register_supplier`。

**改动文件清单**:

- `backend/app/constants/country_registration.py`(**新增**)
  - 导出 `COUNTRY_CODES: tuple[str, ...]`(9 国 code)
  - 导出 `COUNTRY_META: dict[str, dict]`(每国 `{name_zh, name_en, local_lang, reg_no_pattern_hint}`)
  - 导出 `REGISTRATION_NO_MAX_LENGTH = 50`(后端只做长度兜底,精确正则在前端)
  - 导出 `LANGUAGE_CODES: tuple[str, ...]`(所有合法 language_preference 值并集 + `en` + `zh`)
- `backend/app/schemas/auth.py`(改 `SupplierRegisterIn`)
  - 加 `country_code: str`,枚举校验来自 `COUNTRY_CODES`
  - 加 `language_preference: str`,枚举校验来自 `LANGUAGE_CODES`,**必填**
  - 字段名 `business_license_no` → `registration_no`,`max_length=REGISTRATION_NO_MAX_LENGTH`
  - `phone` 必填,正则 `^[+0-9\s\-]{6,20}$`,加 `TODO(I18N-PHONE)` 注释
  - **删除** `username` 字段
- `backend/app/services/auth_service.py`(改 `register_supplier`)
  - 入参增减按上面 schema
  - 唯一性查询:`where((SupplierOrganization.country_code == country_code) & (SupplierOrganization.registration_no == registration_no))`
  - 重复抛错文案严格按 PRD §5.3
  - SupplierOrg 创建带 `country_code`
  - **User 创建时填入 `language_preference`**
  - audit extra 加 `country_code` 和 `language_preference`

**单元测试改动**(`backend/tests/test_auth.py`):

- 已有 `test_supplier_register_success`:改 payload 含 `country_code`/`language_preference`/`registration_no`,断言 User 落库时 `language_preference` 正确
- 已有 `test_supplier_register_duplicate_license`:改成 `test_supplier_register_duplicate_per_country`,断言:
  - 同 country + 同 reg_no → 409
  - **不同 country + 同 reg_no 字符串 → 200**(复合唯一关键测试)
- 新增 `test_supplier_register_invalid_country_code`:传 `XX` 应 422
- 新增 `test_supplier_register_missing_language_preference`:不传应 422
- 新增 `test_supplier_register_no_username_field`:payload 多带 `username` 字段应被忽略/拒绝(确认入参契约)
- 删/迁移所有依赖旧 `business_license_no` 字段名的测试

**交付物**:
1. 上述文件改动到位
2. 跑自测(见 §4.0.1):`pytest backend/tests/test_auth.py -v` 全绿后进入 Step 3

---

### Step 3 · 前端配置 + API 客户端

**目标**:配置文件先行,把"前后端要对齐的字符串 + 9 国数据 + 凭证规则"集中。**不放纯展示的一次性文案**(那些直接写组件里,见 PRD v1.3 §5.3)。

**新增**:`frontend/src/config/country-registration-rules.ts`

```typescript
// 结构示意,实际类型按需扩展
export const COUNTRIES = [
  { code: 'CN', nameZh: '中国', nameEn: 'China', localLang: 'zh', localLangName: '中文',
    regNo: { label: '统一社会信用代码', hint: '18 位', regex: /^[0-9A-Z]{18}$/,
             transform: (v: string) => v.toUpperCase().slice(0, 18) } },
  { code: 'MY', nameZh: '马来西亚', nameEn: 'Malaysia', localLang: 'ms', localLangName: 'Malay',
    regNo: { label: 'SSM 注册号', hint: '12 位纯数字', regex: /^[0-9]{12}$/,
             transform: (v: string) => v.replace(/\D/g, '').slice(0, 12) } },
  // ... KH/PK/MA/IQ/ID/SA/AE 同结构,按 PRD §3 表填
] as const;

export type CountryCode = typeof COUNTRIES[number]['code'];

// 仅"前后端要对齐 / 错一字即 bug"的字符串入常量
export const LANGUAGE_CODES = ['zh', 'en', 'ms', 'km', 'ur', 'ar', 'id'] as const;
export type LanguageCode = typeof LANGUAGE_CODES[number];

export const DUPLICATE_REGISTRATION_ERROR_MESSAGE =
  '当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。';

export const STATUS_DRAFT = 'DRAFT';

/** Step 1 选中国家后的提示文案模板(数据驱动,按国家拼接)*/
export const countryHintTemplate = (c: typeof COUNTRIES[number]) =>
  `您选择了 ${c.nameZh}。后续系统将要求您提供 ${c.regNo.label}(${c.regNo.hint})作为核心准入凭证。`;
```

**新增**:`backend/app/constants/country_registration.py`,导出:
- `COUNTRY_CODES`(9 国 code 元组)
- `LANGUAGE_CODES`(同前端,7 个 code 的元组)
- `DUPLICATE_REGISTRATION_ERROR_MESSAGE`(逐字与前端一致,后端 service 抛错时引用)
- `REGISTRATION_NO_MAX_LENGTH = 50`

**改 `frontend/src/lib/auth.ts`**:`registerSupplier()` 入参 type 同步(加 `country_code` / `language_preference`,删 `username`,字段名 `business_license_no` → `registration_no`)。

**改 `frontend/src/lib/validators.ts`**:
- phone 正则放宽 + 加 `TODO(I18N-PHONE)` 注释
- 新增 `validateRegistrationNoByCountry(code, value)` 函数(读 `COUNTRIES` 配置)

**交付物**:
1. 上述文件改动到位
2. 跑自测(见 §4.0.1):`pnpm -C frontend build && pnpm -C frontend lint` 通过后进入 Step 4

---

### Step 4 · 前端 3 步向导 UI

**目标**:实现 PRD §2 / §5 的 UI。

**文件清单**:

| 文件 | 动作 |
|---|---|
| `frontend/src/app/(auth)/register/page.tsx` | 改:SUPPLIER 分支重构为 3 步向导(BUYER 分支不动) |
| `frontend/src/app/(auth)/register/_components/StepIndicator.tsx` | 新增 |
| `frontend/src/app/(auth)/register/_components/StepCountry.tsx` | 新增 |
| `frontend/src/app/(auth)/register/_components/StepLanguage.tsx` | 新增 |
| `frontend/src/app/(auth)/register/_components/StepForm.tsx` | 新增 |
| `frontend/src/app/(auth)/register/_components/useRegisterDraft.ts` | 新增,封装 sessionStorage 读写 + debounce |

**关键实现细节**:

- `useRegisterDraft` hook:
  - mount 时 hydrate 一次
  - 任何字段更新时,debounce 500ms 后写 sessionStorage
  - 暴露 `clearDraft()`:供提交成功后/切换角色时调用
  - **绝对不存** `password` / `confirmPassword` 字段
  - 存储字段含 `currentStep`(1/2/3),hydrate 时落到对应 Step
- `StepCountry`:
  - 9 国 `<select>`,UI 文案全来自 `COPY`
  - 选中后下方信息条出现,数据来自该国 `regNo.label/hint`
  - 「下一步」在未选时 disabled
- `StepLanguage`:
  - 三个按钮 + 「← 返回重选国家」链接
  - 颜色用项目深蓝/橙(不用截图渐变紫)
  - 选中即把 `language_preference` 写入 draft 并推进 currentStep
- `StepForm`:
  - 顶部展示当前国家 + 凭证规则提示(只读)
  - 字段:`companyName` / `registration_no`(右上角徽章显示 country code,如 `MY`) / `name` / `phone` / `email` / `password` / `confirmPassword`
  - `registration_no` 字段:
    - 用 `COUNTRIES[i].regNo.transform`(若有,如 CN 自动转大写截断)
    - blur 时用 `regNo.regex` 校验
  - 提交成功 → `clearDraft()` → `router.replace('/login?registered=1')`(与现行为对齐)
  - 现有 sessionStorage `prefill_login` 逻辑保留(注册成功后自动填登录页)
- BUYER 分支:**完全不改**,提取共享代码时不能波及 BUYER 路径

**视觉**:Step 3 主按钮文案"提交入驻申请",颜色 `#FF6B35`;返回按钮文案"← 返回上一步"。

**交付物**:
1. 上述文件改动到位
2. 跑自测(见 §4.0.1):`pnpm build && pnpm lint` 通过;**手工启动 `pnpm dev`** 至少用 CN 和 MY 两国各跑通一次完整 3 步流程(截图)
3. 完成后进入 Step 5

---

### Step 5 · Dashboard banner + members 占位 + 登录页文案 + E2E 验证

**5.1 后端 `/auth/me` 补 `organization.status` 字段**

- `backend/app/schemas/auth.py`:`OrganizationOut` 加 `status: str | None = None`
- `backend/app/core/dependencies.py`:`CurrentUser.organization` 构造时把 `status` 填进去(SUPPLIER 看 `SupplierOrganization.status`,BUYER 看 `BuyerOrganization.status`)
- 测试:`test_me` 断言 `organization.status` 存在

**5.2 前端 Dashboard banner**

- `frontend/src/app/supplier/dashboard/page.tsx`:加 banner 区块,显示条件 `me.organization?.status === 'DRAFT'`
- 文案按 PRD §5.4:**入驻申请已提交,资料待完善 · 您的账号已创建,但企业入驻尚未完成审核与资料完善,暂无法上架商品。完整入驻流程将在后续版本上线。**
- 视觉:浅橙背景 + 橙色左边条(参考登录页 success banner 的样式风格,但换橙色)

**5.3 `/supplier/members` 占位页**

- `frontend/src/app/supplier/members/page.tsx`:`PermissionPlaceholderPage` 风格,标题"成员管理",描述"功能即将上线 · owner 可在此邀请、移除企业内员工"
- `frontend/src/config/navigation.ts`:SUPPLIER 侧边栏加入「成员管理」入口
- **不挂权限点**(PRD 明确 T-MEMBER 待办)

**5.4 登录页文案微调**

- `frontend/src/app/(auth)/login/page.tsx`:Label 与 placeholder 从「邮箱 / 用户名 / 手机号」改为「邮箱 / 手机号」
- **不动登录后端逻辑**(`_find_user_by_identifier` 三选一兼容性保留,免得老数据登录失败)

**5.5 E2E 验证(全部跑完后一次性截图)**

跑完整流程,**每条都要截图证明**:

1. `/register` → 选 SUPPLIER → Step 1 选马来西亚 → Step 2 选 Malay → Step 3 填表提交 → 跳 `/login?registered=1`
2. 登录 → 进 `/supplier/dashboard` → 顶部 banner 可见
3. 侧边栏「成员管理」可见,点进去看到占位文案
4. 用相同 country=MY + registration_no 第二次注册 → 报错文案严格匹配 PRD §5.3
5. 用 country=CN + 相同 registration_no 字符串注册 → 成功(复合唯一验证)
6. 刷新 Step 2 → 自动回到 Step 2,country 选择保留(sessionStorage 验证)
7. Step 3 填了一半切回 Step 1 改国家 → 回 Step 3 时已填字段保留

**最终交付物**(完成后**一次性**汇总给我):

- 7 张 E2E 截图
- `pytest backend/` 全绿输出
- `pnpm -C frontend build` 通过输出
- §7 所有 grep 校验项的实际输出(逐条贴 grep 命令 + 结果)
- 全部 commit hash 列表
- 一段总结:"做了什么 + 没做什么(对照 §5 禁止清单) + 遗留 TODO 编号清单"

---

## 5. 不要做的事(明确禁止)

- ❌ **不要改 BUYER 注册逻辑**——所有改动只针对 SUPPLIER 分支
- ❌ **不要改 RBAC 核心**(`backend/app/rbac/*`、`frontend/src/lib/permissions.ts`)
- ❌ **不要改登录后端逻辑** `_find_user_by_identifier`(三选一保留,避免老数据失败)
- ❌ **不要引入新依赖**(form library、i18n library、UI library 都不加)
- ❌ **不要实现成员邀请真实功能**(/supplier/members 是占位)
- ❌ **不要实现审核状态机**(approve/reject 接口、OPERATOR 审核页都不做)
- ❌ **不要实现 i18n 真翻译**(只存 language_preference,本轮不读)
- ❌ **不要在 Step 1/2 调任何后端接口**——3 步向导是纯前端编排
- ❌ **不要存密码到 sessionStorage**(任何路径都不行)
- ❌ **不要硬编码任何中文文案**到组件内(`grep -rn '"[\u4e00-\u9fa5]' frontend/src/app/(auth)/register/_components/` 应该返回 0 条)
- ❌ **不要乱删现有代码**——发现疑似废代码,告诉我,不要自己删
- ❌ **不要顺手做相邻功能**(看到 `/supplier/orders` 还是占位很想填?忍住,告诉我记 TODO)

---

## 6. 输出要求

- **不分 Step 等 review**:5 个 Step 一气呵成,每步自测通过即进下一步
- 每个 Step 完成时,**简短打印**:`✅ Step N 完成,自测通过(<跑的命令>),进入 Step N+1`(单行即可,不贴大段 diff/截图)
- 完整截图与最终汇总放到 **Step 5 结束**,一次性给我
- **关键决策不擅自决定**:发现 PRD 真矛盾才停下问;遇到 PRD 没说的边角,选最简方案 + 加 `TODO(...)` 注释,**不要为此停下**
- 一个 Step 一个 commit,message 格式:`feat(supplier-register): <Step 描述> [Step N/5]`

---

## 7. 验收标准

见 PRD §7。**所有勾选项必须满足才算完成**。**Step 5 结束时,逐条贴出实际执行的命令和输出**:

### 自动化校验(必须全部为绿/0/符合预期)

- [ ] `cd backend && pytest -v` — 全部测试用例通过(含本任务新增的)
- [ ] `cd frontend && pnpm build` — 0 type error
- [ ] `cd frontend && pnpm lint` — 0 error
- [ ] `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` — 三连无报错

### 字段语义校验(grep,**精准规则**,不再泛 grep 中文)

- [ ] **旧字段名彻底退出**:
  `grep -rn 'business_license_no' backend/app/ frontend/src/` → **输出 0 行**(alembic 历史 migration 文件除外,可白名单 `alembic/versions/`)
- [ ] **SUPPLIER 链路不含 username**:
  `grep -rn 'username' backend/app/schemas/auth.py backend/app/services/auth_service.py` 中,**与 SupplierRegister/register_supplier 相关的引用为 0**(允许 BUYER 路径与 `_find_user_by_identifier` 保留)
- [ ] **TODO 编号到位**(至少各 1 处):
  `grep -rn 'TODO(I18N-PHONE)' backend/ frontend/src/` ≥ 2 行 ·
  `grep -rn 'TODO(REG-RULE)' backend/ frontend/src/` ≥ 1 行 ·
  `grep -rn 'TODO(T-LANG-CHANGE)' backend/ frontend/src/` ≥ 1 行
- [ ] **重复注册错误文案前后端逐字一致**:
  `grep -n '当前企业已在平台注册' backend/app/constants/country_registration.py frontend/src/config/country-registration-rules.ts` → **两端各出现一次,字符串完全相同**;`backend/app/services/auth_service.py` 中通过 import 引用,**不再硬编码字面量**
- [ ] **password 不进 sessionStorage**:
  `grep -rn -E "sessionStorage.*(password|confirmPassword)" frontend/src/` → **输出 0 行**

### 功能验收

- [ ] §4 Step 5 的 7 条 E2E 全部截图证明
- [ ] PRD §7 全部勾选项满足

完成后,在 PRD §7 验收记录处签字(写所有 commit hash + 日期)。

---

## 8. 异常处理协议

### 8.1 必须停下报告的情况(**只有这几种**)

- **自测红**(§4.0 任一 Step 的自测命令失败,且尝试修复 2 次未果)
- **PRD 真有矛盾或多种合理理解**(已经看完 PRD v1.3 仍不能确定)
- **发现现有代码有显著 bug**(影响本任务正确性,例如 `_find_user_by_identifier` 中的逻辑缺陷)
- **migration `country_code` 兜底回填**或 alembic 自动检测异常,需要 `[allow-destructive-migration]` 决策
- **CI 拦截破坏性迁移**

### 8.2 **不**停下、按既定方案推进的情况

- PRD 没说的边角 → 选最简方案 + 加 `TODO(...)` 注释
- 发现可优化的相邻代码 → 记 TODO,**不顺手改**
- 实现细节有多种风格选择 → 沿用项目现有风格(参考 BUYER 分支、参考登录页),不发明新风格
- 想到了"未约定的好主意" → **忍住**,记 TODO 给我看

### 8.3 报告格式

```
[Step N] 暂停 · 原因:<8.1 中的哪一类>
跑的命令:<具体命令>
输出:<关键报错 paste>
我的判断:<问题原因>
建议:<选项 A / B / C>
需要拍板:<明确的问题>
```

### 8.4 严禁

- ❌ 修改测试断言以"绕过"失败
- ❌ 删除失败的测试用例
- ❌ try/except 吞异常
- ❌ 跳过失败的 Step 继续下一步
- ❌ 因为"想问问"而停下来——只有 8.1 列出的才允许停

---

## 9. 起手对话话术(给你的)

```
你好。我要按工单 docs/tasks/2026-W21-供应商注册3步向导.md 实现新功能。

请遵循我们项目的协作规范(参考 CLAUDE.md 与 04_ClaudeCode工单模板.docx):

1. 先阅读 docs/ 下的相关文档(含 PRD v1.3)
2. 在响应开头复述工单 §1 的 5 条关键决议(简短即可)
3. 复述完毕立即从 Step 1 开始动手,**不要等我 review**
4. 每个 Step 内部完成后,跑工单 §4.0.1 列出的自测命令
5. 自测全绿 → 继续下一步;自测红 → 按 §8.3 格式报告,等我拍板
6. 全部 5 个 Step 完成后,一次性把 §7 的全部校验结果 + §4 Step 5 的 7 条 E2E 截图 + 总结 汇总给我

例外:发现 PRD 真有矛盾或现有代码有 bug,按 §8.1 停下报告。
其它一律按工单/PRD 既定方案推进,不要为了"问问"而停。

工单已加载,开干。
```

---

*工单结束 · 总 Step 数 5(一气呵成 + 自测驱动)· 预计开发周期 1-1.5 工作日*
