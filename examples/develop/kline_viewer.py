"""
缠论K线可视化 Streamlit 应用

使用方法：
    streamlit run examples/develop/kline_viewer.py
"""

import streamlit as st

from czsc.core import CZSC, Freq, format_standard_kline
from czsc.mock import generate_symbol_kines
from czsc.utils.echarts_plot import trading_view_kline


@st.cache_data
def get_kline_data(symbol, freq, start_date, end_date, seed):
    df = generate_symbol_kines(symbol, freq, start_date, end_date, seed=seed)
    raw_bars = format_standard_kline(df, freq=Freq.D)
    czsc_obj = CZSC(raw_bars, max_bi_num=10000)

    kline_data = [bar.__dict__ for bar in raw_bars]
    fx_data = [{"dt": fx.dt, "fx": fx.fx} for fx in czsc_obj.fx_list] if czsc_obj.fx_list else []
    bi_data = []
    if czsc_obj.bi_list:
        bi_data = [{"dt": bi.fx_a.dt, "bi": bi.fx_a.fx} for bi in czsc_obj.bi_list]
        bi_data.append({"dt": czsc_obj.bi_list[-1].fx_b.dt, "bi": czsc_obj.bi_list[-1].fx_b.fx})

    return kline_data, fx_data, bi_data, len(czsc_obj.bi_list), len(czsc_obj.fx_list)


def main():
    st.set_page_config(page_title="缠论K线分析", page_icon="📈", layout="wide")

    st.title("📈 缠论K线分析可视化")
    st.markdown("---")

    st.sidebar.header("参数配置")
    start_date = st.sidebar.text_input("开始日期", value="20200101")
    end_date = st.sidebar.text_input("结束日期", value="20240101")
    seed = st.sidebar.slider("随机种子", 1, 100, 42)
    height = st.sidebar.slider("图表高度", 400, 800, 580)
    width = st.sidebar.slider("图表宽度", 800, 1800, 1400)

    st.sidebar.markdown("---")
    st.sidebar.info("""
    本页面展示 CZSC 缠论分析结果：
    - **K线**：蜡烛图 + MA均线
    - **分型**：顶分型/底分型标记
    - **笔**：缠论笔的连线
    - **MACD**：副图指标
    """)

    kline_data, fx_data, bi_data, bi_count, fx_count = get_kline_data("test", "日线", start_date, end_date, seed)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("K线数量", f"{len(kline_data)}")
    with col2:
        st.metric("笔数量", f"{bi_count}")
    with col3:
        st.metric("分型数量", f"{fx_count}")

    st.markdown("---")

    chart = trading_view_kline(
        kline=kline_data,
        fx=fx_data,
        bi=bi_data,
        bs=[],
        title="缠中说禅K线分析",
        t_seq=[5, 10, 20],
        use_streamlit=True,
        width=width,
        height=height,
    )
    chart.load()


if __name__ == "__main__":
    main()
