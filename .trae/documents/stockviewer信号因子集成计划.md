# Stockviewer 信号与因子集成计划

## 目标

将 CZSC 项目中已有的信号和因子集成到 `scripts/stockviewer` 中，增强辅助决策能力。

---

## 现状分析

### Stockviewer 已有能力

| 类别 | 已集成内容 |
|------|-----------|
| 缠论结构 | 分型(fx)、笔(bi)、中枢(zs) 识别与可视化 |
| 买卖策略(4个) | 一买一卖、二类买卖点、三类买卖点、MACD买卖点 |
| 技术指标 | MA 均线（可配置周期）、MACD 副图 |
| 背驰检测 | 简单笔力度背驰（阈值 0.8） |
| 可视化 | K线蜡烛图 + 副图指标 |

---

## 第一步：新增买卖点策略（零成本，直接注册 BSStrategy）

### 修改文件
- `scripts/stockviewer/bs_strategies.py` — 在 `_STRATEGIES` 列表中追加

### 新增策略清单

| # | 策略名称 | 信号函数 | 功能说明 | signals_config_template | key_patterns |
|---|---------|---------|---------|----------------------|-------------|
| 1 | MACD 二次背驰 | `tas_macd_second_bs_V221201` | MACD 二次背驰买卖点，过滤假信号 | `[{"name": "czsc.signals.tas_macd_second_bs_V221201", "freq": "{freq}", "di": 1, "fastperiod": 12, "slowperiod": 26, "signalperiod": 9}]` | `[("BS2辅助V221201", "二买", "二卖")]` |
| 2 | 布林带背驰 | `tas_boll_bc_V221118` | 布林带收窄后的背驰信号 | `[{"name": "czsc.signals.tas_boll_bc_V221118", "freq": "{freq}", "di": 1}]` | 需确认具体 key 格式 |
| 3 | KDJ 超买超卖 | `tas_kdj_base_V221101` | KDJ 基础超买超卖信号 | `[{"name": "czsc.signals.tas_kdj_base_V221101", "freq": "{freq}", "di": 1}]` | 需确认具体 key 格式 |
| 4 | RSI 超买超卖 | `tas_rsi_base_V230227` | RSI 基础超买超卖信号 | `[{"name": "czsc.signals.tas_rsi_base_V230227", "freq": "{freq}", "di": 1}]` | 需确认具体 key 格式 |
| 5 | 压力支撑位 | `pressure_support_V240222` | 关键压力/支撑价位标记 | `[{"name": "czsc.signals.pressure_support_V240222", "freq": "{freq}", "di": 1}]` | 需确认具体 key 格式 |
| 6 | 自定义 MACD 背驰 | `zdy_macd_bc_V230422` | 增强版 MACD 背驰 | `[{"name": "czsc.signals.zdy_macd_bc_V230422", "freq": "{freq}", "di": 1}]` | 需确认具体 key 格式 |

### 实施细节

1. 逐一阅读上述信号函数源码，确认：
   - 函数签名（kwargs 参数）
   - 返回的 key 格式和 value 取值
   - 信号触发条件（buy/sell 对应的 value）
2. 为每个信号创建 `BSStrategy` 实例，填入正确的 `signals_config_template` 和 `key_patterns`
3. 追加到 `_STRATEGIES` 列表
4. 无需修改 `app.py`，因为策略选择是动态从 `_STRATEGIES` 读取的

---

## 第二步：新增均线系统策略

### 修改文件
- `scripts/stockviewer/bs_strategies.py`

### 新增策略清单

| # | 策略名称 | 信号函数 | 功能说明 |
|---|---------|---------|---------|
| 7 | 均线多头排列 | `tas_ma_system_V230513` | 多条均线呈多头排列，趋势确认 |
| 8 | 均线粘合 | `tas_ma_cohere_V230512` | 多条均线粘合，变盘前兆 |
| 9 | 布林带变盘 | `tas_boll_vt_V230212` | 布林带收窄变盘信号 |
| 10 | 成交量双均线 | `vol_double_ma_V230313` | 成交量短期均线上穿/下穿长期均线 |

### 实施细节

与第一步相同，需先阅读信号源码确认 key_patterns。

---

## 第三步：增加技术指标副图

### 修改文件
- `scripts/stockviewer/app.py` — 添加 sidebar 控件和指标计算逻辑
- `czsc/utils/echarts_plot.py`（可能）— 如果 `trading_view_kline` 需要扩展支持新副图

### 新增指标

| # | 指标 | 来源函数 | 显示方式 | sidebar 控件 |
|---|------|---------|---------|-------------|
| 1 | RSI | `czsc.utils.ta.RSI(close, period=14)` | 副图（0-100 区间） | checkbox "显示 RSI" |
| 2 | KDJ | `czsc.utils.ta.KDJ(high, low, close)` | 副图（K/D/J 三线） | checkbox "显示 KDJ" |
| 3 | BOLL | `czsc.utils.ta.BOLL(close, period=20, std_dev=2)` | 主图叠加（上中下轨） | checkbox "显示布林带" |
| 4 | ATR | `czsc.utils.ta.ATR(high, low, close)` | 副图 | checkbox "显示 ATR" |

### 实施细节

1. 检查 `trading_view_kline` 是否已原生支持 RSI/KDJ/BOLL/ATR 副图参数
2. 如果不支持，需要在 `echarts_plot.py` 的 `kline_pro` 函数中扩展副图支持
3. 在 `app.py` 中添加 sidebar checkbox 控件
4. 计算指标数据并传入 `trading_view_kline`

---

## 第四步：量价因子面板

### 修改文件
- `scripts/stockviewer/app.py` — 添加因子计算和显示逻辑

### 新增因子

| # | 因子 | 来源 | 功能 | 显示方式 |
|---|------|------|------|---------|
| 1 | VPF001 | `czsc.features.vpf` | 开收盘价与高低价中点关系 → 市场强弱 | st.metric 或表格 |
| 2 | VPF002 | `czsc.features.vpf` | 过去收益率+高低价关系 → 方向判断 | st.metric 或表格 |
| 3 | VPF003 | `czsc.features.vpf` | N天高低价与开收盘比例 → 趋势判断 | st.metric 或表格 |
| 4 | VPF004 | `czsc.features.vpf` | Triple EMA → 平滑趋势 | 可叠加为均线 |
| 5 | VWAP | `czsc.eda.vwap` | 成交量加权均价 | 叠加到 K 线主图 |

### 实施细节

1. 在 sidebar 添加 "显示量价因子" checkbox
2. 调用 VPF 因子函数计算最新因子值
3. 用 `st.metric` 显示最新因子状态
4. VWAP 如果 `trading_view_kline` 支持则叠加，否则用 st.line_chart 单独展示

---

## 第五步：多指标共振策略（进阶）

### 修改文件
- `scripts/stockviewer/bs_strategies.py`

### 新增策略

| # | 策略名称 | 信号函数 | 功能说明 |
|---|---------|---------|---------|
| 11 | 多指标共振 | `coo_cci_kdj_sar_V230510` | CCI+KDJ+SAR 多指标共振 |
| 12 | K线突破 | `bar_break_V240309` 系列 | 价格突破信号 |
| 13 | 三星线 | `jcc_san_xing_xian_V230711` | 三星线 K 线组合形态 |
| 14 | OBV 能量潮 | `ang_obv_V230412` | OBV 能量潮方向 |

### 实施细节

与第一步相同，需先阅读信号源码确认参数和 key_patterns。

---

## 不适合集成的因子

| 因子 | 来源 | 原因 |
|------|------|------|
| RET001-RET008 | `czsc.features.ret` | 包含未来信息，只能用于回测研究 |

---

## 实施优先级总结

| 优先级 | 步骤 | 改动量 | 价值 |
|--------|------|--------|------|
| P0 | 第一步：新增买卖点策略 | 仅修改 bs_strategies.py | 高 — 直接增加交易信号 |
| P1 | 第二步：均线系统策略 | 仅修改 bs_strategies.py | 中 — 趋势确认辅助 |
| P2 | 第三步：技术指标副图 | 修改 app.py + 可能修改 echarts_plot.py | 高 — 增强可视化分析 |
| P3 | 第四步：量价因子面板 | 修改 app.py | 中 — 量化辅助 |
| P4 | 第五步：多指标共振策略 | 修改 bs_strategies.py | 中 — 高级过滤 |
