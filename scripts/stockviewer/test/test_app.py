from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from czsc.connectors.bs_connector import _freq_to_bs, _fq_to_bs, _to_bs_code
from czsc.core import CZSC, Freq, RawBar, format_standard_kline
from czsc.mock import generate_symbol_kines


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
