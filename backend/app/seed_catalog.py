"""主线一品类资料卡种子(工单 17 · Step 2)。

种入内容(铝卷一个品类,完整一张资料卡):
1. catalog_category:铝卷(aluminum-coil)1 行
2. catalog_attribute:6 个属性维度(牌号 / 状态 / 厚度 / 宽度 / 表面处理 / 应用场景)
3. catalog_attribute_value:5 个枚举型属性各自的枚举值
4. catalog_card:1 张资料卡(A 层 7 个字段 + 元数据)
5. catalog_card_supplier:14 家厂商(6 国际 + 8 中国,均渠道搜集未入驻)
6. catalog_card_certification:11 项认证标准

数据源:docs/architecture/通用铝卷资料卡_v0_1.md(四家 AI 聚合 + 人工整理 v0.1)
+ docs/architecture/主线一_通用字段表_v0_3.md §2.4(B 层 6 属性枚举)。

幂等:按 (code) / (category_id, attr_code) / (attr_id, value) / (card_id, supplier_name) /
(card_id, cert_name) 判断是否已存在再插入,重复跑不会重复种入。

价格(字段 6)本期不入主表,留待价格子系统独立议题(预备稿 §6)。
字段 5 厂商 / 字段 8 认证拆独立子表,主表无对应列。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AttrType,
    CardReviewStatus,
    CardSupplierReviewStatus,
    CatalogAttribute,
    CatalogAttributeValue,
    CatalogCard,
    CatalogCardCertification,
    CatalogCardSupplier,
    CatalogCategory,
    CategoryStatus,
    CertCredibility,
    CertSource,
    CertVerifyStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 品类
# =============================================================================
_CATEGORY_CODE = "aluminum-coil"
_CATEGORY = {
    "code": _CATEGORY_CODE,
    "name_zh": "铝卷",
    "name_en": "Aluminum Coil",
    "display_order": 1,
    "status": CategoryStatus.ACTIVE.value,
}


# =============================================================================
# B 层 · 属性维度 + 枚举值
# (attr_code, attr_name, attr_type, attr_unit, min, max, decimal_places,
#  is_filterable, is_variant_axis, display_order, [enum values])
# =============================================================================
_ATTRIBUTES: list[dict] = [
    {
        "attr_code": "grade",
        "attr_name": "牌号",
        "attr_type": AttrType.ENUM.value,
        "is_variant_axis": True,
        "display_order": 1,
        "values": ["1050", "1060", "3003", "5052"],
    },
    {
        "attr_code": "temper",
        "attr_name": "状态",
        "attr_type": AttrType.ENUM.value,
        "is_variant_axis": False,
        "display_order": 2,
        "values": ["O", "H14", "H16", "H18", "H24", "H26", "H112"],
    },
    {
        "attr_code": "thickness",
        "attr_name": "厚度",
        "attr_type": AttrType.NUMBER.value,
        "attr_unit": "mm",
        "min_value": Decimal("0.2"),
        "max_value": Decimal("25"),
        "decimal_places": 2,
        "is_variant_axis": False,
        "display_order": 3,
        "values": [],
    },
    {
        "attr_code": "width",
        "attr_name": "宽度",
        "attr_type": AttrType.NUMBER.value,
        "attr_unit": "mm",
        "min_value": Decimal("1000"),
        "max_value": Decimal("2000"),
        "decimal_places": 0,
        "is_variant_axis": False,
        "display_order": 4,
        "values": [],
    },
    {
        "attr_code": "surface_treatment",
        "attr_name": "表面处理",
        "attr_type": AttrType.ENUM.value,
        "is_variant_axis": False,
        "display_order": 5,
        "values": ["裸卷", "彩涂", "印花", "压花", "阳极氧化"],
    },
    {
        "attr_code": "application",
        "attr_name": "应用场景",
        "attr_type": AttrType.ENUM.value,
        "is_variant_axis": False,
        "display_order": 6,
        "values": ["屋面", "墙面", "管道保温外护", "装饰", "海洋工程"],
    },
]


# =============================================================================
# A 层 · 资料卡内容(对齐 docs/architecture/通用铝卷资料卡_v0_1.md)
# =============================================================================
_FIELD_1_DEFINITION = (
    "铝卷是铝/铝合金经轧制后以连续卷状交付的板带材,属工程加工材"
    "(需开平、压型、彩涂、包覆后使用),非最终构件。\n\n"
    "采购锁定用五要素:厚度 × 宽度 × 牌号 × 状态 × 表面处理。"
    "工程主力区间:厚度 0.3–3.0mm,宽度 1000–1500mm,牌号集中 1xxx/3xxx/5xxx。"
)

_FIELD_2_TECH_PARAMS = (
    "选型五维要点:\n"
    "• 牌号:1050/1060(纯铝,软、耐蚀、便宜)< 3003(防锈、通用主力)"
    "< 5052(耐海洋、强度最高、最贵)\n"
    "• 状态:O(最软,深加工)/ H14(通用半硬)/ H24(强度近 H14 但更易折弯)"
    "/ H16·H18(偏硬,抗变形)\n"
    "• 厚度:0.3–3.0mm 为主;保温 0.3–0.8 / 屋面 0.6–1.2 / 幕墙设备 1.0–3.0\n"
    "• 宽度:常用 1000/1200/1250/1500mm,屋面墙面 1000 最常见\n"
    "• 表面处理:裸卷(最便宜)/ 彩涂 PE(室内)·PVDF(户外耐候)"
    "/ 印花·压花(装饰防滑)/ 阳极氧化(高端)"
)

_FIELD_3_SPEC_SCENE = (
    "典型规格 × 应用场景:\n"
    "• 屋面:牌号 3003(沿海升 5052),厚度 0.6–1.2mm,状态 H24,表处 PVDF 彩涂\n"
    "• 墙面/幕墙:牌号 3003/5052,厚度 0.5–3.0mm,状态 H14/H24,"
    "表处 PVDF / 阳极氧化\n"
    "• 管道保温外护:牌号 1050/1060(腐蚀环境用 3003),"
    "厚度 0.3–0.8mm,状态 O/H14,表处 裸卷/压花\n"
    "• 装饰:牌号 1050/1060/3003,厚度 0.3–1.2mm,状态 O/H24/H18,"
    "表处 阳极氧化/印花/压花\n"
    "• 海洋工程:牌号 5052/5083(禁用纯铝/3003 承力),厚度 ≥1.0mm,"
    "状态码各家不一(按项目规范定),表处 裸卷/高耐候彩涂"
)

_FIELD_4_ORIGIN: list[dict] = [
    {
        "region": "中国",
        "characteristics": "最大、全谱系、性价比最高",
        "fit_for": "普通工程料首选",
        "note": "需关注目的国对华反倾销税/关税影响",
    },
    {
        "region": "中东",
        "characteristics": "能源优势、毛坯卷为主",
        "fit_for": "原料/中端",
        "note": "",
    },
    {
        "region": "印度",
        "characteristics": "中端产能增长快",
        "fit_for": "中端工程料",
        "note": "",
    },
    {
        "region": "欧美/日韩",
        "characteristics": "高端、价高",
        "fit_for": "海洋工程/航空等高端严苛场景",
        "note": "",
    },
    {
        "region": "东南亚",
        "characteristics": "加工分切节点",
        "fit_for": "加工分切环节",
        "note": "",
    },
]

_FIELD_7_COST = {
    "breakdown": [
        {"item": "铝锭原料", "ratio": "70-90%", "note": "随 LME/SHFE 波动,最大头"},
        {"item": "加工费", "ratio": "8-20%", "note": "轧制 / 退火等工艺"},
        {"item": "合金 / 表处 / 包装 / 利润", "ratio": "余量", "note": ""},
    ],
    "volatility_ranking": "铝锭价 > 电价/能源 > 海运/关税 > 涂料",
    "aluminum_price_volatility": "日内 3-5%,年振幅 20-50%",
}

_FIELD_9_LOGISTICS = (
    "海运为主(重货,20GP 限重约 20–28 吨,常未满体积即超重)。\n\n"
    "首要防潮——铝卷受潮生白锈;需 防潮膜 + 干燥剂 + 卷芯护角 + 鞍座固定 + "
    "立式装载防塌卷;彩涂卷需贴保护膜。\n"
    "木托须符合 ISPM 15(熏蒸/热处理 + IPPC 标识),否则检疫拒收。\n\n"
    "时效参考(含备货期口径各家不一,按船期核实):东南亚约 1–2 周海运、"
    "中东 2–3 周、欧洲 4–6 周。"
)

_FIELD_10_RISK: list[dict] = [
    {
        "category": "质量",
        "risks": [
            "牌号以次充好",
            "厚度偷薄(涂层算进总厚)",
            "PE 冒 PVDF",
            "卷重虚标",
        ],
        "controls": [
            "MTC + 光谱抽检",
            "合同明确'基材厚度'口径",
            "膜厚仪检测涂层",
            "第三方过磅",
            "装运前验货(PSI)",
            "封样",
        ],
    },
    {
        "category": "供应商",
        "risks": [
            "产能不实",
            "贸易商冒充工厂",
            "交期延误",
        ],
        "controls": [
            "验厂",
            "要求 ISO 9001",
            "合同写延期罚则",
            "留尾款",
            "建备选池",
        ],
    },
    {
        "category": "合规",
        "risks": [
            "认证滞后",
            "原产地造假 / 非法转口",
            "目的国反倾销税",
        ],
        "controls": [
            "下单前确认证书已持有",
            "CO 真实可查",
            "按 HS 税号核反倾销税现行公告",
        ],
    },
    {
        "category": "商务",
        "risks": [
            "铝价波动",
            "汇率风险",
            "账期",
        ],
        "controls": [
            "'铝锭价 + 加工费'调价机制",
            "L/C 或 30/70 付款",
            "明确 Incoterms",
        ],
    },
]

_CONFIDENCE_MARKS = {
    "field_1_definition": "green",
    "field_2_tech_params": "green",
    "field_3_spec_scene": "green",
    "field_4_origin": "green",
    "field_7_cost": "green",
    "field_9_logistics": "green",
    "field_10_risk": "green",
    "suppliers": "amber",
    "certifications": "yellow",
}

# 资料卡内容快照时点(对应源文档整理日)
_SNAPSHOT_AT = datetime(2026, 5, 28, 0, 0, 0)

_CARD = {
    "field_1_definition": _FIELD_1_DEFINITION,
    "field_2_tech_params": _FIELD_2_TECH_PARAMS,
    "field_3_spec_scene": _FIELD_3_SPEC_SCENE,
    "field_4_origin": _FIELD_4_ORIGIN,
    "field_7_cost": _FIELD_7_COST,
    "field_9_logistics": _FIELD_9_LOGISTICS,
    "field_10_risk": _FIELD_10_RISK,
    "confidence_marks": _CONFIDENCE_MARKS,
    "snapshot_at": _SNAPSHOT_AT,
    "version": "v0.1",
    "review_status": CardReviewStatus.DRAFT.value,
}


# =============================================================================
# 厂商子表(渠道搜集,均未入驻 → linked_supplier_id=None)
# 数据源:源文档 §5,海外业绩按 v0.1 caveat 统一标"待向供应商索取案例核实"
# =============================================================================
_SUPPLIERS: list[dict] = [
    # ===== 国际 =====
    {
        "supplier_name": "Novelis",
        "headquarter": "美国 亚特兰大",
        "origin": "美国 / 印度 / 韩国 / 巴西 / 欧洲多基地",
        "scale": "全球最大铝压延板带集团",
        "main_products": "汽车板、易拉罐料、航空板,工程卷非主打",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "US",
        "display_order": 1,
    },
    {
        "supplier_name": "Constellium",
        "headquarter": "法国 巴黎",
        "origin": "法国 / 美国 / 德国 / 捷克",
        "scale": "高端铝压延材头部",
        "main_products": "航空板、汽车结构件,工程卷非主打",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "FR",
        "display_order": 2,
    },
    {
        "supplier_name": "Norsk Hydro",
        "headquarter": "挪威 奥斯陆",
        "origin": "挪威 / 德国 / 美国",
        "scale": "原铝 + 压延材一体化巨头",
        "main_products": "型材、汽车板、电池铝箔,工程板带相对偏少",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "NO",
        "display_order": 3,
    },
    {
        "supplier_name": "Alcoa",
        "headquarter": "美国 匹兹堡",
        "origin": "美国 / 澳大利亚 / 加拿大",
        "scale": "原铝头部",
        "main_products": "氧化铝 / 原铝为主,压延材业务有限",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "US",
        "display_order": 4,
    },
    {
        "supplier_name": "UACJ",
        "headquarter": "日本 东京",
        "origin": "日本 / 泰国 / 美国",
        "scale": "日本最大铝压延材厂",
        "main_products": "汽车板、罐料、电子箔",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "JP",
        "display_order": 5,
    },
    {
        "supplier_name": "EGA(Emirates Global Aluminium)",
        "headquarter": "阿联酋 阿布扎比",
        "origin": "阿联酋",
        "scale": "中东最大原铝集团",
        "main_products": "原铝 / 重熔 T 锭 / 部分扁锭压延坯料",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "AE",
        "display_order": 6,
    },
    # ===== 中国 =====
    {
        "supplier_name": "中铝(中国铝业)",
        "headquarter": "中国 北京",
        "origin": "中国 山东 / 河南 / 广西",
        "scale": "中国铝行业央企龙头",
        "main_products": "原铝 / 氧化铝为主,板带亦有产能",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "CN",
        "display_order": 11,
    },
    {
        "supplier_name": "山东宏桥(魏桥铝电)",
        "headquarter": "中国 山东 邹平",
        "origin": "中国 山东",
        "scale": "全球最大铝压延企业之一",
        "main_products": "原铝 + 板带一体化",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "CN",
        "display_order": 12,
    },
    {
        "supplier_name": "南山铝业",
        "headquarter": "中国 山东 龙口",
        "origin": "中国 山东 / 印尼宾坦",
        "scale": "汽车板 / 航空板国内头部",
        "main_products": "汽车板、航空板、罐料、工业板带",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "CN",
        "display_order": 13,
    },
    {
        "supplier_name": "明泰铝业",
        "headquarter": "中国 河南 郑州",
        "origin": "中国 河南",
        "scale": "中型板带专精厂",
        "main_products": "1xxx/3xxx/5xxx 工业板带、彩涂卷",
        "overseas_track_record": "出口覆盖中东 / 东南亚 / 非洲,案例待供方提供",
        "country_code": "CN",
        "display_order": 14,
    },
    {
        "supplier_name": "鼎胜新材",
        "headquarter": "中国 江苏 镇江",
        "origin": "中国 江苏 / 内蒙古",
        "scale": "铝箔 / 板带专精厂",
        "main_products": "铝箔、亲水箔、板带、彩涂卷",
        "overseas_track_record": "出口工程卷至多个海外市场,案例待供方提供",
        "country_code": "CN",
        "display_order": 15,
    },
    {
        "supplier_name": "华峰铝业",
        "headquarter": "中国 上海",
        "origin": "中国 上海",
        "scale": "中型板带专精厂",
        "main_products": "热交换器材、汽车板、工业板带",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "CN",
        "display_order": 16,
    },
    {
        "supplier_name": "西南铝(西南铝业)",
        "headquarter": "中国 重庆",
        "origin": "中国 重庆",
        "scale": "国内大型综合铝压延厂",
        "main_products": "板带、锻件、航空材",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "CN",
        "display_order": 17,
    },
    {
        "supplier_name": "云铝(云南铝业)",
        "headquarter": "中国 云南 昆明",
        "origin": "中国 云南",
        "scale": "西南区域原铝头部 + 板带产能",
        "main_products": "原铝 / 板带 / 阳极氧化型材",
        "overseas_track_record": "待向供应商索取案例核实",
        "country_code": "CN",
        "display_order": 18,
    },
]


# =============================================================================
# 认证子表(11 项;均渠道搜集来源,默认未核实)
# =============================================================================
_CERTIFICATIONS: list[dict] = [
    {
        "cert_name": "GB/T 3880",
        "applicable_market": "中国(GB 国标)",
        "source": CertSource.CHANNEL_COLLECTED.value,
        "credibility": CertCredibility.MEDIUM.value,
        "note": "一般工业用变形铝及铝合金板带材;合同须写明标准号 + 版本年份",
        "display_order": 1,
    },
    {
        "cert_name": "GB/T 3190",
        "applicable_market": "中国(GB 国标)",
        "source": CertSource.CHANNEL_COLLECTED.value,
        "credibility": CertCredibility.MEDIUM.value,
        "note": "变形铝及铝合金化学成分",
        "display_order": 2,
    },
    {
        "cert_name": "ASTM B209",
        "applicable_market": "美国(ASTM)",
        "source": CertSource.CHANNEL_COLLECTED.value,
        "credibility": CertCredibility.MEDIUM.value,
        "note": "铝合金板带材规格(美标主用)",
        "display_order": 3,
    },
    {
        "cert_name": "EN 485",
        "applicable_market": "欧盟(EN)",
        "source": CertSource.CHANNEL_COLLECTED.value,
        "credibility": CertCredibility.MEDIUM.value,
        "note": "铝及铝合金板带材力学性能",
        "display_order": 4,
    },
    {
        "cert_name": "EN 573",
        "applicable_market": "欧盟(EN)",
        "source": CertSource.CHANNEL_COLLECTED.value,
        "credibility": CertCredibility.MEDIUM.value,
        "note": "化学成分与产品形式",
        "display_order": 5,
    },
    {
        "cert_name": "EN 515",
        "applicable_market": "欧盟(EN)",
        "source": CertSource.CHANNEL_COLLECTED.value,
        "credibility": CertCredibility.MEDIUM.value,
        "note": "状态代号(temper designation)",
        "display_order": 6,
    },
    {
        "cert_name": "EN 1396",
        "applicable_market": "欧盟(EN)",
        "source": CertSource.CHANNEL_COLLECTED.value,
        "credibility": CertCredibility.MEDIUM.value,
        "note": "彩涂卷材(coil coating)",
        "display_order": 7,
    },
    {
        "cert_name": "MTC(材质证明书)",
        "applicable_market": "全球工程合同",
        "source": CertSource.CHANNEL_COLLECTED.value,
        "credibility": CertCredibility.HIGH.value,
        "note": "工程合同必备,需注明牌号/状态/批次/化学成分/力学性能",
        "display_order": 8,
    },
    {
        "cert_name": "第三方检测(SGS / BV)",
        "applicable_market": "全球",
        "source": CertSource.CHANNEL_COLLECTED.value,
        "credibility": CertCredibility.HIGH.value,
        "note": "出货前第三方质量检测,工程方常要求",
        "display_order": 9,
    },
    {
        "cert_name": "原产地证(CO / Form E 等)",
        "applicable_market": "全球贸易",
        "source": CertSource.CHANNEL_COLLECTED.value,
        "credibility": CertCredibility.HIGH.value,
        "note": "关税优惠 / 反倾销规避凭证;按目的国/协定细化",
        "display_order": 10,
    },
    {
        "cert_name": "ISO 9001",
        "applicable_market": "全球(质量管理体系)",
        "source": CertSource.CHANNEL_COLLECTED.value,
        "credibility": CertCredibility.MEDIUM.value,
        "note": "供应商资质底线,与产品标准独立",
        "display_order": 11,
    },
]


# =============================================================================
# 入库函数(幂等)
# =============================================================================
async def _get_or_create_category(db: AsyncSession) -> CatalogCategory:
    row = await db.execute(
        select(CatalogCategory).where(CatalogCategory.code == _CATEGORY_CODE)
    )
    existing = row.scalar_one_or_none()
    if existing is not None:
        return existing
    obj = CatalogCategory(**_CATEGORY)
    db.add(obj)
    await db.flush()
    logger.info("Seed catalog: category '%s' created (id=%s)", _CATEGORY_CODE, obj.id)
    return obj


async def _seed_attributes(db: AsyncSession, category_id: int) -> dict[str, int]:
    """种入 6 个属性维度 + 各自枚举值。返回 {attr_code: attr_id}。"""
    attr_id_map: dict[str, int] = {}
    for spec in _ATTRIBUTES:
        row = await db.execute(
            select(CatalogAttribute).where(
                CatalogAttribute.category_id == category_id,
                CatalogAttribute.attr_code == spec["attr_code"],
            )
        )
        attr = row.scalar_one_or_none()
        if attr is None:
            attr = CatalogAttribute(
                category_id=category_id,
                attr_code=spec["attr_code"],
                attr_name=spec["attr_name"],
                attr_type=spec["attr_type"],
                attr_unit=spec.get("attr_unit"),
                min_value=spec.get("min_value"),
                max_value=spec.get("max_value"),
                decimal_places=spec.get("decimal_places"),
                is_filterable=True,
                is_variant_axis=spec["is_variant_axis"],
                display_order=spec["display_order"],
            )
            db.add(attr)
            await db.flush()
            logger.info(
                "Seed catalog: attribute '%s' created (id=%s)",
                spec["attr_code"],
                attr.id,
            )
        attr_id_map[spec["attr_code"]] = attr.id

        for idx, value in enumerate(spec["values"], start=1):
            row = await db.execute(
                select(CatalogAttributeValue).where(
                    CatalogAttributeValue.attr_id == attr.id,
                    CatalogAttributeValue.value == value,
                )
            )
            if row.scalar_one_or_none() is None:
                db.add(
                    CatalogAttributeValue(
                        attr_id=attr.id, value=value, value_order=idx
                    )
                )
        await db.flush()
    return attr_id_map


async def _get_or_create_card(db: AsyncSession, category_id: int) -> CatalogCard:
    row = await db.execute(
        select(CatalogCard).where(CatalogCard.category_id == category_id)
    )
    existing = row.scalar_one_or_none()
    if existing is not None:
        return existing
    card = CatalogCard(category_id=category_id, **_CARD)
    db.add(card)
    await db.flush()
    logger.info("Seed catalog: card created (id=%s) for category_id=%s", card.id, category_id)
    return card


async def _seed_card_suppliers(db: AsyncSession, card_id: int) -> None:
    for spec in _SUPPLIERS:
        row = await db.execute(
            select(CatalogCardSupplier).where(
                CatalogCardSupplier.card_id == card_id,
                CatalogCardSupplier.supplier_name == spec["supplier_name"],
            )
        )
        if row.scalar_one_or_none() is not None:
            continue
        db.add(
            CatalogCardSupplier(
                card_id=card_id,
                supplier_name=spec["supplier_name"],
                headquarter=spec.get("headquarter"),
                origin=spec.get("origin"),
                scale=spec.get("scale"),
                main_products=spec.get("main_products"),
                overseas_track_record=spec.get("overseas_track_record"),
                linked_supplier_id=None,
                country_code=spec.get("country_code"),
                registration_no=None,
                review_status=CardSupplierReviewStatus.DRAFT.value,
                display_order=spec["display_order"],
            )
        )
    await db.flush()


async def _seed_card_certifications(db: AsyncSession, card_id: int) -> None:
    for spec in _CERTIFICATIONS:
        row = await db.execute(
            select(CatalogCardCertification).where(
                CatalogCardCertification.card_id == card_id,
                CatalogCardCertification.cert_name == spec["cert_name"],
            )
        )
        if row.scalar_one_or_none() is not None:
            continue
        db.add(
            CatalogCardCertification(
                card_id=card_id,
                cert_name=spec["cert_name"],
                applicable_market=spec.get("applicable_market"),
                source=spec["source"],
                credibility=spec.get("credibility"),
                verify_status=CertVerifyStatus.UNVERIFIED.value,
                note=spec.get("note"),
                display_order=spec["display_order"],
            )
        )
    await db.flush()


async def seed_catalog_module(db: AsyncSession) -> None:
    """主线一品类资料卡 seed 总入口(铝卷 1 张卡完整种入)。

    幂等:每张表都按业务键查后写,重复执行不会重复插入或报错。
    """
    category = await _get_or_create_category(db)
    await _seed_attributes(db, category.id)
    card = await _get_or_create_card(db, category.id)
    await _seed_card_suppliers(db, card.id)
    await _seed_card_certifications(db, card.id)
    await db.commit()
    logger.warning(
        "Seed catalog: aluminum-coil card ready (category_id=%s, card_id=%s)",
        category.id,
        card.id,
    )
