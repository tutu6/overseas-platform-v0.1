"""供应商注册号格式后端兜底校验(KH MOC 6-12 位数字)。

前端正则可被绕过(直接调 API),后端 SupplierRegisterIn 必须兜底校验,
保证前后端一致。未配置精确正则的国家(如 CN)只走长度兜底,不拦格式。
"""
from __future__ import annotations


async def _register(client, country_code, regno, email, phone):
    return await client.post("/api/v1/auth/register/supplier", json={
        "email": email, "name": "S", "phone": phone, "password": "Aa123456789",
        "company_name": f"Co {email}", "country_code": country_code,
        "registration_no": regno, "language_preference": "en",
    })


async def test_kh_valid_digits_ok(client):
    r = await _register(client, "KH", "12345678", "kh.ok@x.com", "+85512345678")
    assert r.status_code == 200, r.text


async def test_kh_with_letters_rejected(client):
    r = await _register(client, "KH", "ABC12345", "kh.b1@x.com", "+85512345601")
    assert r.status_code == 422


async def test_kh_too_short_rejected(client):
    r = await _register(client, "KH", "12345", "kh.b2@x.com", "+85512345602")
    assert r.status_code == 422


async def test_kh_too_long_rejected(client):
    r = await _register(client, "KH", "1234567890123", "kh.b3@x.com", "+85512345603")
    assert r.status_code == 422


async def test_non_kh_country_skips_format_check(client):
    # CN 无精确正则 → 注册号格式不被拦(仅长度兜底)
    r = await _register(client, "CN", "SC-CN-XYZ-001", "cn.ok@x.com", "13800138000")
    assert r.status_code == 200, r.text
