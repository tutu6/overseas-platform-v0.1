# 供应商注册3步向导 PRD v1.4

> **类型** 增量补丁(delta) · **基线** PRD v1.3 已开发完成
> **本版定位** 仅描述"在 v1.3 实现之上的新增/改动",**不重复 v1.3 已有内容**
> **同步文档** PM 对齐清单 v1.4(决议归档)、工单 prompt v1.4(执行指令)
>
> **v1.4 增量来源**
> 1. 收到 PM 新需求文档《供应商注册模块详细开发需求》
> 2. PM 对齐清单 v1.4 闭环的 13 条决议
> 3. 用户强调的"提交按钮全字段校验通过才亮"主流程硬规则

---

## 0. v1.3 基线快速回顾(不再展开)

v1.3 已实现:
- 3 步向导(国家 / 语言 / 注册填报)+ sessionStorage 草稿暂存
- 9 国清单(MY / KH / PK / MA / IQ / ID / SA / AE / CN)+ 配置驱动的 `country-registration-rules.ts`
- 后端 `supplier_organizations` 含 `country_code` + `registration_no`,`(country_code, registration_no)` 复合唯一
- `users.language_preference` 字段
- 重复注册 A 方案(不暴露 owner)
- Dashboard 待完善资料 banner + `/supplier/members` 占位 + 登录页文案微调

**本轮 v1.4 不重做以上任何已实现项**,只做 §1 列出的 9 项增量。

---

## 1. 本版增量(9 项)

### Δ1 · 全局密码规则升级(影响所有角色)

**改 `backend/app/core/security.py`** 的 `validate_password_strength`:

```python
PASSWORD_MIN_LENGTH = 11
PASSWORD_MAX_LENGTH = 50

def validate_password_strength(password: str) -> bool:
    """密码强度:11-50 位 + 数字/大写/小写/特殊字符 至少 3 类。
    特殊字符宽松定义:任何非字母数字字符。
    """
    if not (PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH):
        return False
    cats = sum([
        any(c.isdigit() for c in password),
        any(c.isupper() for c in password),
        any(c.islower() for c in password),
        any(not c.isalnum() for c in password),
    ])
    return cats >= 3
```

**配套**:
- 错误文案统一:"密码 11-50 位,需包含数字、大写字母、小写字母、特殊字符中至少 3 类"
- `BuyerRegisterIn` / `SupplierRegisterIn` / `ChangePasswordIn` 自动跟着新函数走(已是)
- 内部账号创建(`admin_users` 路径)同样走新规则

**种子用户密码迁移**:
- `backend/.env.example` 与 `backend/.env`(若有):`SUPER_ADMIN_INITIAL_PASSWORD=Aa123456789`(11 位 + 3 类,合法)
- `backend/app/seed.py` 内若硬编码弱密码,同步替换
- `backend/tests/` 所有测试用例的弱密码统一替换成 `Aa123456789` 或 `Test1234567`(均 11 位 + 3 类)

### Δ2 · 前端密码 validator 同步

**改 `frontend/src/lib/validators.ts`**:
- `validatePassword` 升级到与后端等价的规则
- `PASSWORD_RE`(若存在)同步,或改用编程式校验(逐位查 4 类字符)
- 错误文案与后端一致

**改前端密码强度提示组件**(如有):文案同步。

### Δ3 · 5 国正则按 PM 文档替换

PM 新需求文档 §2.1 给出了具体正则,**替换 v1.3 占位**:

| 国家 | v1.3 占位 | v1.4 PM 文档值 | 凭证名变化 |
|---|---|---|---|
| **KH** 柬埔寨 | `^[0-9]{6,12}$` | `^[A-Z0-9]{10,12}$` | MOC(不变) |
| **PK** 巴基斯坦 | `^[0-9]{7,8}$`(NTN) | `^[A-Z0-9]{7,10}$` | **NTN → SECP** |
| **MA** 摩洛哥 | `^[0-9]{1,20}$`(RC) | `^[0-9]{15}$` | **RC → ICE** |
| **IQ** 伊拉克 | `^.{1,30}$` | `^[0-9]{6,10}$` | MoC(不变) |
| **AE** 阿联酋 | `^.{1,30}$` | `^[A-Z0-9]{6,12}$` | License(不变) |

**4 国不动**(v1.3 占位已经与 PM 文档或国标等价):
- MY:`^\d{12}$` / SSM
- SA:`^\d{10}$` / CR(PM 文档已给,与 v1.3 占位等价)
- ID:`^\d{13}$` / NIB
- CN:`^[0-9A-Z]{18}$` / 统一社会信用代码(国标 GB 32100-2015,无需 PM 给)

**改动位置**(单一可信源):
- `frontend/src/config/country-registration-rules.ts`:5 国 `regNo.regex` 和 `regNo.hint` 更新;PK/MA 的 `regNo.label` 改成 SECP / ICE
- `backend/app/constants/country_registration.py`:如有正则同步,跟前端逐字一致

⚠️ **保留** `TODO(REG-RULE)` 注释:各国精确正则待业务深化时再校,本轮以 PM 文档为最新基准。

### Δ4 · 改国家自动清字段 + 重置语言

**`useRegisterDraft` 暴露两个新方法**:
- `clearRegistrationNo()` — 清空 `registration_no`
- `clearLanguagePreference()` — 重置 `language_preference`

**触发点**:`StepCountry` 内,用户在 Step 1 重新选择国家时(包括从 Step 2/3 返回 Step 1 改选),自动调用上述两个方法。

**保留**的其他字段:`company_name` / `name` / `phone` / `email`(不受国家影响)。

### Δ5 · 注册号自动 trim + 按国家配置 transform

**改 `country-registration-rules.ts`** 的 `transform` 函数:

| 国家 | transform 行为 |
|---|---|
| **字母数字国家**(CN / KH / PK / AE)| `v.trim().toUpperCase().slice(0, MAX)` |
| **纯数字国家**(MY / ID / MA / IQ / SA)| `v.trim().replace(/\D/g, '').slice(0, MAX)` |

`StepForm` 内 `registration_no` 字段 `onChange` 时调用 `COUNTRIES[i].regNo.transform(value)` 后再 setState。

效果:
- 用户复制粘贴带空格 → 自动 trim
- 字母数字国家用户输小写 → 自动转大写
- 纯数字国家用户误输字母 → 自动过滤掉

### Δ6 · 提交按钮置灰(主流程级硬规则)

**这是本轮 UI 最重要的变更,Step 3 提交按钮的可用性 = 全字段校验状态的实时映射**。

**新增 `validators.ts` 函数**:

```typescript
export function validateAllRegisterFields(
  form: SupplierRegisterForm,
  countryCode: CountryCode
): { valid: boolean; errors: { field: string; fieldLabel: string; message: string }[] };
```

**`StepForm` 内**:
```typescript
const validation = useMemo(
  () => validateAllRegisterFields(form, country.code),
  [form, country.code]
);
const isFormValid = validation.valid;
const missingFields = validation.errors.map(e => e.fieldLabel);

<button
  type="submit"
  disabled={!isFormValid}
  title={isFormValid ? '' : `请完善:${missingFields.join('、')}`}
  className={
    isFormValid
      ? 'bg-[#FF6B35] hover:bg-[#e05a25] text-white cursor-pointer ...'
      : 'bg-gray-300 text-gray-500 cursor-not-allowed ...'
  }
>
  提交入驻申请
</button>
```

⚠️ 校验 `useMemo` 依赖 `form` 与 `country.code`,确保任一字段变化都重算。

### Δ7 · 离开页 beforeunload 提示

**新增** `frontend/src/app/(auth)/register/_components/useBeforeUnload.ts`:

```typescript
export function useBeforeUnload(shouldWarn: boolean): void {
  useEffect(() => {
    if (!shouldWarn) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';  // 浏览器使用原生文案,自定义 message 在现代浏览器已被禁用
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [shouldWarn]);
}
```

**触发条件**:`currentStep >= 2 && draft 中至少有一个字段非空`。

**注意**:与 sessionStorage 草稿暂存是双保险——用户即便确认离开,再回 `/register` 仍能接续草稿。这个 beforeunload 只是给用户一个"刹车提示"。

### Δ8 · 已登录用户访问 `/register` 自动跳工作台

**实现位置**:`/register` 页面 mount 时 + `frontend/src/middleware.ts`(双保险)。

**逻辑**:
```typescript
// /register page mount
const me = useAuthStore(s => s.me);
useEffect(() => {
  if (me && me.roles?.length) {
    if (me.roles.includes('SUPPLIER')) router.replace('/supplier/dashboard');
    else if (me.roles.includes('BUYER')) router.replace('/buyer/dashboard');
    // OPERATOR / ADMIN 默认跳 /admin 或对应工作台(沿用现有 defaultDashboardOf 逻辑)
  }
}, [me]);
```

如果项目已有 `defaultDashboardOf(role)` 工具,直接复用。

### Δ9 · 错误响应 code 数字明确

**约束**(已在 v1.3 实现,本轮**显式强化**):
- HTTP 409 重复注册响应:`code: 40901`(**数字**)+ message + `data: null`
- 后端代码内部异常类名 `SupplierAlreadyRegisteredError`(**字符串**只在 Python / 日志 / 审计可见)
- **前端识别错误必须用数字** `if (response.code === 40901)`;**严禁字符串比较**

**新增配置**(若 v1.3 未导出):
```typescript
// country-registration-rules.ts
export const BUSINESS_CODE_DUPLICATE_SUPPLIER_REGISTRATION = 40901;
```

前端组件内 `if (err.code === BUSINESS_CODE_DUPLICATE_SUPPLIER_REGISTRATION) { ... }`。

---

## 2. 不在本轮范围

| 不做 | 原因 |
|---|---|
| 9 国清单调整 | v1.3 已定,不变(PM 文档里"泰国"是 PM 误,我们沿用 SA 不含 TH)|
| 重新设计 3 步向导 / sessionStorage | v1.3 已实现 |
| Dashboard banner / members 占位 / 登录页文案 | v1.3 已实现 |
| 后端 schema 字段重命名 / 复合唯一约束 | v1.3 已实现 |
| BUYER 注册业务字段改动 | **但** Δ1 密码规则升级会同步影响 BUYER 密码校验的错误文案 |
| 真翻译 / 资质上传 / 审核状态机 / 注册防刷 / D&B | 待办,v1.3 已记录 |
| 沙特(SA)精确正则进一步校 | PM 文档已给 `^\d{10}$`,与 v1.3 占位一致 |
| 注册号问号图标 + 示例图片(PM §6 提议)| T-FORM-HELP 待办 |
| 强弱校验分级(PM §6 提议)| 待 T-REVIEW 配套 |

---

## 3. 增量验收(只验本轮新增,v1.3 验收项不重复)

### 功能验收

- [ ] **Δ1/Δ2** · 密码 `Aa12345` (< 11 位) → 拒绝
- [ ] **Δ1/Δ2** · 密码 `aaaaaaaaaaa` (11 位但只 1 类字符)→ 拒绝
- [ ] **Δ1/Δ2** · 密码 `Aa123456789` (11 位 + 3 类)→ 通过
- [ ] **Δ1** · 种子超管账号用 `.env.example` 默认 `Aa123456789` 启动,可正常工作
- [ ] **Δ3** · PK 注册用 SECP 格式 `ABC1234567`(7-10 位字母数字)→ 通过
- [ ] **Δ3** · MA 注册用 ICE 格式 15 位数字 → 通过
- [ ] **Δ3** · IQ 注册号填字母 → 拒绝(只能数字)
- [ ] **Δ4** · Step 1 选了 MY,Step 3 填了 `202301012345`,回 Step 1 改选 ID → 回到 Step 3 时 `registration_no` 已清空
- [ ] **Δ4** · Step 1 选了 ID,Step 2 选了印尼语,回 Step 1 改选 CN → Step 2 语言已重置为未选状态
- [ ] **Δ5** · MY 注册号输入 `  202301012345  `(带空格)→ 自动 trim
- [ ] **Δ5** · CN 输入 `91110000abc123de45`(小写字母)→ 自动转大写
- [ ] **Δ5** · MY 输入 `2023ABC01012`(含字母)→ 字母自动过滤,只剩 `2023010124`(实际只剩数字)
- [ ] **Δ6** · Step 3 任一字段未通过校验 → 提交按钮置灰
- [ ] **Δ6** · Step 3 任一字段未通过校验 → 鼠标 hover 按钮显示"请完善:X、Y、Z"
- [ ] **Δ6** · Step 3 全字段通过 → 按钮亮起为橙色 `#FF6B35`
- [ ] **Δ7** · Step 2/3 有未提交数据,关 tab → 浏览器原生确认框
- [ ] **Δ7** · 注册成功后跳 `/login`,关 tab 不弹框(因为 draft 已清)
- [ ] **Δ8** · 已登录 SUPPLIER 访问 `/register` → 自动跳 `/supplier/dashboard`
- [ ] **Δ8** · 已登录 BUYER 访问 `/register` → 自动跳 `/buyer/dashboard`
- [ ] **Δ9** · 重复注册 → Network 面板看到响应 `code: 40901`(数字,非字符串)

### 自动化校验

- [ ] `cd backend && pytest -v` 全绿(密码强度相关测试用例已升级)
- [ ] `cd frontend && pnpm build && pnpm lint` 0 error
- [ ] `grep -rn -E "code.*===.*['\"]SUPPLIER" frontend/src/` → 0 行(前端不允许字符串比较 code)
- [ ] `grep -rn "SUPPLIER_ALREADY_REGISTERED" frontend/src/` → 0 行(异常类名只在后端)
- [ ] `grep -n '11' backend/app/core/security.py` → 看到 `PASSWORD_MIN_LENGTH = 11` 或等价逻辑
- [ ] `grep -rn -E "'8.*32'|'8-32'" backend/ frontend/src/lib/` → 0 行(旧的 8-32 表述已退出)

---

## 4. 待办更新(基于本轮决议)

| 编号 | 内容 | 状态 |
|---|---|---|
| T-REGRULE | 各国 registration_no 精确正则 | **本轮 PM 已补 7 国;沙特(SA)用 v1.3 占位 + PM 文档给的 `^\d{10}$`(已等价);剩 CN 用国标,无需补** |
| T-FORM-HELP | 注册号问号图标 + 示例图片(PM §6 提议)| 新增 |
| T-PWD-POLICY | ~~全局密码规则升级~~ | **本轮已完成,标记 ✅ 关闭** |
| 其它沿用 v1.3 T-* 列表 | (见 v1.3 PRD §8) | 不变 |

---

*PRD v1.4 (delta) · 与 PM 对齐清单 v1.4 / 工单 prompt v1.4 同步 · 基线 v1.3 已开发完成*
