# Task: 修复 SUPPLIER 注册→登录回填手机号导致 401,统一登录页文案 · v1.6 增量补丁

> **类型** 增量工单(delta · 纯前端 fix)· **基线** v1.5 已合入主干
> **触发** 用户报告生产 bug:`+86 13301165882` 回填后无法登录
> **交付节奏** 一气呵成,自测驱动;只有自测失败或与本工单矛盾时停下报告
> **PR** [#23](https://github.com/tutu6/overseas-platform-v0.1/pull/23) · 主分支 commit `ce05aa6` · 部署 run `26264858356`(2m44s 成功)

---

## 1. 任务上下文

### 1.1 用户报告

供应商注册时填手机号 `+86 13301165882`(按 placeholder 提示的国际格式),注册成功跳转登录页,identifier 输入框自动回填出 `+86 13301165882`。点登录返回 401(`凭证或密码错误,请重试`)。

### 1.2 在响应开头复述以下 3 条关键决议,复述完毕立即进入实施,不要等 review

1. **只改前端**:不动后端 login classifier、不动 SUPPLIER phone 校验、不动 DB schema、不动 BUYER 路径
2. **prefill identifier 改用 email**:SUPPLIER 注册成功后回填登录页的标识符只取 `draft.email`,不再 fallback 到 phone
3. **登录页文案统一为 "邮箱 / 手机号 / 用户名"**:`账号` 这个项目里没出现过的术语全部下线,且把"用户名"挪到末尾(因为 SUPPLIER 没有 username,优先级最低)

### 1.3 唯一允许停下的时机

仅在以下情况停下报告:
- 实际代码与本文档"现状"描述不符(基线已漂移)
- 改 4 个文案 / 1 个 prefill 仍无法让线上回填→登录链路通

否则按既定方案推进。

---

## 2. 根因(必读,不要再调查)

| 层 | 现状 |
|---|---|
| SUPPLIER phone 校验 | `SUPPLIER_PHONE_REGEX = ^[+0-9\s\-]{6,20}$`(`backend/app/schemas/auth.py:26`)— i18n 占位规则,允许 `+`、空格、`-`、6-20 位 |
| 注册存储 | 前后端均不规整,phone **原样入库**(`+86 13301165882` 共 14 字符,含 `+` 与空格)|
| StepForm prefill | `identifier: draft.phone \|\| draft.email`(`frontend/src/app/(auth)/register/_components/StepForm.tsx:224`),优先 phone |
| 登录 classifier | `_classify_identifier`(`backend/app/services/auth_service.py:81-88`)仅识别 `ident.isdigit() and len == 11 and startswith("1")` 为 phone;带 `+`/空格 → `.isdigit()` False → 走 username 分支 → `WHERE username = '+86 13301165882'` → 找不到 → 401 |

**关键洞察**:不是值不匹配 — DB 里的 phone 就是 `+86 13301165882`,跟回填的字符串一字不差。问题是 classifier 把它分类成 username,查的是 `username` 列(NULL),不是 `phone` 列。

**BUYER 路径不受影响**:BUYER phone 走 `_validate_phone_optional`(`auth.py:43-49`)严格 11 位中国手机号(`PHONE_REGEX = ^1[3-9]\d{9}$`),存的就是 `13301165882` 纯数字;且 BUYER prefill 优先 `form.username || form.phone || form.email`,username 在前。

---

## 3. 技术约束

### 3.1 沿用 CLAUDE.md 项目级规范

略,与历次工单一致。

### 3.2 本轮特别强调

- **纯前端 fix**:任何后端 / DB / migration / schema 改动一律不做
- **最小改动**:5 处编辑,2 个文件,合计 10 行
- **加注释要解释 WHY,不要解释 WHAT**:prefill 改 email 那行必须留 WHY 注释 + `TODO(I18N-PHONE)` 标记,说明为什么不能用 phone,以及"何时可以重新启用 phone"的触发条件

---

## 4. 实现步骤(一步到位)

### 4.0 自测命令

| 命令 | 通过标准 |
|---|---|
| `cd frontend && pnpm lint` | 0 warning、0 error |
| 手工跑 3 个场景(见 §6) | 全部预期一致 |

后端不动,无需跑 pytest;DB 不动,无需 alembic。

---

### Step 1 · `frontend/src/app/(auth)/register/_components/StepForm.tsx`

**改 SUPPLIER 注册成功后的 prefill identifier**

```diff
       try {
         sessionStorage.setItem(
           "prefill_login",
           JSON.stringify({
-            identifier: draft.phone || draft.email,
+            // WHY 用 email 不用 phone:SUPPLIER phone 走 i18n 占位校验(允许 +、空格、-),
+            // 而 login _classify_identifier 仅识别纯 11 位中国手机号,prefill 国际格式 phone
+            // 会被当 username 查必然 401。TODO(I18N-PHONE):各国 phone 精确规则就绪后再放开。
+            identifier: draft.email,
             password,
           }),
         );
```

---

### Step 2 · `frontend/src/app/(auth)/login/page.tsx`

**改 5 处文案 + 删 1 个 subtitle 元素**

| 位置 | 原 | 新 |
|---|---|---|
| 卡片 h2 | `欢迎回来` | `登录` |
| subtitle `<p>` | `登录您的账户继续使用`(整行) | **整行删除**("账户" 非项目术语,品牌区已在外层 `(auth)/layout.tsx` 充分展示) |
| Label | `账号 / 邮箱 / 手机号` | `邮箱 / 手机号 / 用户名` |
| input placeholder | `输入账号 / 邮箱 / 手机号` | `输入邮箱 / 手机号 / 用户名` |
| `onSubmit` 空值校验 | `请填写账号 / 邮箱 / 手机号` | `请填写邮箱 / 手机号 / 用户名` |
| `onBlur` 空值校验 | `请填写账号 / 邮箱 / 手机号` | `请填写邮箱 / 手机号 / 用户名` |
| `justRegistered` 提示 | `注册成功,请使用账号密码登录` | `注册成功,请登录` |

**为什么把"用户名"挪到末尾**:SUPPLIER 没有 username(后端 service 也未自动填充 username = email,见 §5 的决策记录),把"用户名"放最后,排序按"实际使用频率从高到低"。

**为什么删 subtitle**:外层 `AuthLayout` 已有完整品牌区(logo + 品牌名 + 英文名 + slogan),卡片内的 subtitle "登录您的账户继续使用" 既冗余,又引入了 "账户" 这个项目里从未定义的术语(我们的概念是"用户" + "组织")。卡片 h2 "登录" 已足以做"登录 vs 注册"的视觉区分。

---

## 5. 不做(已与用户对齐的边界)

讨论过、决定**本轮不做**的事:

| 改动 | 决定不做的理由 |
|---|---|
| 改 login classifier 支持 `+` 开头的国际格式 | 触及 i18n 边界,与各国 phone 精确规则一起做(TODO(I18N-PHONE)) |
| SUPPLIER 注册时自动 `User.username = email` | `User.username` 列 `String(50)`,`email` 列 `String(255)`,长邮箱会触发 PG `value too long` → 注册失败;改 schema 又超出"最小改动"边界。决定 D = 不动后端,只改前端 label + prefill,实际 UX 等价(SUPPLIER 用 email 登录 classifier 走 `@` 分支命中)|
| 注册时 phone 输入做规整(strip 空格 / 去 `+86` 前缀) | 跟"国际格式占位"产品意图冲突,且单独修这一处不能根治 I18N-PHONE |
| phone 输入旁加国家拨号前缀下拉 / chip | 范围过大,需要先有各国 dial code + 校验规则数据;留作 I18N-PHONE 工单 |
| BUYER 路径任何改动 | 用户明确"只改 SUPPLIER";BUYER 本来就没这个 bug(phone 严格 11 位) |
| DB schema / alembic migration | 本轮不动数据库 |

---

## 6. 自测场景

线上 http://114.55.135.216 走 3 个场景:

### 场景 A · SUPPLIER 新注册 → 自动回填登录

1. 进 `/register`,选 SUPPLIER + 任意国家
2. Step 3 填写:phone = `+86 18515189769`(故意带 `+86` 和空格),email = `test_v16@example.com`,其他字段合法
3. 提交注册 → 跳 `/login?registered=1`
4. **预期**:
   - 卡片标题显示 `登录`(不是 `欢迎回来`)
   - h2 下方**没有** subtitle
   - 绿色提示条 `注册成功,请登录`
   - identifier 输入框自动回填值为 `test_v16@example.com`(**不是** `+86 18515189769`)
   - Label 是 `邮箱 / 手机号 / 用户名`
5. 直接点登录 → **预期**:成功跳 dashboard

### 场景 B · 手动用 phone 登录(已知不支持,验证不退化)

1. 退出登录,回到 `/login`
2. 手动在 identifier 框输入 `+86 18515189769`,密码用注册时密码
3. **预期**:仍然 401(本轮不解决,跟 v1.6 前一致)。Label 文案不应误导用户认为带 `+` 的格式能登录 — 若 UX 上需要进一步引导,留作 I18N-PHONE 工单

### 场景 C · BUYER 路径不退化

1. 用既有 BUYER 账号(任一可用 BUYER)登录
2. **预期**:无论用 username / email / 11 位中国手机号,登录均正常;UI 文案虽变为 `邮箱 / 手机号 / 用户名`,后端 classifier 三种都认

---

## 7. 已知遗留 TODO

| ID | 说明 | 触发时机 |
|---|---|---|
| `TODO(I18N-PHONE)` | 各国 phone 精确规则 + login classifier 扩展 + 是否引入国家拨号前缀下拉 + prefill 是否恢复 phone 优先 | 出海多国上线、产品决定 phone 是首要登录凭证时 |

---

## 8. 交付物清单

- [x] `frontend/src/app/(auth)/register/_components/StepForm.tsx`(prefill identifier 改 email,+3 行 WHY 注释)
- [x] `frontend/src/app/(auth)/login/page.tsx`(6 处文案改动 + 删 1 个 subtitle 元素)
- [x] `pnpm lint` 通过
- [x] PR #23 squash 合 main
- [x] ECS 部署成功(run 26264858356,2m44s)
- [ ] 用户线上自测(场景 A / B / C)

---

## 9. 决策追溯(本工单形成过程中的关键讨论点)

| 议题 | 备选 | 决定 | 决定时间 |
|---|---|---|---|
| 修复策略 | A 改 classifier / B 改注册存储 / C 改 prefill 用 email | C(最小、不动 i18n 边界) | 2026-05-22 用户拍板 |
| Label 文案 | "用户名" 单选 / "邮箱" 单选 / "邮箱 / 手机号 / 用户名" 并列 | 并列(账号 → 用户名,移到末尾) | 2026-05-22 用户最终方案 |
| 卡片 h2 | 保留 "欢迎回来" / 改 "登录" / 完全删除 | 改 "登录"(克制、动作型、跟注册页风格统一) | 2026-05-22 用户拍板 |
| Subtitle | 保留 / 改文案 / 删除 | 删除("账户" 非项目术语,品牌区在外层 layout) | 2026-05-22 用户拍板 |
| SUPPLIER username 自动 = email | A 改 schema 扩列 / B 优雅降级 / C 截断 / D 不做 | D(实际 UX 等价,且不破坏 `User.username` 列长度约束) | 2026-05-22 用户拍板 |
| 国家拨号前缀控件 | 只读 chip / 可下拉 / 国家+前缀绑定 | 本轮不做,留 I18N-PHONE | 2026-05-22 决定推迟 |

---

*文档结束*
