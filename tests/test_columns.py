# -*- coding: utf-8 -*-
from core import columns


def test_core_column_constants_preserve_existing_contract_values():
    assert columns.COL_TICKER == "代碼"
    assert columns.COL_NAME == "名稱"
    assert columns.COL_PRICE == "股價"
    assert columns.COL_MARKET_VALUE == "市值"
    assert columns.COL_HOLDABILITY_SCORE == "holdabilityScore"
    assert columns.COL_COMFORT_SCORE == "comfortScore"
    assert columns.COL_MATURITY_SCORE == "maturityScore"
    assert columns.COL_HISTORY_YEARS == "historyYears"

