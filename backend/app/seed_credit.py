"""信用评估模块种子(信用评估技术方案 §七 + 工单 Step 9-10)。

种入内容:
1. 评分模型骨架 — 4 维度 + 12 子项 + 51 规则(对齐 PRD v0.3 §4.3)
2. 4 家 demo 企业 mock 数据(覆盖 A/B/C/D 各档)
3. 调用 ScoringEngine 给每家算一次分(写 snapshot + 12 detail + audit_log)

幂等:每步用 code / 复合键判断是否已存在再插入。
不调 LLM 生成 ai_summary(节约启动时间;首访详情页时再生成)。
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import _utcnow
from app.db.models import (
    CertStatus,
    CertType,
    CreditCompany,
    CreditCompanyBasicData,
    CreditCompanyCertification,
    CreditCompanyFinanceData,
    CreditCompanyLegalData,
    DataSourceTag,
    DimensionCode,
    NegativeNewsLevel,
    RevenueTrend,
    CashFlowStatus,
    ScoreDimension,
    ScoreRule,
    ScoreSubitem,
    TriggerType,
)
from app.services.credit.data_source.mock_data_source import MockDataSource
from app.services.credit.evaluators import EVALUATORS
from app.services.credit.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


# =============================================================================
# 评分模型骨架配置
# =============================================================================

# (dim_code, name, max_score, display_order)
_DIMENSIONS: list[tuple[str, str, int, int]] = [
    (DimensionCode.BASIC_INFO, "基础工商信息", 15, 1),
    (DimensionCode.CERTIFICATION, "资质认证储备", 25, 2),
    (DimensionCode.FINANCE, "财务健康状况", 30, 3),
    (DimensionCode.LEGAL, "司法与舆情风险", 30, 4),
]

# (subitem_code, dim_code, name, max_score, default_score, display_order, hint)
_SUBITEMS: list[tuple[str, str, str, int, int, int, str]] = [
    # 维度1
    ("BASIC_REG_INFO", DimensionCode.BASIC_INFO, "注册信息完整性", 5, 0, 1,
     "国家企业信用信息公示系统 / 海外工商数据库"),
    ("BASIC_STATUS", DimensionCode.BASIC_INFO, "存续状态", 5, 0, 2,
     "同上"),
    ("BASIC_SHAREHOLDERS", DimensionCode.BASIC_INFO, "股东与股权", 5, 0, 3,
     "同上"),
    # 维度2
    ("CERT_MANDATORY", DimensionCode.CERTIFICATION, "目标国强制认证", 10, 0, 1,
     "认证机构公开数据库(目标国 SASO/SNI/CE 等)"),
    ("CERT_SYSTEM_GENERAL", DimensionCode.CERTIFICATION, "通用体系认证", 8, 0, 2,
     "ISO9001 / ISO14001 等"),
    ("CERT_INDUSTRY_SPECIFIC", DimensionCode.CERTIFICATION, "行业专项认证", 7, 0, 3,
     "CE / UL / OHSAS 等"),
    # 维度3(整维度 missing 时 default=4,但 default_score 字段是 fallback,
    # 我们用 priority=0 的 override rule 处理 missing 情况)
    ("FINANCE_REVENUE", DimensionCode.FINANCE, "营收与盈利", 10, 0, 1, "企业年报 / 财报公开渠道"),
    ("FINANCE_DEBT", DimensionCode.FINANCE, "资产负债", 10, 0, 2, "同上"),
    ("FINANCE_CASHFLOW", DimensionCode.FINANCE, "现金流", 10, 0, 3, "同上"),
    # 维度4
    ("LEGAL_LITIGATION", DimensionCode.LEGAL, "法律诉讼", 10, 0, 1, "裁判文书网 / 海外法院公开系统"),
    ("LEGAL_DEFAULTER", DimensionCode.LEGAL, "失信被执行", 10, 0, 2, "同上"),
    ("LEGAL_NEWS", DimensionCode.LEGAL, "负面舆情", 10, 0, 3, "媒体舆情监测"),
]

# (subitem_code, rule_code, description, score, evaluator_key, priority)
# priority 0 = 维度级 override(优先级最高);10/20/30... = 档位由高到低
_RULES: list[tuple[str, str, str, int, str, int]] = [
    # =========================================================================
    # 维度1
    # =========================================================================
    ("BASIC_REG_INFO", "R_BASIC_REG_FULL", "注册时间/资本金/经营范围齐全", 5, "basic_reg_info_full", 10),
    ("BASIC_REG_INFO", "R_BASIC_REG_MISS_ONE", "缺 1 项", 3, "basic_reg_info_miss_one", 20),
    ("BASIC_REG_INFO", "R_BASIC_REG_MISS_TWO", "缺 ≥2 项", 0, "basic_reg_info_miss_two_or_more", 30),

    ("BASIC_STATUS", "R_BASIC_STATUS_NORMAL", "正常经营", 5, "basic_status_normal", 10),
    ("BASIC_STATUS", "R_BASIC_STATUS_ABNORMAL", "存续但有异常", 2, "basic_status_abnormal", 20),
    ("BASIC_STATUS", "R_BASIC_STATUS_CANCELLED", "已注销/吊销/未知", 0, "basic_status_cancelled", 30),

    ("BASIC_SHAREHOLDERS", "R_BASIC_SH_CLEAR", "股权结构清晰可查", 5, "basic_shareholders_clear", 10),
    ("BASIC_SHAREHOLDERS", "R_BASIC_SH_PARTIAL", "部分可查", 3, "basic_shareholders_partial", 20),
    ("BASIC_SHAREHOLDERS", "R_BASIC_SH_MISSING", "无法查证", 0, "basic_shareholders_missing", 30),

    # =========================================================================
    # 维度2(每子项加 priority=0 override:关键证书伪造/过期 → 该子项 0)
    # =========================================================================
    ("CERT_MANDATORY", "R_CERT_CRITICAL_MANDATORY", "关键证书伪造/过期 → 维度清零", 0, "cert_critical_problem", 0),
    ("CERT_MANDATORY", "R_CERT_MANDATORY_VALID", "目标国强制认证且有效期内", 10, "cert_mandatory_valid", 10),
    ("CERT_MANDATORY", "R_CERT_MANDATORY_EXPIRED", "目标国强制认证已过期", 3, "cert_mandatory_expired", 20),
    ("CERT_MANDATORY", "R_CERT_MANDATORY_MISSING", "无目标国强制认证", 0, "cert_mandatory_missing", 30),

    ("CERT_SYSTEM_GENERAL", "R_CERT_CRITICAL_SYSTEM", "关键证书伪造/过期 → 维度清零", 0, "cert_critical_problem", 0),
    ("CERT_SYSTEM_GENERAL", "R_CERT_SYSTEM_2_OR_MORE", "通用体系认证 ≥2 项", 8, "cert_system_count_2_or_more", 10),
    ("CERT_SYSTEM_GENERAL", "R_CERT_SYSTEM_1", "通用体系认证 1 项", 4, "cert_system_count_1", 20),
    ("CERT_SYSTEM_GENERAL", "R_CERT_SYSTEM_0", "无通用体系认证", 0, "cert_system_count_0", 30),

    ("CERT_INDUSTRY_SPECIFIC", "R_CERT_CRITICAL_INDUSTRY", "关键证书伪造/过期 → 维度清零", 0, "cert_critical_problem", 0),
    ("CERT_INDUSTRY_SPECIFIC", "R_CERT_INDUSTRY_3_OR_MORE", "行业专项认证 ≥3 项(cap 7)", 7, "cert_industry_count_3_or_more", 10),
    ("CERT_INDUSTRY_SPECIFIC", "R_CERT_INDUSTRY_2", "行业专项认证 2 项", 6, "cert_industry_count_2", 20),
    ("CERT_INDUSTRY_SPECIFIC", "R_CERT_INDUSTRY_1", "行业专项认证 1 项", 3, "cert_industry_count_1", 30),
    ("CERT_INDUSTRY_SPECIFIC", "R_CERT_INDUSTRY_0", "无行业专项认证", 0, "cert_industry_count_0", 40),

    # =========================================================================
    # 维度3(每子项加 priority=0 override:整维度 missing → 4 分)
    # =========================================================================
    ("FINANCE_REVENUE", "R_FIN_REV_MISSING", "财务数据整维度缺失", 4, "finance_dimension_missing", 0),
    ("FINANCE_REVENUE", "R_FIN_REV_GROWING", "近 2 年营收稳定或增长", 10, "finance_revenue_growing", 10),
    ("FINANCE_REVENUE", "R_FIN_REV_FLUCTUATING", "波动但盈利", 7, "finance_revenue_fluctuating", 20),
    ("FINANCE_REVENUE", "R_FIN_REV_LOSS", "亏损", 3, "finance_revenue_loss", 30),
    ("FINANCE_REVENUE", "R_FIN_REV_UNKNOWN", "数据不可查", 5, "finance_revenue_unknown", 40),

    ("FINANCE_DEBT", "R_FIN_DEBT_MISSING", "财务数据整维度缺失", 4, "finance_dimension_missing", 0),
    ("FINANCE_DEBT", "R_FIN_DEBT_LOW", "资产负债率 < 70%", 10, "finance_debt_low", 10),
    ("FINANCE_DEBT", "R_FIN_DEBT_MEDIUM", "资产负债率 70-85%", 6, "finance_debt_medium", 20),
    ("FINANCE_DEBT", "R_FIN_DEBT_HIGH", "资产负债率 > 85%", 2, "finance_debt_high", 30),
    ("FINANCE_DEBT", "R_FIN_DEBT_UNKNOWN", "数据不可查", 5, "finance_debt_unknown", 40),

    ("FINANCE_CASHFLOW", "R_FIN_CASH_MISSING", "财务数据整维度缺失", 4, "finance_dimension_missing", 0),
    ("FINANCE_CASHFLOW", "R_FIN_CASH_POSITIVE", "经营性现金流为正", 10, "finance_cashflow_positive", 10),
    ("FINANCE_CASHFLOW", "R_FIN_CASH_NEG_FUND", "为负但融资正常", 6, "finance_cashflow_negative_with_funding", 20),
    ("FINANCE_CASHFLOW", "R_FIN_CASH_PERSIST_NEG", "持续为负", 2, "finance_cashflow_persistent_negative", 30),
    ("FINANCE_CASHFLOW", "R_FIN_CASH_UNKNOWN", "数据不可查", 5, "finance_cashflow_unknown", 40),

    # =========================================================================
    # 维度4(每子项加 priority=0 一票否决:失信未结案 → 维度全 0)
    # =========================================================================
    ("LEGAL_LITIGATION", "R_LEG_VETO_LITIGATION", "失信被执行未结案 → 一票否决", 0, "legal_dimension_veto", 0),
    ("LEGAL_LITIGATION", "R_LEG_LITI_ZERO", "无诉讼记录", 10, "legal_litigation_zero", 10),
    ("LEGAL_LITIGATION", "R_LEG_LITI_LOW", "诉讼 < 5 起", 7, "legal_litigation_low", 20),
    ("LEGAL_LITIGATION", "R_LEG_LITI_MEDIUM", "诉讼 5-20 起", 4, "legal_litigation_medium", 30),
    ("LEGAL_LITIGATION", "R_LEG_LITI_HIGH", "诉讼 > 20 起", 1, "legal_litigation_high", 40),

    ("LEGAL_DEFAULTER", "R_LEG_VETO_DEFAULTER", "失信被执行未结案 → 一票否决", 0, "legal_dimension_veto", 0),
    ("LEGAL_DEFAULTER", "R_LEG_DEF_NONE", "无失信记录", 10, "legal_defaulter_none", 10),
    ("LEGAL_DEFAULTER", "R_LEG_DEF_RESOLVED", "有失信记录但已结案", 4, "legal_defaulter_resolved_only", 20),
    ("LEGAL_DEFAULTER", "R_LEG_DEF_UNRESOLVED", "有未结案失信记录", 0, "legal_defaulter_unresolved", 30),

    ("LEGAL_NEWS", "R_LEG_VETO_NEWS", "失信被执行未结案 → 一票否决", 0, "legal_dimension_veto", 0),
    ("LEGAL_NEWS", "R_LEG_NEWS_NONE", "无负面报道", 10, "legal_news_none", 10),
    ("LEGAL_NEWS", "R_LEG_NEWS_OCCASIONAL", "偶发已澄清", 6, "legal_news_occasional", 20),
    ("LEGAL_NEWS", "R_LEG_NEWS_PERSISTENT", "持续负面", 2, "legal_news_persistent", 30),
    ("LEGAL_NEWS", "R_LEG_NEWS_MAJOR", "重大丑闻", 0, "legal_news_major_scandal", 40),
]


# =============================================================================
# 4 家 demo 企业 mock 数据
# =============================================================================

_TODAY = date.today()


def _date(s: str) -> date:
    return date.fromisoformat(s)


_DEMO_COMPANIES: list[dict[str, Any]] = [
    # ---------- A 档:沙特 Al-Rashid Industrial Co. ----------
    {
        "name": "Al-Rashid Industrial Co.",
        "legal_name_en": "Al-Rashid Industrial Company",
        "country_code": "SA",
        "registration_no": "1010-XXXXX-A1",
        "expected_grade": "A",
        "basic": {
            "established_date": _date("2008-04-15"),
            "registered_capital": "50,000,000 SAR",
            "business_scope": "海外工程总承包、建材进出口、机电安装",
            "legal_representative": "Mohammed Al-Rashid",
            "shareholders": "Al-Rashid Group 60%, KSA Investment Co. 40%(完整披露)",
            "status_text": "normal",
            "address": "King Fahd Road, Riyadh, KSA",
            "website": "https://al-rashid.example.com",
        },
        "finance": {
            "revenue_trend": RevenueTrend.GROWING,
            "debt_ratio": Decimal("58.50"),
            "cash_flow_status": CashFlowStatus.POSITIVE,
        },
        "legal": {
            "litigation_count": 0,
            "defaulter_unresolved_count": 0,
            "defaulter_resolved_count": 0,
            "negative_news_level": NegativeNewsLevel.NONE,
        },
        "certs": [
            {"cert_type": CertType.MANDATORY_COUNTRY, "cert_name": "SASO Certificate",
             "target_country_code": "SA", "issuer": "Saudi Standards (SASO)",
             "issued_at": _date("2024-01-10"), "expires_at": _date("2027-01-09"),
             "status": CertStatus.VALID},
            {"cert_type": CertType.SYSTEM_GENERAL, "cert_name": "ISO 9001:2015",
             "issuer": "TÜV NORD", "issued_at": _date("2024-06-01"),
             "expires_at": _date("2027-05-31"), "status": CertStatus.VALID},
            {"cert_type": CertType.SYSTEM_GENERAL, "cert_name": "ISO 14001:2015",
             "issuer": "TÜV NORD", "issued_at": _date("2024-06-01"),
             "expires_at": _date("2027-05-31"), "status": CertStatus.VALID},
            {"cert_type": CertType.INDUSTRY_SPECIFIC, "cert_name": "CE Marking",
             "issuer": "Notified Body 0123", "issued_at": _date("2024-09-12"),
             "expires_at": _date("2029-09-11"), "status": CertStatus.VALID},
            {"cert_type": CertType.INDUSTRY_SPECIFIC, "cert_name": "UL Listed",
             "issuer": "UL LLC", "issued_at": _date("2024-02-20"),
             "expires_at": _date("2029-02-19"), "status": CertStatus.VALID},
            {"cert_type": CertType.INDUSTRY_SPECIFIC, "cert_name": "OHSAS 18001",
             "issuer": "BSI", "issued_at": _date("2024-04-01"),
             "expires_at": _date("2027-03-31"), "status": CertStatus.VALID},
        ],
    },
    # ---------- B 档:印尼 PT Cahaya Sentosa ----------
    {
        "name": "PT Cahaya Sentosa",
        "legal_name_en": "PT Cahaya Sentosa Tbk",
        "country_code": "ID",
        "registration_no": "AHU-B2",
        "expected_grade": "B",
        "basic": {
            "established_date": _date("2012-08-20"),
            "registered_capital": "15,000,000,000 IDR",
            "business_scope": "建材贸易、工程咨询",
            "legal_representative": "Budi Santoso",
            "shareholders": "Sentosa Holding(部分披露,具体股权比例未公开)",
            "status_text": "normal",
            "address": "Jakarta, Indonesia",
            "website": "https://cahaya-sentosa.example.id",
        },
        "finance": {
            "revenue_trend": RevenueTrend.FLUCTUATING,
            "debt_ratio": Decimal("75.20"),
            "cash_flow_status": CashFlowStatus.POSITIVE,
        },
        "legal": {
            "litigation_count": 2,
            "defaulter_unresolved_count": 0,
            "defaulter_resolved_count": 0,
            "negative_news_level": NegativeNewsLevel.OCCASIONAL,
        },
        "certs": [
            {"cert_type": CertType.MANDATORY_COUNTRY, "cert_name": "SNI Certificate",
             "target_country_code": "ID", "issuer": "BSN", "issued_at": _date("2023-11-01"),
             "expires_at": _date("2026-10-31"), "status": CertStatus.VALID},
            {"cert_type": CertType.SYSTEM_GENERAL, "cert_name": "ISO 9001:2015",
             "issuer": "Sucofindo ICS", "issued_at": _date("2024-03-15"),
             "expires_at": _date("2027-03-14"), "status": CertStatus.VALID},
            {"cert_type": CertType.INDUSTRY_SPECIFIC, "cert_name": "CE Marking",
             "issuer": "Notified Body 0035", "issued_at": _date("2024-01-08"),
             "expires_at": _date("2029-01-07"), "status": CertStatus.VALID},
        ],
    },
    # ---------- C 档:巴基斯坦 Karachi Steel Works Ltd. ----------
    {
        "name": "Karachi Steel Works Ltd.",
        "legal_name_en": "Karachi Steel Works Limited",
        "country_code": "PK",
        "registration_no": "SECP-C3",
        "expected_grade": "C",
        "basic": {
            "established_date": _date("2015-03-10"),
            # 缺资本金
            "registered_capital": None,
            "business_scope": "钢材加工与出口",
            "legal_representative": "Ahmad Khan",
            "shareholders": "Ahmad Khan Family Trust(部分披露)",
            "status_text": "normal",
            "address": "Karachi, Pakistan",
            "website": None,
        },
        "finance": {
            "revenue_trend": RevenueTrend.FLUCTUATING,
            "debt_ratio": Decimal("78.00"),
            "cash_flow_status": CashFlowStatus.NEGATIVE_WITH_FUNDING,
        },
        "legal": {
            "litigation_count": 3,
            "defaulter_unresolved_count": 0,
            "defaulter_resolved_count": 1,
            "negative_news_level": NegativeNewsLevel.OCCASIONAL,
        },
        "certs": [
            # 目标国 PK 强制认证已过期
            {"cert_type": CertType.MANDATORY_COUNTRY, "cert_name": "PSQCA Mark",
             "target_country_code": "PK", "issuer": "PSQCA",
             "issued_at": _date("2020-05-01"), "expires_at": _date("2023-04-30"),
             "status": CertStatus.EXPIRED},  # 注意:这会触发 cert_critical_problem!
            {"cert_type": CertType.SYSTEM_GENERAL, "cert_name": "ISO 9001:2015",
             "issuer": "TÜV PAK", "issued_at": _date("2023-09-01"),
             "expires_at": _date("2026-08-31"), "status": CertStatus.VALID},
        ],
    },
    # ---------- D 档:摩洛哥 Atlas Construction SARL(触发司法一票否决)----------
    {
        "name": "Atlas Construction SARL",
        "legal_name_en": "Atlas Construction SARL",
        "country_code": "MA",
        "registration_no": "RC-D4",
        "expected_grade": "D",
        "basic": {
            "established_date": _date("2018-11-22"),
            "registered_capital": "5,000,000 MAD",
            "business_scope": "建筑工程总承包",
            "legal_representative": "Hassan El Idrissi",
            "shareholders": "",  # 无法查证
            "status_text": "abnormal",  # 存续但有异常
            "address": "Casablanca, Morocco",
            "website": None,
        },
        # finance 数据完全缺失 → 整维度走 missing override
        "finance": None,
        "legal": {
            "litigation_count": 15,
            "defaulter_unresolved_count": 2,  # 触发一票否决
            "defaulter_resolved_count": 3,
            "negative_news_level": NegativeNewsLevel.PERSISTENT,
        },
        "certs": [],
    },
]


# =============================================================================
# Seed 主流程
# =============================================================================

async def seed_credit_score_model(db: AsyncSession) -> None:
    """种入评分模型骨架:4 维度 + 12 子项 + 51 规则。

    幂等:按 code 检查是否已存在。
    启动后校验:每条 rule 的 evaluator_key 必须在 EVALUATORS 字典中存在,否则日志 WARN(不阻断)。
    """
    # ---- dimensions ----
    code_to_dim: dict[str, ScoreDimension] = {}
    for code, name, max_score, order in _DIMENSIONS:
        row = await db.execute(
            select(ScoreDimension).where(ScoreDimension.code == code)
        )
        existing = row.scalar_one_or_none()
        if existing is None:
            d = ScoreDimension(
                code=code, name=name, max_score=max_score, display_order=order,
                description=f"{name}(满分 {max_score})", is_active=True, version=1,
            )
            db.add(d)
            await db.flush()
            code_to_dim[code] = d
        else:
            code_to_dim[code] = existing

    # ---- subitems ----
    code_to_sub: dict[str, ScoreSubitem] = {}
    for sub_code, dim_code, name, max_score, default_score, order, hint in _SUBITEMS:
        row = await db.execute(
            select(ScoreSubitem).where(ScoreSubitem.code == sub_code)
        )
        existing = row.scalar_one_or_none()
        if existing is None:
            s = ScoreSubitem(
                dimension_id=code_to_dim[dim_code].id,
                code=sub_code, name=name, max_score=max_score,
                default_score=default_score, display_order=order,
                data_source_hint=hint, is_active=True, version=1,
            )
            db.add(s)
            await db.flush()
            code_to_sub[sub_code] = s
        else:
            code_to_sub[sub_code] = existing

    # ---- rules ----
    orphan_evaluator_keys: list[str] = []
    for sub_code, rule_code, desc, score, ev_key, priority in _RULES:
        row = await db.execute(select(ScoreRule).where(ScoreRule.code == rule_code))
        if row.scalar_one_or_none() is not None:
            continue
        if ev_key not in EVALUATORS:
            orphan_evaluator_keys.append(f"{rule_code} → {ev_key}")
        db.add(
            ScoreRule(
                subitem_id=code_to_sub[sub_code].id,
                code=rule_code, description=desc, score=score,
                evaluator_key=ev_key, condition_expr=None,
                priority=priority, is_active=True, version=1,
            )
        )
    await db.commit()
    if orphan_evaluator_keys:
        logger.warning(
            "Credit seed: 发现 %d 条 rule 的 evaluator_key 在 EVALUATORS 中找不到: %s",
            len(orphan_evaluator_keys), orphan_evaluator_keys,
        )
    logger.info(
        "Credit seed: 评分模型骨架完成 (4 维度 / 12 子项 / 51 规则)"
    )


async def seed_credit_demo_companies(db: AsyncSession) -> None:
    """种入 4 家 demo 企业 + 各类数据 + 首次评分。

    幂等:按 (country_code, name) 检查是否已存在;已存在则全部跳过(含评分)。
    """
    engine = ScoringEngine(MockDataSource())

    for spec in _DEMO_COMPANIES:
        row = await db.execute(
            select(CreditCompany).where(
                CreditCompany.country_code == spec["country_code"],
                CreditCompany.name == spec["name"],
            )
        )
        if row.scalar_one_or_none() is not None:
            continue  # 已存在,整家跳过

        # 1. 企业主表
        company = CreditCompany(
            name=spec["name"],
            legal_name_en=spec["legal_name_en"],
            country_code=spec["country_code"],
            registration_no=spec["registration_no"],
            linked_supplier_org_id=None,
            data_status={"expected_grade": spec["expected_grade"]},
        )
        db.add(company)
        await db.flush()

        # 2. basic
        b = spec["basic"]
        db.add(
            CreditCompanyBasicData(
                company_id=company.id,
                established_date=b["established_date"],
                registered_capital=b["registered_capital"],
                business_scope=b["business_scope"],
                legal_representative=b["legal_representative"],
                shareholders=b["shareholders"],
                status_text=b["status_text"],
                address=b["address"],
                website=b["website"],
                data_source=DataSourceTag.MOCK,
                fetched_at=_utcnow(),
            )
        )

        # 3. finance(D 档为 None,跳过)
        if spec["finance"] is not None:
            f = spec["finance"]
            db.add(
                CreditCompanyFinanceData(
                    company_id=company.id,
                    revenue_trend=f["revenue_trend"],
                    debt_ratio=f["debt_ratio"],
                    cash_flow_status=f["cash_flow_status"],
                    raw_data=None,
                    data_source=DataSourceTag.MOCK,
                    fetched_at=_utcnow(),
                )
            )

        # 4. legal
        leg = spec["legal"]
        db.add(
            CreditCompanyLegalData(
                company_id=company.id,
                litigation_count=leg["litigation_count"],
                defaulter_unresolved_count=leg["defaulter_unresolved_count"],
                defaulter_resolved_count=leg["defaulter_resolved_count"],
                negative_news_level=leg["negative_news_level"],
                raw_data=None,
                data_source=DataSourceTag.MOCK,
                fetched_at=_utcnow(),
            )
        )

        # 5. certs
        for c in spec["certs"]:
            db.add(
                CreditCompanyCertification(
                    company_id=company.id,
                    cert_type=c["cert_type"],
                    cert_name=c["cert_name"],
                    target_country_code=c.get("target_country_code"),
                    issuer=c.get("issuer"),
                    issued_at=c.get("issued_at"),
                    expires_at=c.get("expires_at"),
                    status=c["status"],
                    data_source=DataSourceTag.MOCK,
                )
            )

        await db.commit()  # 数据落地后再算分,引擎需要从 DB 读
        logger.info(
            "Credit seed: 企业 %s 数据写入完成,开始首次评分", company.name
        )

        # 6. 首次评分(不调 LLM,工单 Step 10)
        snapshot = await engine.compute(
            session=db,
            company_id=company.id,
            trigger_type=TriggerType.INITIAL,
            trigger_detail={"source": "seed"},
            operator_user_id=None,
        )
        await db.commit()

        logger.info(
            "Credit seed: 企业 %s 首次评分 = %d (%s),预期 %s",
            company.name, snapshot.total_score, snapshot.grade,
            spec["expected_grade"],
        )
        if snapshot.grade != spec["expected_grade"]:
            logger.warning(
                "Credit seed: 企业 %s 实际评级 %s 与预期 %s 不一致(检查 mock 数据 / 规则)",
                company.name, snapshot.grade, spec["expected_grade"],
            )


async def seed_credit_module(db: AsyncSession) -> None:
    """信用评估模块种子入口。"""
    await seed_credit_score_model(db)
    await seed_credit_demo_companies(db)
    logger.info("Credit seed: 评分模型骨架 + 4 家 demo 企业 seed 完成")
