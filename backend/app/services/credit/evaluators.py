"""规则求值函数集中地(信用评估 §3.3 + PRD v0.3 §4.3)。

设计:
- 函数签名统一 `def fn(data: dict) -> bool`
- data 含 4 类数据 + today + country_code(详见 ScoringEngine.compute)
- 末尾导出 EVALUATORS 字典,key 严格对应 score_rule.evaluator_key

档位语义:
- 同 subitem 的 rule 按 priority 升序求值,首条命中即停;全部未命中走 subitem.default_score
- "维度级一票否决"通过给该维度的每个 subitem 加 priority=0 的 override 规则实现,
  触发后整维度归 0 / 整维度走默认分

子项 EVALUATORS 分布(约 43 个):
- 维度1 基础工商: 9 个(reg_info × 3 + status × 3 + shareholders × 3)
- 维度2 资质认证: 10 + 1 override(mandatory × 3 + system × 3 + industry × 4 + cert_critical_problem)
- 维度3 财务健康: 12 + 1 override(revenue/debt/cashflow × 4 + finance_dimension_missing)
- 维度4 司法舆情: 11 + 1 override(litigation × 4 + defaulter × 3 + news × 4 + legal_dimension_veto)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Callable


# =============================================================================
# 工具
# =============================================================================

def _basic(data: dict) -> dict:
    return data.get("basic") or {}


def _finance(data: dict) -> dict:
    return data.get("finance") or {}


def _legal(data: dict) -> dict:
    return data.get("legal") or {}


def _certs(data: dict) -> list[dict]:
    return data.get("certifications") or []


def _today(data: dict) -> date:
    return data.get("today") or date.today()


def _country(data: dict) -> str:
    return data.get("country_code") or ""


def _is_cert_effective(cert: dict, today: date) -> bool:
    """证书有效 = status==valid AND (没设过期 OR 过期日期 > today)。

    过期未更新(status==valid 但 expires_at < today)算无效。
    """
    if cert.get("status") != "valid":
        return False
    expires = cert.get("expires_at")
    if expires is None:
        return True  # 没设过期视为有效(如 ISO 通用证书有时不标过期)
    if isinstance(expires, str):
        # ISO date string,可能从 model_dump 来
        try:
            expires = date.fromisoformat(expires)
        except ValueError:
            return False
    return expires >= today


# =============================================================================
# 维度1: 基础工商(15 分 = 3 子项 × 5 分)
# =============================================================================

# ---- 子项 1.1: 注册信息完整性(注册时间 / 资本金 / 经营范围 齐全度)----

def basic_reg_info_full(data: dict) -> bool:
    """3 项齐全 → 5 分。"""
    b = _basic(data)
    have = [b.get("established_date"), b.get("registered_capital"), b.get("business_scope")]
    return sum(1 for f in have if f) == 3


def basic_reg_info_miss_one(data: dict) -> bool:
    """缺 1 项 → 3 分。"""
    b = _basic(data)
    have = [b.get("established_date"), b.get("registered_capital"), b.get("business_scope")]
    return sum(1 for f in have if f) == 2


def basic_reg_info_miss_two_or_more(data: dict) -> bool:
    """缺 ≥2 项 → 0 分(兜底命中)。"""
    b = _basic(data)
    have = [b.get("established_date"), b.get("registered_capital"), b.get("business_scope")]
    return sum(1 for f in have if f) <= 1


# ---- 子项 1.2: 存续状态 ----

def basic_status_normal(data: dict) -> bool:
    return _basic(data).get("status_text") == "normal"


def basic_status_abnormal(data: dict) -> bool:
    return _basic(data).get("status_text") == "abnormal"


def basic_status_cancelled(data: dict) -> bool:
    """已注销/吊销/None → 0 分(兜底)。"""
    s = _basic(data).get("status_text")
    return s in (None, "", "cancelled")


# ---- 子项 1.3: 股东与股权 ----
# 用 shareholders 文本特征区分:
#   - 含 "%" 且 含 "公司" / "持股" → 清晰
#   - 非空但无百分比 → 部分可查
#   - None/空 → 无法查证

def basic_shareholders_clear(data: dict) -> bool:
    s = _basic(data).get("shareholders") or ""
    return ("%" in s) and (("公司" in s) or ("持股" in s))


def basic_shareholders_partial(data: dict) -> bool:
    s = _basic(data).get("shareholders") or ""
    if not s:
        return False
    return "%" not in s  # 有文本但没百分比 → 部分


def basic_shareholders_missing(data: dict) -> bool:
    """空 → 0 分(兜底)。"""
    s = _basic(data).get("shareholders") or ""
    return s == ""


# =============================================================================
# 维度2: 资质认证(25 分)
#   override: 关键证书伪造/过期未更新 → 整维度清零
# =============================================================================

# ---- 维度级 override(给该维度每个 subitem 配 priority=0 的 rule)----

def cert_critical_problem(data: dict) -> bool:
    """命中 → 整维度 0:
    - status == suspicious_forged(伪造)
    - status == expired(过期未更新)
    """
    today = _today(data)
    for c in _certs(data):
        if c.get("status") == "suspicious_forged":
            return True
        if c.get("status") == "expired":
            return True
        # status=valid 但 expires_at 已过(实际等同 expired,但 seed 数据未更新 status)
        if c.get("status") == "valid":
            expires = c.get("expires_at")
            if expires is not None:
                if isinstance(expires, str):
                    try:
                        expires = date.fromisoformat(expires)
                    except ValueError:
                        continue
                if expires < today:
                    return True
    return False


# ---- 子项 2.1: 目标国强制认证(10 分)----

def cert_mandatory_valid(data: dict) -> bool:
    """具备目标国强制认证且在有效期内 → 10 分。"""
    today = _today(data)
    country = _country(data)
    for c in _certs(data):
        if c.get("cert_type") != "mandatory_country":
            continue
        if c.get("target_country_code") and c["target_country_code"] != country:
            continue
        if _is_cert_effective(c, today):
            return True
    return False


def cert_mandatory_expired(data: dict) -> bool:
    """有目标国强制认证但已过期(且无有效的同类)→ 3 分。"""
    if cert_mandatory_valid(data):
        return False
    country = _country(data)
    for c in _certs(data):
        if c.get("cert_type") != "mandatory_country":
            continue
        if c.get("target_country_code") and c["target_country_code"] != country:
            continue
        # status=expired 或 valid 但已过期
        if c.get("status") in ("expired", "valid"):
            return True
    return False


def cert_mandatory_missing(data: dict) -> bool:
    """无目标国强制认证 → 0 分(兜底)。"""
    country = _country(data)
    for c in _certs(data):
        if c.get("cert_type") != "mandatory_country":
            continue
        if c.get("target_country_code") and c["target_country_code"] != country:
            continue
        return False  # 有这类证书(无论状态)→ 不算 missing
    return True


# ---- 子项 2.2: 通用体系认证(8 分,每项 +4 最高 8)----

def _system_valid_count(data: dict) -> int:
    today = _today(data)
    return sum(
        1
        for c in _certs(data)
        if c.get("cert_type") == "system_general" and _is_cert_effective(c, today)
    )


def cert_system_count_2_or_more(data: dict) -> bool:
    return _system_valid_count(data) >= 2


def cert_system_count_1(data: dict) -> bool:
    return _system_valid_count(data) == 1


def cert_system_count_0(data: dict) -> bool:
    return _system_valid_count(data) == 0


# ---- 子项 2.3: 行业专项认证(7 分,每项 +3,3 项及以上 cap 7)----

def _industry_valid_count(data: dict) -> int:
    today = _today(data)
    return sum(
        1
        for c in _certs(data)
        if c.get("cert_type") == "industry_specific" and _is_cert_effective(c, today)
    )


def cert_industry_count_3_or_more(data: dict) -> bool:
    return _industry_valid_count(data) >= 3


def cert_industry_count_2(data: dict) -> bool:
    return _industry_valid_count(data) == 2


def cert_industry_count_1(data: dict) -> bool:
    return _industry_valid_count(data) == 1


def cert_industry_count_0(data: dict) -> bool:
    return _industry_valid_count(data) == 0


# =============================================================================
# 维度3: 财务健康(30 分)
#   override: 整维度数据缺失 → 每子项给 4 分(整维度 12 = 40% 满分)
# =============================================================================

def finance_dimension_missing(data: dict) -> bool:
    """整维度数据缺失 → priority 0 命中,每子项给 4 分(整维度 12 = 40% × 30)。"""
    return (_finance(data).get("data_source") or "") == "missing"


# ---- 子项 3.1: 营收与盈利(10 分)----

def finance_revenue_growing(data: dict) -> bool:
    return _finance(data).get("revenue_trend") == "growing"


def finance_revenue_fluctuating(data: dict) -> bool:
    return _finance(data).get("revenue_trend") == "fluctuating"


def finance_revenue_loss(data: dict) -> bool:
    return _finance(data).get("revenue_trend") == "loss"


def finance_revenue_unknown(data: dict) -> bool:
    """单子项 unknown → 5 分(50%);兜底命中包括 None。"""
    v = _finance(data).get("revenue_trend")
    return v in (None, "", "unknown")


# ---- 子项 3.2: 资产负债(10 分)----

def _debt_ratio(data: dict) -> Decimal | None:
    v = _finance(data).get("debt_ratio")
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:  # noqa: BLE001
        return None


def finance_debt_low(data: dict) -> bool:
    v = _debt_ratio(data)
    return v is not None and v < Decimal("70")


def finance_debt_medium(data: dict) -> bool:
    v = _debt_ratio(data)
    return v is not None and Decimal("70") <= v <= Decimal("85")


def finance_debt_high(data: dict) -> bool:
    v = _debt_ratio(data)
    return v is not None and v > Decimal("85")


def finance_debt_unknown(data: dict) -> bool:
    return _debt_ratio(data) is None


# ---- 子项 3.3: 现金流(10 分)----

def finance_cashflow_positive(data: dict) -> bool:
    return _finance(data).get("cash_flow_status") == "positive"


def finance_cashflow_negative_with_funding(data: dict) -> bool:
    return _finance(data).get("cash_flow_status") == "negative_with_funding"


def finance_cashflow_persistent_negative(data: dict) -> bool:
    return _finance(data).get("cash_flow_status") == "persistent_negative"


def finance_cashflow_unknown(data: dict) -> bool:
    v = _finance(data).get("cash_flow_status")
    return v in (None, "", "unknown")


# =============================================================================
# 维度4: 司法舆情(30 分)
#   override: 失信被执行未结案 → 整维度 0
# =============================================================================

def legal_dimension_veto(data: dict) -> bool:
    """一票否决:未结案失信记录 > 0 → 整维度 0。"""
    return (_legal(data).get("defaulter_unresolved_count") or 0) > 0


# ---- 子项 4.1: 法律诉讼(10 分)----

def legal_litigation_zero(data: dict) -> bool:
    return (_legal(data).get("litigation_count") or 0) == 0


def legal_litigation_low(data: dict) -> bool:
    n = _legal(data).get("litigation_count") or 0
    return 1 <= n < 5


def legal_litigation_medium(data: dict) -> bool:
    n = _legal(data).get("litigation_count") or 0
    return 5 <= n <= 20


def legal_litigation_high(data: dict) -> bool:
    return (_legal(data).get("litigation_count") or 0) > 20


# ---- 子项 4.2: 失信被执行(10 分)----

def legal_defaulter_none(data: dict) -> bool:
    leg = _legal(data)
    return (leg.get("defaulter_unresolved_count") or 0) == 0 and (
        leg.get("defaulter_resolved_count") or 0
    ) == 0


def legal_defaulter_resolved_only(data: dict) -> bool:
    leg = _legal(data)
    return (leg.get("defaulter_unresolved_count") or 0) == 0 and (
        leg.get("defaulter_resolved_count") or 0
    ) > 0


def legal_defaulter_unresolved(data: dict) -> bool:
    """有未结案 → 0(兜底命中,理论上 veto 会先拦截整维度)。"""
    return (_legal(data).get("defaulter_unresolved_count") or 0) > 0


# ---- 子项 4.3: 负面舆情(10 分)----

def legal_news_none(data: dict) -> bool:
    return _legal(data).get("negative_news_level") in ("none", None, "")


def legal_news_occasional(data: dict) -> bool:
    return _legal(data).get("negative_news_level") == "occasional"


def legal_news_persistent(data: dict) -> bool:
    return _legal(data).get("negative_news_level") == "persistent"


def legal_news_major_scandal(data: dict) -> bool:
    return _legal(data).get("negative_news_level") == "major_scandal"


# =============================================================================
# 导出字典(rule.evaluator_key 严格对应这里的 key)
# =============================================================================

EVALUATORS: dict[str, Callable[[dict[str, Any]], bool]] = {
    # 维度1
    "basic_reg_info_full": basic_reg_info_full,
    "basic_reg_info_miss_one": basic_reg_info_miss_one,
    "basic_reg_info_miss_two_or_more": basic_reg_info_miss_two_or_more,
    "basic_status_normal": basic_status_normal,
    "basic_status_abnormal": basic_status_abnormal,
    "basic_status_cancelled": basic_status_cancelled,
    "basic_shareholders_clear": basic_shareholders_clear,
    "basic_shareholders_partial": basic_shareholders_partial,
    "basic_shareholders_missing": basic_shareholders_missing,
    # 维度2(含 override)
    "cert_critical_problem": cert_critical_problem,
    "cert_mandatory_valid": cert_mandatory_valid,
    "cert_mandatory_expired": cert_mandatory_expired,
    "cert_mandatory_missing": cert_mandatory_missing,
    "cert_system_count_2_or_more": cert_system_count_2_or_more,
    "cert_system_count_1": cert_system_count_1,
    "cert_system_count_0": cert_system_count_0,
    "cert_industry_count_3_or_more": cert_industry_count_3_or_more,
    "cert_industry_count_2": cert_industry_count_2,
    "cert_industry_count_1": cert_industry_count_1,
    "cert_industry_count_0": cert_industry_count_0,
    # 维度3(含 override)
    "finance_dimension_missing": finance_dimension_missing,
    "finance_revenue_growing": finance_revenue_growing,
    "finance_revenue_fluctuating": finance_revenue_fluctuating,
    "finance_revenue_loss": finance_revenue_loss,
    "finance_revenue_unknown": finance_revenue_unknown,
    "finance_debt_low": finance_debt_low,
    "finance_debt_medium": finance_debt_medium,
    "finance_debt_high": finance_debt_high,
    "finance_debt_unknown": finance_debt_unknown,
    "finance_cashflow_positive": finance_cashflow_positive,
    "finance_cashflow_negative_with_funding": finance_cashflow_negative_with_funding,
    "finance_cashflow_persistent_negative": finance_cashflow_persistent_negative,
    "finance_cashflow_unknown": finance_cashflow_unknown,
    # 维度4(含 veto)
    "legal_dimension_veto": legal_dimension_veto,
    "legal_litigation_zero": legal_litigation_zero,
    "legal_litigation_low": legal_litigation_low,
    "legal_litigation_medium": legal_litigation_medium,
    "legal_litigation_high": legal_litigation_high,
    "legal_defaulter_none": legal_defaulter_none,
    "legal_defaulter_resolved_only": legal_defaulter_resolved_only,
    "legal_defaulter_unresolved": legal_defaulter_unresolved,
    "legal_news_none": legal_news_none,
    "legal_news_occasional": legal_news_occasional,
    "legal_news_persistent": legal_news_persistent,
    "legal_news_major_scandal": legal_news_major_scandal,
}
