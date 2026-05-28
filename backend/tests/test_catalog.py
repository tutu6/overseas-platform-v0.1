"""主线一品类资料卡读接口集成测试(工单 17 · Step 3)。

覆盖:
- 权限矩阵:BUYER/OPERATOR 200,SUPPLIER/ADMIN 403,未登录 401
- 业务:存在的品类返回完整资料卡(主表 + B 层属性 + 枚举值 + 厂商/认证)
- 业务:不存在的品类返回 404 规范错误响应
- 数据形态:variant_axis 标记、JSONB 字段、confidence_marks 等

client fixture 已自动跑 run_all_seeds → catalog seed 会种铝卷 1 张卡。
"""
from __future__ import annotations

import pytest


# -------- 登录工具(与 test_credit_scope 同款,避免跨文件 fixture 依赖) --------

async def _login(client, email: str, password: str) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _admin_token(client) -> str:
    return await _login(client, "admin@platform.local", "Aa123456789")


async def _operator_token(client) -> str:
    return await _login(client, "operator@platform.local", "Aa123456789")


async def _buyer_token(client) -> str:
    return await _login(client, "buyer@cscec3b.local", "Aa123456789")


async def _supplier_token(client) -> str:
    """注册一个新供应商并登录(seed 不含 supplier demo 账号)。"""
    email = "catalog_test_supplier@example.com"
    r = await client.post(
        "/api/v1/auth/register/supplier",
        json={
            "email": email,
            "name": "S",
            "phone": "+8613800001234",
            "password": "Aa123456789",
            "company_name": "Catalog Test Supplier",
            "country_code": "CN",
            "registration_no": "91110000CATALOGTEST",
            "language_preference": "zh",
        },
    )
    assert r.status_code in (200, 201), r.text
    return await _login(client, email, "Aa123456789")


def _auth(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


CARD_PATH = "/api/v1/catalog/cards/aluminum-coil"


# =============================================================================
# 权限矩阵
# =============================================================================

@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client):
    r = await client.get(CARD_PATH)
    # 未带 token → require_permission 之前先撞 auth → 401
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_buyer_can_read_card(client):
    t = await _buyer_token(client)
    r = await client.get(CARD_PATH, headers=_auth(t))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0


@pytest.mark.asyncio
async def test_operator_can_read_card(client):
    t = await _operator_token(client)
    r = await client.get(CARD_PATH, headers=_auth(t))
    assert r.status_code == 200, r.text
    assert r.json()["code"] == 0


@pytest.mark.asyncio
async def test_supplier_cannot_read_card_403(client):
    t = await _supplier_token(client)
    r = await client.get(CARD_PATH, headers=_auth(t))
    assert r.status_code == 403
    assert r.json()["code"] == 40003


@pytest.mark.asyncio
async def test_admin_cannot_read_card_403(client):
    """ADMIN 严格不触业务数据,不持有 catalog:read。"""
    t = await _admin_token(client)
    r = await client.get(CARD_PATH, headers=_auth(t))
    assert r.status_code == 403
    assert r.json()["code"] == 40003


# =============================================================================
# 业务正确性
# =============================================================================

@pytest.mark.asyncio
async def test_nonexistent_category_returns_404(client):
    t = await _buyer_token(client)
    r = await client.get(
        "/api/v1/catalog/cards/nonexistent-category", headers=_auth(t)
    )
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == 40400


@pytest.mark.asyncio
async def test_response_shape_complete(client):
    """完整校验:主表字段 + B 层 6 属性(牌号 variant_axis) + 14 厂商 + 11 认证。"""
    t = await _buyer_token(client)
    r = await client.get(CARD_PATH, headers=_auth(t))
    assert r.status_code == 200
    data = r.json()["data"]

    # 卡级
    assert data["id"] > 0
    assert data["version"] == "v0.1"
    assert data["review_status"] == "draft"
    assert data["confidence_marks"] is not None
    assert data["confidence_marks"]["field_1_definition"] == "green"

    # 品类
    assert data["category"]["code"] == "aluminum-coil"
    assert data["category"]["name_zh"] == "铝卷"
    assert data["category"]["name_en"] == "Aluminum Coil"

    # A 层字段(原样返回,未拼接)
    assert "铝/铝合金经轧制后" in data["field_1_definition"]
    assert data["field_4_origin"] is not None
    assert isinstance(data["field_4_origin"], list)
    assert len(data["field_4_origin"]) == 5  # 中国/中东/印度/欧美日韩/东南亚
    assert data["field_7_cost"]["aluminum_price_volatility"]
    assert isinstance(data["field_10_risk"], list)
    assert len(data["field_10_risk"]) == 4  # 质量/供应商/合规/商务

    # B 层属性维度
    attrs = data["attributes"]
    assert len(attrs) == 6
    attr_codes = [a["attr_code"] for a in attrs]
    assert attr_codes == ["grade", "temper", "thickness", "width", "surface_treatment", "application"]
    # 核心区分属性
    grade_attr = next(a for a in attrs if a["attr_code"] == "grade")
    assert grade_attr["is_variant_axis"] is True
    assert grade_attr["attr_type"] == "enum"
    assert [v["value"] for v in grade_attr["values"]] == ["1050", "1060", "3003", "5052"]
    # 数值型属性
    thickness_attr = next(a for a in attrs if a["attr_code"] == "thickness")
    assert thickness_attr["attr_type"] == "number"
    assert thickness_attr["attr_unit"] == "mm"
    # Pydantic JSON 序列化 Decimal → string,值校验用 in
    assert str(thickness_attr["min_value"]) in ("0.2", "0.2000")
    assert thickness_attr["values"] == []
    # 其他属性非 variant_axis
    for a in attrs:
        if a["attr_code"] != "grade":
            assert a["is_variant_axis"] is False

    # 子表行数
    assert len(data["suppliers"]) == 14
    assert len(data["certifications"]) == 11

    # 厂商样本
    novelis = next(s for s in data["suppliers"] if s["supplier_name"] == "Novelis")
    assert novelis["country_code"] == "US"
    assert novelis["linked_supplier_id"] is None  # 渠道搜集未入驻
    assert novelis["review_status"] == "draft"

    # 认证样本
    mtc = next(c for c in data["certifications"] if "MTC" in c["cert_name"])
    assert mtc["source"] == "channel_collected"
    assert mtc["verify_status"] == "unverified"
    assert mtc["credibility"] == "high"


@pytest.mark.asyncio
async def test_buyer_response_no_b_layer_dynamic_join(client):
    """本期字段 2/3 不做 B 层动态拼接,原样返回种子静态文本。"""
    t = await _buyer_token(client)
    r = await client.get(CARD_PATH, headers=_auth(t))
    assert r.status_code == 200
    data = r.json()["data"]
    # field_2 是手写文本,不含动态生成痕迹
    assert "选型五维要点" in data["field_2_tech_params"]
    # B 层 attributes 单独返回,不是嵌入 field_2/field_3
    assert isinstance(data["attributes"], list)


@pytest.mark.asyncio
async def test_trace_id_header_present(client):
    t = await _buyer_token(client)
    r = await client.get(CARD_PATH, headers=_auth(t))
    assert r.headers.get("x-trace-id"), "X-Trace-Id 响应头缺失"
