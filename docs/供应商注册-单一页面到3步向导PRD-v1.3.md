# PRD · 供应商注册(3 步向导)

> **版本** v1.3 · **状态** 待 review
> **变更性质** 改造现有 `/register` 的 SUPPLIER 分支 + 后端 schema 适配
> **不动** BUYER 注册;审核状态机;资质上传;成员管理逻辑
>
> **v1.3 相对 v1.2 的变更**
> - **§5.3 收窄"常量化"边界**:仅"前后端必须一致 / 错一字即 bug 的字符串"进常量;一次性展示文案直接硬编码在组件 JSX 里。
>
> **v1.2 相对 v1.0 的变更**
> 1. `language_preference` 落到 **`users.language_preference`**(个人属性,nullable):本轮只在 SUPPLIER 自助注册时写入,BUYER 注册 / 内部账号 / owner 添加员工等场景均不写,值为 NULL。**用户自助切换语言偏好的入口列为待办 T-LANG-CHANGE**(本轮不做)。
> 2. 3 步向导期间用 **sessionStorage 草稿暂存**:刷新不丢、Step 间回退不丢、密码不存、关 tab 即清。
> 3. 明确**不存在"每步 update"接口**:整个注册仍是 Step 3 提交时唯一一次 `POST /register/supplier`。

---

## 1. 背景与目标

现有 `/register` 是单页表单,BUYER/SUPPLIER 共用。本次只重做 **SUPPLIER 分支**:拆为 **3 步向导**,让海外供应商先选属地、再选语言偏好、最后填表。属地决定后续凭证规则,语言偏好留占位为后续国际化铺路。

**关键约束**

- 所有可枚举数据(9 国、凭证规则、文案 key、状态码)集中在配置/常量文件,**禁止散落硬编码**
- 视觉沿用现有 `(auth)/layout.tsx`(深蓝渐变 + 白卡片 + 橙顶边),**不照搬截图的紫色按钮**
- 文案严格按产品经理示意图(三张截图)措辞

---

## 2. 流程与字段

### 2.1 三步向导

```
Step 1 属地选择            Step 2 语言偏好             Step 3 注册填报
──────────────             ──────────────              ──────────────
选择企业注册地              选(不真翻译,只存偏好)        公司名 / 注册号 /
↓                          ↓                            联系人 / 电话 /
看到该国凭证规则提示         · 翻译为 <本地语>            邮箱 / 密码
↓                          · 翻译为 English              ↓
[下一步]                    · 保持中文                    [← 上一步][提交入驻申请]
                            [← 返回重选国家]               ↓
                                                          成功 → /login?registered=1
```

### 2.2 字段表

| 字段 | 必填 | 校验 | 备注 |
|---|---|---|---|
| `country_code` | ✓ | 9 国枚举之一 | Step 1 选择,贯穿后续 |
| `language_preference` | ✓ | `<本地语 code>` / `en` / `zh` | Step 2 选择,提交时落到 **`users.language_preference`**;本轮不影响表单文案 |
| `company_name` | ✓ | 1-200 字符,trim 非空 | |
| `registration_no` | ✓ | **按 country_code 分发校验**,见 §3 配置 | 由 `business_license_no` 重命名而来 |
| `name`(联系人) | ✓ | 1-100 字符 | |
| `phone`(联系电话)| ✓ | 占位正则 `^[+0-9\s\-]{6,20}$`,能覆盖中国 11 位 | **本轮必填**(因为去 username 后,phone 是主要登录凭证)。`TODO(I18N-PHONE)`:各国 phone 规则待补 |
| `email` | ✓ | EmailStr | |
| `password` | ✓ | 8-32 位 + 1 字母 + 1 数字(沿用现规则)| |
| `confirmPassword` | ✓ | 与 password 一致 | 仅前端校验,不入后端 |
| `username` | — | **去掉** | SUPPLIER 不收 username;登录页同步去掉 username 提示 |

### 2.3 跨步骤状态(sessionStorage 暂存)

3 步向导期间所有用户输入暂存在 **sessionStorage**(`register_supplier_draft`),实现:

- **刷新不丢**:Step 1/2/3 任意位置刷新,数据保留,自动回到原 Step
- **回退不丢**:从 Step 3 点「← 返回上一步」回到 Step 2 / Step 1,Step 3 已填字段保留
- **关 tab 即清**:sessionStorage 是 tab 级,关闭后自动清,无残留风险
- **跨 tab 不串**:新开 tab 不读旧 tab 的草稿

**存储字段**:`country_code` / `language_preference` / `company_name` / `registration_no` / `name` / `phone` / `email` / `currentStep`(1/2/3)

**不存**:`password` / `confirmPassword`——密码不进任何本地存储,刷新/回退后用户重填。这是硬规则,不可妥协(XSS 防御纵深)。

**清除时机**:
- 注册提交成功跳转 `/login` 时 → 清
- 用户在 `/register` 入口重新选择角色(BUYER/SUPPLIER 切换)时 → 清

**写入策略**:input/select 变化时写,加 500ms debounce 避免高频写。

**读取**:`/register` 页面 mount 时一次性 hydrate,根据 `currentStep` 落到对应 Step。

**Step 间数据契约**:Step N 之间的导航不调后端,纯前端 state 与 sessionStorage。**只有 Step 3 「提交入驻申请」按钮触发唯一一次 `POST /api/v1/auth/register/supplier`**——后端事务原子创建 User + SupplierOrg + SupplierMember + UserRole + AuditLog。

---

## 3. 9 国凭证规则(配置单一可信源)

落地位置:`frontend/src/config/country-registration-rules.ts`(前端用) + `backend/app/constants/country_registration.py`(后端校验用,与前端保持手工同步)。

| code | 中文 | 英文 | localLang | 凭证名 | 格式正则(占位) | UI 提示 |
|---|---|---|---|---|---|---|
| CN | 中国 | China | zh | 统一社会信用代码 | `^[0-9A-Z]{18}$` | "统一社会信用代码 (18 位)" |
| KH | 柬埔寨 | Cambodia | km | MOC 注册号 | `^[0-9]{6,12}$` | "MOC 注册号 (6-12 位数字)" |
| PK | 巴基斯坦 | Pakistan | ur | NTN 税号 | `^[0-9]{7,8}$` | "NTN 税号 (7-8 位数字)" |
| MA | 摩洛哥 | Morocco | ar | RC 商业登记号 | `^[0-9]{1,20}$` | "RC 商业登记号" |
| IQ | 伊拉克 | Iraq | ar | 商业登记号 | `^.{1,30}$` | "商业登记号" |
| ID | 印尼 | Indonesia | id | NIB(营业识别号)| `^[0-9]{13}$` | "NIB 注册号 (13 位纯数字)" |
| MY | 马来西亚 | Malaysia | ms | SSM 注册号 | `^[0-9]{12}$` | "SSM 注册号 (12 位纯数字)" |
| SA | 沙特阿拉伯 | Saudi Arabia | ar | CR Number | `^[0-9]{10}$` | "CR 商业登记号 (10 位数字)" |
| AE | 阿联酋 | UAE | ar | Trade License No | `^.{1,30}$` | "营业执照号" |

**注**:正则是占位,前端轻校验 + 后端长度/字符集兜底。各国精确规则后续业务深化时补。代码层 `TODO(REG-RULE)` 标注。

---

## 4. 后端改动

### 4.1 数据库迁移(1 个 alembic migration)

**表 `supplier_organizations`**:

| 改动 | 说明 |
|---|---|
| 加列 `country_code VARCHAR(2) NOT NULL` | 9 国 code 之一,应用层枚举校验 |
| 重命名 `business_license_no` → `registration_no` | `ALTER COLUMN ... RENAME TO ...`,数据保留 |
| **删除原 UNIQUE(business_license_no)** | 因不再全表单字段唯一 |
| **新增 UNIQUE(country_code, registration_no)** | 复合唯一,不同国家可撞号 |

**表 `users`**:

| 改动 | 说明 |
|---|---|
| 加列 `language_preference VARCHAR(10) NULL` | 个人语言偏好,nullable。本轮只在 **SUPPLIER 自助注册**时由 Step 2 写入;BUYER 注册、内部账号(OPERATOR/ADMIN)、未来 owner 添加员工等场景**均不写**,值为 NULL。本轮代码不读此字段。|

**注意**:本地 dev 库目前只有少量测试数据,生产暂未部署。migration 含 ALTER/RENAME 但不含 DROP COLUMN/TABLE,不触发 CI 破坏性拦截。

### 4.2 Schema 改动

`backend/app/schemas/auth.py` 的 `SupplierRegisterIn`:

- 加 `country_code: str`(Pydantic 枚举校验,值取自 `app.constants.country_registration.COUNTRY_CODES`)
- 加 `language_preference: str`(必填,值取自配置中合法 code 集合)
- 字段名 `business_license_no` → `registration_no`
- `phone` 必填(`min_length=6`)
- `username` 字段移除(SUPPLIER 入参不再含 username)
- phone 正则放宽到占位规则,加 `TODO(I18N-PHONE)`

### 4.3 Service 改动

`auth_service.register_supplier`:

- 唯一性查询从 `where(business_license_no == ...)` 改为 `where((country_code == ...) & (registration_no == ...))`
- 重复时抛 `ConflictError("当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。")`(按设计点 1 · A 方案,**不暴露 owner 信息**)
- SupplierOrg 创建时填 `country_code`,字段名同步更新
- **User 创建时填入 `language_preference`**
- 审计 extra 加 `country_code` 与 `language_preference`

### 4.4 已闭环的契约(不变)

- 首次注册:User + SupplierOrg(DRAFT)+ SupplierMember(is_owner=true)+ SUPPLIER 角色,事务内
- 重复注册:**立即抛 409,不创建任何数据**(User/Member/Org/审计都不写)
- 注册成功后**不自动登录**,前端跳 `/login?registered=1`

---

## 5. 前端改动

### 5.1 文件清单

| 文件 | 动作 |
|---|---|
| `src/config/country-registration-rules.ts` | **新增**,9 国 + 凭证规则 + 文案 key |
| `src/app/(auth)/register/page.tsx` | **改造**:SUPPLIER 分支拆为 3 步向导 |
| `src/app/(auth)/register/_components/StepCountry.tsx` | **新增**,Step 1 |
| `src/app/(auth)/register/_components/StepLanguage.tsx` | **新增**,Step 2 |
| `src/app/(auth)/register/_components/StepForm.tsx` | **新增**,Step 3 |
| `src/app/(auth)/register/_components/StepIndicator.tsx` | **新增**,步骤条 |
| `src/app/(auth)/login/page.tsx` | **微改**:placeholder 与 label 去掉"用户名",改为"手机号或邮箱" |
| `src/app/supplier/dashboard/page.tsx` | **微改**:加"待完善资料"banner(详见 §5.4)|
| `src/app/supplier/members/page.tsx` | **新增**,占位页(`PermissionPlaceholderPage` 风格,文案"成员管理功能即将上线")|
| `src/config/navigation.ts` | 加 `/supplier/members` 入口 |
| `src/lib/validators.ts` | 加 `validateRegistrationNoByCountry(code, value)`;phone 正则放宽 |
| `src/lib/auth.ts` | `registerSupplier` 请求体加 `country_code` / 去 `username` / 重命名字段 |

### 5.2 Step 行为细节

**Step 1**:9 国 `<select>`(原生 select,无第三方下拉库);选中后下方出现浅蓝信息条「您选择了 <X>。后续系统将要求您提供 <凭证名> (<规则提示>) 作为核心准入凭证。」;[下一步] 按钮在选中前 disabled。

**Step 2**:三个按钮 + 一个返回链接,按钮颜色用项目深蓝/橙体系(不用截图渐变紫)。选中后 `language_preference` 存入组件状态,**本轮不改表单文案**。

**Step 3**:展示当前选择的国家与凭证规则(只读,右上角小徽章 `<country code>`,如 `MY` `SA`);字段按 §2.2,Step 3 内的 `companyName`、`registration_no` 用截图风格的浅蓝填充框,其余字段沿用现有 input 风格;按 country_code 分发 `registration_no` 的前端校验。

### 5.3 文案与常量边界

**判断标准**:**这句话错一个字会不会引发 bug?**

- 错一个字 = bug(前后端要对齐 / 状态值 / 字段标识)→ **进常量文件**
- 错一个字 = 看着别扭但不影响功能(纯一次性展示)→ **直接写在组件 JSX 里**

#### 进 `country-registration-rules.ts` 的内容

- `COUNTRIES`:9 国 code + 中英文名 + localLang + 凭证规则(label / hint / regex / transform)
- `LANGUAGE_CODES`:`language_preference` 合法值并集(`zh` / `en` / 9 国 localLang)
- `DUPLICATE_REGISTRATION_ERROR_MESSAGE`:重复注册错误文案。**后端常量同步**(`backend/app/constants/country_registration.py`),前后端字符串必须**逐字一致**
- `COUNTRY_HINT_TEMPLATE(country)`:Step 1 选中后的提示文案模板函数(数据驱动)
- `STATUS_DRAFT = 'DRAFT'`:状态字符串(未来增加状态时统一加在此处)

#### 直接硬编码在组件 JSX 里的内容

- 品牌主标 / 副标
- Step 标题 / 副标题
- 字段 label / placeholder
- 按钮文字
- Dashboard banner 文案

#### 文案措辞(严格按截图,无论硬编码还是入常量)

| 文案 | 措辞 |
|---|---|
| 品牌主标 | "海外工程供应链平台" |
| 品牌副标 | "Global EPC Supply Chain Portal" |
| Step 1 标题 | "选择您的企业注册地" |
| Step 1 副标题 | "请严格按照营业执照所在国家选择,这决定了后续的资质校验标准。" |
| Step 1 选中提示 | "您选择了 {nameZh}。后续系统将要求您提供 {regNoLabel}({regNoHint})作为核心准入凭证。" |
| Step 2 标题 | "是否开启多语种适配?" |
| Step 2 副标题 | "检测到您选择了 {nameZh}。是否需要启用 Gemini AI 本地化引擎,将后续的注册表单翻译为 {localLangName} ({langCode}-{countryCode})?" |
| Step 3 标题 | "海外供应商入驻" |
| Step 3 副标题 | "请填写真实的自然人与企业组织信息" |
| 字段 label | "公司名称" / "{凭证名}" + 国别徽章 / "联系人" / "联系电话" / "联系邮箱" / "输入密码" / "密码确认" |
| 提交按钮 | "提交入驻申请" |
| 返回按钮 | "返回上一步" |
| 重复注册错误 | "当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。" |
| Dashboard banner | "入驻申请已提交,资料待完善 · 您的账号已创建,但企业入驻尚未完成审核与资料完善,暂无法上架商品。完整入驻流程将在后续版本上线。" |

### 5.4 Dashboard 待完善资料 banner

`/supplier/dashboard` 加一个 banner,样式参照项目现有 alert 风格(橙色边):

> **入驻申请已提交,资料待完善** · 您的账号已创建,但企业入驻尚未完成审核与资料完善,**暂无法上架商品**。完整入驻流程将在后续版本上线。

**显示条件**:`SupplierOrg.status === 'DRAFT'`。**目前所有 SUPPLIER 都是 DRAFT,所以始终显示**——直到审核流程上线后状态变更,banner 才会消失。这一行为是当前预期。

**实现**:`/auth/me` 已返回 `organization`,但当前 `OrganizationOut` schema 没有 `status` 字段。需要在 `OrganizationOut` 里**加 `status` 可选字段**,并在 `core/dependencies.py` 的 `CurrentUser.organization` 取数时把 `status` 填上。

### 5.5 `/supplier/members` 占位

复用 `PermissionPlaceholderPage` 风格,标题"成员管理",描述"功能即将上线 · owner 可在此邀请、移除企业内员工"。**不挂权限点**(未来再补)。导航项位置:供应商工作台侧边栏「我的档案」附近。

---

## 6. 不在范围

| 不做 | 原因 |
|---|---|
| 成员邀请/移除真实功能 | 单独 PRD,涉及邀请链接 / 邮件 / 设密流程 |
| 资质图片上传 | 单独 PRD,涉及 OSS / 文件鉴权 |
| 审核状态机 (`UNDER_REVIEW` → `APPROVED`/`REJECTED`) | 单独 PRD,涉及 OPERATOR 审核工作台 |
| 国际化真翻译 | 单独 PRD,涉及 i18n 框架选型(MVP 明确不引入) |
| 注册防刷 (验证码/IP 限流) | 记为待办,本轮唯一约束兜底足够 |
| 各国 phone 精确校验 | `TODO(I18N-PHONE)` 标记,本轮占位正则覆盖中国 |
| 各国凭证精确正则 | `TODO(REG-RULE)` 标记,本轮占位规则 |
| BUYER 注册任何改动 | 本次需求明确限定 SUPPLIER |
| owner 转让 / owner 离职 | 单独议题,记入待办 |

---

## 7. 验收标准

### 功能

- [ ] 访问 `/register` → 选 SUPPLIER 角色 → 进入 Step 1
- [ ] Step 1 不选国家时 [下一步] 按钮 disabled
- [ ] 选中任一国后下方出现该国凭证规则提示
- [ ] Step 2 可选三个语言按钮,可返回 Step 1
- [ ] Step 3 表单字段按 §2.2 完整,凭证号字段右上角带国别徽章
- [ ] 凭证号格式不符 → 前端报错(blur 时)
- [ ] 字段全合法 → 提交成功 → 跳 `/login?registered=1`
- [ ] 同 country_code + registration_no 第二次注册 → 报「当前企业已在平台注册...」,409
- [ ] 不同国家但相同 registration_no 字符串可成功(复合唯一)
- [ ] 注册成功的供应商登录后 → `/supplier/dashboard` 顶部显示「入驻申请已提交,资料待完善」banner
- [ ] 侧边栏可看到「成员管理」入口,点击进入显示占位

### 技术

- [ ] 后端 pytest 全绿(含新增的复合唯一 + country_code 校验用例)
- [ ] 后端 alembic migration 一次 upgrade + 一次 downgrade 干净跑过
- [ ] 前端 `pnpm build` 0 type error
- [ ] 9 国数据、凭证规则、所有文案均集中在 `country-registration-rules.ts`,组件内**零硬编码字符串**(grep 验证)
- [ ] `TODO(I18N-PHONE)` / `TODO(REG-RULE)` 注释存在于配置文件

### 安全/合规

- [ ] 重复注册错误**不返回**任何已存在 SupplierOrg 的字段(不暴露公司名、owner 信息)
- [ ] 重复注册时审计日志**不写**(沿用现行为)

---

## 8. 已知待办(记录,不做)

| 编号 | 内容 |
|---|---|
| T-MEMBER | 成员邀请/移除真实功能 |
| T-REVIEW | 供应商审核状态机 + OPERATOR 审核页 |
| T-UPLOAD | 资质图片上传 |
| T-I18N | 国际化真翻译 |
| T-RATELIMIT | 注册防刷 |
| T-OWNER | owner 转让 / 离职边界 |
| T-PHONE | 各国 phone 精确校验规则 |
| T-REGRULE | 各国 registration_no 精确正则 |
| **T-LANG-CHANGE** | **用户自助切换 `language_preference` 的入口**。本轮只有 SUPPLIER 注册 Step 2 能写入此字段;其他用户(BUYER、内部账号、owner 邀请的员工等)首次入库时为 NULL,且没有任何途径修改。需要补:(1) `PATCH /api/v1/auth/me/language` 接口;(2) 设置页 / 顶栏的语言切换入口 |

---

## 9. 开放问题

无。所有设计点已闭环。

---

*PRD 结束 · 字数控制在必要范围,不展开赘述*
