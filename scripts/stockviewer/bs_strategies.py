"""买卖点策略注册表"""

from dataclasses import dataclass

from czsc.py.enum import Operate
from czsc.traders.base import generate_czsc_signals


@dataclass
class BSStrategy:
    name: str
    description: str
    signals_config_template: list[dict]
    key_patterns: list[tuple]

    def get_signals_config(self, freq_str: str) -> list[dict]:
        result = []
        for sc in self.signals_config_template:
            item = {}
            for k, v in sc.items():
                if isinstance(v, str) and "{freq}" in v:
                    item[k] = v.format(freq=freq_str)
                else:
                    item[k] = v
            result.append(item)
        return result


_STRATEGIES: list[BSStrategy] = [
    BSStrategy(
        name="一买一卖",
        description="缠论一买一卖信号（背驰判断）",
        signals_config_template=[
            {"name": "czsc.signals.cxt_first_buy_V221126", "freq": "{freq}", "di": 1},
            {"name": "czsc.signals.cxt_first_sell_V221126", "freq": "{freq}", "di": 1},
        ],
        key_patterns=[("D1B_BUY1", "一买", None), ("D1B_SELL1", None, "一卖")],
    ),
    BSStrategy(
        name="二类买卖点",
        description="均线辅助二类买卖点",
        signals_config_template=[
            {
                "name": "czsc.signals.cxt_second_bs_V230320",
                "freq": "{freq}",
                "di": 1,
                "ma_type": "SMA",
                "timeperiod": 21,
            },
        ],
        key_patterns=[("BS2辅助V230320", "二买", "二卖")],
    ),
    BSStrategy(
        name="三类买卖点",
        description="均线辅助三类买卖点（含均线形态）",
        signals_config_template=[
            {
                "name": "czsc.signals.cxt_third_bs_V230319",
                "freq": "{freq}",
                "di": 1,
                "ma_type": "SMA",
                "timeperiod": 34,
            },
        ],
        key_patterns=[("BS3辅助V230319", "三买", "三卖")],
    ),
    BSStrategy(
        name="MACD 买卖点",
        description="MACD 背驰一买一卖",
        signals_config_template=[
            {
                "name": "czsc.signals.tas_macd_first_bs_V221201",
                "freq": "{freq}",
                "di": 1,
                "fastperiod": 12,
                "slowperiod": 26,
                "signalperiod": 9,
            },
        ],
        key_patterns=[("BS1辅助V221201", "一买", "一卖")],
    ),
]


def get_available_strategies() -> list[BSStrategy]:
    return list(_STRATEGIES)


def compute_bs_points(raw_bars, selected_strategy_names, sdt, freq_str):
    if not selected_strategy_names or not raw_bars:
        return []

    all_config = []
    key_patterns = []
    for strategy in _STRATEGIES:
        if strategy.name in selected_strategy_names:
            all_config.extend(strategy.get_signals_config(freq_str))
            key_patterns.extend(strategy.key_patterns)

    seen = set()
    deduped_config = []
    for sc in all_config:
        key = (sc["name"], tuple(sorted((k, v) for k, v in sc.items() if k != "name")))
        if key not in seen:
            seen.add(key)
            deduped_config.append(sc)

    sigs = generate_czsc_signals(raw_bars, deduped_config, sdt=sdt, df=False)

    bs = []
    last_valid = {}
    for sig in sigs:
        for key_contains, buy_v1, sell_v1 in key_patterns:
            for sig_key, sig_value in sig.items():
                if key_contains in sig_key and isinstance(sig_value, str):
                    parts = sig_value.split("_")
                    v1 = parts[0] if parts else ""
                    if (buy_v1 and v1 == buy_v1) or (sell_v1 and v1 == sell_v1):
                        if last_valid.get(sig_key) != v1:
                            last_valid[sig_key] = v1
                            op = Operate.LO if (buy_v1 and v1 == buy_v1) else Operate.LE
                            bs.append(
                                {
                                    "dt": sig["dt"],
                                    "price": sig["close"],
                                    "op": op,
                                    "op_desc": v1,
                                }
                            )
                    else:
                        last_valid.pop(sig_key, None)

    return bs
