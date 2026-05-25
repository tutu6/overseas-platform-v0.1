# Task: 供应商注册3步向导 · v1.4 增量补丁

> **类型** 增量工单(delta) · **基线** v1.3 已开发完成并合入
> **本工单定位** 仅描述"在 v1.3 已有代码上的新增/改动",**不重做 v1.3 已实现部分**
> **PRD 依据** `docs/prd/供应商注册3步向导 PRD v1.4.md`(delta)
> **PM 决议归档** `docs/供应商注册3步向导 PM对齐清单 v1.4.md`
> **交付节奏** 一气呵成,自测驱动;**只有自测失败或 PRD 真矛盾时才停下报告**

---

## 1. 任务上下文

请先阅读以下文档:

- `CLAUDE.md`(项目级协作约定)
- `docs/prd/供应商注册3步向导 PRD v1.4.md`(**本任务核心契约,delta 类型**)
- `docs/供应商注册3步向导 PM对齐清单 v1.4.md`(13 条决议归档)

**v1.3 已开发完成的内容不需要重读历史 PRD**;直接在现有代码基础上加 delta 即可。

### 1.1 在响应开头复述以下 6 条关键决议(简短即可,各 1-2 句话证明你理解了),复述完毕立即进入 Step 1,不要等 review:

1. **本轮是 delta 增量**:基线 v1.3 已开发完成,9 国清单 / 3 步向导 / sessionStorage / 复合唯一约束 / Dashboard banner / members 占位 / 登录页文案这些**已存在,不重做**
2. **全局密码规则升级 11-50 + 3 类**:影响所有角色,本轮一锅完成,种子用户密码 `Aa123456789`
3. **5 国正则按 PM 文档替换**:KH / PK / MA / IQ / AE;PK 凭证 NTN→SECP,MA 凭证 RC→ICE;MY / SA / ID / CN 不动
4. **改国家自动清** `registration_no` + 重置 `language_preference`;其他字段保留
5. **注册号 transform**:字母数字国 trim+toUpperCase;纯数字国 trim+replace 非数字
6. **提交按钮置灰主流程级硬规则**:Step 3 全字段校验通过前置灰,hover 显示"请完善:X、Y、Z"

### 1.2 唯一允许停下来的时机

复述后**仅在以下情况停下**:
- 仓库现状与 PRD v1.3 基线不符(v1.3 似乎没跑完 / 字段命名不一致 / 等)
- PRD v1.4 与 v1.3 已实现代码真矛盾

否则一律按 PRD/工单既定方案推进。

---

## 2. 任务范围

实现 PRD v1.4 §1 的 9 项增量(Δ1-Δ9)。详见 PRD。**不做** PRD §2 列的"不在本轮范围"。

---

## 3. 技术约束

### 3.1 项目级(沿用 CLAUDE.md,不变)

略,跟之前所有工单一致。

### 3.2 本轮特别强调

- **delta 思维**:不要重写已实现的文件,只改/加必要部分;改之前先 `view` 现状
- **5 国正则替换**只动 `country-registration-rules.ts` 的 `regex` / `label` / `hint` 三个字段;**保留** `TODO(REG-RULE)` 注释
- **常量化边界**沿用 v1.3 §5.3:仅"前后端要对齐的字符串"进常量;一次性展示文案硬编码 JSX
- **密码规则升级是全局**:不只供应商注册,所有密码校验路径(BUYER 注册 / 改密 / 内部账号创建)都跟着新规则;错误文案统一
- **错误响应 code 必须是数字**;前端识别错误**严禁** `if (data.code === 'SUPPLIER_ALREADY_REGISTERED')`

### 3.3 视觉规范(不变)

沿用 v1.3。

---

## 4. 实现步骤(4 步,自测驱动)

### 4.0 总流程

```
复述 6 条决议
    ↓
Step 1: 密码规则升级(全局)→ 自测 pytest → 进 Step 2
Step 2: 5 国正则替换 + transform 升级 + 配置文件改动 → 自测 build/lint → 进 Step 3
Step 3: 前端 UI 增量(改国家清字段 / transform / 提交按钮置灰 / beforeunload / 已登录跳转)→ 自测 build + 手工 → 进 Step 4
Step 4: 增量 E2E + grep 校验 → 汇总
```

### 4.0.1 自测命令

| Step | 自测命令 | 通过标准 |
|---|---|---|
| Step 1 | `cd backend && pytest -v` | 全绿;**所有依赖密码强度的测试用例已升级到新规则** |
| Step 2 | `cd frontend && pnpm build && pnpm lint` | 0 error |
| Step 3 | `cd frontend && pnpm build && pnpm lint` + 手工 `pnpm dev` 跑通 | build 通过;Δ4/Δ5/Δ6/Δ7/Δ8 各跑一遍 |
| Step 4 | `cd backend && pytest` + `cd frontend && pnpm build` + §7 全部 grep | 全绿 + grep 全过 |

### 4.0.2 失败硬规则

参考 §8.4。简言之:**不许**修改测试断言以绕过、不许吞异常、不许跳过失败的 Step。

---

### Step 1 · 全局密码规则升级(PRD Δ1 + Δ2)

**改 `backend/app/core/security.py`**:`validate_password_strength` 按 PRD §1 Δ1 重写。

**改错误文案**(后端):统一为"密码 11-50 位,需包含数字、大写字母、小写字母、特殊字符中至少 3 类"。

**改 `backend/.env.example`** 与 `backend/.env`(若有):`SUPER_ADMIN_INITIAL_PASSWORD=Aa123456789`。

**改 `backend/app/seed.py`**:如有硬编码弱密码,替换为 `Aa123456789`。

**改 `backend/tests/`**:**所有**测试用例的弱密码统一替换。常见替换:
- `password123` / `Pass1234` 等 8-10 位 → `Aa123456789` 或 `Test1234567`
- 关键测试用例(测密码强度的)保留弱密码作为反例(应被拒)

**新增至少 1 个测试用例**:`test_password_3_categories_required`,测 11 位但只 2 类字符应被拒。

**改 `frontend/src/lib/validators.ts`**:`validatePassword` 升级到与后端等价的逻辑。错误文案同步。

**改前端密码强度提示组件**(若有):文案同步。

**自测**:`pytest -v` 全绿。

---

### Step 2 · 配置文件增量(PRD Δ3 + Δ5 + Δ9)

**改 `frontend/src/config/country-registration-rules.ts`**:

5 国正则与凭证名替换(精确改 5 个国家的 3 个字段:`regex` / `label` / `hint`):

| Code | regex | label | hint |
|---|---|---|---|
| KH | `/^[A-Z0-9]{10,12}$/` | `MOC 注册号` | `10-12 位字母数字` |
| PK | `/^[A-Z0-9]{7,10}$/` | `SECP 注册号` | `7-10 位字母数字` |
| MA | `/^[0-9]{15}$/` | `ICE 企业统一编号` | `15 位数字` |
| IQ | `/^[0-9]{6,10}$/` | `MoC 商业登记号` | `6-10 位数字` |
| AE | `/^[A-Z0-9]{6,12}$/` | `Trade License No` | `6-12 位字母数字` |

**MY / SA / ID / CN 不动**。

**transform 函数升级**(若 v1.3 没有按国家区分):

| 国家 | transform |
|---|---|
| 字母数字国(CN / KH / PK / AE)| `(v) => v.trim().toUpperCase().slice(0, MAX)` |
| 纯数字国(MY / ID / MA / IQ / SA)| `(v) => v.trim().replace(/\D/g, '').slice(0, MAX)` |

**新增常量**(若 v1.3 未导出):
```typescript
export const BUSINESS_CODE_DUPLICATE_SUPPLIER_REGISTRATION = 40901;
```

**保留** `TODO(REG-RULE)` 注释。

**自测**:`pnpm build && pnpm lint` 0 error。

---

### Step 3 · 前端 UI 增量(PRD Δ4 + Δ6 + Δ7 + Δ8)

**3.1 Δ4 · 改国家自动清字段 + 重置语言**

改 `useRegisterDraft` hook,暴露新方法:
```typescript
const { ..., clearRegistrationNo, clearLanguagePreference } = useRegisterDraft();
```

`StepCountry` 内,用户重新选择国家时调用上述两个方法。

**3.2 Δ6 · 提交按钮置灰(主流程级硬规则)**

新增 `validators.ts` 函数:
```typescript
export function validateAllRegisterFields(
  form: SupplierRegisterForm,
  countryCode: CountryCode
): { valid: boolean; errors: { field: string; fieldLabel: string; message: string }[] }
```

`StepForm` 提交按钮按 PRD §1 Δ6 实现,含:
- `disabled` 绑定 `!isFormValid`
- `title` 属性 hover 显示未完成项
- 置灰态样式 `bg-gray-300 text-gray-500 cursor-not-allowed`
- 亮态样式 `bg-[#FF6B35] hover:bg-[#e05a25] text-white cursor-pointer`

**3.3 Δ7 · beforeunload**

新增 `frontend/src/app/(auth)/register/_components/useBeforeUnload.ts`(按 PRD §1 Δ7 实现)。

`/register` page 内:
```typescript
const shouldWarn = currentStep >= 2 && hasAnyNonEmptyDraftField;
useBeforeUnload(shouldWarn);
```

**3.4 Δ8 · 已登录跳转**

`/register` page mount 时检查 `me`,若已登录则 `router.replace(defaultDashboardOf(role))`。

复用现有 `defaultDashboardOf(role)` 工具(若无,在 `frontend/src/lib/auth.ts` 加一个)。

**自测**:`pnpm build && pnpm lint` 通过;`pnpm dev` 手工跑 Δ4/Δ5/Δ6/Δ7/Δ8 各一遍。

---

### Step 4 · 增量 E2E 验证 + 汇总

跑 PRD v1.4 §3 列出的全部增量验收项,**每条截图证明**:

**密码相关(Δ1/Δ2)**:
1. 密码 `Aa12345`(< 11 位)→ 拒绝
2. 密码 `aaaaaaaaaaa`(11 位 1 类)→ 拒绝
3. 密码 `Aa123456789`(11 位 3 类)→ 通过
4. 种子超管 `.env.example` 默认密码登录正常

**国家正则(Δ3)**:
5. PK · SECP `ABC1234567` → 通过
6. MA · ICE 15 位数字 → 通过
7. IQ 填字母 → 拒绝

**改国家联动(Δ4)**:
8. MY → 填 `202301012345` → 改 ID → 回 Step 3 看到 `registration_no` 已清空
9. ID → 选印尼语 → 改 CN → Step 2 语言重置

**Transform(Δ5)**:
10. MY 输入带空格 → 自动 trim
11. CN 输入小写 → 自动转大写
12. MY 输入含字母 → 字母自动过滤

**提交按钮(Δ6)**:
13. Step 3 缺字段 → 按钮置灰
14. Step 3 缺字段 → hover 显示"请完善:X、Y、Z"
15. Step 3 全过 → 按钮亮橙

**beforeunload(Δ7)**:
16. Step 3 有数据 关 tab → 原生确认框

**已登录跳转(Δ8)**:
17. 已登录 SUPPLIER 访问 `/register` → 自动跳 `/supplier/dashboard`

**错误响应(Δ9)**:
18. 重复注册 → Network 看到 `code: 40901`(数字)

**最终汇总**(一次性给我):
- 18 张 E2E 截图
- `pytest backend/` 全绿输出
- `pnpm build` + `pnpm lint` 通过输出
- §7 全部 grep 校验项的实际命令 + 输出
- 全部 commit hash
- 总结:"做了什么 + 没做什么(对照 PRD §2 不在范围)+ 遗留 TODO"

---

## 5. 不要做的事(明确禁止)

- ❌ **不要重做 v1.3 已实现的部分**(3 步向导骨架 / sessionStorage / 9 国配置文件结构 / Dashboard banner / members 占位 / 登录页 / 复合唯一 / `/auth/me` 加 status / `business_license_no` 重命名)——这些全是 v1.3 已有,**只动 PRD §1 列出的 9 项 delta**
- ❌ **不要改 BUYER 注册业务字段**(但 Δ1 密码规则升级会同步影响 BUYER 密码校验的错误文案——这是必然连锁,不算"改 BUYER 业务")
- ❌ **不要改 RBAC 核心**(`backend/app/rbac/*`、`frontend/src/lib/permissions.ts`)
- ❌ **不要改登录后端逻辑** `_find_user_by_identifier`
- ❌ **不要引入新依赖**
- ❌ **不要实现成员邀请真实功能**(`/supplier/members` 沿用 v1.3 占位)
- ❌ **不要实现审核状态机**
- ❌ **不要实现 i18n 真翻译**
- ❌ **不要存密码到 sessionStorage**
- ❌ **不要在前端用字符串比较 code**(数字 40901)
- ❌ **不要给前端组件 JSX 里硬编码 9 国名 / 凭证名 / 重复注册文案**
- ❌ **不要乱删 v1.3 现有代码**——只增量改

---

## 6. 输出要求

- 每个 Step 完成时,**简短打印**:`✅ Step N 完成,自测通过(<跑的命令>),进入 Step N+1`
- 完整截图 + grep 输出 + 总结放到 **Step 4 结束**,一次性给我
- 关键决策不擅自决定:PRD 真矛盾才停下;边角问题选最简方案 + 加 `TODO(...)`
- 一个 Step 一个 commit:
  - Step 1: `feat(security): 升级全局密码规则至 11-50 + 3 类 [v1.4 Step 1/4]`
  - Step 2: `feat(supplier-register): 5 国正则按 PM 文档替换 + transform 升级 [v1.4 Step 2/4]`
  - Step 3: `feat(supplier-register): 提交按钮置灰 / beforeunload / 改国家清字段 / 已登录跳转 [v1.4 Step 3/4]`
  - Step 4: `test(supplier-register): v1.4 增量 E2E 验证 [v1.4 Step 4/4]`

---

## 7. 验收标准

见 PRD v1.4 §3。**Step 4 结束时逐条贴出实际命令和输出**:

### 自动化校验

- [ ] `cd backend && pytest -v` 全绿
- [ ] `cd frontend && pnpm build` 0 type error
- [ ] `cd frontend && pnpm lint` 0 error

### grep 校验(增量项,v1.3 验收项不重复)

- [ ] **密码规则升级生效**:
  - `grep -n '11' backend/app/core/security.py` → 看到 `PASSWORD_MIN_LENGTH = 11` 或等价
  - `grep -rn -E "['\"]?8.*32['\"]?" backend/app/core/security.py frontend/src/lib/validators.ts` → 0 行(旧 8-32 已退出,允许 git history 历史 migration / test 文件保留弱密码反例)
- [ ] **PK 凭证名更新**:
  - `grep -rn 'SECP' frontend/src/config/country-registration-rules.ts backend/app/constants/country_registration.py` → ≥ 1 行
  - `grep -rn "'NTN'" frontend/src/config/country-registration-rules.ts` → 0 行(NTN 已退出)
- [ ] **MA 凭证名更新**:
  - `grep -rn 'ICE' frontend/src/config/country-registration-rules.ts` → ≥ 1 行
- [ ] **前端不用字符串比较错误 code**:
  - `grep -rn -E "code.*===.*['\"]SUPPLIER" frontend/src/` → 0 行
  - `grep -rn "SUPPLIER_ALREADY_REGISTERED" frontend/src/` → 0 行
- [ ] **种子密码已更新**:
  - `grep -n 'ChangeMe123' backend/.env.example backend/.env 2>/dev/null` → 0 行
  - `grep -n 'Aa123456789' backend/.env.example` → ≥ 1 行

### 功能验收

- [ ] PRD v1.4 §3 全部 18 项 E2E 截图证明

完成后,commit hash + 日期写入 PRD v1.4 §3 验收记录(若该节存在留白处)。

---

## 8. 异常处理协议

### 8.1 必须停下报告(只这几种)

- 自测红(§4.0.1 任一 Step 失败,尝试修复 2 次未果)
- PRD v1.4 与 v1.3 实际代码真矛盾(比如发现 v1.3 没按 PRD 跑全 / 字段命名不符)
- 发现 v1.3 代码有显著 bug 影响本轮正确性
- CI 拦截破坏性迁移

### 8.2 不停下、按既定方案推进的情况

- PRD 没说的边角 → 选最简方案 + 加 `TODO`
- 发现可优化的相邻代码 → 记 TODO,不顺手改
- 想到"未约定的好主意" → 忍住,记 TODO

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

- ❌ 修改测试断言以绕过失败
- ❌ 删除失败的测试用例
- ❌ try/except 吞异常让代码看起来通过
- ❌ 跳过失败的 Step 继续下一步
- ❌ 因为"想问问"而停下来——只 8.1 列出的才允许停

---

## 9. 起手对话话术(给用户的)

```
你好。我要按工单 docs/tasks/供应商注册3步向导 工单 prompt v1.4.md 实现增量补丁。

请遵循协作规范:

1. 先阅读 docs/ 下的相关文档(PRD v1.4 是 delta 类型,基线 v1.3 已开发完成)
2. 在响应开头复述工单 §1.1 的 6 条关键决议(简短即可)
3. 复述完毕立即从 Step 1 开始动手,**不要等我 review**
4. 每个 Step 完成后跑 §4.0.1 自测命令
5. 自测全绿 → 继续下一步;自测红 → 按 §8.3 格式报告
6. 全部 4 个 Step 完成后,一次性把 §7 校验结果 + §4 Step 4 的 18 条 E2E 截图 + 总结 汇总给我

例外:发现 PRD v1.4 与 v1.3 实际代码真矛盾,按 §8.1 停下报告。
其它一律按既定方案推进,不要为了"想问问"而停。

工单已加载,开干。
```

---

*工单 prompt v1.4 (delta) · 总 Step 数 4 · 预计开发周期 0.5-1 工作日 · 基线 v1.3 已开发完成 · 与 PRD v1.4 / PM 对齐清单 v1.4 同步*
