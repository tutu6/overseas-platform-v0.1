# Task: 供应商注册3步向导 · v1.5 增量补丁

> **类型** 增量工单(delta) · **基线** v1.4 已开发完成并合入主干
> **PRD 依据** `docs/prd/供应商注册3步向导 PRD v1.5.md`
> **交付节奏** 一气呵成,自测驱动;只有自测失败或 PRD 真矛盾时停下报告

---

## 1. 任务上下文

请先阅读以下文档:

- `CLAUDE.md`(项目级协作约定)
- `docs/prd/供应商注册3步向导 PRD v1.5.md`(本任务核心契约,delta 类型)

**v1.4 已开发完成的内容不需要重读**;直接在现有代码基础上加 delta 即可。

### 1.1 在响应开头复述以下 3 条关键决议,复述完毕立即进入 Step 1,不要等 review:

1. **邮箱和手机号全局唯一**:`users.email` 与 `users.phone` 加 UNIQUE 约束
2. **新增业务码** 40902(邮箱已注册)、40903(手机号已注册);原 40901(企业已注册)不变
3. **一次返回所有错误**:注册接口收集所有唯一性校验失败,一次性返回 `data.errors` 数组;前端按字段定位显示,≥2 个错误时顶部 banner 显示"请修正以下 N 项问题"

### 1.2 唯一允许停下的时机

仅在以下情况停下报告:
- 仓库现状与 PRD v1.4 基线不符
- PRD v1.5 与 v1.4 实际代码真矛盾
- 数据库现有数据存在重复邮箱/手机号,UNIQUE 约束加不上

否则按 PRD/工单既定方案推进。

---

## 2. 任务范围

实现 PRD v1.5 §1 的 3 项增量(Δ1 / Δ2 / Δ3)。详见 PRD。**不做** PRD §2 列的"不在本轮范围"。

---

## 3. 技术约束

### 3.1 沿用 CLAUDE.md 项目级规范

略,与 v1.4 工单一致。

### 3.2 本轮特别强调

- **delta 思维**:不重写已实现文件;改前先 view 现状
- **新增业务码** 40902 / 40903 落到后端 `app/constants/country_registration.py`(或对应业务码常量文件,沿用 v1.4 已建立的位置);前端 `country-registration-rules.ts` 同步导出常量
- **错误文案前后端逐字一致**:三条新增/已有的重复错误文案(40901 / 40902 / 40903)前后端各一份,字符串完全相同
- **响应结构 `data.errors`**:无论是单个错误还是多个错误,后端**统一返回** `data.errors` 数组(单错误时数组长度为 1);前端统一按数组解析
- **前端识别错误必须用数字 code**,严禁字符串比较

---

## 4. 实现步骤(3 步,自测驱动)

### 4.0 自测命令

| Step | 自测命令 | 通过标准 |
|---|---|---|
| Step 1 | `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` | 三连无报错 |
| Step 2 | `cd backend && pytest tests/test_auth.py -v` | 全绿;新增用例覆盖三种错误并发场景 |
| Step 3 | `cd frontend && pnpm build && pnpm lint` + 手工跑场景 | build 通过;3 种场景跑通(单错误 / 多错误 / 成功)|

---

### Step 1 · DB migration

**改 `users` 表**:
- 加 `UNIQUE(email)` 约束
- 加 `UNIQUE(phone)` 约束

**migration 实现要点**:
- 加约束前先检测是否有重复数据;有则停下报告,**不要自动清理数据**
- downgrade 删除两个 UNIQUE 约束

**注意**:本地 dev 环境数据量小,通常无重复。若检测到重复,按 §1.2 停下报告。

**自测**:三连 alembic 通过。

---

### Step 2 · 后端 schema + service + 测试

**改 `backend/app/constants/country_registration.py`**:
- 新增 `BUSINESS_CODE_EMAIL_ALREADY_REGISTERED = 40902`
- 新增 `BUSINESS_CODE_PHONE_ALREADY_REGISTERED = 40903`
- 新增 `EMAIL_ALREADY_REGISTERED_MESSAGE = "该邮箱已注册,请直接登录或更换邮箱"`
- 新增 `PHONE_ALREADY_REGISTERED_MESSAGE = "该手机号已注册,请直接登录或更换手机号"`

**改 `auth_service.register_supplier`**:
- 在事务开始前**先收集所有唯一性校验结果**(并行或顺序无所谓):
  - email 是否已存在
  - phone 是否已存在
  - (country_code, registration_no) 是否已存在
- 若任一存在,构造 `errors` 列表后**统一抛出**,**不要短路**
- 顶层 code 按优先级取:40901(若注册号重) > 40902(若邮箱重) > 40903(若仅手机号重)
- 若全部不存在,继续原事务流程

**错误响应格式**(后端框架层 / 异常处理器实现):

```python
{
  "code": <顶层 code>,
  "message": "请修正以下问题" if len(errors) > 1 else <首条错误 message>,
  "data": {
    "errors": [
      {"field": "...", "code": ..., "message": "..."}
    ]
  },
  "trace_id": "..."
}
```

**异常类设计**:沿用 v1.4 已有的 `SupplierAlreadyRegisteredError` 模式,新增:
- `EmailAlreadyRegisteredError`(单独使用时)
- `PhoneAlreadyRegisteredError`(单独使用时)
- **新增** `MultipleValidationError`:接受 errors 列表,用于多错误并发场景

异常处理器统一把上述异常转成上面的响应结构。

**新增测试用例**(`backend/tests/test_auth.py`):

1. `test_supplier_register_duplicate_email_only`:已存在邮箱 + 新手机号 + 新注册号 → 响应 `code = 40902`,`data.errors` 长度 = 1
2. `test_supplier_register_duplicate_phone_only`:同上,但只手机号重 → `code = 40903`
3. `test_supplier_register_duplicate_all_three`:三者均重 → `code = 40901`(优先级最高),`data.errors` 长度 = 3
4. `test_supplier_register_duplicate_email_and_phone`:邮箱 + 手机号重 → `code = 40902`,`data.errors` 长度 = 2
5. `test_supplier_register_response_structure`:无论单错误还是多错误,`data.errors` 一定是数组(单错误数组长度为 1)
6. 已有 `test_supplier_register_duplicate_per_country` 更新:断言响应也含 `data.errors`(单元素数组)

**自测**:`pytest tests/test_auth.py -v` 全绿。

---

### Step 3 · 前端增量

**改 `frontend/src/config/country-registration-rules.ts`**:
- 新增 `BUSINESS_CODE_EMAIL_ALREADY_REGISTERED = 40902`
- 新增 `BUSINESS_CODE_PHONE_ALREADY_REGISTERED = 40903`
- 新增对应的错误文案常量(与后端逐字一致)

**改 `frontend/src/app/(auth)/register/_components/StepForm.tsx`**:

提交结果处理:

```typescript
try {
  await registerSupplier(form);
  // 成功跳转
} catch (err) {
  // err.data.errors 是数组(可能 1 个或多个)
  if (err.data?.errors) {
    const errs = err.data.errors;
    if (errs.length === 1) {
      // 单错误:顶部 banner 显示该错误 message,字段下方也标红
      setBannerError(errs[0].message);
      setFieldErrors({ [errs[0].field]: errs[0].message });
    } else {
      // 多错误:顶部 banner 显示总数,所有字段标红
      setBannerError(`请修正以下 ${errs.length} 项问题`);
      const fieldErrMap = Object.fromEntries(errs.map(e => [e.field, e.message]));
      setFieldErrors(fieldErrMap);
      // 滚动到首个错误字段
      scrollToField(errs[0].field);
    }
  }
}
```

**关键点**:
- 字段级红色提示:每个出错字段下方显示对应 message
- 顶部 banner:1 个错误时显示原文,≥2 个时显示"请修正以下 N 项问题"
- 滚动到首个错误字段(可用 `document.getElementById(...).scrollIntoView`)

**自测**:`pnpm build && pnpm lint`,然后手工跑 3 个场景:
- 仅邮箱重 → 顶部 banner 单条文案 + 邮箱字段标红
- 邮箱 + 手机号 + 注册号都重 → 顶部 banner "请修正以下 3 项问题" + 3 个字段都标红
- 全部不重 → 注册成功跳转

---

## 5. 不要做的事

- ❌ 不重写 v1.4 已实现的部分
- ❌ 不引入 blur 时的实时唯一性查重(安全考量)
- ❌ 不实现邮箱验证 / 短信验证(本期不做)
- ❌ 不修改 v1.4 已定的字段(注册号、密码规则等)
- ❌ 不在前端用字符串比较 code
- ❌ 不硬编码错误文案(必须从配置 import)

---

## 6. 输出要求

- 每个 Step 完成时简短打印:`✅ Step N 完成,自测通过(<命令>),进入 Step N+1`
- 完整截图 + 总结放到 Step 3 结束
- commit message:
  - Step 1: `feat(supplier-register): users 表加邮箱/手机号 UNIQUE 约束 [v1.5 Step 1/3]`
  - Step 2: `feat(supplier-register): 邮箱/手机号查重 + 一次返回所有错误 [v1.5 Step 2/3]`
  - Step 3: `feat(supplier-register): 多错误前端展示 + 字段定位 [v1.5 Step 3/3]`

---

## 7. 验收

### 自动化校验

- [ ] `cd backend && pytest -v` 全绿
- [ ] `cd frontend && pnpm build` 0 type error
- [ ] `cd frontend && pnpm lint` 0 error
- [ ] alembic 三连通过

### grep 校验

- [ ] `grep -rn '40902' backend/app/ frontend/src/config/` → 后端和前端各至少 1 处
- [ ] `grep -rn '40903' backend/app/ frontend/src/config/` → 同上
- [ ] `grep -rn '该邮箱已注册' backend/app/ frontend/src/config/` → 后端常量、前端常量各 1 处,字符串完全相同
- [ ] `grep -rn '该手机号已注册' backend/app/ frontend/src/config/` → 同上
- [ ] `grep -rn "data.errors" frontend/src/app/\(auth\)/register/` → 至少 1 处(前端解析数组)

### 功能验收

- [ ] PRD v1.5 §3 全部 4 项功能验收 + 4 项自动化校验通过
- [ ] 手工 3 种场景跑通

---

## 8. 异常处理协议

### 8.1 必须停下报告

- 自测红(尝试修复 2 次未果)
- 数据库现有数据存在重复邮箱/手机号,UNIQUE 加不上
- PRD v1.5 与 v1.4 实际代码真矛盾
- 多错误响应结构与项目级 API 规范冲突

### 8.2 不停下、按既定推进

- PRD 没说的边角 → 选最简方案 + 加 TODO
- 想到"未约定的好主意" → 记 TODO,不顺手改

### 8.3 报告格式

参考 v1.4 工单 §8.3。

---

## 9. 起手对话话术

```
你好。我要按工单 docs/prompts/供应商注册3步向导 工单 prompt v1.5.md 实现增量补丁。

请遵循协作规范:

1. 先阅读 docs/ 下的 PRD v1.5(delta 类型,基线 v1.4 已开发完成)
2. 在响应开头复述工单 §1.1 的 3 条关键决议(简短即可)
3. 复述完毕立即从 Step 1 开始动手,不要等我 review
4. 每个 Step 完成后跑 §4.0 自测命令
5. 自测全绿 → 继续;自测红 → 按 §8.3 报告
6. 全部 3 个 Step 完成后,一次性汇总 §7 校验结果 + 手工 3 场景截图 + 总结 给我

例外:发现数据库有重复邮箱/手机数据或 PRD 真矛盾,按 §8.1 停下报告。

工单已加载,开干。
```

---

*工单 prompt v1.5 (delta) · 3 Step · 基线 v1.4 已开发完成*
