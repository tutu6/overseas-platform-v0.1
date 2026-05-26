# 柬埔寨双源对照 PoC

针对同一家柬埔寨公司、同一维度,**并排展示 Tavily+LLM 路径与自建爬虫路径的真实结果**,
为技术选型提供客观数据。覆盖两维度:工商基础、司法舆情。

## 与主项目的隔离声明

本 PoC 位于主项目 git 仓库下 `crawler-poc-comparison/` 独立目录,但与主项目**严格物理隔离**:

- 不 `import` 任何 `backend.*` / `frontend/*` 模块
- 不修改主项目任何文件
- 自带独立 `requirements.txt` / `.env` / `.gitignore`
- 端口 8004(避开主项目 8000/8003)

## 启动

```bash
cd crawler-poc-comparison
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # 填 TAVILY_API_KEY 和 QWEN_API_KEY
uvicorn main:app --reload --port 8004
```

访问:http://localhost:8004/

## API

```bash
curl -X POST http://localhost:8004/api/poc/compare \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Kampot Cement","force_refresh":false}'
```

## 测试公司

| 公司名 | MOC 注册号(参考) | 测试要点 |
|---|---|---|
| `KHALIBRE CO.,LTD` | 00002730 | OpenCorporates 有真实数据,Tavily 应能召回 |
| `T.S SPORT (CAMBODIA) CO., LTD.` | 00052477 | 中型企业 |
| `Kampot Cement` | (大企业) | 媒体覆盖高,司法舆情演示效果好 |
| `Acleda Bank` | (大银行) | 媒体覆盖极高 |

## 已知限制

- Tavily 侧 24h 文件缓存(`.cache/`);爬虫侧每次实时
- 不做反幻觉(诚实展示 LLM 原始抽取效果)
- 不做反爬对抗、不引入 Playwright;爬虫被反爬(403/登录/JS)即记录,不绕过
- 仅英文媒体,不处理柬语
- 跑测结果与判断见 `reports/poc_report.md`
