"""按国别路由数据源的占位(信用评估 §3.1 长期)。

第一阶段:所有国别都用 MockDataSource。
TODO(T-2): 真实数据源接入后,按 country_code 路由到 QichachaDataSource / OpenCorporatesDataSource 等。
"""
from __future__ import annotations

from app.services.credit.data_source.base import DataSource
from app.services.credit.data_source.mock_data_source import MockDataSource


_MOCK = MockDataSource()


def resolve_data_source(country_code: str) -> DataSource:
    """按国别返回对应 DataSource 实例。

    第一阶段忽略 country_code,统一返回 MockDataSource。
    """
    # TODO(T-2): 按 country_code 分流到企查查 / OpenCorporates / 海外数据商
    _ = country_code
    return _MOCK
