"""
author: zengbin93
email: zeng_bin8888@163.com
create_dt: 2025/4/16 10:00
describe: BaoStock数据源

BaoStock 是一个免费、开源的证券数据平台，无需注册 Token。
官网：http://baostock.com
"""

import re

import baostock as bs
import pandas as pd
from loguru import logger

from czsc import Freq, RawBar


def _to_bs_code(symbol: str) -> str:
    """将股票代码转换为 BaoStock 格式

    支持两种输入格式：
    - BaoStock 格式：sh.600000、sz.000001
    - Tushare 格式：600000.SH、000001.SZ

    :param symbol: 股票代码
    :return: BaoStock 格式的股票代码，如 sh.600000
    """
    symbol = symbol.strip()
    if re.match(r"^(sh|sz)\.\d{6}$", symbol, re.IGNORECASE):
        return symbol.lower()
    if re.match(r"^\d{6}\.(SH|SZ)$", symbol, re.IGNORECASE):
        parts = symbol.split(".")
        return f"{parts[1].lower()}.{parts[0]}"
    if re.match(r"^\d{6}$", symbol):
        code = int(symbol)
        if code >= 600000:
            return f"sh.{symbol}"
        return f"sz.{symbol}"
    raise ValueError(f"无法识别的股票代码格式: {symbol}")


def _freq_to_bs(freq: Freq) -> str:
    """将 CZSC Freq 枚举转换为 BaoStock 的 frequency 参数

    :param freq: CZSC 周期枚举
    :return: BaoStock frequency 参数值
    """
    freq_map = {
        Freq.D: "d",
        Freq.W: "w",
        Freq.M: "m",
        Freq.F5: "5",
        Freq.F15: "15",
        Freq.F30: "30",
        Freq.F60: "60",
    }
    if freq not in freq_map:
        raise ValueError(f"BaoStock 不支持的周期: {freq.value}，仅支持 日线/周线/月线/5分钟/15分钟/30分钟/60分钟")
    return freq_map[freq]


def _fq_to_bs(fq: str) -> str:
    """将复权方式转换为 BaoStock 的 adjustflag 参数

    :param fq: 复权方式，可选值：'前复权', '后复权', '不复权'
    :return: BaoStock adjustflag 参数值
    """
    fq_map = {"前复权": "2", "后复权": "1", "不复权": "3"}
    if fq not in fq_map:
        raise ValueError(f"不支持的复权方式: {fq}，可选值: '前复权', '后复权', '不复权'")
    return fq_map[fq]


def format_kline(kline: pd.DataFrame, freq: Freq) -> list[RawBar]:
    """BaoStock K线数据转换

    :param kline: BaoStock 数据接口返回的K线数据
    :param freq: K线周期
    :return: 转换好的K线数据
    """
    bars = []
    kline = kline.sort_values("date", ascending=True, ignore_index=True)
    records = kline.to_dict("records")

    for i, record in enumerate(records):
        vol = float(record["volume"]) if record["volume"] else 0
        amount = float(record["amount"]) if record["amount"] else 0

        bar = RawBar(
            symbol=record["code"],
            dt=pd.to_datetime(record["date"]),
            id=i,
            freq=freq,
            open=float(record["open"]),
            close=float(record["close"]),
            high=float(record["high"]),
            low=float(record["low"]),
            vol=vol,
            amount=amount,
        )
        bars.append(bar)
    return bars


def get_symbols(day: str = "", **kwargs) -> list[str]:
    """获取标的代码列表

    :param day: 交易日期，格式为 YYYY-MM-DD，为空则获取最新交易日数据
    :return: BaoStock 格式的股票代码列表
    """
    lg = bs.login()
    if lg.error_code != "0":
        logger.error(f"BaoStock 登录失败: {lg.error_msg}")
        return []

    try:
        rs = bs.query_all_stock(day=day)
        if rs.error_code != "0":
            logger.error(f"获取股票列表失败: {rs.error_msg}")
            return []

        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())

        df = pd.DataFrame(rows, columns=rs.fields)
        symbols = df["code"].tolist()
        logger.info(f"获取到 {len(symbols)} 个标的代码")
        return symbols
    finally:
        bs.logout()


def get_raw_bars(symbol, freq, sdt, edt, fq="前复权", raw_bar: bool = True, **kwargs):
    """获取K线数据

    :param symbol: 股票代码，支持 BaoStock 格式（sh.600000）和 Tushare 格式（600000.SH）
    :param freq: K线周期，支持 Freq 枚举或字符串，如 Freq.D、'日线'、Freq.F60、'60分钟'
    :param sdt: 开始日期，格式为 YYYYMMDD 或 YYYY-MM-DD
    :param edt: 结束日期，格式为 YYYYMMDD 或 YYYY-MM-DD
    :param fq: 复权方式，可选值：'前复权', '后复权', '不复权'，默认为 '前复权'
    :param raw_bar: 是否返回 RawBar 对象列表，默认为 True；为 False 时返回 DataFrame
    :return: list[RawBar] 或 DataFrame
    """
    bs_code = _to_bs_code(symbol)
    freq = Freq(freq)
    bs_freq = _freq_to_bs(freq)
    adjustflag = _fq_to_bs(fq)

    sdt = pd.to_datetime(sdt).strftime("%Y-%m-%d")
    edt = pd.to_datetime(edt).strftime("%Y-%m-%d")

    fields = "date,code,open,high,low,close,volume,amount,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST"

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"BaoStock 登录失败: {lg.error_msg}")

    try:
        rs = bs.query_history_k_data_plus(
            code=bs_code,
            fields=fields,
            start_date=sdt,
            end_date=edt,
            frequency=bs_freq,
            adjustflag=adjustflag,
        )

        if rs.error_code != "0":
            raise RuntimeError(f"获取K线数据失败: {rs.error_msg}")

        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            logger.warning(f"未获取到数据: {bs_code} {freq.value} {sdt} ~ {edt}")
            return [] if raw_bar else pd.DataFrame()

        df = pd.DataFrame(rows, columns=rs.fields)

        numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        df = df[df["tradestatus"] == "1"].copy()
        df = df.drop(columns=["tradestatus"], errors="ignore")

        if df.empty:
            logger.warning(f"过滤停牌后无数据: {bs_code} {freq.value} {sdt} ~ {edt}")
            return [] if raw_bar else pd.DataFrame()

        logger.info(f"获取 {bs_code} {freq.value} K线数据，时间范围：{sdt} ~ {edt}，数据量：{len(df)}")

        if raw_bar:
            return format_kline(df, freq)
        return df
    finally:
        bs.logout()
