# Task: 子项明细表 override 触发文案标注 · 增量工单 prompt v0.2-Δ3

> 状态:可下发 Claude Code
> 日期:2026-05-23
> 类型:**增量补充**,基于 v0.2-Δ2 回滚后状态,补回子项明细表行末的 override 触发文案
> 关联文档:
> - 上一轮工单:`docs/prompts/信用评估模块_工单prompt_v0_2-Δ2.md`(回滚版,已合入)
> - 技术方案:`docs/architecture/信用评估模块技术方案设计-v0_2.md`
> - 评分规则清单:`docs/architecture/评分规则清单-v0_1.md` §五维度级 override
> - PRD:`docs/prd/信用评估模块 PRD v0.3_四维评分模型版.md.docx` §4.3
> 当前分支:`feat/credit-override-row-label`(基于 main 切出)

---

## 1. 任务上下文

### 1.1 当前代码状态

v0.2-Δ2 已合入,前端的 override UI 增强已全部回滚。当前详情页:

- 雷达图按 PRD §8.1 配色规则正常着色
- 12 子项明细表正常显示自然得分
- **没有任何 override 触发的文字提示**

### 1.2 问题

当某维度被 override 强制清零或降级时(如维度4 失信一票否决),用户看到该维度 0 分,**无法区分**:

- 是因为该子项自然评分为 0(如 QUAL_MANDATORY_NONE "无证书")
- 还是被维度级规则强制清零(如 DIM2_CERT_FORGED_OR_EXPIRED "证书伪造")

两者业务含义完全不同,采购决策也不同。**PRD v0.3 §4.3 维度3 明确写有"标注'数据未知'"**,本次任务在此精神下补全维度2 和维度4 的对应标注。

### 1.3 本次任务目标

在 12 子项明细表的行末追加**简短文字标注**,告诉用户"这一行的得分是被维度级规则覆盖的结果"。**不加图标、不加卡片、不加提示框**,仅一行小文字。

---

## 2. 范围

**做**:

- 12 子项明细表的"得分"列(或单独"备注"列,视实施方案)末尾追加一行小文字标注
- 标注按维度场景区分文案(三种文案,见 §3)
- 仅对触发了 override 的维度下的 3 行子项添加标注

**不做**:

- 不加任何图标(⚠ 等)
- 不加任何卡片/提示框
- 不动雷达图(雷达图保持 v0.2-Δ2 状态)
- 不动后端

---

## 3. 实现步骤

### Step 1:确定文案

在前端定义一个常量映射,key 为维度 override 的 `override_rule_code`,value 为行末标注文案:

```typescript
const OVERRIDE_ROW_LABELS: Record<string, string> = {
  DIM2_CERT_FORGED_OR_EXPIRED: "关键证书伪造或过期,维度强制清零",
  DIM3_UNKNOWN: "数据未知,维度按 40% 满分计",
  DIM4_UNRESOLVED_DEFAULTER: "失信未结案,维度一票否决",
};
```

文案来源:
- DIM2 / DIM4 直接复用 `score_dimension_override.description` 字段的措辞精神,简化为业务事实陈述
- DIM3 严格对齐 PRD §4.3 维度3 "标注'数据未知'" 的原话

### Step 2:从接口数据匹配维度

`GET /credit/companies/{id}` 响应中的 `dimension_overrides` 数组每条含 `dimension_code` 和 `override_rule_code`。前端处理逻辑:

```typescript
// 构建被 override 的 dimension_code → override_rule_code 映射
const overriddenDimensions: Map<string, string> = new Map();
(snapshot.dimension_overrides ?? []).forEach(o => {
  overriddenDimensions.set(o.dimension_code, o.override_rule_code);
});

// 渲染明细表每行时
const isOverridden = overriddenDimensions.has(detail.dimension_code);
const labelText = isOverridden 
  ? OVERRIDE_ROW_LABELS[overriddenDimensions.get(detail.dimension_code)!]
  : null;
```

### Step 3:行末标注样式与位置

样式建议(可按现有 Tailwind 工具类调整):

- 字体:小灰字,`text-xs text-slate-500`(或对应 design token)
- 位置:"得分"列分数右侧,用括号包裹,如 `0 (失信未结案,维度一票否决)`;或在该行单独占一小段位置
- 颜色:**不用红色或警示色**,保持中性灰色——文案本身已表达事实,不需要额外视觉强调
- 不加边框、不加背景色、不加图标

**实施时优先方案**:在子项行的"命中规则"列(或末尾的备注列)追加该文案,与该列原有"自然命中规则描述"并列展示。例如:

| 子项 | 满分 | 得分 | 命中规则 |
|---|---|---|---|
| 失信被执行 | 10 | 0 | 有未结案记录(`LEGAL_DEFAULTER_UNRESOLVED`)<br/><span class="text-xs text-slate-500">失信未结案,维度一票否决</span> |

实施时如有更合适的版面位置(如单独"备注"列),可自由调整,但保持"小灰字、简短、无视觉强调"的原则。

### Step 4:边界处理

- `dimension_overrides` 为空数组或 null 时,所有行**不显示任何标注**(明细表与 v0.2-Δ2 状态完全一致)
- 仅对 `dimension_overrides` 中存在的维度下的 3 行子项添加标注;其他维度的子项行**保持不变**
- 如未来 `score_dimension_override` 表新增 override(超出当前 3 条),`OVERRIDE_ROW_LABELS` 字典里没有匹配的 code 时,**降级为不显示标注**(不报错、不显示空字符串、不显示原始 code),并在 console.warn 一次:`Unknown override code: ${code}`

---

## 4. 验收标准

### 前端

- Atlas Construction(D 档,维度4 触发 DIM4_UNRESOLVED_DEFAULTER):
  - 明细表维度4 的 3 行子项末尾显示小灰字 `失信未结案,维度一票否决`
  - 其他 3 个维度的子项行末**无任何标注**
- A/B/C 档其他 3 家企业:明细表**无任何 override 标注**(因 dimension_overrides 为空)
- 如有 demo 企业 mock 数据 finance_data_id 为 NULL(触发 DIM3_UNKNOWN):
  - 维度3 的 3 行子项末尾显示 `数据未知,维度按 40% 满分计`
- 如有 demo 企业 mock 数据触发 DIM2(证书伪造/过期):
  - 维度2 的 3 行子项末尾显示 `关键证书伪造或过期,维度强制清零`
- 标注文字为小灰字,无图标、无背景色、无边框
- 雷达图、其他 UI 元素与 v0.2-Δ2 状态完全一致

### 后端

- **后端无任何改动**

### 代码

- `pnpm tsc --noEmit` + `pnpm build` 通过
- `OVERRIDE_ROW_LABELS` 字典集中定义,文案易维护

---

## 5. 严格不做的事

1. 不加图标(`AlertTriangle` 或任何 lucide-react icon)
2. 不加单独的 override 提示卡片/banner
3. 不加雷达图的轴标注
4. 不加红色/橙色/黄色等警示色——文案保持中性灰色
5. 不修改自然得分的展示方式
6. **不自行扩展文案、不"丰富"措辞**——严格按 §3 Step 1 定义的三种文案
7. 不动后端、不动接口

---

## 6. 提交规范

- commit message:`Ref: docs/prompts/信用评估模块_工单prompt_v0_2-Δ3.md`
- 性质标注:`feat(credit): add override row labels to score detail table`

---

*工单 v0.2-Δ3(增量) · 基线 v0.2-Δ2 · 仅前端、仅明细表行末文字标注*
