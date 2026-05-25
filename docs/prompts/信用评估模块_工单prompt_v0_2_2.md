# Task: 维度级 override UI 回滚 · 增量工单 prompt v0.2-Δ2

> 状态:可下发 Claude Code
> 日期:2026-05-23
> 类型:**增量回滚**,撤销 v0.2-Δ1 工单中超出 PRD 范围的前端 UI 改动
> 关联文档:
> - 上一轮工单:`docs/prompts/信用评估模块_工单prompt_v0_2-Δ1.md`(本工单回滚其前端部分)
> - 技术方案:`docs/architecture/信用评估模块技术方案设计-v0_2.md`(§八前端要点已同步更新)
> - PRD:`docs/prd/信用评估模块 PRD v0.3_四维评分模型版.md.docx`(§5.2 + §8.1)
> 当前分支:`feat/credit-override-ui-rollback`(基于 main 切出)

---

## 1. 任务上下文

### 1.1 当前代码状态

v0.2-Δ1 工单已实施完毕并合入主干。后端的"维度级 override 重构"(独立表 `score_dimension_override` + ScoringEngine 两步流程 + score_detail 保留自然命中规则)是正确的,**保留**。

但前端实施了**超出 PRD 范围**的 UI 增强:

- 雷达图轴标签旁追加⚠图标 + hover tooltip
- 雷达图下方新增"override 提示卡片"
- 12 子项明细表中标注"(被维度规则覆盖)"

**PRD v0.3 没有要求这三项**。仅 PRD §5.2 + §8.1 要求"数据缺失维度雷达图虚线描边"。

### 1.2 本次回滚目标

撤销超出 PRD 范围的前端 UI 改动,保留所有后端能力:

- 撤销 3 项 UI 增强(图标、卡片、明细表标注)
- 保留 `dimension_overrides` 字段在接口返回中,作为数据契约,前端不消费
- 保留所有后端表结构、ScoringEngine 两步流程、score_detail 自然命中记录逻辑

### 1.3 阅读顺序

1. 本工单 §2 回滚范围 + §3 实现步骤
2. 上一轮工单 `docs/prompts/信用评估模块_工单prompt_v0_2-Δ1.md` Step 9 —— 知道当时具体做了什么
3. 技术方案 `docs/architecture/信用评估模块技术方案设计-v0_2.md` §八前端要点(已更新为本次回滚后的状态)
4. PRD §5.2 数据缺失降级 + §8.1 四维雷达图视觉规范

---

## 2. 回滚范围

**回滚(撤销)**:

- `/credit/companies/[id]` 详情页中所有 override 相关 UI 元素
- 雷达图轴标签的⚠图标与 tooltip 组件
- override 提示卡片组件
- 明细表"(被维度规则覆盖)"标注

**保留(不动)**:

- 后端所有改动:`score_dimension_override` 表、ORM、ScoringEngine 两步流程、Evaluators 拆分、seed 数据
- 接口返回字段:`dimension_N_natural_score` × 4、`dimension_overrides` 数组——保留,作为数据契约
- score_detail 表中自然命中规则的记录逻辑
- demo 数据中 Atlas Construction 触发维度4 一票否决的设定

**补充(按 PRD)**:

- 确认雷达图按 PRD §5.2 实现"数据缺失维度虚线描边"——如果之前没做,本次补上

---

## 3. 实现步骤

### Step 1:撤销雷达图轴标签的⚠图标

`frontend/src/app/credit/companies/[id]/page.tsx`(或对应的雷达图子组件):

- 把雷达图轴标签从带 ⚠ 图标的自定义 React 组件**还原为纯文本标签**(默认 recharts `<PolarAngleAxis>` 行为)
- 删除相关 import:`AlertTriangle` from lucide-react(如果仅本处使用)
- 删除任何根据 `dimension_overrides` 判断是否显示图标的条件分支

### Step 2:删除"override 提示卡片"组件

详情页中,雷达图下方、明细表上方的整块 override 提示区域:

- 删除该区域的 JSX
- 如有提取为独立组件(如 `<OverrideAlertCard>`),删除该组件文件
- 删除相关样式(浅黄色背景、警示橙色边框等)
- 删除根据 `dimension_overrides.length > 0` 的条件渲染

### Step 3:撤销明细表中的"被维度规则覆盖"标注

12 子项明细表:

- 删除每行末尾的"(被维度规则覆盖)"小标记
- "得分"列恢复为显示 score_detail 中的自然得分本身(不再标注)
- 明细表样式按基线 v0.1 状态保持(包含"所属维度"列 rowspan 合并)

### Step 4:确保雷达图实现 PRD §5.2 数据缺失虚线描边

检查雷达图实现,**该项是 PRD 明确要求的**:

- 当 snapshot 的 `basic_data_id` 为 NULL → 维度1 轴虚线描边、无填充
- `finance_data_id` 为 NULL → 维度3 轴虚线描边、无填充
- `legal_data_id` 为 NULL → 维度4 轴虚线描边、无填充
- 资质认证维度(维度2)无对应 data_id 字段,根据 `credit_company_certification` 是否有该公司任何证书记录判断,如完全无证书数据则同样虚线描边

实现思路:recharts 的 `<Radar>` 可通过 `strokeDasharray` 属性设置虚线,或对单维度数据点单独设置样式。如 recharts 不直接支持每轴单独样式,可使用两个叠加的 `<Radar>`(一个绘制有数据维度的实线,另一个绘制缺失维度的虚线)。

颜色按 PRD §8.1 配色规则:80-100% 绿 / 60-79% 黄 / 40-59% 橙 / <40% 红 / 数据缺失 灰色虚线。

### Step 5:保留接口返回字段

`GET /credit/companies/{id}` 响应中以下字段**继续返回**,前端不消费:

- `dimension_1_natural_score` ~ `dimension_4_natural_score`
- `dimension_overrides`

类型定义保留,但移除前端任何对这两类字段的读取/渲染代码。可在 TypeScript 类型上加注释:

```typescript
// 后端数据契约保留字段,本期前端不消费
dimension_1_natural_score: number;
dimension_2_natural_score: number;
dimension_3_natural_score: number;
dimension_4_natural_score: number;
dimension_overrides: DimensionOverride[];
```

### Step 6:清理无用 import 与未引用代码

回滚完成后,检查:

- 详情页文件不再 import 跟 override UI 相关的图标、组件、工具函数
- 如有为 override UI 单独建的子组件文件(如 `components/credit/OverrideAlertCard.tsx`),整体删除
- 如有为 override UI 单独写的样式文件或 Tailwind 工具类组合,清理

---

## 4. 验收标准

### 前端

- Atlas Construction(D 档,维度4 触发 override)详情页:
  - 雷达图维度4 为红色填充(得分 0,按 PRD §8.1 配色),**无任何⚠图标或额外标注**
  - 雷达图下方**无 override 提示卡片**
  - 12 子项明细表正常显示,**无"被维度规则覆盖"等额外标注**;维度4 子项展示自然得分,与 snapshot.dimension_4_score(0)的不一致由数据自然呈现,不做文案解释
- 其他 3 家企业详情页:UI 一致,无 override 相关元素
- 如有 demo 企业 mock 数据 finance_data_id 设为 NULL 的场景,雷达图维度3 轴虚线描边
- `pnpm tsc --noEmit` + `pnpm build` 通过

### 后端

- **后端无任何改动**,以下保持现状:
  - score_dimension_override 表与数据
  - ScoringEngine 10 步流程
  - score_detail 自然命中规则记录
  - 接口返回 dimension_overrides 与 dimension_N_natural_score 字段

### 接口

- `GET /credit/companies/{atlas_id}` 响应仍包含 `dimension_overrides` 非空数组
- `score_detail` 维度4 的 3 条记录 hit_rule_code 仍为自然命中规则

---

## 5. 提交规范

按 step 拆 commit,或单个大 commit:

- commit message 包含:`Ref: docs/prompts/信用评估模块_工单prompt_v0_2-Δ2.md`
- 性质标注:`refactor(credit): rollback override UI to align with PRD §5.2/§8.1`

---

## 6. 严格不做的事

1. 不要回滚后端的 score_dimension_override 表与 ScoringEngine 重构
2. 不要从接口返回中删除 dimension_overrides 字段
3. 不要修改 PRD 已明确的"数据缺失虚线描边"以外的雷达图行为
4. **不要自行新增 PRD 未要求的任何 UI 元素**——本次回滚的根本原因就是上一轮超出 PRD 范围
5. 不要修改 RBAC、权限、其他模块

如遇上一轮工单实施时 UI 改动比本工单描述的更多(如修改了顶部 header、按钮位置等无关元素),也一并回滚到 v0.1 基线状态,但**仅限 override 相关的部分**——本次不动其他独立的 UI 改进。

如遇方案未覆盖的细节,**保守回退到 v0.1 基线 UI 状态**,不自行扩展功能。

---

*工单 v0.2-Δ2(增量回滚) · 撤销 v0.2-Δ1 中超出 PRD 范围的 UI 改动 · 后端保留*
