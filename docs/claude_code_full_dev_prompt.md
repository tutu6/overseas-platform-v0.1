# Claude Code 开发任务书：海外严选供应链平台 V1.0

> **发送对象**：Claude Code
> **任务定位**：从零开发一个**完整可运行的全栈Web应用**（不是静态demo），所有按钮可点、所有表单可提交、所有数据真实落库、供应商可真实上传资料并走完审核流程
> **预计开发时长**：60-90 分钟连续会话
> **交付标准**：`npm install && npm run db:setup && npm run dev` 三条命令后，浏览器打开 http://localhost:3000，所有功能可演示

---

## 0. 项目使命（必读，决定所有设计取舍）

我们要建的是**"中国央企海外EPC项目的工业品严选商城 + 供应商信用履约系统 + AI智能体工具箱"**，定位是建筑行业海外供应链的"京东工业品 + 邓白氏 + Palantir"三合一。

**核心用户三类**：
1. **采购方（央企）**：中建三局、中交建、中铁建等海外项目部采购员，浏览商城、发起询价、追踪履约
2. **供应商**：中国制造业海外贸易商，注册入驻、上传资质、上架商品、接单履约
3. **平台运营**：审核供应商、风控监测、运营数据看板

**业务核心循环**：
```
供应商注册 → 上传资质 → 平台审核通过 → 上架商品 → 央企浏览询价 →
平台撮合 → 生成订单 → 履约追踪 → 评分沉淀 → 信用积累
```

**禁止设计为静态展示**：每个功能必须有真实数据库支撑，必须可CRUD，必须有真实状态流转。

---

## 1. 技术栈（已锁定，不要改）

| 层 | 选型 | 理由 |
|---|---|---|
| 框架 | **Next.js 14 (App Router) + TypeScript** | 全栈一体，部署简单 |
| UI | **Tailwind CSS + shadcn/ui** | 工业级组件库 |
| 数据库 | **SQLite + Prisma ORM** | 零配置本地可跑，生产可一键换Postgres |
| 认证 | **NextAuth.js v5 (Auth.js) + bcrypt** | 邮箱密码+角色权限 |
| 文件上传 | **本地存储到 `public/uploads/`** | MVP不引入S3 |
| 图表 | **Recharts** | React生态最稳 |
| AI集成 | **`@anthropic-ai/sdk`** | 直接调Claude API |
| 表单 | **React Hook Form + Zod** | 类型安全 |
| 国际化 | **next-intl**（仅中文一套，预留i18n结构） | 后期接入英语/法语/阿语 |
| 状态管理 | **Zustand**（仅购物车等极少全局态用）| 不要Redux |

**禁止引入**：MongoDB、Express单独后端、Docker（开发阶段）、微服务、GraphQL、Redis、消息队列。MVP阶段一切从简。

---

## 2. 项目目录结构

```
overseas-supply-platform/
├── prisma/
│   ├── schema.prisma
│   ├── seed.ts
│   └── migrations/
├── public/
│   ├── uploads/              # 供应商上传的资质照片
│   │   ├── licenses/
│   │   ├── certificates/
│   │   └── products/
│   └── logos/                # 平台logo等静态资源
├── src/
│   ├── app/
│   │   ├── (marketing)/      # 公开访问区
│   │   │   ├── page.tsx              # 首页
│   │   │   ├── mall/page.tsx         # 商城首页
│   │   │   ├── mall/[id]/page.tsx    # 商品详情
│   │   │   ├── countries/page.tsx    # 国别准入数据库
│   │   │   ├── countries/[code]/page.tsx
│   │   │   ├── suppliers/page.tsx    # 供应商目录
│   │   │   ├── suppliers/[id]/page.tsx
│   │   │   ├── cases/page.tsx        # 案例
│   │   │   ├── about/page.tsx
│   │   │   └── layout.tsx
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   ├── register/page.tsx
│   │   │   └── layout.tsx
│   │   ├── buyer/            # 采购方工作台
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── rfqs/page.tsx           # 询价单
│   │   │   ├── rfqs/new/page.tsx
│   │   │   ├── rfqs/[id]/page.tsx
│   │   │   ├── orders/page.tsx
│   │   │   ├── orders/[id]/page.tsx     # 含履约追踪
│   │   │   └── layout.tsx
│   │   ├── supplier/         # 供应商工作台
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── onboarding/page.tsx     # 8步入驻流程
│   │   │   ├── profile/page.tsx
│   │   │   ├── products/page.tsx
│   │   │   ├── products/new/page.tsx
│   │   │   ├── rfqs/page.tsx           # 收到的询价
│   │   │   ├── orders/page.tsx
│   │   │   ├── score/page.tsx          # 我的信用分
│   │   │   └── layout.tsx
│   │   ├── admin/            # 平台运营后台
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── suppliers/page.tsx       # 供应商审核
│   │   │   ├── suppliers/[id]/review/page.tsx
│   │   │   ├── products/page.tsx
│   │   │   ├── orders/page.tsx
│   │   │   ├── risk-cockpit/page.tsx   # 风控驾驶舱
│   │   │   ├── countries/page.tsx       # 国别数据维护
│   │   │   └── layout.tsx
│   │   ├── ai/               # AI智能体工具箱
│   │   │   ├── page.tsx                 # Agent列表
│   │   │   ├── qa/page.tsx              # 标准问答
│   │   │   ├── cert-review/page.tsx     # 证书审查
│   │   │   ├── quote-compare/page.tsx   # 报价比价
│   │   │   ├── translate/page.tsx       # 多语种翻译
│   │   │   ├── rfq-response/page.tsx    # RFQ响应
│   │   │   ├── demand-mining/page.tsx   # 需求挖掘
│   │   │   ├── country-query/page.tsx   # 国别准入查询
│   │   │   ├── risk-alert/page.tsx      # 风险预警
│   │   │   └── supplier-match/page.tsx  # 供应商推荐
│   │   ├── api/
│   │   │   ├── auth/[...nextauth]/route.ts
│   │   │   ├── upload/route.ts
│   │   │   ├── suppliers/...
│   │   │   ├── products/...
│   │   │   ├── rfqs/...
│   │   │   ├── orders/...
│   │   │   ├── countries/...
│   │   │   └── ai/
│   │   │       ├── qa/route.ts
│   │   │       ├── cert-review/route.ts
│   │   │       ├── translate/route.ts
│   │   │       └── ... (每个agent一个route)
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── ui/                # shadcn组件
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Footer.tsx
│   │   │   ├── BuyerSidebar.tsx
│   │   │   ├── SupplierSidebar.tsx
│   │   │   └── AdminSidebar.tsx
│   │   ├── mall/
│   │   │   ├── ProductCard.tsx
│   │   │   ├── CategoryNav.tsx
│   │   │   └── ProductFilters.tsx
│   │   ├── supplier/
│   │   │   ├── OnboardingStepper.tsx
│   │   │   ├── ScoreRadar.tsx
│   │   │   └── DocumentUploader.tsx
│   │   ├── risk/
│   │   │   ├── VestRelationGraph.tsx    # 马甲关系图谱
│   │   │   ├── PriceAnomalyChart.tsx
│   │   │   └── ComplianceRadar.tsx
│   │   └── ai/
│   │       ├── ChatInterface.tsx
│   │       └── AgentCard.tsx
│   ├── lib/
│   │   ├── prisma.ts          # Prisma单例
│   │   ├── auth.ts            # NextAuth配置
│   │   ├── anthropic.ts       # Claude SDK封装
│   │   ├── upload.ts          # 文件上传工具
│   │   ├── permissions.ts     # 角色权限校验
│   │   └── utils.ts
│   ├── agents/                # AI Agent实现
│   │   ├── qa-agent.ts
│   │   ├── cert-review-agent.ts
│   │   ├── quote-compare-agent.ts
│   │   ├── translate-agent.ts
│   │   ├── rfq-response-agent.ts
│   │   ├── demand-mining-agent.ts
│   │   ├── country-query-agent.ts
│   │   ├── risk-alert-agent.ts
│   │   └── supplier-match-agent.ts
│   ├── types/
│   │   └── index.ts
│   └── middleware.ts          # 路由保护
├── .env.example
├── .env.local                 # 不要提交
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.js
├── README.md
└── DEMO_GUIDE.md              # 给Luna看的演示路径文档
```

---

## 3. 数据库 Schema（Prisma 完整定义）

直接复制到 `prisma/schema.prisma`，**不要简化、不要删字段**：

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "sqlite"
  url      = env("DATABASE_URL")
}

// =================== 用户与认证 ===================
model User {
  id              String    @id @default(cuid())
  email           String    @unique
  passwordHash    String
  name            String
  phone           String?
  role            String    // BUYER | SUPPLIER | ADMIN
  avatarUrl       String?
  createdAt       DateTime  @default(now())
  updatedAt       DateTime  @updatedAt

  // 关系
  buyerProfile    BuyerProfile?
  supplierProfile SupplierProfile?
  rfqsCreated     RFQ[]            @relation("RFQBuyer")
  ordersAsBuyer   Order[]          @relation("OrderBuyer")
  reviewsGiven    SupplierReview[] @relation("ReviewAuthor")
  sessions        Session[]
  accounts        Account[]
}

model Account {
  id                String  @id @default(cuid())
  userId            String
  type              String
  provider          String
  providerAccountId String
  user              User    @relation(fields: [userId], references: [id], onDelete: Cascade)
  @@unique([provider, providerAccountId])
}

model Session {
  id           String   @id @default(cuid())
  sessionToken String   @unique
  userId       String
  expires      DateTime
  user         User     @relation(fields: [userId], references: [id], onDelete: Cascade)
}

// =================== 采购方 ===================
model BuyerProfile {
  id              String   @id @default(cuid())
  userId          String   @unique
  companyName     String   // 如"中建三局海外事业部"
  companyType     String   // SOE | PRIVATE
  projectCountry  String?  // 主要项目所在国
  contactTitle    String?
  user            User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  createdAt       DateTime @default(now())
}

// =================== 供应商 ===================
model SupplierProfile {
  id                String   @id @default(cuid())
  userId            String   @unique
  companyName       String
  companyNameEn     String?
  unifiedSocialCode String?  // 统一社会信用代码
  legalRep          String?
  registeredCapital String?
  establishedYear   Int?
  address           String?
  website           String?

  // 业务范围
  mainCategories    String   // JSON数组: ["铝单板","幕墙","机电"]
  exportCountries   String   // JSON数组: ["TZA","ETH","KEN"]
  annualRevenue     String?

  // 入驻状态
  onboardingStep    Int      @default(1) // 1-8
  status            String   @default("DRAFT") // DRAFT | SUBMITTED | UNDER_REVIEW | APPROVED | REJECTED | SUSPENDED
  submittedAt       DateTime?
  reviewedAt        DateTime?
  reviewedBy        String?
  reviewNotes       String?

  // 信用评分(0-100)
  totalScore        Int      @default(0)
  qualityScore      Int      @default(0)  // 质量
  deliveryScore     Int      @default(0)  // 交付
  serviceScore      Int      @default(0)  // 服务
  complianceScore   Int      @default(0)  // 合规
  financialScore    Int      @default(0)  // 财务
  exportScore       Int      @default(0)  // 出口能力
  certScore         Int      @default(0)  // 认证完整度
  responseScore     Int      @default(0)  // 响应速度
  reputationScore   Int      @default(0)  // 口碑

  tier              String   @default("UNRATED") // T1 | T2 | T3 | BLACKLIST | UNRATED

  // 关系
  user              User              @relation(fields: [userId], references: [id], onDelete: Cascade)
  documents         SupplierDocument[]
  certificates      Certificate[]
  products          Product[]
  rfqsReceived      RFQResponse[]
  ordersAsSupplier  Order[]           @relation("OrderSupplier")
  reviews           SupplierReview[]
  riskAlerts        RiskAlert[]

  createdAt         DateTime @default(now())
  updatedAt         DateTime @updatedAt
}

model SupplierDocument {
  id           String    @id @default(cuid())
  supplierId   String
  docType      String    // BUSINESS_LICENSE | TAX_CERT | BANK_INFO | LEGAL_REP_ID | OTHER
  fileName     String
  fileUrl      String    // /uploads/licenses/xxx.jpg
  fileSize     Int
  mimeType     String
  status       String    @default("PENDING") // PENDING | APPROVED | REJECTED
  reviewNotes  String?
  uploadedAt   DateTime  @default(now())
  supplier     SupplierProfile @relation(fields: [supplierId], references: [id], onDelete: Cascade)
}

model Certificate {
  id           String    @id @default(cuid())
  supplierId   String
  certType     String    // ISO9001 | CE | SASO | KEBS | TBS | SONCAP | etc
  certName     String
  certNumber   String?
  issuedBy     String?
  issuedDate   DateTime?
  expiryDate   DateTime?
  fileName     String
  fileUrl      String
  status       String    @default("PENDING") // PENDING | APPROVED | REJECTED | EXPIRED
  reviewNotes  String?
  aiReviewResult String? // AI证书审查Agent结果(JSON)
  uploadedAt   DateTime  @default(now())
  supplier     SupplierProfile @relation(fields: [supplierId], references: [id], onDelete: Cascade)
}

// =================== 商品 ===================
model Category {
  id          String     @id @default(cuid())
  code        String     @unique // ALU_PANEL | CURTAIN_WALL | MEP | ...
  nameZh      String
  nameEn      String?
  parentId    String?
  parent      Category?  @relation("CategoryParent", fields: [parentId], references: [id])
  children    Category[] @relation("CategoryParent")
  products    Product[]
  sortOrder   Int        @default(0)
}

model Product {
  id              String    @id @default(cuid())
  supplierId      String
  categoryId      String
  sku             String    @unique
  nameZh          String
  nameEn          String?
  brand           String?
  model           String?
  spec            String?   // 规格描述
  unit            String    // 个/套/㎡/吨
  priceRefCNY     Float?    // 参考价格(CNY)
  priceRefUSD     Float?
  minOrderQty     Int       @default(1)
  leadTimeDays    Int?      // 交货周期

  // 出口属性
  exportToCountries String  // JSON数组
  hsCode            String?
  packingDetails    String?
  certRequirements  String? // 该商品出口需要的证书清单(JSON)

  // 描述
  description       String?
  images            String  // JSON数组 ["/uploads/products/xxx.jpg"]
  technicalSpecs    String? // JSON对象

  // 状态
  status            String  @default("DRAFT") // DRAFT | PUBLISHED | OFFLINE
  viewCount         Int     @default(0)
  inquiryCount      Int     @default(0)

  // 关系
  supplier          SupplierProfile @relation(fields: [supplierId], references: [id])
  category          Category        @relation(fields: [categoryId], references: [id])
  rfqItems          RFQItem[]

  createdAt         DateTime @default(now())
  updatedAt         DateTime @updatedAt
}

// =================== 国别准入 ===================
model Country {
  code          String  @id // ISO三位码 TZA/ETH/KEN/NGA/EGY/SAU/UAE/DZA
  nameZh        String
  nameEn        String
  region        String  // 东非/西非/北非/中东/东南亚
  flag          String? // emoji
  capital       String?
  currency      String?
  populationM   Float?
  gdpUSDB       Float?  // GDP (Billion USD)

  // 准入概况
  importTariffAvg Float?  // 平均关税
  vatRate         Float?
  hasFTA          Boolean @default(false)
  ftaDetails      String?

  // 主要建筑材料准入要求总结
  accessSummary   String? // markdown
  riskLevel       String  @default("MEDIUM") // LOW | MEDIUM | HIGH

  accessRules     CountryAccessRule[]
}

model CountryAccessRule {
  id            String   @id @default(cuid())
  countryCode   String
  categoryCode  String   // 关联Category.code
  requiredCerts String   // JSON数组 ["TBS","SONCAP"]
  tariffRate    Float?
  vatRate       Float?
  specialRules  String?  // markdown
  inspectionReq String?  // 商检要求
  laborImport   String?  // 劳务输入限制
  updatedAt     DateTime @updatedAt
  country       Country  @relation(fields: [countryCode], references: [code])
}

// =================== 询价单 RFQ ===================
model RFQ {
  id              String    @id @default(cuid())
  rfqNo           String    @unique // 系统生成 RFQ-2026-00001
  buyerId         String
  projectName     String
  projectCountry  String
  description     String?
  deadline        DateTime
  status          String    @default("DRAFT") // DRAFT | OPEN | CLOSED | AWARDED | CANCELLED

  buyer           User           @relation("RFQBuyer", fields: [buyerId], references: [id])
  items           RFQItem[]
  responses       RFQResponse[]

  createdAt       DateTime @default(now())
}

model RFQItem {
  id          String  @id @default(cuid())
  rfqId       String
  productId   String?
  description String  // 即便不绑定Product也能描述
  quantity    Float
  unit        String
  targetPrice Float?
  remarks     String?
  rfq         RFQ      @relation(fields: [rfqId], references: [id], onDelete: Cascade)
  product     Product? @relation(fields: [productId], references: [id])
}

model RFQResponse {
  id           String   @id @default(cuid())
  rfqId        String
  supplierId   String
  quotedPrice  Float
  currency     String   @default("USD")
  leadTimeDays Int?
  validUntil   DateTime?
  remarks      String?
  status       String   @default("SUBMITTED") // SUBMITTED | SHORTLISTED | AWARDED | REJECTED

  rfq          RFQ              @relation(fields: [rfqId], references: [id])
  supplier     SupplierProfile  @relation(fields: [supplierId], references: [id])
  createdAt    DateTime @default(now())
}

// =================== 订单 ===================
model Order {
  id              String    @id @default(cuid())
  orderNo         String    @unique // ORD-2026-00001
  buyerId         String
  supplierId      String
  rfqId           String?

  totalAmount     Float
  currency        String    @default("USD")
  destCountry     String

  status          String    @default("CREATED")
  // CREATED | CONFIRMED | IN_PRODUCTION | INSPECTION | PACKED | CUSTOMS_EXPORT
  // | SHIPPED | IN_TRANSIT | CUSTOMS_IMPORT | DELIVERED | INSTALLED | ACCEPTED | CLOSED

  buyer           User             @relation("OrderBuyer", fields: [buyerId], references: [id])
  supplier        SupplierProfile  @relation("OrderSupplier", fields: [supplierId], references: [id])
  items           OrderItem[]
  milestones      OrderMilestone[]
  documents       OrderDocument[]
  review          SupplierReview?

  createdAt       DateTime @default(now())
  updatedAt       DateTime @updatedAt
}

model OrderItem {
  id          String  @id @default(cuid())
  orderId     String
  productId   String?
  description String
  quantity    Float
  unit        String
  unitPrice   Float
  amount      Float
  order       Order @relation(fields: [orderId], references: [id], onDelete: Cascade)
}

model OrderMilestone {
  id          String    @id @default(cuid())
  orderId     String
  nodeCode    String    // PO_CONFIRMED | PROD_START | PROD_END | QC_PASS | PACKED | EXPORTED | SHIPPED | ETA | IMPORTED | DELIVERED | INSTALLED | ACCEPTED
  nodeName    String
  plannedDate DateTime?
  actualDate  DateTime?
  status      String    @default("PENDING") // PENDING | IN_PROGRESS | DONE | DELAYED
  remarks     String?
  sortOrder   Int
  order       Order     @relation(fields: [orderId], references: [id], onDelete: Cascade)
}

model OrderDocument {
  id         String   @id @default(cuid())
  orderId    String
  docType    String   // PO | PI | BL | CO | PACKING_LIST | INSPECTION_REPORT | INSTALL_PHOTO
  fileName   String
  fileUrl    String
  uploadedAt DateTime @default(now())
  order      Order    @relation(fields: [orderId], references: [id], onDelete: Cascade)
}

// =================== 评价 ===================
model SupplierReview {
  id          String  @id @default(cuid())
  orderId     String  @unique
  supplierId  String
  authorId    String
  qualityRating  Int  // 1-5
  deliveryRating Int
  serviceRating  Int
  comment        String?
  createdAt   DateTime @default(now())

  order       Order    @relation(fields: [orderId], references: [id])
  supplier    SupplierProfile @relation(fields: [supplierId], references: [id])
  author      User     @relation("ReviewAuthor", fields: [authorId], references: [id])
}

// =================== 风控 ===================
model RiskAlert {
  id          String   @id @default(cuid())
  supplierId  String?
  alertType   String   // VEST_RELATION | PRICE_ANOMALY | CERT_EXPIRY | COMPLIANCE | DELIVERY_DELAY
  severity    String   // LOW | MEDIUM | HIGH | CRITICAL
  title       String
  description String
  evidence    String?  // JSON
  status      String   @default("OPEN") // OPEN | INVESTIGATING | RESOLVED | DISMISSED

  supplier    SupplierProfile? @relation(fields: [supplierId], references: [id])
  createdAt   DateTime @default(now())
}

// =================== AI对话记录 ===================
model AIConversation {
  id          String   @id @default(cuid())
  userId      String?
  agentType   String   // QA | CERT_REVIEW | QUOTE_COMPARE | TRANSLATE | ...
  title       String?
  messages    String   // JSON数组
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
}
```

---

## 4. 认证与权限模型

**三角色**：
- `BUYER`（采购方）：可访问 `/buyer/*`、`/mall`、`/countries`、`/suppliers`、`/ai/*`
- `SUPPLIER`（供应商）：可访问 `/supplier/*`、`/mall`、`/ai/*`（仅部分Agent）
- `ADMIN`（平台运营）：可访问全部，包括 `/admin/*`

**实现要求**：
- `src/middleware.ts` 做路由守卫：未登录访问 `/buyer/*`、`/supplier/*`、`/admin/*` → 重定向到 `/login?callbackUrl=...`
- 注册时选角色，BUYER直接进入采购方工作台；SUPPLIER进入入驻流程
- ADMIN账号只能通过seed脚本创建，**不开放注册**
- 所有API路由用 `getServerSession()` 校验

---

## 5. API 路由清单（必须全部实现）

### 5.1 文件上传
- `POST /api/upload` 接受multipart/form-data，参数 `type=license|cert|product`，返回 `{url, fileName, size}`

### 5.2 供应商
- `POST /api/suppliers/onboarding/step/:n` 保存某一步数据
- `GET /api/suppliers/me` 获取当前供应商档案
- `POST /api/suppliers/me/submit` 提交审核
- `GET /api/suppliers/:id` 公开档案
- `GET /api/suppliers` 列表（带筛选：品类、国别、信用分段）

### 5.3 商品
- `POST /api/products` 创建
- `PATCH /api/products/:id` 更新
- `DELETE /api/products/:id` 软删
- `GET /api/products` 列表（筛选：分类、国别、价格区间、供应商）
- `GET /api/products/:id` 详情

### 5.4 询价单
- `POST /api/rfqs` 采购方发起
- `GET /api/rfqs` 列表（按角色返回不同数据：采购方看自己发的，供应商看自己可响应的）
- `GET /api/rfqs/:id`
- `POST /api/rfqs/:id/responses` 供应商响应报价
- `POST /api/rfqs/:id/award` 采购方授标 → 自动创建Order

### 5.5 订单
- `GET /api/orders`
- `GET /api/orders/:id`
- `PATCH /api/orders/:id/milestones/:milestoneId` 更新里程碑
- `POST /api/orders/:id/documents` 上传单据
- `POST /api/orders/:id/review` 评价

### 5.6 国别准入
- `GET /api/countries`
- `GET /api/countries/:code`
- `POST /api/countries/:code/rules` （ADMIN）

### 5.7 风控
- `GET /api/risk/alerts` （ADMIN）
- `POST /api/risk/scan` （ADMIN手动触发扫描）

### 5.8 AI Agents（9个）
- `POST /api/ai/qa` 标准问答
- `POST /api/ai/cert-review` 证书审查（接受文件URL或文本）
- `POST /api/ai/quote-compare` 报价比价
- `POST /api/ai/translate` 翻译
- `POST /api/ai/rfq-response` RFQ自动响应草稿生成
- `POST /api/ai/demand-mining` 需求挖掘
- `POST /api/ai/country-query` 国别准入查询（RAG）
- `POST /api/ai/risk-alert` 风险预警分析
- `POST /api/ai/supplier-match` 供应商推荐

---

## 6. 页面功能清单（每页必须实现的最小功能）

### 6.1 公开访问区

**首页 `/`**：
- 顶部Hero：核心价值主张 "央企海外EPC严选供应链平台"，3个核心数据（覆盖国别数/认证供应商数/累计撮合金额）
- 4大能力卡片：严选商城、国别准入、信用履约、AI智能体
- 央企客户Logo墙（用占位图）
- 行业洞察3-5篇（mock数据）
- CTA：注册成为采购方 / 入驻供应商

**商城 `/mall`**：
- 左侧分类导航（树形，从Category表）
- 顶部筛选：目的国（多选）、价格区间、供应商Tier
- 主区域：商品卡片网格，每卡显示主图、名称、规格、参考价、供应商名+Tier徽章
- 每张卡片可点进入详情
- 顶部搜索框

**商品详情 `/mall/[id]`**：
- 左：图片轮播
- 右：基本信息、规格表、价格、目的国准入提示（自动从CountryAccessRule拉）
- 下：供应商信息卡（信用分、Tier）
- 操作按钮：**【发起询价】**（必须可点，跳到 `/buyer/rfqs/new?productId=...`，未登录则重定向登录）
- "AI证书要求分析"按钮：调 `/api/ai/country-query` 返回该品类出口到选定国家的证书清单

**国别准入 `/countries`**：
- 卡片网格，每个国家一张
- 点入 `/countries/[code]`：国家概况、准入规则表格（按品类）、关税表、风险等级、AI智能问答框（嵌入国别准入Agent）

**供应商目录 `/suppliers`**：
- 列表，仅显示 status=APPROVED 的供应商
- 筛选：品类、出口国、Tier
- 点入档案页

### 6.2 采购方工作台

**仪表盘 `/buyer/dashboard`**：
- 4个指标卡：进行中询价数、进行中订单数、待评价订单数、本月采购额
- 近期活动时间线
- 推荐商品（mock）

**询价单 `/buyer/rfqs`**：列表 + 新建按钮
**`/buyer/rfqs/new`**：表单，可添加多个RFQ Item，可选择目的国、截止日期
**`/buyer/rfqs/[id]`**：
- 上半部分：RFQ详情
- 下半部分：收到的报价列表（供应商名、Tier、报价、交期）
- **【授标】**按钮：选中一家 → 调 `/api/rfqs/:id/award` → 自动生成订单并跳转

**订单 `/buyer/orders/[id]`**：
- 订单基本信息
- **履约时间轴**：12个节点（PO确认/生产开工/生产完成/QC/打包/出口报关/装船/在途/到港/进口清关/送达现场/安装/验收/关闭），每个节点有状态、计划日期、实际日期
- 单据中心：可看到供应商上传的BL、CO、装箱单、检验报告等
- 完成后【评价】按钮 → 跳评价页

### 6.3 供应商工作台

**入驻流程 `/supplier/onboarding`**（核心功能，必须完整跑通）：

8步Stepper，**每一步保存到数据库**，可中断继续：

1. **企业基本信息**：公司名、统一社会信用代码、法人、注册资本、成立年份、地址、官网
2. **业务范围**：主营品类（多选CheckboxGroup）、出口国别（多选）、年营业额
3. **营业执照上传**：DocumentUploader组件，调 `/api/upload?type=license`，预览图片，可重传
4. **核心资质证书**：可上传多个，每个包含证书类型下拉（ISO9001/CE/SASO/TBS/KEBS/SONCAP/其他）、证书号、签发机构、有效期、证书图片
5. **商品上架**：至少录1个商品（名称、品类、规格、参考价、主图）
6. **银行账户信息**：开户名、开户行、账号
7. **联系人信息**：业务联系人、技术联系人
8. **协议签署**：勾选《平台入驻协议》+ 提交按钮，提交后 status → SUBMITTED

**`/supplier/dashboard`**：信用分卡片（雷达图）、收到的询价数、进行中订单、待办事项
**`/supplier/products`**：商品管理
**`/supplier/rfqs`**：收到的询价 → 点击进入响应表单
**`/supplier/orders/[id]`**：可更新里程碑状态、上传单据
**`/supplier/score`**：信用评分详细展示（9维雷达图 + 历史趋势）

### 6.4 平台运营后台

**`/admin/dashboard`**：全平台指标（供应商数、商品数、本月GMV、风险预警数）

**`/admin/suppliers`**：供应商列表，按status筛选
**`/admin/suppliers/[id]/review`**：
- 左侧：供应商提交的所有信息和文件预览
- 右侧：审核操作面板
  - 每份文件可单独【通过】/【驳回】+ 备注
  - 整体决定：【通过入驻】/【驳回，发回修改】/【加入黑名单】
  - **【一键AI预审】**按钮：调用cert-review Agent批量分析所有证书 → 显示AI结论 → 运营拍最终板

**`/admin/risk-cockpit`**（必须做出"驾驶舱感"）：
- 顶部4个大数字：监测中供应商、本周预警数、待处理高危事件、马甲关系发现数
- 左侧：**马甲关系图谱**（Force-directed graph，用 react-force-graph 或 d3-force，节点是供应商，边是异常关联：相同法人/相同地址/相同电话）
- 右侧上：**价格异常监测**（折线图，某品类价格趋势 + 异常点标红）
- 右侧下：**合规雷达**（雷达图，6个维度：证书完整性、税务、海关、劳工、环保、反腐败）
- 底部：**AI智能洞察**面板（调supplier-match agent，定期生成洞察文本）

**`/admin/countries`**：国别准入数据维护（CRUD）

### 6.5 AI智能体工具箱 `/ai`

每个Agent一个独立页面，统一的 `ChatInterface` 组件 + Agent特定的输入控件。

---

## 7. AI 智能体实现规范（核心创新点）

**统一封装** `src/lib/anthropic.ts`：

```typescript
import Anthropic from "@anthropic-ai/sdk";

export const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY!,
});

export async function chat(opts: {
  system: string;
  messages: Array<{ role: "user" | "assistant"; content: string }>;
  model?: string;
  maxTokens?: number;
}) {
  const response = await anthropic.messages.create({
    model: opts.model ?? "claude-sonnet-4-5",
    max_tokens: opts.maxTokens ?? 2048,
    system: opts.system,
    messages: opts.messages,
  });
  const textBlock = response.content.find((b) => b.type === "text");
  return textBlock?.type === "text" ? textBlock.text : "";
}
```

**9个Agent的实现要点**（每个在 `src/agents/xxx.ts`）：

### Agent 1: 标准问答 (`qa-agent.ts`)
- 输入：用户问题 + 上下文（产品信息、订单信息等）
- System prompt：你是大司空海外严选平台的客服助手，熟悉建筑材料海外采购全流程...
- 输出：自然语言回答

### Agent 2: 证书审查 (`cert-review-agent.ts`)
- 输入：证书图片URL + 证书类型 + 出口目的国
- 流程：
  1. **MVP阶段OCR用Claude Vision** —— 把图片以base64传给Claude，让它直接读取证书内容（不需要外部OCR服务）
  2. 提取：证书号、签发日期、有效期、签发机构、覆盖产品范围
  3. 校验：是否过期、签发机构权威性、目的国是否承认
  4. 输出JSON：`{passed: boolean, issues: [], extracted: {...}, recommendation: ""}`

### Agent 3: 报价比价 (`quote-compare-agent.ts`)
- 输入：同一RFQ下多个供应商的报价（含价格、交期、付款条件）+ 历史成交数据
- 输出：每家的优劣分析、综合推荐、风险提示

### Agent 4: 多语种翻译 (`translate-agent.ts`)
- 输入：源文本 + 目标语言（英/法/阿/葡/俄/西）+ 领域（建筑/法律/技术）
- System prompt强调建筑行业术语准确性
- 输出：译文 + 关键术语对照

### Agent 5: RFQ自动响应 (`rfq-response-agent.ts`)
- 输入：央企RFQ内容 + 供应商档案
- 输出：一封专业的报价回函草稿（中英双语）

### Agent 6: 需求挖掘 (`demand-mining-agent.ts`)
- 输入：模糊的项目描述（如"我们在埃塞俄比亚做一个商业综合体"）
- 输出：建议采购清单（结构化品类列表 + 预估数量 + 关键证书要求）

### Agent 7: 国别准入查询 (`country-query-agent.ts`)
- 输入：商品类目 + 目的国
- 流程：先从`CountryAccessRule`表查规则 → 用Claude把规则转成专业建议
- 输出：完整准入指引（证书清单、关税、商检、特殊要求、风险提示）

### Agent 8: 风险预警分析 (`risk-alert-agent.ts`)
- 输入：供应商完整档案 + 行为日志
- 输出：风险扫描结果（5个维度）+ 建议动作
- **此Agent前置规则引擎过滤**：先用代码逻辑筛出candidates（如证书要过期、价格异常、相同法人等），再让Claude做最终判断

### Agent 9: 供应商推荐 (`supplier-match-agent.ts`)
- 输入：采购需求（品类、目的国、预算、交期）
- 流程：DB先按硬条件筛选 → 取Top 20候选 → Claude rerank + 给出推荐理由

---

## 8. 风控驾驶舱可视化（重头戏）

`/admin/risk-cockpit` 必须做出"科技驾驶舱"感，**不能是普通后台**。

**配色锁死**：
- 背景：#0A1929（深海蓝黑）
- 主色：#003366
- 高亮：#FF6B35（橙）
- 警告：#FF3333（红）
- 安全：#10B981（绿）
- 文字：#E5E7EB

**4个核心面板**：

1. **马甲关系图谱**（左上，占50%宽）
   - 用 `react-force-graph-2d` 库
   - 节点 = 供应商，节点大小 = 与其他供应商关联度
   - 边 = 异常关系（相同法人/相同地址/相同电话/相同邮箱）
   - 节点点击 → 弹窗显示关联细节
   - seed数据中预埋3-4个"马甲关系"案例

2. **价格异常监测**（右上，占50%宽）
   - 折线图，X轴时间，Y轴某品类报价
   - 多条线（多个供应商）
   - 异常点用红色三角标记，hover显示偏离度

3. **合规雷达**（左下）
   - 雷达图6维度：证书完整性、税务合规、海关合规、劳工合规、环保合规、反腐败
   - 整体平台均值 vs 选中供应商对比

4. **AI智能洞察**（右下）
   - 文字流，定时调supplier-match agent
   - 显示3-5条洞察："发现3家供应商电话相同，疑似关联企业..."

---

## 9. 种子数据（seed.ts，必须丰富）

不能是空架子，至少要：

- **3个ADMIN账号**：admin@dasikong.com / 123456
- **5个BUYER账号**：分别属于中建三局/中交建/中铁建/中国电建/中国能建（用海外事业部命名）
- **20个SUPPLIER账号**：覆盖铝单板、幕墙、机电、钢结构、给排水等品类，**其中：**
  - 12个 status=APPROVED 已上架
  - 3个 status=UNDER_REVIEW（用来演示审核流程）
  - 3个 status=DRAFT
  - 2个故意预埋"马甲关系"（相同法人/相同电话）用于风控演示
- **8个国别**：TZA坦桑/ETH埃塞/KEN肯尼亚/NGA尼日利亚/EGY埃及/DZA阿尔及利亚/SAU沙特/UAE阿联酋
- **每个国家10个品类的准入规则**
- **80+商品**
- **5个进行中的RFQ**
- **8个不同阶段的订单**（每个状态都有1个，演示用）
- **15条风险预警**

供应商logo和商品图：用 `https://picsum.photos/seed/xxx/400/300` 占位，确保每次稳定

---

## 10. 设计系统

**颜色变量** `globals.css`：
```css
:root {
  --primary: #003366;
  --primary-light: #0F4C81;
  --accent: #FF6B35;
  --accent-light: #FF8A5C;
  --bg: #F5F7FA;
  --card: #FFFFFF;
  --text: #1A1A1A;
  --text-muted: #6B7280;
  --border: #E5E7EB;
  --success: #10B981;
  --warning: #F59E0B;
  --error: #EF4444;
}
```

**字体**：默认 system-ui，标题加粗

**Tier徽章**（可复用 `<TierBadge tier="T1" />`）：
- T1：金色背景 #C9A96E，文字白
- T2：银色背景 #94A3B8
- T3：铜色背景 #B07A4A
- BLACKLIST：红底 #EF4444

**统一布局**：
- 工作台左侧 sidebar 宽 240px，深色背景 #0A1929
- 内容区背景 #F5F7FA
- 卡片用 shadcn `<Card>` 组件，圆角 12px

---

## 11. 环境配置与运行

**`.env.example`**：
```
DATABASE_URL="file:./dev.db"
NEXTAUTH_SECRET="change-me-in-production"
NEXTAUTH_URL="http://localhost:3000"
ANTHROPIC_API_KEY="sk-ant-xxx"
```

**`package.json` scripts**：
```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "db:generate": "prisma generate",
    "db:push": "prisma db push",
    "db:seed": "tsx prisma/seed.ts",
    "db:setup": "prisma db push && tsx prisma/seed.ts",
    "db:reset": "prisma db push --force-reset && tsx prisma/seed.ts",
    "db:studio": "prisma studio"
  }
}
```

**用户运行流程**（写进README）：
```bash
git clone ... && cd overseas-supply-platform
cp .env.example .env.local
# 编辑 .env.local 填入 ANTHROPIC_API_KEY
npm install
npm run db:setup
npm run dev
# 打开 http://localhost:3000
```

---

## 12. 验收清单（开发完成后逐项自检）

**基础**：
- [ ] `npm run db:setup && npm run dev` 一次成功
- [ ] 首页所有链接都能跳转，没有404
- [ ] 三个角色都能登录，路由权限正确

**采购方流程**：
- [ ] 注册BUYER → 登录 → 浏览商城 → 选3个商品 → 发起RFQ → 等供应商响应 → 授标 → 看到订单生成
- [ ] 订单详情页12个履约里程碑都显示

**供应商流程**：
- [ ] 注册SUPPLIER → 进入8步入驻 → 上传真实图片（任意jpg/png）→ 提交审核
- [ ] 入驻审核后 → 上架商品 → 收到RFQ → 响应报价
- [ ] 中标后看到订单 → 更新里程碑状态 → 上传单据

**Admin流程**：
- [ ] admin登录 → 进入供应商审核 → 一键AI预审 → 看到Claude返回的证书审查结论
- [ ] 进入风控驾驶舱 → 4个面板都有数据 → 马甲关系图谱可交互
- [ ] 至少能看到2个预埋的"马甲关系"

**AI Agents**：
- [ ] 9个Agent页面都能打开
- [ ] 标准问答/翻译/比价/国别查询 → 真实调通Anthropic API
- [ ] 证书审查 → 上传图片 → Claude Vision返回结构化结果
- [ ] 风险预警 → 触发扫描 → 生成RiskAlert记录

**数据完整性**：
- [ ] 所有上传的文件都能在 `public/uploads/` 看到
- [ ] 所有状态流转（DRAFT→SUBMITTED→APPROVED等）真实更新DB
- [ ] 刷新页面后数据不丢失

---

## 13. 推荐的开发顺序（Claude Code内部分阶段执行）

**Phase 1: 骨架（先跑通）**——预计 25 分钟
1. 初始化Next.js + 配置Tailwind + shadcn
2. 完整Prisma schema → 生成client
3. 写seed.ts（先少量数据）
4. NextAuth配置 + 注册/登录/中间件
5. 三套Layout（公开/buyer/supplier/admin）

**Phase 2: 核心业务流（看到真实数据流转）**——预计 35 分钟
6. 商城 + 商品详情
7. 供应商8步入驻 + 文件上传API
8. Admin供应商审核
9. RFQ创建 + 响应 + 授标
10. 订单 + 履约里程碑
11. 国别准入数据展示

**Phase 3: AI + 风控驾驶舱（差异化亮点）**——预计 25 分钟
12. Anthropic SDK封装
13. 9个Agent实现（先实现4个核心：QA、cert-review、translate、country-query）
14. 风控驾驶舱4面板可视化
15. 完整seed数据填充
16. 写DEMO_GUIDE.md

**Phase 4: 收尾**——预计 5 分钟
17. 修复明显bug
18. 写README
19. 自检验收清单

---

## 14. 禁止事项（避免常见踩坑）

❌ **不要**用 mock 数据替代真实DB——所有列表都从数据库查
❌ **不要**省略文件上传——必须真实写入 `public/uploads/`
❌ **不要**让按钮"看起来能点"——每个按钮要有真实API调用
❌ **不要**搞复杂的Server Actions+Server Components混合——统一用 API Routes，前端用 fetch/SWR
❌ **不要**引入 next-intl 之外的i18n库
❌ **不要**用 PostgreSQL/MySQL/MongoDB——锁死SQLite
❌ **不要**做用户头像生成、邮件发送、短信验证等次要功能
❌ **不要**写测试代码（MVP阶段不需要单测）
❌ **不要**做PWA、SSG、ISR等优化——一律用动态渲染
❌ **不要**用"京东"、"建发"等任何真实品牌做UI上的明示
❌ **不要**在风控驾驶舱里乱用第三方图谱可视化库——`react-force-graph-2d` 是首选；如果安装失败就用 d3 手写一个简化版

---

## 15. 最后的话

**关键成功标准**：开发完后，把链接发给一个没看过这份文档的人，让TA分别用 buyer / supplier / admin 三个账号登录，**TA能在30分钟内自己跑通"入驻→上架→询价→订单→评价"全流程**，且**触达9个AI Agent中至少4个**。

如果遇到不确定的设计取舍，遵循优先级：
> **可演示性 > 数据真实性 > 代码优雅性 > 性能 > 类型完美**

开始吧。先输出 `package.json` 和 `prisma/schema.prisma`，然后逐文件构建。
