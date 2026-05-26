# 柬埔寨双源对照 PoC 报告

> 跑测日期:2026-05-26
> 环境:本地,Tavily Search + qwen-plus 裸调 / httpx + BeautifulSoup 爬虫(无浏览器、无反爬对抗)
> 测试公司:Kampot Cement、KHALIBRE CO.,LTD、Acleda Bank

## 0. 一句话结论

**Tavily + LLM 可行,自建爬虫完全不可行。** 三家公司、两维度、共 6 次爬虫调用(MOC 官网 + 两家媒体)**全部 HTTP 403** 被反爬挡死;Tavily + LLM 侧能稳定拿到部分工商字段与司法文章。**强烈建议柬埔寨工商/司法维度走 Tavily + LLM 路径(即 Δ7 主线),不要自建爬虫。**

## 1. 跑测结果汇总

| 公司 | 维度 | Tavily+LLM | 爬虫 | Tavily 耗时 |
|---|---|---|---|---|
| Kampot Cement | 工商 | success · 2/7 字段 | ❌ blocked 403 | 4493ms |
| Kampot Cement | 司法 | success · 2 篇 / 2 负面 | ❌ blocked 403 | 9595ms |
| KHALIBRE CO.,LTD | 工商 | success · 1/7 字段 | ❌ blocked 403 | 2752ms |
| KHALIBRE CO.,LTD | 司法 | not_found · 0 篇 | ❌ blocked 403 | 2286ms |
| Acleda Bank | 工商 | success · 3/7 字段(含注册号 00003077) | ❌ blocked 403 | 3747ms |
| Acleda Bank | 司法 | not_found · 0 篇 | ❌ blocked 403 | 1458ms |

## 2. 工商基础维度观察

### 2.1 Tavily + LLM 侧
- **召回**:三家都能 success,但字段填充率低(1~3 / 7)。
- **能稳定拿到**:`company_full_name`、`country_region`;大企业(Acleda)能拿到 `registration_no`。
- **拿不到**:`established_date` / `legal_representative` / `business_scope` / `registered_capital` —— 公开摘要里基本没有,`search_depth=basic` 摘要太短是主因。
- **幻觉**:未观察到明显编造(prompt 要求无证据填 null,LLM 守住了)。

### 2.2 爬虫(MOC 官网)侧
- **三家全部 HTTP 403**:`businessregistration.moc.gov.kh` 直接拒绝非浏览器请求(反爬 / 需登录 / WAF)。
- 连 HTML 都拿不到,DOM 解析无从谈起。

### 2.3 对比结论
- **工商基础:Tavily+LLM 完胜**(有数据 vs 0)。但填充率偏低(1~3/7),离"完整工商档案"有差距,需 `advanced` depth / 补充权威数据源(OpenCorporates 等)提升。

## 3. 司法舆情维度观察

### 3.1 Tavily + LLM 侧
- Kampot Cement 召回 2 篇且判为负面;KHALIBRE / Acleda 召回 0(司法 query 命中少,或确无公开负面)。
- 召回不稳定,与公司知名度 + 公开报道量强相关。

### 3.2 爬虫(媒体站)侧
- `phnompenhpost.com` + `khmertimeskh.com` **全部 403**(Cloudflare 挑战页)。
- 与单独跑的 10 号 PoC 结论一致:两站均 Cloudflare,简单爬虫拿不到任何内容。

### 3.3 对比结论
- **司法舆情:Tavily+LLM 是唯一能出数据的路径**;爬虫被 Cloudflare 完全挡死。

## 4. 反爬观察(爬虫侧)

| 站点 | 结果 | 性质 |
|---|---|---|
| businessregistration.moc.gov.kh | HTTP 403 | 官网反爬 / WAF,首请求即拒 |
| phnompenhpost.com | HTTP 403 | Cloudflare JS challenge |
| khmertimeskh.com | HTTP 403 | Cloudflare JS challenge |

三个目标站**无一例外**首次请求即 403,改 UA 无效,需浏览器执行 JS / CF-bypass —— 超出"简单爬虫"范畴。

## 5. 成本对比

- Tavily:每公司每维度 1 次搜索(工商+司法 = 2 次/公司),叠加 24h 缓存,配额可控。
- qwen-plus:每维度 1 次抽取,Token 消耗小(摘要级输入)。
- 爬虫:无外部成本,但**产出为 0**,成本再低也无意义。

## 6. 维护难度直观判断

- Tavily+LLM 侧:裸调约 150 行,无 DOM 依赖,站点改版不影响(Tavily 替你扛)。
- 爬虫侧:即使绕过反爬,还要持续适配各站 DOM + CF 规则升级,维护成本高且不可控 —— 而当前连第一步(拿到 HTML)都过不了。

## 7. 结论与建议

**A. 柬埔寨工商基础**:走 Tavily+LLM。但填充率偏低(1~3/7),建议:① `search_depth=advanced` ② 接 OpenCorporates 等结构化源补全 ③ 关键字段(成立日期/法人/资本)接受"部分缺失 + 用户上传补全"。

**B. 柬埔寨司法舆情**:走 Tavily+LLM(媒体站爬虫被 Cloudflare 完全挡死,无替代)。召回不稳定,可加大 `max_results` / 多 query 提升。

**C. 整体路径**:**自建爬虫在柬埔寨(MOC 官网 + 主流媒体)不可行,反爬是硬墙**。本 PoC 用很小成本反向证明了 Δ7 主线(Tavily+LLM)的正确性。后续不建议为柬埔寨投入自建爬虫;其他国别若数据源无反爬,可另行评估。

---

*PoC v1.0 跑测以本报告为准。核心结论:Tavily+LLM 可行且印证 Δ7 主线,自建爬虫被三站 403 全面挡死、不可行。*
