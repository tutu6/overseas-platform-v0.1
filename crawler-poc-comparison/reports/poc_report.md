# 柬埔寨双源对比调研报告

> 跑测日期:2026-05-26
> 环境:本地,Tavily Search + qwen-plus 裸调 / httpx + BeautifulSoup 爬虫(无浏览器、无反爬对抗)
> 测试公司:Kampot Cement、KHALIBRE CO.,LTD、Acleda Bank

## 1. 调研背景与范围

对比两条数据获取路径在柬埔寨场景下的实际表现:
- **路径 A**:Tavily + LLM(公开网络搜索 + qwen-plus 结构化抽取)
- **路径 B**:自建爬虫(MOC 官网 / 媒体站直抓)

覆盖维度:工商基础(7 字段)+ 司法舆情。两路调用层独立、互不兜底。

## 2. 跑测结果汇总

| 测试公司 | 维度 | 路径 A(Tavily+LLM) | 路径 B(爬虫) | A 耗时 |
|---|---|---|---|---|
| Kampot Cement | 工商基础 | ok · 2/7 字段 | access_restricted(MOC 403) | 4.5s |
| Kampot Cement | 司法舆情 | ok · 2 篇 / 2 负面 | access_restricted(媒体 403) | 9.6s |
| KHALIBRE CO.,LTD | 工商基础 | ok · 1/7 字段 | access_restricted | 2.8s |
| KHALIBRE CO.,LTD | 司法舆情 | no_match · 0 篇 | access_restricted | 2.3s |
| Acleda Bank | 工商基础 | ok · 3/7 字段(含注册号 00003077) | access_restricted | 3.7s |
| Acleda Bank | 司法舆情 | no_match · 0 篇 | access_restricted | 1.5s |

## 3. 工商基础维度

### 3.1 路径 A:Tavily + LLM 观察
- 调用结果:三家均 ok。
- 字段填充:1~3 / 7;稳定拿到 `company_full_name`、`country_region`,大企业(Acleda)能拿 `registration_no`。
- 数据来源:OpenDevelopment Mekong、OpenCorporates 镜像等公开聚合站。
- 运行特征:单次 2.8~4.5s,`search_depth=basic` 摘要短是填充率偏低主因。

### 3.2 路径 B:自建爬虫(MOC 官网)观察
- 调用结果:三家均 access_restricted。
- 字段填充:0 / 7(未取得 HTML)。
- 站点访问特征:`businessregistration.moc.gov.kh` 直接 HTTP 403,首请求即拒(WAF / 需登录)。
- 运行特征:快速失败(<1s),无重试无绕过。

### 3.3 两条路径对比
- 字段覆盖:路径 A 有部分字段,路径 B 为 0。
- 适用场景:工商基础在当前调用方式下,只有路径 A 能产出数据;路径 B 需要更重的访问手段(浏览器渲染 / 授权)才可能可用,本期未引入。

## 4. 司法舆情维度

### 4.1 路径 A:Tavily + LLM 观察
- Kampot Cement 召回 2 篇且判负面;KHALIBRE / Acleda 召回 0(no_match)。
- 召回量与公司公开报道量强相关。

### 4.2 路径 B:自建爬虫(媒体站)观察
- phnompenhpost.com + khmertimeskh.com 均 access_restricted(Cloudflare JS challenge,HTTP 403)。
- 三家公司、两站均未取得任何内容。

### 4.3 召回内容对比(以 Kampot Cement 为例)
| 项 | 数量 |
|---|---|
| Tavily + LLM 召回 | 2 |
| 爬虫召回 | 0 |
| 两边同时召回 | 0 |
| 仅 Tavily + LLM 召回 | 2 |
| 仅爬虫召回 | 0 |

对比解读:重合度 0/(2+0-0) = 0% → 两条路径内容无重合,但**原因是路径 B 完全无召回**(被反爬挡),并非内容互补。当前无法做有意义的重合度对照,因为爬虫侧无数据。

### 4.4 两条路径对比
- 路径 A 是司法舆情唯一能产出数据的路径;路径 B 被 Cloudflare 完全挡死。

## 5. 调研结论与后续建议

### 5.1 数据观察
- 三个目标站(MOC + 两媒体)共 6 次爬虫调用全部 access_restricted(403)。
- Tavily+LLM 两维度均能调通,工商填充 1~3/7,司法召回与知名度相关。

### 5.2 后续路径选项

**选项 1:以 Tavily + LLM 为主路径**
- 适用条件:目标站点普遍有反爬,公开网络有一定覆盖。
- 待解决:工商填充率偏低(1~3/7),需 `advanced` depth / 补结构化源。

**选项 2:以爬虫为主路径**
- 适用条件:目标站点无反爬、有稳定结构化页面。
- 待解决:本场景三站全 403,需浏览器渲染 / 授权,成本高、合规存疑 —— 本期判定不适用。

**选项 3:两条路径组合(Tavily 主 + 爬虫补特定可爬源)**
- 组合方式:Tavily 兜底全量,对个别无反爬的权威源补爬虫。
- 待解决:柬埔寨暂未发现可稳定爬取的权威结构化源。

**选项 4:其他路径**
- 商业工商数据 API(OpenCorporates 付费)、官方 RSS、用户上传 + OCR 补全。

### 5.3 推荐

基于本次调研数据,推荐 **选项 1(Tavily + LLM 为主路径)**,并以选项 4 的"用户上传补全"补工商关键字段。

理由:
- 爬虫路径在柬埔寨三站全部 403,当前调用方式不可用。
- Tavily + LLM 是唯一稳定产出数据的路径,与主项目 Δ7 主线一致。

### 5.4 待进一步验证
- `search_depth=advanced` 能否显著提升工商填充率。
- 司法召回随 `max_results` / 多 query 的提升空间。
- 其他国别(非柬埔寨)目标站是否也普遍反爬。

## 附录

### A. 重合 URL 完整清单
当前爬虫侧 0 召回,无重合 URL。Tavily 侧召回 URL 见前端"召回内容对比"点击展开。

### B. 各路径调用特征
- Tavily+LLM:每公司每维度 1 次搜索 + 1 次 LLM 抽取,24h 文件缓存。
- 爬虫:每次实时,均 403 快速失败。

### C. 测试公司原始返回
见前端页面底部"完整调用元信息(ComparisonResponse JSON)"展开。

---

*v1.1 调研报告。核心结论:柬埔寨场景爬虫路径三站全 403 不可用,Tavily+LLM 是唯一可行路径,印证主项目 Δ7 主线。*
