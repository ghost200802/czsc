from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from czsc.py import (
        BI as BI,
        CZSC as CZSC,
        FX as FX,
        ZS as ZS,
        BarGenerator as BarGenerator,
        Direction as Direction,
        Event as Event,
        FakeBI as FakeBI,
        Freq as Freq,
        Mark as Mark,
        NewBar as NewBar,
        Operate as Operate,
        Position as Position,
        RawBar as RawBar,
        Signal as Signal,
    )
    try:
        from rs_czsc import WeightBacktest as WeightBacktest
    except ImportError:
        WeightBacktest = None

from czsc.py import (
    check_bi as check_bi,
)
from czsc.py import (
    check_fx as check_fx,
)
from czsc.py import (
    check_fxs as check_fxs,
)
from czsc.py import (
    freq_end_time as freq_end_time,
)
from czsc.py import (
    is_trading_time as is_trading_time,
)
from czsc.py import (
    remove_include as remove_include,
)
from czsc.utils.analysis.stats import cal_break_even_point as cal_break_even_point

__all__ = [
    "Operate",
    "Freq",
    "Mark",
    "Direction",
    "CZSC",
    "remove_include",
    "check_bi",
    "check_fx",
    "check_fxs",
    "BarGenerator",
    "freq_end_time",
    "is_trading_time",
    "format_standard_kline",
    "RawBar",
    "NewBar",
    "FX",
    "BI",
    "FakeBI",
    "ZS",
    "Signal",
    "Event",
    "Position",
    "WeightBacktest",
    "check_rs_czsc",
    "cal_break_even_point",
]

def check_rs_czsc() -> tuple[bool, str | None]: ...
def format_standard_kline(bars: list[RawBar], df=None, freqs=None) -> list[RawBar]: ...
