# ADR-0003:信用评估模块 LLM 选型

## 元信息

| 字段 | 内容 |
|---|---|
| 编号 | ADR-0003 |
| 标题 | 信用评估模块 LLM 选型(MVP 阶段) |
| 状态 | Accepted |
| 决策日期 | 2026-05-23 |
| 决策范围 | 信用评估模块下所有 LLM 调用场景 |
| 影响模块 | 信用评估 AI 综合评价、AI 对话追问 |
| 关联 | ADR-0001 OCR 选型(`docs/adr/ADR-0001-OCR模型选型.md`,共用 DashScope 账号) |

## 一、背景

信用评估模块需要 LLM 能力支撑两类场景:

1. **AI 综合评价生成**:评分计算完成后,基于结构化评分数据生成一段约 200-400 字的总评(优势/风险/建议),写入 `score_snapshot.ai_summary` 缓存
2. **AI 对话追问**:用户在详情页对话框中针对当前企业追问,需流式输出 + 多轮上下文

## 二、决策

**MVP 阶段采用通义千问 qwen-plus 作为信用评估模块的默认 LLM。**

- 主力模型:`qwen-plus`(阿里云 DashScope)
- SDK:**`openai` Python SDK + DashScope OpenAI 兼容端点**(`https://dashscope.aliyuncs.com/compatible-mode/v1`)
  - 决策更新(2026-05-23 C2 实施时):本节原写 dashscope 原生 SDK,实施时改为 openai SDK,
    理由见 §三"协议兼容"+ §五;dashscope 仅适用于其原生独占特性(本期 chat+stream 用不到)
- 接口抽象:后端封装 `LLMService` 抽象基类,所有 LLM 调用走该接口,具体实现为 `QwenChatService`
- 失败降级:LLM 不可用时,综合评价字段留空,前端展示"AI 评价暂时不可用";对话追问返回错误提示
- 数据留痕:对话记录写入 `credit_ai_conversation` + `credit_ai_message` 两张表

## 三、选型理由

| 因素 | 说明 |
|---|---|
| 与 ADR-0001 OCR 选型一致 | DashScope 账号与 API Key 复用,采购流程零增量 |
| 性价比 | qwen-plus 单次调用成本约几分钱,200-400 字总评 + 几轮对话单家企业成本可控 |
| 合规 | 国内云服务,数据不出境,央企场景默认合规 |
| 协议兼容 | DashScope 兼容 OpenAI messages 格式,后续切换其他模型代码改动小 |
| 流式输出 | 原生支持 SSE 流式,前端对话体验有保障 |

## 四、未选用方案(简记)

- qwen-max:质量略好但成本高 2-3 倍,MVP 阶段过剩
- qwen-turbo:成本更低但 200-400 字总评质量不够稳
- Claude/GPT:合规与采购流程问题,且 ADR-0001 已规避境外模型
- DeepSeek/智谱:可作为备选,但 MVP 阶段优先生态一致性

## 五、抽象层设计要点

```
app/services/llm/
  ├── base.py                # LLMService 抽象基类
  └── qwen_chat_service.py   # 千问实现
```

`LLMService` 暴露两个方法:

- `generate(prompt: str) -> str` 同步生成(用于 AI 综合评价)
- `stream_chat(messages: list[dict]) -> AsyncIterator[str]` 流式对话(用于追问)

后续切换模型仅替换实现类,业务层不感知。

## 六、未来演进触发条件

| 触发条件 | 评估方向 |
|---|---|
| 月调用量超过预算阈值 | 评估降级到 qwen-turbo 或混合调用 |
| 综合评价质量不达标 | 评估升级到 qwen-max 或调整 prompt |
| 国家合规政策变化 | 评估引入 Claude/GPT 作为备选 |
| 出现新一代国产模型(明显优于 qwen) | 评估切换 |

## 七、变更历史

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-05-23 | v1.0 | 初版,确定 MVP 采用 qwen-plus |