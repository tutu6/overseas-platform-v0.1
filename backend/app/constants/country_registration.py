"""供应商注册:9 国常量(前后端必须对齐部分)。

边界(PRD v1.3 §5.3):仅"前后端要对齐 / 错一字即 bug"的字符串进这里。
一次性展示文案直接写在前端组件 JSX,不进常量。

与 `frontend/src/config/country-registration-rules.ts` **逐字一致**(手工同步)。
"""
from __future__ import annotations

# 9 国 ISO 2 位 code(用于 schema 枚举校验)
COUNTRY_CODES: tuple[str, ...] = (
    "CN",
    "KH",
    "PK",
    "MA",
    "IQ",
    "ID",
    "MY",
    "SA",
    "AE",
)

# 国家元数据(后端目前只用到 local_lang 与 name_*,精确正则放前端)
COUNTRY_META: dict[str, dict[str, str]] = {
    "CN": {"name_zh": "中国", "name_en": "China", "local_lang": "zh",
           "reg_no_hint": "统一社会信用代码 18 位"},
    "KH": {"name_zh": "柬埔寨", "name_en": "Cambodia", "local_lang": "km",
           "reg_no_hint": "MOC 注册号 6-12 位数字"},
    "PK": {"name_zh": "巴基斯坦", "name_en": "Pakistan", "local_lang": "ur",
           "reg_no_hint": "NTN 税号 7-8 位数字"},
    "MA": {"name_zh": "摩洛哥", "name_en": "Morocco", "local_lang": "ar",
           "reg_no_hint": "RC 商业登记号"},
    "IQ": {"name_zh": "伊拉克", "name_en": "Iraq", "local_lang": "ar",
           "reg_no_hint": "商业登记号"},
    "ID": {"name_zh": "印尼", "name_en": "Indonesia", "local_lang": "id",
           "reg_no_hint": "NIB 注册号 13 位数字"},
    "MY": {"name_zh": "马来西亚", "name_en": "Malaysia", "local_lang": "ms",
           "reg_no_hint": "SSM 注册号 12 位数字"},
    "SA": {"name_zh": "沙特阿拉伯", "name_en": "Saudi Arabia", "local_lang": "ar",
           "reg_no_hint": "CR 商业登记号 10 位数字"},
    "AE": {"name_zh": "阿联酋", "name_en": "UAE", "local_lang": "ar",
           "reg_no_hint": "营业执照号"},
}

# language_preference 合法值并集:zh + en + 9 国 local_lang 去重
# 与前端 LANGUAGE_CODES 必须一致
LANGUAGE_CODES: tuple[str, ...] = (
    "zh", "en", "km", "ur", "ar", "id", "ms",
)

# 后端只做长度兜底,精确正则在前端(TODO(REG-RULE) 各国正则待补)
REGISTRATION_NO_MAX_LENGTH = 50

# 重复注册错误文案(前后端逐字一致,不暴露 owner / 公司名信息)
DUPLICATE_REGISTRATION_ERROR_MESSAGE = (
    "当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。"
)

# v1.5 Δ2:邮箱 / 手机号全局唯一,前后端按数字 code 识别(严禁字符串比较)
BUSINESS_CODE_SUPPLIER_ALREADY_REGISTERED = 40901
BUSINESS_CODE_EMAIL_ALREADY_REGISTERED = 40902
BUSINESS_CODE_PHONE_ALREADY_REGISTERED = 40903

EMAIL_ALREADY_REGISTERED_MESSAGE = "该邮箱已注册,请直接登录或更换邮箱"
PHONE_ALREADY_REGISTERED_MESSAGE = "该手机号已注册,请直接登录或更换手机号"

# v1.5 Δ3:多错误并发时顶部 banner 文案(单错误时不使用)
MULTIPLE_VALIDATION_ERRORS_MESSAGE = "请修正以下问题"
