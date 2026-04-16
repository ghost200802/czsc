from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from czsc.connectors.bs_connector import _freq_to_bs, _fq_to_bs, _to_bs_code
from czsc.core import CZSC, Freq, RawBar, format_standard_kline
from czsc.mock import generate_symbol_kines
from czsc.py.enum import Operate


class TestFreqToBs:
    def test_freq_enum(self):
        assert _freq_to_bs(Freq.D) == "d"
        assert _freq_to_bs(Freq.W) == "w"
        assert _freq_to_bs(Freq.M) == "m"

    def test_freq_string(self):
        assert _freq_to_bs("日线") == "d"
        assert _freq_to_bs("周线") == "w"
        assert _freq_to_bs("月线") == "m"
        assert _freq_to_bs("60分钟") == "60"

    def test_unsupported_freq(self):
        with pytest.raises(ValueError, match="BaoStock 不支持的周期"):
            _freq_to_bs("1分钟")


class TestFqToBs:
    def test_all_options(self):
        assert _fq_to_bs("前复权") == "2"
        assert _fq_to_bs("后复权") == "1"
        assert _fq_to_bs("不复权") == "3"

    def test_unsupported_fq(self):
        with pytest.raises(ValueError, match="不支持的复权方式"):
            _fq_to_bs("无效")


class TestToBsCode:
    def test_tushare_format(self):
        assert _to_bs_code("000001.SZ") == "sz.000001"
        assert _to_bs_code("600000.SH") == "sh.600000"

    def test_baostock_format(self):
        assert _to_bs_code("sh.600000") == "sh.600000"
        assert _to_bs_code("SZ.000001") == "sz.000001"

    def test_pure_number(self):
        assert _to_bs_code("600000") == "sh.600000"
        assert _to_bs_code("000001") == "sz.000001"

    def test_invalid(self):
        with pytest.raises(ValueError):
            _to_bs_code("INVALID")


class TestReadTushareToken:
    def test_token_file_exists(self, tmp_path, monkeypatch):
        import hashlib
        from pathlib import Path

        token = "test_token_123"
        url = "http://api.tushare.pro"
        hash_key = hashlib.md5(str(url).encode("utf-8")).hexdigest()
        token_file = tmp_path / f"{hash_key}.txt"
        token_file.write_text(token, encoding="utf-8")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        from scripts.stockviewer.app import _read_tushare_token

        assert _read_tushare_token() == token

    def test_token_file_not_exists(self, tmp_path, monkeypatch):
        from pathlib import Path

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        from scripts.stockviewer.app import _read_tushare_token

        assert _read_tushare_token() is None


class TestFetchStockData:
    def _make_raw_bars(self, n=10):
        df = generate_symbol_kines("000001", "日线", "20240101", "20240601", seed=42)
        return format_standard_kline(df, freq=Freq.D)[:n]

    def test_tushare_success(self):
        from scripts.stockviewer.app import fetch_stock_data

        mock_bars = self._make_raw_bars(5)
        with patch("scripts.stockviewer.app.ts_connector") as mock_ts:
            mock_ts.get_raw_bars.return_value = mock_bars
            bars, source, errors = fetch_stock_data("000001.SZ", "日线", "20240101", "20240416", "前复权", True)
            assert source == "Tushare"
            assert len(bars) == 5
            assert errors == ""

    def test_tushare_fail_baostock_success(self):
        from scripts.stockviewer.app import fetch_stock_data

        mock_bars = self._make_raw_bars(5)
        with (
            patch("scripts.stockviewer.app.ts_connector") as mock_ts,
            patch("scripts.stockviewer.app.bs_connector") as mock_bs,
        ):
            mock_ts.get_raw_bars.side_effect = Exception("Tushare API error")
            mock_bs.get_raw_bars.return_value = mock_bars
            bars, source, errors = fetch_stock_data("000001.SZ", "日线", "20240101", "20240416", "前复权", True)
            assert source == "BaoStock"
            assert len(bars) == 5
            assert "Tushare API error" in errors

    def test_both_fail(self):
        from scripts.stockviewer.app import fetch_stock_data

        with (
            patch("scripts.stockviewer.app.ts_connector") as mock_ts,
            patch("scripts.stockviewer.app.bs_connector") as mock_bs,
        ):
            mock_ts.get_raw_bars.side_effect = Exception("Tushare error")
            mock_bs.get_raw_bars.side_effect = Exception("BaoStock error")
            bars, source, errors = fetch_stock_data("000001.SZ", "日线", "20240101", "20240416", "前复权", True)
            assert bars == []
            assert source is None
            assert "Tushare error" in errors
            assert "BaoStock error" in errors

    def test_token_unavailable_skip_tushare(self):
        from scripts.stockviewer.app import fetch_stock_data

        mock_bars = self._make_raw_bars(5)
        with (
            patch("scripts.stockviewer.app.ts_connector") as mock_ts,
            patch("scripts.stockviewer.app.bs_connector") as mock_bs,
        ):
            mock_bs.get_raw_bars.return_value = mock_bars
            bars, source, errors = fetch_stock_data("000001.SZ", "日线", "20240101", "20240416", "前复权", False)
            assert source == "BaoStock"
            mock_ts.get_raw_bars.assert_not_called()

    def test_tushare_returns_empty_fallback_to_baostock(self):
        from scripts.stockviewer.app import fetch_stock_data

        mock_bars = self._make_raw_bars(5)
        with (
            patch("scripts.stockviewer.app.ts_connector") as mock_ts,
            patch("scripts.stockviewer.app.bs_connector") as mock_bs,
        ):
            mock_ts.get_raw_bars.return_value = []
            mock_bs.get_raw_bars.return_value = mock_bars
            bars, source, errors = fetch_stock_data("000001.SZ", "日线", "20240101", "20240416", "前复权", True)
            assert source == "BaoStock"
            assert len(bars) == 5


class TestRunCzscAnalysis:
    def _make_raw_bars(self, n=200):
        df = generate_symbol_kines("000001", "日线", "20220101", "20250101", seed=42)
        return format_standard_kline(df, freq=Freq.D)[:n]

    def test_basic_analysis(self):
        from scripts.stockviewer.app import run_czsc_analysis

        raw_bars = self._make_raw_bars(200)
        kline_data, fx_data, bi_data, bi_count, fx_count = run_czsc_analysis(raw_bars)

        assert len(kline_data) == 200
        assert bi_count >= 0
        assert fx_count >= 0
        assert isinstance(bi_data, list)
        assert isinstance(fx_data, list)

    def test_kline_data_structure(self):
        from scripts.stockviewer.app import run_czsc_analysis

        raw_bars = self._make_raw_bars(50)
        kline_data, _, _, _, _ = run_czsc_analysis(raw_bars)

        for item in kline_data:
            assert "dt" in item
            assert "open" in item
            assert "close" in item
            assert "high" in item
            assert "low" in item
            assert "vol" in item

    def test_fx_data_structure(self):
        from scripts.stockviewer.app import run_czsc_analysis

        raw_bars = self._make_raw_bars(200)
        _, fx_data, _, _, _ = run_czsc_analysis(raw_bars)

        for item in fx_data:
            assert "dt" in item
            assert "fx" in item

    def test_bi_data_structure(self):
        from scripts.stockviewer.app import run_czsc_analysis

        raw_bars = self._make_raw_bars(200)
        _, _, bi_data, _, _ = run_czsc_analysis(raw_bars)

        for item in bi_data:
            assert "dt" in item
            assert "bi" in item


class TestDictsToRawBars:
    def _make_bar_dicts(self, n=5, freq_as_str=False):
        df = generate_symbol_kines("000001", "日线", "20240101", "20240601", seed=42)
        bars = format_standard_kline(df, freq=Freq.D)[:n]
        dicts = [bar.__dict__.copy() for bar in bars]
        if freq_as_str:
            for d in dicts:
                f = d["freq"]
                d["freq"] = f.value if hasattr(f, "value") else str(f)
        return dicts

    def test_freq_as_enum(self):
        from scripts.stockviewer.app import _dicts_to_raw_bars

        bar_dicts = self._make_bar_dicts(5, freq_as_str=False)
        raw_bars = _dicts_to_raw_bars(bar_dicts)
        assert len(raw_bars) == 5
        for bar in raw_bars:
            assert isinstance(bar.freq, Freq)
            assert bar.freq == Freq.D

    def test_freq_as_string(self):
        from scripts.stockviewer.app import _dicts_to_raw_bars

        bar_dicts = self._make_bar_dicts(5, freq_as_str=True)
        raw_bars = _dicts_to_raw_bars(bar_dicts)
        assert len(raw_bars) == 5
        for bar in raw_bars:
            assert isinstance(bar.freq, Freq)
            assert bar.freq == Freq.D

    def test_round_trip_with_czsc_analysis(self):
        from scripts.stockviewer.app import _dicts_to_raw_bars, _raw_bars_to_dicts, run_czsc_analysis

        df = generate_symbol_kines("000001", "日线", "20220101", "20250101", seed=42)
        original_bars = format_standard_kline(df, freq=Freq.D)[:200]

        dicts = _raw_bars_to_dicts(original_bars)
        for d in dicts:
            f = d["freq"]
            d["freq"] = f.value if hasattr(f, "value") else str(f)

        reconstructed_bars = _dicts_to_raw_bars(dicts)
        kline_data, fx_data, bi_data, bi_count, fx_count = run_czsc_analysis(reconstructed_bars)

        assert len(kline_data) == 200
        assert bi_count >= 0
        assert fx_count >= 0
        assert isinstance(fx_data, list)
        assert isinstance(bi_data, list)


class TestBSStrategies:
    def test_get_available_strategies(self):
        from scripts.stockviewer.bs_strategies import get_available_strategies

        strategies = get_available_strategies()
        assert len(strategies) == 4
        names = [s.name for s in strategies]
        assert "一买一卖" in names
        assert "二类买卖点" in names
        assert "三类买卖点" in names
        assert "MACD 买卖点" in names

    def test_strategy_has_required_fields(self):
        from scripts.stockviewer.bs_strategies import get_available_strategies

        for strategy in get_available_strategies():
            assert strategy.name
            assert strategy.description
            assert len(strategy.signals_config_template) > 0
            assert len(strategy.key_patterns) > 0

    def test_strategy_get_signals_config_replaces_freq(self):
        from scripts.stockviewer.bs_strategies import get_available_strategies

        for strategy in get_available_strategies():
            config = strategy.get_signals_config("日线")
            for sc in config:
                assert sc["freq"] == "日线"
                assert "{freq}" not in sc["freq"]

    def test_strategy_get_signals_config_different_freq(self):
        from scripts.stockviewer.bs_strategies import get_available_strategies

        for strategy in get_available_strategies():
            for freq_str in ["周线", "月线"]:
                config = strategy.get_signals_config(freq_str)
                for sc in config:
                    assert sc["freq"] == freq_str


class TestComputeBsPoints:
    def _make_raw_bars(self, n=200):
        df = generate_symbol_kines("000001", "日线", "20220101", "20250101", seed=42)
        return format_standard_kline(df, freq=Freq.D)[:n]

    def test_empty_selection(self):
        from scripts.stockviewer.bs_strategies import compute_bs_points

        raw_bars = self._make_raw_bars(200)
        bs = compute_bs_points(raw_bars, [], "20240101", "日线")
        assert bs == []

    def test_empty_raw_bars(self):
        from scripts.stockviewer.bs_strategies import compute_bs_points

        bs = compute_bs_points([], ["一买一卖"], "20240101", "日线")
        assert bs == []

    def test_no_signals_found(self):
        from scripts.stockviewer.bs_strategies import compute_bs_points

        raw_bars = self._make_raw_bars(200)
        mock_sigs = [
            {"dt": datetime(2024, 3, 15), "close": 15.5, "日线_D1B_BUY1": "其他_任意_任意_0"},
            {"dt": datetime(2024, 4, 10), "close": 17.8, "日线_D1B_BUY1": "其他_任意_任意_0"},
        ]
        with patch("scripts.stockviewer.bs_strategies.generate_czsc_signals", return_value=mock_sigs):
            bs = compute_bs_points(raw_bars, ["一买一卖"], "20240101", "日线")
        assert bs == []

    def test_buy_signals_detected(self):
        from scripts.stockviewer.bs_strategies import compute_bs_points

        raw_bars = self._make_raw_bars(200)
        mock_sigs = [
            {
                "dt": datetime(2024, 3, 15),
                "close": 15.5,
                "日线_D1B_BUY1": "一买_5笔_任意_0",
                "日线_D1B_SELL1": "其他_任意_任意_0",
            },
        ]
        with patch("scripts.stockviewer.bs_strategies.generate_czsc_signals", return_value=mock_sigs):
            bs = compute_bs_points(raw_bars, ["一买一卖"], "20240101", "日线")
        assert len(bs) == 1
        assert bs[0]["op"] == Operate.LO
        assert bs[0]["op_desc"] == "一买"
        assert bs[0]["price"] == 15.5
        assert bs[0]["dt"] == datetime(2024, 3, 15)

    def test_sell_signals_detected(self):
        from scripts.stockviewer.bs_strategies import compute_bs_points

        raw_bars = self._make_raw_bars(200)
        mock_sigs = [
            {
                "dt": datetime(2024, 4, 10),
                "close": 17.8,
                "日线_D1B_BUY1": "其他_任意_任意_0",
                "日线_D1B_SELL1": "一卖_7笔_任意_0",
            },
        ]
        with patch("scripts.stockviewer.bs_strategies.generate_czsc_signals", return_value=mock_sigs):
            bs = compute_bs_points(raw_bars, ["一买一卖"], "20240101", "日线")
        assert len(bs) == 1
        assert bs[0]["op"] == Operate.LE
        assert bs[0]["op_desc"] == "一卖"

    def test_multiple_signals_across_strategies(self):
        from scripts.stockviewer.bs_strategies import compute_bs_points

        raw_bars = self._make_raw_bars(200)
        mock_sigs = [
            {
                "dt": datetime(2024, 3, 15),
                "close": 15.5,
                "日线_D1B_BUY1": "一买_5笔_任意_0",
                "日线_D1B_SELL1": "其他_任意_任意_0",
                "日线_D1#SMA#21_BS2辅助V230320": "二买_任意_任意_0",
            },
            {
                "dt": datetime(2024, 4, 10),
                "close": 17.8,
                "日线_D1B_BUY1": "其他_任意_任意_0",
                "日线_D1B_SELL1": "一卖_7笔_任意_0",
                "日线_D1#SMA#21_BS2辅助V230320": "其他_任意_任意_0",
            },
        ]
        with patch("scripts.stockviewer.bs_strategies.generate_czsc_signals", return_value=mock_sigs):
            bs = compute_bs_points(raw_bars, ["一买一卖", "二类买卖点"], "20240101", "日线")
        assert len(bs) == 3
        ops = [(b["op"], b["op_desc"]) for b in bs]
        assert (Operate.LO, "一买") in ops
        assert (Operate.LE, "一卖") in ops
        assert (Operate.LO, "二买") in ops

    def test_third_bs_signals(self):
        from scripts.stockviewer.bs_strategies import compute_bs_points

        raw_bars = self._make_raw_bars(200)
        mock_sigs = [
            {
                "dt": datetime(2024, 5, 1),
                "close": 18.0,
                "日线_D1#SMA#34_BS3辅助V230319": "三买_均线新高_任意_0",
            },
        ]
        with patch("scripts.stockviewer.bs_strategies.generate_czsc_signals", return_value=mock_sigs):
            bs = compute_bs_points(raw_bars, ["三类买卖点"], "20240101", "日线")
        assert len(bs) == 1
        assert bs[0]["op"] == Operate.LO
        assert bs[0]["op_desc"] == "三买"

    def test_macd_signals(self):
        from scripts.stockviewer.bs_strategies import compute_bs_points

        raw_bars = self._make_raw_bars(200)
        mock_sigs = [
            {
                "dt": datetime(2024, 5, 1),
                "close": 18.0,
                "日线_D1MACD12#26#9_BS1辅助V221201": "一买_任意_任意_0",
            },
        ]
        with patch("scripts.stockviewer.bs_strategies.generate_czsc_signals", return_value=mock_sigs):
            bs = compute_bs_points(raw_bars, ["MACD 买卖点"], "20240101", "日线")
        assert len(bs) == 1
        assert bs[0]["op"] == Operate.LO
        assert bs[0]["op_desc"] == "一买"

    def test_bs_format_for_chart(self):
        from scripts.stockviewer.bs_strategies import compute_bs_points

        raw_bars = self._make_raw_bars(200)
        mock_sigs = [
            {
                "dt": datetime(2024, 3, 15),
                "close": 15.5,
                "日线_D1B_BUY1": "一买_5笔_任意_0",
            },
        ]
        with patch("scripts.stockviewer.bs_strategies.generate_czsc_signals", return_value=mock_sigs):
            bs = compute_bs_points(raw_bars, ["一买一卖"], "20240101", "日线")
        for item in bs:
            assert "dt" in item
            assert "price" in item
            assert "op" in item
            assert "op_desc" in item
            assert isinstance(item["op"], Operate)
            assert isinstance(item["op_desc"], str)
