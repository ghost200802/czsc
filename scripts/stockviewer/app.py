"""
股票K线分析查看器

使用方法：
    streamlit run scripts/stockviewer/app.py
"""

import hashlib
from datetime import datetime
from pathlib import Path

import streamlit as st

from czsc.connectors import bs_connector, ts_connector
from czsc.core import CZSC, Freq, RawBar
from czsc.utils.echarts_plot import trading_view_kline

from scripts.stockviewer.bs_strategies import compute_bs_points, get_available_strategies

TUSHARE_URL = "http://api.tushare.pro"


def _get_token_file_path():
    hash_key = hashlib.md5(str(TUSHARE_URL).encode("utf-8")).hexdigest()
    return Path.home() / f"{hash_key}.txt"


def _read_tushare_token(_token_file=None):
    file_token = _token_file or _get_token_file_path()
    if file_token.exists():
        return file_token.read_text(encoding="utf-8").strip()
    return None


def _raw_bars_to_dicts(raw_bars):
    return [bar.__dict__ for bar in raw_bars]


def _dicts_to_raw_bars(bar_dicts):
    raw_bars = []
    for i, d in enumerate(bar_dicts):
        freq = d["freq"]
        if isinstance(freq, str):
            freq = Freq(freq)
        bar = RawBar(
            symbol=d["symbol"],
            id=d["id"],
            dt=d["dt"],
            freq=freq,
            open=d["open"],
            close=d["close"],
            high=d["high"],
            low=d["low"],
            vol=d["vol"],
            amount=d["amount"],
        )
        raw_bars.append(bar)
    return raw_bars


@st.cache_data
def fetch_stock_data(symbol, freq, sdt, edt, fq, _token_available):
    errors = []

    if _token_available:
        ts_symbol = f"{symbol}#E"
        try:
            raw_bars = ts_connector.get_raw_bars(ts_symbol, freq, sdt, edt, fq=fq)
            if raw_bars:
                return _raw_bars_to_dicts(raw_bars), "Tushare", ""
        except Exception as e:
            errors.append(f"Tushare: {e}")

    try:
        raw_bars = bs_connector.get_raw_bars(symbol, freq, sdt, edt, fq=fq)
        if raw_bars:
            return _raw_bars_to_dicts(raw_bars), "BaoStock", "; ".join(errors) if errors else ""
    except Exception as e:
        errors.append(f"BaoStock: {e}")

    return [], None, "; ".join(errors)


def run_czsc_analysis(raw_bars):
    czsc_obj = CZSC(raw_bars, max_bi_num=10000)

    kline_data = [bar.__dict__ for bar in raw_bars]

    fx_data = [{"dt": fx.dt, "fx": fx.fx} for fx in czsc_obj.fx_list] if czsc_obj.fx_list else []

    bi_data = []
    if czsc_obj.bi_list:
        bi_data = [{"dt": bi.fx_a.dt, "bi": bi.fx_a.fx} for bi in czsc_obj.bi_list]
        bi_data.append({"dt": czsc_obj.bi_list[-1].fx_b.dt, "bi": czsc_obj.bi_list[-1].fx_b.fx})

    return kline_data, fx_data, bi_data, len(czsc_obj.bi_list), len(czsc_obj.fx_list)


def main():
    st.set_page_config(page_title="股票K线分析", page_icon="📈", layout="wide")

    st.title("📈 股票K线分析查看器")
    st.markdown("---")

    st.sidebar.header("参数配置")
    symbol = st.sidebar.text_input("股票代码", value="000001.SZ", help="支持 Tushare 格式（如 000001.SZ）或纯数字（如 000001）")
    freq = st.sidebar.selectbox("K线频率", options=["日线", "周线", "月线"], index=0)
    fq = st.sidebar.selectbox("复权方式", options=["前复权", "后复权", "不复权"], index=0)

    today_str = datetime.now().strftime("%Y%m%d")
    start_date = st.sidebar.text_input("开始日期", value="20240101")
    end_date = st.sidebar.text_input("结束日期", value=today_str)

    st.sidebar.markdown("---")
    height = st.sidebar.slider("图表高度", 400, 800, 580)
    width = st.sidebar.slider("图表宽度", 800, 1800, 1400)

    ma_periods_str = st.sidebar.text_input("均线周期", value="5, 10, 20", help="用逗号分隔多个周期")
    try:
        ma_periods = [int(p.strip()) for p in ma_periods_str.split(",") if p.strip()]
    except ValueError:
        ma_periods = [5, 10, 20]

    st.sidebar.markdown("---")
    available_strategies = get_available_strategies()
    strategy_names = [s.name for s in available_strategies]
    strategy_descriptions = {s.name: s.description for s in available_strategies}
    selected_strategies = st.sidebar.multiselect(
        "买卖点策略",
        options=strategy_names,
        default=[],
        help="选择要显示的买卖点策略，可多选",
    )
    if selected_strategies:
        st.sidebar.caption("**已选策略：**")
        for name in selected_strategies:
            st.sidebar.caption(f"  • {name}：{strategy_descriptions[name]}")

    st.sidebar.markdown("---")
    st.sidebar.info("""
    本页面展示股票K线与 CZSC 缠论分析结果：
    - **K线**：蜡烛图 + MA均线
    - **分型**：顶分型/底分型标记
    - **笔**：缠论笔的连线
    - **MACD**：副图指标
    - **买卖点**：选中策略后在图表上标记
    """)

    token = _read_tushare_token()
    token_available = bool(token)
    if not token_available:
        st.warning(
            "⚠️ 未检测到 Tushare Token，当前使用 BaoStock 数据源。"
            "如需更稳定的数据服务，请通过 `czsc.set_url_token(token='your_token', url='http://api.tushare.pro')` 设置 Token。"
        )

    if not symbol:
        st.error("请输入股票代码")
        return

    with st.spinner("正在获取数据并分析..."):
        try:
            bar_dicts, data_source, fetch_errors = fetch_stock_data(symbol, freq, start_date, end_date, fq, token_available)
        except Exception as e:
            st.error(f"数据获取失败: {e}")
            return

    if not bar_dicts:
        error_msg = "未获取到数据，请检查股票代码、日期范围或网络连接。"
        if fetch_errors:
            error_msg += f"\n\n详细错误：{fetch_errors}"
        st.error(error_msg)
        return

    if data_source == "BaoStock":
        msg = "📊 当前数据来源：**BaoStock**"
        if fetch_errors:
            msg += f"（Tushare 获取失败，已自动降级：{fetch_errors}）"
        else:
            msg += "（Tushare 不可用，已自动降级）"
        st.info(msg)
    else:
        st.success(f"📊 当前数据来源：**{data_source}**")

    try:
        raw_bars = _dicts_to_raw_bars(bar_dicts)
        kline_data, fx_data, bi_data, bi_count, fx_count = run_czsc_analysis(raw_bars)
    except Exception as e:
        st.error(f"CZSC 缠论分析失败: {e}")
        return

    bs_data = []
    if selected_strategies:
        try:
            bs_data = compute_bs_points(raw_bars, selected_strategies, start_date, freq)
        except Exception as e:
            st.warning(f"买卖点计算失败: {e}")

    last_close = bar_dicts[-1]["close"]
    first_close = bar_dicts[0]["close"]
    change_pct = (last_close - first_close) / first_close * 100

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("K线数量", f"{len(kline_data)}")
    with col2:
        st.metric("笔数量", f"{bi_count}")
    with col3:
        st.metric("分型数量", f"{fx_count}")
    with col4:
        st.metric("最新收盘价", f"{last_close:.2f}", delta=f"{change_pct:+.2f}%")

    st.markdown("---")

    try:
        chart = trading_view_kline(
            kline=kline_data,
            fx=fx_data,
            bi=bi_data,
            bs=bs_data,
            title=f"{symbol} 缠论K线分析（{data_source}）",
            t_seq=ma_periods,
            use_streamlit=True,
            width=width,
            height=height,
        )
        chart.load()
    except Exception as e:
        st.error(f"图表渲染失败: {e}")


if __name__ == "__main__":
    main()
