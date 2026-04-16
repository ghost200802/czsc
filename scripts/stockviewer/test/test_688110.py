"""688110.SH 真实数据集成测试

验证针对688110这只股票的 CZSC 缠论分析结果符合预期：
- 有足够数量的笔和分型
- 中枢数量大于0
- 背驰点数量大于0

运行方式（需要网络）：
    pytest scripts/stockviewer/test/test_688110.py -m integration
"""

import pytest

from czsc.connectors import bs_connector
from czsc.core import CZSC

from scripts.stockviewer.app import (
    _dicts_to_raw_bars,
    _raw_bars_to_dicts,
    compute_bc_markers,
    run_czsc_analysis,
)

SYMBOL = "sh.688110"
FREQ = "日线"
SDT = "20240101"
EDT = "20260416"
FQ = "前复权"


@pytest.fixture(scope="class")
def raw_bars():
    bars = bs_connector.get_raw_bars(SYMBOL, FREQ, SDT, EDT, fq=FQ)
    assert len(bars) > 0, f"未能获取 {SYMBOL} 数据"
    bar_dicts = _raw_bars_to_dicts(bars)
    return _dicts_to_raw_bars(bar_dicts)


@pytest.mark.integration
class Test688110BasicAnalysis:
    def test_kline_count(self, raw_bars):
        kline_data, fx_data, bi_data, zs_data, bi_count, fx_count, zs_count = run_czsc_analysis(raw_bars)
        assert len(kline_data) >= 500, f"K线数量应>=500，实际: {len(kline_data)}"

    def test_bi_count(self, raw_bars):
        _, _, _, _, bi_count, _, _ = run_czsc_analysis(raw_bars)
        assert bi_count >= 40, f"笔数量应>=40，实际: {bi_count}"

    def test_fx_count(self, raw_bars):
        _, _, _, _, _, fx_count, _ = run_czsc_analysis(raw_bars)
        assert fx_count >= 150, f"分型数量应>=150，实际: {fx_count}"


@pytest.mark.integration
class Test688110ZS:
    def test_zs_count_positive(self, raw_bars):
        _, _, _, zs_data, _, _, zs_count = run_czsc_analysis(raw_bars)
        assert zs_count > 0, f"688110 在 {SDT}~{EDT} 区间应产生有效中枢，实际: {zs_count}"

    def test_zs_data_structure(self, raw_bars):
        _, _, _, zs_data, _, _, zs_count = run_czsc_analysis(raw_bars)
        assert zs_count == len(zs_data)
        for zs in zs_data:
            assert "sdt" in zs
            assert "edt" in zs
            assert "zg" in zs
            assert "zd" in zs
            assert "zz" in zs
            assert "gg" in zs
            assert "dd" in zs
            assert "direction" in zs
            assert "bi_count" in zs

    def test_zs_price_overlap(self, raw_bars):
        _, _, _, zs_data, _, _, _ = run_czsc_analysis(raw_bars)
        for zs in zs_data:
            assert zs["zg"] > zs["zd"], f"中枢上沿应大于下沿: zg={zs['zg']}, zd={zs['zd']}"
            assert zs["gg"] >= zs["zg"], f"中枢最高点应>=上沿"
            assert zs["dd"] <= zs["zd"], f"中枢最低点应<=下沿"
            assert zs["sdt"] <= zs["edt"], f"中枢开始时间应早于结束时间"

    def test_zs_direction(self, raw_bars):
        _, _, _, zs_data, _, _, _ = run_czsc_analysis(raw_bars)
        for zs in zs_data:
            assert zs["direction"] in ("向上", "向下"), f"中枢方向应为'向上'或'向下'，实际: {zs['direction']}"

    def test_zs_bi_count(self, raw_bars):
        _, _, _, zs_data, _, _, _ = run_czsc_analysis(raw_bars)
        for zs in zs_data:
            assert zs["bi_count"] >= 1, f"中枢应包含至少1笔"


@pytest.mark.integration
class Test688110BC:
    def test_bc_count_positive(self, raw_bars):
        czsc_obj = CZSC(raw_bars, max_bi_num=10000)
        bc_data = compute_bc_markers(czsc_obj.finished_bis)
        assert len(bc_data) > 0, f"688110 在 {SDT}~{EDT} 区间应检测到背驰点，实际: {len(bc_data)}"

    def test_bc_data_structure(self, raw_bars):
        czsc_obj = CZSC(raw_bars, max_bi_num=10000)
        bc_data = compute_bc_markers(czsc_obj.finished_bis)
        for bc in bc_data:
            assert "dt" in bc
            assert "price" in bc
            assert "bc_type" in bc
            assert bc["bc_type"] in ("下跌背驰", "上涨背驰")
            assert isinstance(bc["price"], (int, float))
            assert bc["price"] > 0

    def test_bc_both_types(self, raw_bars):
        czsc_obj = CZSC(raw_bars, max_bi_num=10000)
        bc_data = compute_bc_markers(czsc_obj.finished_bis)
        types = {bc["bc_type"] for bc in bc_data}
        assert "下跌背驰" in types or "上涨背驰" in types, "应检测到至少一种背驰类型"

    def test_bc_direction_consistency(self, raw_bars):
        czsc_obj = CZSC(raw_bars, max_bi_num=10000)
        bc_data = compute_bc_markers(czsc_obj.finished_bis)
        bi_list = czsc_obj.bi_list

        for bc in bc_data:
            bi_idx = next(i for i, bi in enumerate(bi_list) if bi.fx_b.dt == bc["dt"])
            if bc["bc_type"] == "下跌背驰":
                assert bi_list[bi_idx].direction.value == "向下", (
                    f"下跌背驰应出现在向下笔末端, dt={bc['dt']}"
                )
            elif bc["bc_type"] == "上涨背驰":
                assert bi_list[bi_idx].direction.value == "向上", (
                    f"上涨背驰应出现在向上笔末端, dt={bc['dt']}"
                )


@pytest.mark.integration
class Test688110RoundTrip:
    def test_raw_bars_to_dicts_round_trip(self, raw_bars):
        bar_dicts = _raw_bars_to_dicts(raw_bars)
        reconstructed = _dicts_to_raw_bars(bar_dicts)
        assert len(reconstructed) == len(raw_bars)

    def test_analysis_consistent_after_round_trip(self, raw_bars):
        _, _, _, _, bi_count1, fx_count1, zs_count1 = run_czsc_analysis(raw_bars)

        bar_dicts = _raw_bars_to_dicts(raw_bars)
        reconstructed = _dicts_to_raw_bars(bar_dicts)
        _, _, _, _, bi_count2, fx_count2, zs_count2 = run_czsc_analysis(reconstructed)

        assert bi_count1 == bi_count2, f"笔数量不一致: {bi_count1} vs {bi_count2}"
        assert fx_count1 == fx_count2, f"分型数量不一致: {fx_count1} vs {fx_count2}"
        assert zs_count1 == zs_count2, f"中枢数量不一致: {zs_count1} vs {zs_count2}"
