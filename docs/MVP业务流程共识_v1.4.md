# 央企海外工程供应链平台 · MVP 业务流程共识

> **文档性质**:MVP 阶段业务范围、角色组织、权限点、流程的**功能全集与参考基线**
> **遵循原则**:最小可行性,V1.0 增量功能全部不做
> **版本**:v1.4
> **更新历史**:
> - v1.0:初版,3 角色 / 5 流程 / 4 Agent / 7 待定点
> - v1.1:补充风控驾驶舱章节,优先级排在 MVP 最后
> - v1.2:新增"全局设计原则"章节,补充 AI 留占位原则及相关待定点
> - v1.3:角色从 3 类升至 4 类(拆出 OPERATOR / ADMIN);新增**权限点全集 + 角色 × 权限矩阵**章节;新增"决策已闭环"章节;清理已完成的"待提供材料"章节;`Organization` 一节扩成"角色与组织模型"
> - v1.4:**重写"十一、前端页面与功能模块全集"** ——以 `frontend/src/config/navigation.ts` 为单一可信源,按 `PUBLIC_NAV` + 4 个 `WORKSPACES` 逐项列出 tab 路径与所绑定权限点;补全 `/suppliers` 供应商目录、`/credit` 信用评估、`/risk` 风控驾驶舱、`/ai` AI 工具箱、ADMIN 的"RBAC 调试组";去掉与代码不一致的冗余条目

> **本文档不追踪实施进度**。是否已落地以 git history / PR 为准。

---

## 一、范围红线

- **V1.0 所有增量功能全部砍掉**,只做 MVP
- 严格遵循《研发可行性研究报告》中的 MVP 范围
- 技术栈不参考研发可行性报告中的建议,基于后续沟通具体设计(已锁定见 `CLAUDE.md`)

---

## 二、全局设计原则

贯穿所有流程和模块的横向准则。

### 原则 1:最小可行性(MVP 第一原则)

- 不擅自扩展需求
- V1.0 所有增量功能全部不做
- "锦上添花"让位于"主链路打通"

### 原则 2:AI 能力"留占位 + 可降级" ⭐

**核心立场**:除了明确的 4 个 Agent,业务流程中还有大量节点"可能"用 AI 辅助(资质 OCR / 入驻 AI 初审 / 报价合理性提示等)。这类 AI 能力**优先级靠后**,但**必须留占位**。

**MVP 实施要求**:

| 维度 | 要求 |
|---|---|
| 模型选择 | 国内平价大模型(DeepSeek、Qwen 等),具体到节点时再定 |
| 实现程度 | "基础"水平,不追求精度 |
| 占位强制要求 | 即便暂时不真实接入,**业务逻辑、数据结构、UI 展示位置必须预留** |
| Mock 标识 | 所有 AI 相关接口 Response 中加 `mock_ai: true` 字段(命名待 Q16 闭环) |
| 优先级 | 排在底座和基础功能之后 |

**典型 AI 占位场景**:

| 流程节点 | 潜在 AI 占位点 |
|---|---|
| 流程 1 供应商入驻 | 资质 OCR、入驻材料 AI 初审意见 |
| 流程 2 商品上架 | 国别准入资质 OCR、商品上架 AI 初审意见 |
| 流程 4 询价/报价 | 报价比价 Agent(已在 4 Agent 内)、报价合理性提示(Q14) |
| 流程 5 订单履约 | 单据 OCR、异常节点提示(Q14) |

**Mock 实现方案**(倾向 B,待 Q15 闭环):

- A. 固定文案
- B(倾向). 基于业务数据模板化生成,嵌入文件名/供应商名等真实数据
- C. 直接接入便宜模型做基础版

**与"4 个 Agent"的关系**:

- 4 个 Agent = **有独立用户入口的 AI 产品**(独立页面 / 功能按钮)
- 本原则覆盖 = **业务流程内嵌的 AI 辅助**(无独立入口,内嵌在流程节点)

### 原则 3:审计与可追溯底座 ⭐

**Trace ID**(全链路):

- 每个请求由中间件生成 UUID,写入 `request.state.trace_id` 和 contextvar
- 所有日志格式带 `[trace=xxx]`
- 所有响应头带 `X-Trace-Id`
- 失败响应 body 也带 `trace_id`

**审计日志**(只记敏感操作,不记 GET):

- 登录成功 / 失败 / 锁定 / 登出
- 注册、创建内部用户
- 改密、角色分配 / 撤销
- 所有业务写操作(POST / PUT / DELETE / PATCH)
- 失败也记

---

## 三、角色与组织模型

### 3.1 4 角色定义

| 角色 | 中文标签 | 组织归属 | 定位 |
|---|---|---|---|
| **BUYER** | 采购方 / 业主 | 挂 `BuyerOrganization` | 项目部采购员,央企项目方的现场使用者 |
| **SUPPLIER** | 供应商 | 挂 `SupplierOrganization` | 海外材料供货方 |
| **OPERATOR** | 平台运营 | 不挂组织 | 平台业务管理员(供应商审核 / 商品审核 / 国别数据 / 风控驾驶舱 / 订单总览) |
| **ADMIN** | 系统管理员 | 不挂组织 | 平台系统管理员(账号 / 角色 / 权限 / 审计 / 系统配置),**严格不触业务数据**(Q25)|

> **OPERATOR vs ADMIN 拆分原因**:运营人员审核业务,系统管理员只动系统配置。两者职责正交,权限点无交集。

### 3.2 2 组织实体

| 实体 | 表名 | MVP 数量 | 说明 |
|---|---|---|---|
| BuyerOrganization | `buyer_organizations` | 1 条("中建三局")| 按**统一社会信用代码**识别企业;新注册 BUYER 落到对应 Org |
| SupplierOrganization | `supplier_organizations` | N 条 | 按 `(country_code, registration_no)` 复合唯一(各国凭证号可撞,跨国不撞)|

**用户 ↔ 组织的关联表**:`buyer_members` / `supplier_members`(MVP 阶段一对一,但留 N:M 扩展空间)。

### 3.3 数据隔离与可见性

| 角色 | 业务数据可见范围 | 数据过滤维度 |
|---|---|---|
| BUYER | 仅本组织 | `buyer_organization_id = current_user.org_id` |
| SUPPLIER | 仅本企业 | `supplier_organization_id = current_user.supplier_id` |
| OPERATOR | 全平台业务数据 | 无过滤(但**不能改系统配置**)|
| ADMIN | **无业务数据访问**(Q25)| 不查 / 不写业务表 |

---

## 四、关键架构决策

### 决策 1:双 Organization 抽象 ⭐

- 采购方与供应商**独立建模**(不复用一张 `organizations` 表,字段差异大)
- BUYER 必须挂 `BuyerOrganization`,SUPPLIER 必须挂 `SupplierOrganization`
- 数据隔离边界 = Organization(项目、采购清单、询价单、订单都归属某个 Org)
- OPERATOR / ADMIN **不挂组织**

### 决策 2:会员 / 会费机制

- 供应商通过审核后,有一个**加入会员**的环节
- 缴会费是平台主要盈利来源之一
- 只有会员状态的供应商才能上架商品
- 时机待定(Q1)

### 决策 3:RBAC 标准化 ⭐

- 标准 RBAC0 五张表:`users / roles / permissions / user_roles / role_permissions`
- 权限点命名:`resource:action`,小写冒号分隔(`user:read`、`supplier:approve`)
- 配置文件(`app/rbac/permissions_config.py`)+ 启动同步为单一可信源(Q22 决策)
- 权限校验**三级**:后端 Guard(`require_permission(code)`,安全底线)→ 前端路由守卫 → 前端按钮显隐
- **绝对禁止**:JWT payload / 登录响应里塞 permissions、业务代码里 `if role == 'BUYER'` 硬判断、ADMIN 拿业务数据

---

## 五、权限点全集

### 5.1 35 个权限点(按资源分组)

| 分组 | 权限点 | 含义 |
|---|---|---|
| **auth(会话)** | `auth:login` / `auth:logout` / `auth:me` | 所有角色共有,系统底层会话 |
| **supplier(供应商档案)** | `supplier:read` / `supplier:write` / `supplier:approve` / `supplier:reject` | 公开池读 / 自家档案写 / 审核通过 / 驳回 |
| **product(商品)** | `product:read` / `product:write` / `product:approve` / `product:reject` | 商品 SKU 的读写与审核 |
| **country(国别准入)** | `country:read` / `country:write` | 8 国×品类准入规则 |
| **project(项目)** | `project:read` / `project:write` | BUYER 项目管理 |
| **purchase_list(采购清单)** | `purchase_list:read` / `purchase_list:write` | 基于项目的清单 |
| **cart(购物车)** | `cart:read` / `cart:write` | 商城选品 |
| **rfq(询价单)** | `rfq:read` / `rfq:create` / `rfq:respond` | 发起 / 收件响应 |
| **quote(报价)** | `quote:read` / `quote:write` | 报价单 |
| **order(订单)** | `order:read` / `order:write` / `order:checkin` | 履约 + 12 节点打卡 |
| **membership(会员)** | `membership:read` / `membership:write` | 供应商会员状态 |
| **risk(风控)** | `risk:read` | 风控驾驶舱只读视图 |
| **user(账号)** | `user:manage` | ADMIN 管账号 |
| **role(角色)** | `role:manage` | ADMIN 管角色 |
| **permission(权限点)** | `permission:manage` | ADMIN 管权限 |
| **system(系统)** | `system:config` / `system:audit` | 配置 / 审计 |

### 5.2 角色 × 权限矩阵

✓ = 该角色拥有此权限点;空 = 无。

| 资源 / 权限点 | BUYER | SUPPLIER | OPERATOR | ADMIN |
|---|:-:|:-:|:-:|:-:|
| auth:login / logout / me | ✓ | ✓ | ✓ | ✓ |
| supplier:read | ✓ | ✓ | ✓ | |
| supplier:write | | ✓ | | |
| supplier:approve / reject | | | ✓ | |
| product:read | ✓ | ✓ | ✓ | |
| product:write | | ✓ | | |
| product:approve / reject | | | ✓ | |
| country:read | ✓ | ✓ | ✓ | |
| country:write | | | ✓ | |
| project:read | ✓ | | ✓ | |
| project:write | ✓ | | | |
| purchase_list:read | ✓ | | ✓ | |
| purchase_list:write | ✓ | | | |
| cart:read / write | ✓ | | | |
| rfq:read | ✓ | ✓ | ✓ | |
| rfq:create | ✓ | | | |
| rfq:respond | | ✓ | | |
| quote:read | ✓ | ✓ | ✓ | |
| quote:write | | ✓ | | |
| order:read | ✓ | ✓ | ✓ | |
| order:write | ✓ | ✓ | | |
| order:checkin | | ✓ | | |
| membership:read | | ✓ | ✓ | |
| membership:write | | ✓ | | |
| risk:read | | | ✓ | |
| user:manage | | | | ✓ |
| role:manage | | | | ✓ |
| permission:manage | | | | ✓ |
| system:config | | | | ✓ |
| system:audit | | | | ✓ |

### 5.3 Scope 数据可见性

权限点 code 不带 scope 后缀(禁止 `:own` / `:all` / `:org`)。**同一个 code 在不同角色身上的"可见数据范围"由独立的 scope 配置决定**:

| Scope | 含义 | 典型对应 |
|---|---|---|
| `ALL` | 全平台数据,无 WHERE 过滤 | OPERATOR 拿到的业务读权限 |
| `ORG` | 本组织数据(按 `buyer_organization_id` 过滤)| BUYER 的项目 / 清单 / RFQ / 订单 |
| `OWN` | 本人 / 本企业数据(按 `supplier_id` 过滤)| SUPPLIER 的档案 / 商品 / RFQ 响应 |
| `NONE` | 无访问权 | ADMIN 对所有业务表 |

> 拆 scope 的核心收益:**权限矩阵保持精简**(35 个 code,而不是 35×3 个 code),数据隔离规则集中维护。

---

## 六、MVP 业务流程

### 流程 1:供应商入驻(含会员缴费)

```
供应商注册账号
   ↓
入驻向导:填基本信息 + 上传资质 + 选择主营品类(商品三级分类)
   ↓ [AI 占位:资质 OCR]
提交审核
   ↓ [AI 占位:入驻材料 AI 初审意见,给 OPERATOR 审核员参考]
OPERATOR 审核
   ├─ 驳回 → 供应商补材料/改信息 → 重新提交
   └─ 通过
        ↓
   缴纳会员费(成为会员)
        ↓
   获得"可上架商品"权限
```

> 注:V1.2 之前文档写的"ADMIN 审核",实际职责归 **OPERATOR**(平台运营/业务管理员);ADMIN 不触业务数据。

### 流程 2:商品上架(含国别准入审批)

```
会员供应商在工作台 → 新增 SKU
   ↓
填规格 + 阶梯报价 + 选择目标出口国别 + 关联商品三级分类
   ↓
上传国别准入相关资质(按目标国别要求的认证)
   ↓ [AI 占位:国别准入资质 OCR]
提交审核
   ↓ [AI 占位:商品上架 AI 初审意见]
OPERATOR 审核(商品信息 + 国别准入资质)
   ├─ 驳回 → 修改/补资质 → 重新提交
   └─ 通过 → SKU 上架商城
```

### 流程 3:采购方创建项目与采购清单

```
采购方登录(隶属于某 BuyerOrganization)
   ↓
创建项目(项目信息:名称 / 目的国别 / 工程类型 / 预算 / 时间窗等)
   ↓
基于项目创建 1~N 个采购清单(一个项目可对应多份采购清单)
   ↓
浏览商城(按三级分类 / 国别 / 搜索)
   ↓
将符合条件的商品加入指定采购清单
```

### 流程 4:询价(RFQ) → 报价 → 达成

```
采购方基于采购清单 → 发起询价单
   ↓
询价单审批(流程内审批,Q4 待定)
   ↓
审批通过 → 询价单分发给供应商(Q3 待定:手动选 vs 自动加载)
   ↓
供应商收到询价单 → 进行报价 → 提交报价(Q5 待定:是否需要草稿态)
   ↓ [AI 占位:报价合理性提示,Q14 待定]
采购方查看报价 → 接受 / 驳回
   ↓ [报价比价 Agent:多家比价]
(可能多轮往返,Q6 待定:是否纳入 MVP)
   ↓
最终达成一致 → 询价/报价流程结束
   ↓
基于最终报价生成订单(合同)主体
```

### 流程 5:订单履约(12 节点追踪)

```
订单生成
   ↓
12 节点全链路追踪:
节点1  订单立项
节点2  国别准入审查
节点3  三方合同签约
节点4  工厂排产
节点5  样品确认
节点6  大货生产
节点7  出厂检验
节点8  出运订舱
节点9  海运在途
节点10 目的港清关
节点11 到场验收
节点12 回款结算
   ↓ [AI 占位:单据 OCR / 异常节点提示,Q14 待定]
每个节点由对应责任方打卡 + 上传凭证
   ↓
异常状态汇入 OPERATOR 风控驾驶舱
```

### 流程关系总览

```
[流程1 供应商入驻+会员]
         ↓
[流程2 商品上架]            ← OPERATOR 持续维护"国别准入数据库"
         ↓
   商城有可售 SKU
         ↓
[流程3 项目+采购清单]       ← 采购方入口
         ↓
[流程4 询价 ⇄ 报价(可能多轮)]
         ↓
[流程5 订单生成 + 12 节点履约]
         ↓
   OPERATOR 风控驾驶舱(横向汇聚监控)
```

---

## 七、AI 智能体范围(MVP 锁定 4 个)

与研发可行性报告 §10.2.3 W10 一致,MVP 阶段交付 4 个 Agent:

| # | Agent | 集成位置 |
|---|---|---|
| 1 | **标准问答 Agent** | 独立页面 + 国别准入页面侧边助手 |
| 2 | **证书审查 Agent** | 供应商入驻审核 / 商品上架国别准入审批流程内嵌 + 独立页面 |
| 3 | **报价比价 Agent** | 询价单详情页"生成比价报告"功能 |
| 4 | **多语种翻译 Agent** | 独立页面(中↔阿/法/英 等技术文档/合同/认证翻译) |

> V1.0 的 5 个 Agent(供应商尽调 / 履约预警 / 风控资料包 / RFQ 自动响应 / 需求挖掘)**全部不做**。
> 流程内嵌的 AI 辅助见**二、全局设计原则 · 原则 2**。

---

## 八、风控驾驶舱(纳入 MVP,优先级最低) ⚠️

### 基本定位

- **不是一条主流程,是横向监控视图**
- **不发起业务**,被动消费流程 1~5 产生的数据
- **MVP 开发优先级最低**,排在 MVP 末尾(等流程 1~5 主链路稳定后再做)
- 入口在 **OPERATOR** 后台(`risk:read` 权限)

### MVP 锁定 3 个子模块

对应研发可行性报告 §1.3 底线:

| # | 子模块 | 数据来源 |
|---|---|---|
| 1 | **马甲关系图谱** | 供应商工商穿透数据(公司原有自研算法) |
| 2 | **价格异常监测** | 历史报价数据库 + 当前 RFQ 报价 |
| 3 | **合规雷达** | 订单/供应商/资金流数据(规则引擎基础版) |

### 砍掉的部分(不进 MVP)

研发可行性报告 §7.1 一共列了 6 个风控模块,以下 3 个**不做**:

- ❌ 供应商实时风险预警(依赖企查查/天眼查 API 外部对接)
- ❌ 海外项目交付看板(依赖船舶 API/物流 API)
- ❌ AI 智能洞察(LLM 自动生成日报/周报)

### 与流程的数据流向

```
[流程1 供应商入驻]   ──→ 喂数据 → [马甲关系图谱]、[合规雷达]
[流程2 商品上架]     ──→ 喂数据 → [合规雷达]
[流程4 询价/报价]    ──→ 喂数据 → [价格异常监测]
[流程5 订单+12节点]  ──→ 喂数据 → [合规雷达]
                                      ↓
                              OPERATOR 风控驾驶舱(实时监控)
```

### 可见性方案(待定)

ADMIN / 采购方 / 供应商分别看到什么 **后续讨论**,见待定点 Q11~Q13。

---

## 九、决策已闭环

以下决策点已在前序设计 / 实现中闭环,作为后续讨论的**底线契约**,不再撤回。

| 编号 | 决策 | 闭环方案 |
|---|---|---|
| **Q22** | 角色-权限关系定义方式 | 配置文件 + 启动同步(`app/rbac/permissions_config.py` 单一可信源) |
| **Q23** | `Role.scope` 字段 | 引入字段,MVP 阶段仅用 `GLOBAL`(为未来"上海公司管理员"等子作用域留位) |
| **Q24** | OPERATOR 是否细分 | **不细分**,MVP 阶段一个 OPERATOR 拿全部业务管理权限点 |
| **Q25** | ADMIN 能否访问业务数据 | **严格分离**。ADMIN 不读不写任何业务表,只动系统配置 / 账号 / 角色 / 权限 / 审计 |
| **Q26** | super admin 密码策略 | 环境变量注入初始密码 + 强制首次登录改密 |
| **Q27** | 何时切换 PostgreSQL | 已切(2026-05-18,本机 brew @16 端口 5433) |
| **Q28** | 是否容器化部署 | 已切(2026-05-20,Docker compose + GitHub Actions **手动触发**部署) |

---

## 十、待定点清单 📌

后续需要逐一讨论确认,**不擅自决定**。

### 流程相关

| 编号 | 待定问题 | 所属流程 |
|---|---|---|
| **Q1** | 会员费缴纳时机:**入驻申请前缴费** vs **审批通过后缴费** | 流程 1 |
| **Q2** | 商品上架时的国别准入审批**具体流程细节** | 流程 2 |
| **Q3** | 询价时供应商的选择方式:**采购方手动选** vs **系统按采购清单内商品所属供应商自动加载** | 流程 4 |
| **Q4** | 询价单的**审批流程具体设计**(谁审?审什么?) | 流程 4 |
| **Q5** | 供应商报价是否需要**提交确认环节**(草稿态/已提交态) | 流程 4 |
| **Q6** | **多轮报价是否纳入 MVP**(采购方驳回 → 供应商重新报价) | 流程 4 |
| **Q7** | 是否需要新增角色(除现有 4 角色之外) | 全局 |

### 风控驾驶舱相关(MVP 末期讨论)

| 编号 | 待定问题 |
|---|---|
| **Q8** | 马甲关系识别算法是直接复用公司现有的,还是 MVP 阶段先用简化版? |
| **Q9** | 价格异常监测的"历史报价数据库"从哪里来?是否需要导入公司原有招投标历史价格库做冷启动? |
| **Q10** | 合规雷达的规则具体包括哪些?MVP 阶段先做哪几条核心规则? |
| **Q11** | 风控信息是否对采购方/供应商可见?分层可见还是仅 OPERATOR 可见? |
| **Q12** | 如果分层可见,采购方侧的入口是独立页面还是内嵌到询价单/订单详情页? |
| **Q13** | 供应商侧是否在 MVP 做申诉入口? |

### AI 留占位相关

| 编号 | 待定问题 |
|---|---|
| **Q14** | AI 占位的具体覆盖节点(报价合理性提示 / 单据 OCR / 异常节点提示等是否要留占位?) |
| **Q15** | Mock 数据的真实程度:固定文案 / 模板化 / 直接接入便宜模型?(倾向模板化) |
| **Q16** | Mock 标识字段的具体命名(`mock_ai` / `meta.mockAI` / `_mock` 等),待 API 规范统一确认 |

---

## 十一、前端页面与功能模块全集

> **单一可信源**:`frontend/src/config/navigation.ts`(`PUBLIC_NAV` 6 项 + 4 个 `WORKSPACES`)。
> 本节按代码中实际配置逐项列出,任何 tab 变更应优先改 `navigation.ts`,然后回写本表。

### A. 公开 / 营销区

顶部 header 主导航,公开 layout 与工作台 layout 共用。匿名用户全可见;登录后按 `NavItem.hideForRoles` 过滤。

| 模块 | 路径 | 备注 |
|---|---|---|
| 平台首页 | `/` | 落地页 |
| 严选商城 | `/mall` | B2B 工业品采购前台(三级分类导航 + 国别筛选)|
| 供应商目录 | `/suppliers` | 供应商列表 / 供应商画像页 |
| 国别准入 | `/countries` | 8 国准入卡详情 |
| 信用评估 | `/credit` | 供应商信用评估与资质认证 |
| 风控驾驶舱 | `/risk` | 马甲关系 / 价格异常 / 合规雷达(对外营销视图)|
| AI 工具箱 | `/ai` | 4 Agent 入口(标准问答 / 证书审查 / 报价比价 / 多语种翻译)|

**Auth 配套页**(不在主导航):`/login` / `/register` / `/change-password` / `/account` / `/no-permission`。

### B. 采购方(BUYER) 工作台

路径前缀 `/buyer`,主题色 `#003366`。

| 模块 | 路径 | 绑定权限点 |
|---|---|---|
| 工作台 | `/buyer/dashboard` | (登录即可)|
| 项目管理 | `/buyer/projects` | `project:read` / `project:write` |
| 采购清单 | `/buyer/purchase-lists` | `purchase_list:read` / `purchase_list:write` |
| 购物车 | `/buyer/cart` | `cart:read` / `cart:write` |
| 询价管理 | `/buyer/rfqs` | `rfq:read` / `rfq:create`(询价单详情、比价决策为其子能力)|
| 订单管理 | `/buyer/orders` | `order:read` / `order:write`(订单详情、12 节点履约、单据中心为其子能力)|

### C. 供应商(SUPPLIER) 工作台

路径前缀 `/supplier`,主题色 `#FF6B35`。

| 模块 | 路径 | 绑定权限点 |
|---|---|---|
| 工作台 | `/supplier/dashboard` | (登录即可)|
| 企业入驻 | `/supplier/onboarding` | `supplier:write`(3 步向导 + 资质上传,含 OCR 占位)|
| 会员中心 | `/supplier/membership` | `membership:read` / `membership:write` |
| 商品管理 | `/supplier/products` | `product:read` / `product:write`(SKU 列表 + 国别准入资质关联)|
| 收到的询价 | `/supplier/rfqs` | `rfq:read` / `rfq:respond` |
| 我的报价 | `/supplier/quotes` | `quote:read` / `quote:write` |
| 订单管理 | `/supplier/orders` | `order:read` / `order:write` / `order:checkin`(节点打卡)|
| 企业档案 | `/supplier/profile` | `supplier:read`(企业资料 + 评分查看)|
| 成员管理 | `/supplier/members` | (待细化,Owner 邀请 / 移除企业内员工)|

### D. 平台运营(OPERATOR) 后台

路径前缀 `/operator`,主题色 `#0F4C81`。

| 模块 | 路径 | 绑定权限点 | 优先级 |
|---|---|---|---|
| 管理首页 | `/operator/dashboard` | (登录即可)| 正常 |
| 供应商审核 | `/operator/supplier-review` | `supplier:approve` / `supplier:reject` | 正常 |
| 商品审核 | `/operator/product-review` | `product:approve` / `product:reject` | 正常 |
| 订单总览 | `/operator/orders` | `order:read` | 正常 |
| 国别数据维护 | `/operator/countries` | `country:write` | 正常 |
| **风控驾驶舱** | `/operator/risk-cockpit` | `risk:read` | **MVP 末期** |

### E. 系统管理员(ADMIN) 后台

路径前缀 `/admin`,主题色 `#475569`。**严格不出现任何业务数据**(Q25)。

| 模块 | 路径 | 绑定权限点 |
|---|---|---|
| 用户管理 | `/admin/users` | `user:manage`(创建 / 禁用 ADMIN 与 OPERATOR 账号)|
| 角色管理 | `/admin/roles` | `role:manage`(MVP 阶段角色由启动同步管理,主要为只读)|
| 权限管理 | `/admin/permissions` | `permission:manage` |
| 系统配置 | `/admin/config` | `system:config`(JWT / 限流 / Trace 等系统级配置)|
| 审计日志 | `/admin/audit-logs` | `system:audit`(按 trace_id / 用户 / 资源 / 动作筛选)|

**RBAC 调试组**(同样挂在 `/admin` 工作台下,辅助 RBAC 验证,**MVP 临时**):

| 模块 | 路径 |
|---|---|
| 权限矩阵全景 | `/admin/permission-matrix` |
| BUYER API 调试 | `/test/buyer-only` |
| SUPPLIER API 调试 | `/test/supplier-only` |
| OPERATOR API 调试 | `/test/operator-only` |
| ADMIN API 调试 | `/test/admin-only` |

### F. AI 智能体工具箱

4 个 Agent 见**第七节**。流程内嵌 AI 辅助见**第二节原则 2**。

---

*文档结束*
