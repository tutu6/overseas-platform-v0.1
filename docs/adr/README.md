# 架构决策记录(ADR)

本目录存放本项目所有的**架构决策记录(Architecture Decision Records)**。

## 什么是 ADR

ADR 是一种轻量的文档格式,用来记录**重要的技术/架构决策的"为什么"**。

每个 ADR 回答三个核心问题:
1. **背景**:为什么需要做这个决策?
2. **决策**:我们选了什么?
3. **后果**:这个选择带来什么正面/负面影响?

## 什么时候写 ADR

以下情况需要写 ADR:

- ✅ 重大技术选型(数据库、缓存、消息队列、LLM 模型等)
- ✅ 重大架构模式选择(单体 vs 微服务、同步 vs 异步、SSR vs CSR 等)
- ✅ 跨模块的设计约定(API 风格、错误码规范、审计日志策略等)
- ✅ 重大业务模型设计(评分模型架构、权限模型、数据隔离方案等)
- ✅ 安全/合规相关的决策(数据加密策略、敏感字段处理、跨境合规等)

不需要写 ADR 的:
- ❌ 单个函数的实现方式
- ❌ 临时性的代码风格选择
- ❌ 显而易见的常规决策

## 编号与命名规则

- 编号:四位数字,从 0001 开始,顺序递增,**不重用**
- 文件名:`ADR-XXXX-短标题-用连字符.md`
- 例:`ADR-0001-ocr-model-selection.md`

## 状态流转

每个 ADR 的状态字段使用以下取值:

| 状态 | 含义 |
|---|---|
| `Proposed` | 提议中,讨论阶段 |
| `Accepted` | 已采纳,执行中 |
| `Deprecated` | 已废弃,但保留历史(不删除文件) |
| `Superseded by ADR-XXXX` | 被新决策取代(注明取代它的 ADR 编号) |

**重要**:**ADR 一旦进入 Accepted 状态,不再修改正文**。如需调整决策,新建一份 ADR 标记"Supersedes ADR-XXXX",老 ADR 状态改为 `Superseded by ADR-XXXX`。

## ADR 模板

新建 ADR 请参考模板:`_template.md`(待补充)

简化版结构:

```markdown
# ADR-XXXX:标题

## 元信息
| 字段 | 内容 |
|---|---|
| 编号 | ADR-XXXX |
| 状态 | Proposed / Accepted / ... |
| 决策日期 | YYYY-MM-DD |
| 决策人 | xxx |

## 一、背景与上下文
## 二、决策
## 三、备选方案对比
## 四、后果(正面/负面/风险)
## 五、实施计划
## 六、未来演进
## 七、相关文档
## 八、变更历史
```

## 当前 ADR 清单

| 编号 | 标题 | 状态 | 决策日期 |
|---|---|---|---|
| ADR-0001 | 信用评估模块 OCR 模型选型 | Accepted | 2026-05-22 |

## 参考资料

- Michael Nygard 提出的 ADR 原始格式:[Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- ThoughtWorks Tech Radar 把 ADR 列为 Adopt 级实践
