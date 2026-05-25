# Task: 维度级 override 重构 · 增量工单 prompt v0.2-Δ1

> 状态:可下发 Claude Code
> 日期:2026-05-23
> 类型:**增量重构**,基于已合入主干的 v0.1 信用评估模块
> 关联文档:
> - 基线工单:`docs/prompts/信用评估模块_工单prompt_v0_1.md`
> - 技术方案:`docs/architecture/信用评估模块技术方案设计-v0_1.md`
> - PRD:`docs/prd/信用评估模块 PRD v0.3_四维评分模型版.md.docx`(§4.3 + §5.2)
> 当前分支:`feat/credit-dimension-override-refactor`(基于 main 切出)

---

## 1. 任务上下文

### 1.1 当前代码状态

v0.1 信用评估模块已开发完成并合入主干,**维度级强制规则当前用"9 条 priority=0 的 score_rule 子项级 override 规则"实现**:

- 维度2 "关键证书伪造/过期 → 维度强制清零":3 条 score=0 的 priority=0 rule(挂在维度2 的 3 个子项上)
- 维度3 "整维度数据缺失 → 该维度 40% 满分(12 分)":3 条 score=4 的 priority=0 rule
- 维度4 "失信被执行未结案 → 维度直接判 0(一票否决)":3 条 score=0 的 priority=0 rule

这种实现的**遗留问题**:`score_detail` 表的 `hit_rule_code` / `hit_rule_description` 被 override 规则覆盖,丢失了"自然命中规则"信息——无法回答"如果没有这次失信,这家公司本来会得多少分"。

### 1.2 本次重构目标

将维度级 override **从 score_rule 表中剥离**,单独建模为 `score_dimension_override` 表,在 ScoringEngine 中实现"自然评分 → 维度级 post-process"两步流程。重构后:

- `score_rule` 表保持纯子项级语义,不混入维度级规则
- `score_detail` 表完整保留"自然命中规则"信息
- `score_snapshot` 同时记录"自然分"和"override 后的最终分"
- 用户可见"原本得分 vs 实际得分"的差异(为未来 UI 展示预留数据)

### 1.3 阅读顺序

按顺序阅读后开始动手:

1. 本工单 §2 重构范围 + §3 实现步骤
2. 基线工单 `docs/prompts/信用评估模块_工单prompt_v0_1.md` —— 了解现有代码结构
3. 技术方案 `docs/architecture/信用评估模块技术方案设计-v0_1.md` —— 数据模型与抽象层
4. PRD `docs/prd/信用评估模块 PRD v0.3_四维评分模型版.md.docx` §4.3 + §5.2

---

## 2. 重构范围

**做**:

- 新建 `score_dimension_override` 表 + ORM 模型
- 扩展 `score_snapshot` 表,新增 5 个字段(4 个 natural_score + 1 个 dimension_overrides jsonb)
- 拆分 evaluators 为"子项级 evaluator"和"维度级 override evaluator"两组
- 重构 ScoringEngine:加"维度级 post-process"步骤
- 修订 seed:删除 9 条假装的 priority=0 子项 rule,改为 3 条 dimension_override 记录
- 重算所有已存在的 score_snapshot(可选,见 §3.7)
- 详情接口返回字段补充 dimension_overrides
- 前端详情页据 dimension_overrides 展示 override 提示

**不做**:

- 不改 DataSource / LLMService / AI 对话相关代码
- 不改 RBAC 权限点
- 不改 credit_company / credit_company_*_data / credit_company_certification 表结构
- 不改 ScoreDetail 表结构

---

## 3. 实现步骤

### Step 1:alembic 迁移

新增迁移文件 `20260523_0007_dimension_override_refactor.py`,包含:

**建新表 `score_dimension_override`**:

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | int | PK 自增 | |
| `dimension_id` | int | FK → score_dimension.id NOT NULL | |
| `code` | varchar(128) | UNIQUE NOT NULL | 如 DIM2_CERT_FORGED_OR_EXPIRED |
| `description` | varchar(500) | NOT NULL | UI 展示用文案 |
| `override_score` | smallint | NOT NULL | 命中后该维度强制得分 |
| `evaluator_key` | varchar(100) | NOT NULL | 映射到 Python 函数名 |
| `priority` | smallint | NOT NULL default 0 | 同维度多条 override 时的优先级,升序求值 |
| `is_active` | boolean | NOT NULL default true | |
| `version` | int | NOT NULL default 1 | |
| `created_at` / `updated_at` | timestamp | NOT NULL | |

**扩展 `score_snapshot` 表**:

```python
op.add_column('score_snapshot', sa.Column('dimension_1_natural_score', sa.SmallInteger(), nullable=True))
op.add_column('score_snapshot', sa.Column('dimension_2_natural_score', sa.SmallInteger(), nullable=True))
op.add_column('score_snapshot', sa.Column('dimension_3_natural_score', sa.SmallInteger(), nullable=True))
op.add_column('score_snapshot', sa.Column('dimension_4_natural_score', sa.SmallInteger(), nullable=True))
op.add_column('score_snapshot', sa.Column('dimension_overrides', postgresql.JSONB(), nullable=True))
```

**注意**:新字段先 nullable=True(避免对历史数据的强约束)。Step 7 数据回填后,可选在后续迁移中改为 NOT NULL,**本次重构不做此约束变更**。

**清理旧的 priority=0 子项 override rule**:

```python
# 删除 9 条 priority=0 的旧 override rule(它们已经被 score_dimension_override 表替代)
op.execute("DELETE FROM score_rule WHERE priority = 0 AND code LIKE 'DIM%_OVERRIDE_%'")
```

注意:这条 DELETE 语句对应具体的 rule code 命名规则,**请先查仓库实际 seed 出的 code,改成精确匹配条件**,避免误删其他规则。建议改为显式枚举 9 条 code。

`downgrade()` 写完整,按建表反序 drop 列、drop 表。但 **DELETE 不可逆**,downgrade 时通过重新 INSERT 9 条 rule 恢复(可以从 git 历史拿到原始 seed 代码),如复杂可在 downgrade 文档内标注"不完全可逆"。

### Step 2:ORM 模型

新增 `backend/app/db/models/score_dimension_override.py`,沿用现有规范(继承 `Base, TimestampUpdateMixin`,字段类型对齐迁移)。

修改 `backend/app/db/models/score_snapshot.py`,添加 5 个新字段。

`__init__.py` 导出新模型。

### Step 3:Evaluators 拆分

`backend/app/services/credit/evaluators.py` 文件内部分为两组:

**第一组:子项级 evaluators**(保留现有的 ~35 个自然规则函数)

```python
# === 子项级 evaluators(自然评分) ===

def basic_reg_info_full(data: dict) -> bool: ...
def basic_reg_info_miss_one(data: dict) -> bool: ...
# ... ~35 个

SUBITEM_EVALUATORS = {
    "basic_reg_info_full": basic_reg_info_full,
    # ...
}
```

**第二组:维度级 override evaluators**(新增 3 个)

```python
# === 维度级 override evaluators ===

def dim2_cert_forged_or_expired(data: dict) -> bool:
    """维度2 强制清零:任意关键证书伪造或过期未更新"""
    certs = data.get('certifications', [])
    return any(
        c.get('status') in ('expired', 'suspicious_forged')
        and c.get('cert_type') == 'mandatory_country'
        for c in certs
    )

def dim3_unknown(data: dict) -> bool:
    """维度3 数据完全缺失 → 该维度得满分 40%"""
    return data.get('finance_data') is None

def dim4_unresolved_defaulter(data: dict) -> bool:
    """维度4 一票否决:有未结案失信被执行记录"""
    legal = data.get('legal_data')
    if legal is None:
        return False
    return legal.get('defaulter_unresolved_count', 0) > 0

DIMENSION_OVERRIDE_EVALUATORS = {
    "dim2_cert_forged_or_expired": dim2_cert_forged_or_expired,
    "dim3_unknown": dim3_unknown,
    "dim4_unresolved_defaulter": dim4_unresolved_defaulter,
}
```

**注意**:原有 EVALUATORS 字典如被 ScoringEngine / 其他地方引用,**重命名为 SUBITEM_EVALUATORS** 并更新所有调用方;不要简单 alias,要让"子项级"和"维度级"在代码层面就明确区分。

### Step 4:ScoringEngine 重构

`backend/app/services/credit/scoring_engine.py` 的 `compute()` 方法,工作流程从 9 步扩展为 10 步:

```
1. 加载 active 规则集(SUBITEM_EVALUATORS 适用的 score_rule + score_dimension_override)
2. 通过 DataSource 获取四类数据 + 证书清单
3. 子项级自然评分:
     对每个 active subitem:
       - 加载该 subitem 下所有 active rule,按 priority 升序
       - 依次调用 SUBITEM_EVALUATORS[rule.evaluator_key](data)
       - 首条命中即停,记录 score 和 hit_rule
       - 全部未命中,走 subitem.default_score
4. 维度自然分:
     对每个维度,subitem 自然得分求和 → dimension_N_natural_score
5. 维度级 override post-process:
     对每个维度:
       - 加载该维度下所有 active dimension_override,按 priority 升序
       - 依次调用 DIMENSION_OVERRIDE_EVALUATORS[override.evaluator_key](data)
       - 首条命中即停,记录:
           · final_score = override.override_score
           · 在 dimension_overrides jsonb 数组追加一条:
             {dimension_code, override_rule_code, override_description,
              natural_score, final_score}
       - 没命中,final_score = natural_score
6. 总分 = sum(四个维度的 final_score)
7. grade 阈值映射(A≥80 / B≥60 / C≥40 / D<40)
8. 写 score_snapshot(同时写入 natural_score 和 final_score 两份字段)
9. 写 12 条 score_detail(hit_rule_code / hit_rule_description 保留自然命中规则,**不受 override 影响**)
10. 对比前快照,如分数有变化,写 score_audit_log + 平台 audit_logs
```

**事务边界**:步骤 8-10 在同一事务内提交。

**关键点**:被 override 的维度,score_detail 里 3 个子项的 hit_rule 仍然是"自然命中规则",分数也是自然得分;只在 snapshot 表的 `dimension_N_score` 字段上呈现 override 后的最终分。**score_detail.score 与 sum 维度分**可能不一致,这是预期行为(因为有维度级 override),代码注释中明确这一点。

### Step 5:dimension_overrides JSON 结构

snapshot 的 `dimension_overrides` 字段格式:

```json
[
  {
    "dimension_code": "LEGAL_RISK",
    "override_rule_code": "DIM4_UNRESOLVED_DEFAULTER",
    "override_description": "失信被执行未结案,维度直接判 0 分(一票否决)",
    "natural_score": 23,
    "final_score": 0
  },
  {
    "dimension_code": "QUALIFICATION",
    "override_rule_code": "DIM2_CERT_FORGED_OR_EXPIRED",
    "override_description": "关键证书伪造或过期未更新,维度强制清零",
    "natural_score": 18,
    "final_score": 0
  }
]
```

未触发 override 时,字段为空数组 `[]` 或 NULL(任选一种,但代码内保持一致;推荐空数组,前端判断更简单)。

### Step 6:Seed 数据修订

`backend/app/seed.py` 的 `seed_credit_score_model()`:

**删除**(已被 Step 1 迁移的 DELETE 处理,但 seed 代码也要清理):

- 删除原 9 条 priority=0 的 score_rule seed 记录代码段

**新增 `seed_credit_dimension_overrides()`**,seed 3 条 dimension_override:

| code | dimension | description | override_score | evaluator_key | priority |
|---|---|---|---|---|---|
| `DIM2_CERT_FORGED_OR_EXPIRED` | QUALIFICATION | 关键证书伪造或过期未更新,维度强制清零 | 0 | dim2_cert_forged_or_expired | 0 |
| `DIM3_UNKNOWN` | FINANCE | 财务数据完全缺失,维度给满分 40% | 12 | dim3_unknown | 0 |
| `DIM4_UNRESOLVED_DEFAULTER` | LEGAL_RISK | 失信被执行未结案,维度直接判 0(一票否决) | 0 | dim4_unresolved_defaulter | 0 |

挂到 `run_all_seeds()`,在 `seed_credit_score_model()` 之后调用,幂等(检查 code 是否存在再插入)。

**启动校验**:在 seed 完成后,扫描所有 dimension_override 的 evaluator_key 必须在 DIMENSION_OVERRIDE_EVALUATORS 字典中存在,不一致则日志报错(不阻断启动,同现有 SUBITEM_EVALUATORS 校验风格)。

### Step 7:历史数据回填(可选)

现有 4 家 demo 企业的 score_snapshot 已经写过分。本次重构后,这些快照的:

- `dimension_N_natural_score` 字段为 NULL(因迁移加列默认 NULL)
- `dimension_overrides` 字段为 NULL
- 但 `dimension_N_score` 和 `total_score` 是旧机制算出的结果(实际上等价于"override 后的最终分",因为旧机制把 override 也算成 0/4/12 子项分,加起来跟新机制最终分一致)

**推荐做法**:启动时自动触发一次"对所有 is_current=true 的 snapshot 重算"。在 `app/seed.py` 加一个开关式函数 `recompute_existing_snapshots()`,通过 settings 字段 `RECOMPUTE_ON_REFACTOR_BOOT=true` 控制,默认 false。

启动一次后,运营手动跑:

```bash
RECOMPUTE_ON_REFACTOR_BOOT=true uv run uvicorn app.main:app
```

观察日志确认 4 家企业全部重算成功(natural_score 字段被回填,如果有 override 命中,dimension_overrides 也被回填),之后关掉这个开关。

**或更简单的做法**:重算逻辑通过 `POST /credit/recompute-all` 接口触发,部署后手动 curl 一次。

### Step 8:详情接口字段补充

`GET /credit/companies/{id}` 的响应 schema 增加:

```python
class ScoreSnapshotResponse(BaseModel):
    # ... 原有字段
    dimension_1_natural_score: int | None
    dimension_2_natural_score: int | None
    dimension_3_natural_score: int | None
    dimension_4_natural_score: int | None
    dimension_overrides: list[dict] | None
```

序列化时,空数组与 None 都允许,前端按 `dimension_overrides && dimension_overrides.length > 0` 判断是否有 override。

### Step 9:前端详情页

`frontend/src/app/credit/companies/[id]/page.tsx`:

**1. 雷达图 override 标注**:

雷达图绘制时,数据源仍是 `dimension_N_score`(即最终分)。但对于命中 override 的维度,在该轴的标签旁追加一个⚠图标(`lucide-react` 的 `AlertTriangle`)+ hover tooltip 显示 override 原因。

实现思路:把雷达图轴标签从纯文本改为 React 组件,根据 dimension_overrides 数组判断是否该轴需要标注。

**2. 维度 override 提示卡片**(新增):

详情页**雷达图下方、12 子项明细表上方**,新增一个 override 提示区域(仅当 dimension_overrides 非空时显示):

```
┌──────────────────────────────────────────────────────────┐
│ ⚠ 该评分包含 N 项强制规则触发                              │
├──────────────────────────────────────────────────────────┤
│ 司法与舆情风险维度:失信被执行未结案,维度直接判 0(一票否决)│
│   自然评分 23 → 最终评分 0                                  │
└──────────────────────────────────────────────────────────┘
```

样式:浅黄色背景 + 警示橙色边框 + AlertTriangle 图标。

**3. 12 子项明细表中的 override 行处理**:

被 override 的维度,3 行子项的"得分"列展示自然得分(从 score_detail 拿),并在每行末尾追加一个小标记"(被维度规则覆盖)"。这样用户既能看到"原本子项该得多少分",也知道"这分数最终被强制清零了"。

### Step 10:demo 数据验证

确认 4 家 demo 企业的 mock 数据能正确触发 override:

| 企业 | 预期等级 | 是否触发 override |
|---|---|---|
| Al-Rashid Industrial(沙特) | A | 无 |
| PT Cahaya Sentosa(印尼) | B | 无 |
| Karachi Steel Works(巴基斯坦) | C | 无 |
| Atlas Construction(摩洛哥) | D | **触发维度4 一票否决**(legal_data 的 defaulter_unresolved_count ≥ 1) |

如果原 mock 数据有不符合预期的(比如 D 档企业的失信记录数为 0,实际通过低分自然评分凑到 D 档),需要调整 seed 数据,确保 D 档企业**真正触发 override**,作为这个机制的演示用例。

### Step 11:TODO 标记清理

代码内搜索原 v0.1 关于"维度级 override 用 9 条子项 rule 实现"的 TODO 或注释,删除(本次重构已经解决了)。

新增一处注释,在 ScoringEngine 的 post-process 步骤:

```python
# 维度级 override:命中后该维度最终分被覆盖,但 score_detail 仍保留自然命中规则,
# 用于"原本得分 vs 实际得分"的可解释性展示。详见技术方案 §3.2 步骤 5。
```

---

## 4. 验收标准

### 数据库

- `alembic upgrade head` 成功执行,score_dimension_override 表创建,score_snapshot 加 5 列
- 旧的 9 条 priority=0 子项 override rule 被删除,`SELECT COUNT(*) FROM score_rule WHERE priority=0` 应为 0
- `SELECT COUNT(*) FROM score_dimension_override` 应为 3
- 4 家 demo 企业重算后,Atlas Construction 的 snapshot 应有:
  - `dimension_4_natural_score > 0`(比如 23)
  - `dimension_4_score = 0`
  - `dimension_overrides` 包含一条 DIM4_UNRESOLVED_DEFAULTER 记录
  - `grade = 'D'`

### 接口

- `GET /credit/companies/{atlas_id}` 返回数据含 dimension_overrides 数组非空
- `score_detail` 中维度4 的 3 个子项,hit_rule_code 是真实的自然命中规则(不是 override 规则)

### 前端

- Atlas Construction 详情页:
  - 雷达图维度4 轴标签旁有⚠图标
  - 雷达图下方有 override 提示卡片,显示"自然评分 23 → 最终评分 0"
  - 12 子项明细表中,维度4 的 3 行末尾标注"(被维度规则覆盖)"
- 其他 3 家企业:override 提示卡片不显示

### 代码

- `pnpm tsc --noEmit` + `pnpm build` 通过
- 后端 `uv run pytest` 通过(如有相关单测,补充 ScoringEngine override 路径的单测)
- evaluators.py 中 SUBITEM_EVALUATORS 和 DIMENSION_OVERRIDE_EVALUATORS 两个字典明确分开,不混用

---

## 5. 提交规范

按 step 拆 commit,或单个大 commit 也接受。commit message 包含:

- 关联文档:`Ref: docs/architecture/信用评估模块技术方案设计-v0_1.md`
- 关联工单:`Ref: docs/prompts/信用评估模块_工单prompt_v0_2-Δ1.md`(即本工单)
- 重构性质标注:`refactor(credit): dimension override → standalone table`

---

## 6. 不要做的事

1. 不要改 score_detail 表结构(保留自然命中规则就是这张表的职责)
2. 不要把 dimension_override 的求值塞进 score_rule 表(那是回退到改动 A 的方案)
3. 不要为 evaluators.py 引入新的运行时库(simpleeval / asteval 等),DSL 解析是 T-3 的事
4. 不要顺手实现 PDF 导出 / T+1 调度 / 真实数据源接入,这些是其他 TODO
5. 不要修改 RBAC 权限点(本次不涉及权限变更)
6. 不要破坏现有 v0.1 接口契约(详情接口只增字段,不减不改名)

如遇方案未覆盖的细节,选最简实现 + 代码标注 `TODO: 方案未覆盖,采用最简实现`,**不自行扩展功能**。

---

*工单 v0.2-Δ1(增量) · 基线 v0.1 已合入主干 · 重构维度级 override 实现机制*
