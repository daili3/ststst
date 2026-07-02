"""信号规则：金叉/死叉/突破/放量/超买超卖"""
from config import SIGNAL_THRESHOLDS


def detect_macd_cross(ind: dict) -> str:
    """MACD 金叉/死叉
    判断逻辑：MACD柱 从负转正 = 金叉；从正转负 = 死叉
    Returns: "macd_golden_cross" / "macd_death_cross" / ""
    """
    cur, prev = ind.get("macd_bar", 0), ind.get("macd_prev_bar", 0)
    if prev <= 0 < cur:
        return "macd_golden_cross"
    if prev >= 0 > cur:
        return "macd_death_cross"
    return ""


def detect_ma_cross(ind: dict) -> str:
    """5日/10日均线金叉（基于价格与均线位置近似）
    判断逻辑：5日线 > 10日线 且 价格站上5日线 = 均线多头排列
    """
    ma_s, ma_m = ind.get("ma_short"), ind.get("ma_mid")
    price = ind.get("price")
    if ma_s is None or ma_m is None or price is None:
        return ""
    if ma_s > ma_m and price > ma_s:
        return "ma_bullish_align"
    if ma_s < ma_m and price < ma_s:
        return "ma_bearish_align"
    return ""


def detect_breakout_20ma(ind: dict) -> str:
    """放量突破 20 日均线"""
    ma_l = ind.get("ma_long")
    price = ind.get("price")
    prev_close = ind.get("prev_close")
    vol_ratio = ind.get("volume_ratio", 1.0)

    if ma_l is None or price is None or prev_close is None:
        return ""

    # 昨日在 20 日线下，今日站上 20 日线 + 放量
    if prev_close < ma_l and price > ma_l and vol_ratio >= SIGNAL_THRESHOLDS["volume_ratio"]:
        return "breakout_20ma_with_volume"
    return ""


def detect_volume_surge(ind: dict) -> str:
    """放量（量比超阈值，无方向信号）"""
    if ind.get("volume_ratio", 1.0) >= SIGNAL_THRESHOLDS["volume_ratio"]:
        return "volume_surge"
    return ""


def detect_kdj_extreme(ind: dict) -> str:
    """KDJ 超买/超卖"""
    j = ind.get("kdj_j", 50)
    if j > SIGNAL_THRESHOLDS["kdj_overbought"]:
        return "kdj_overbought"
    if j < SIGNAL_THRESHOLDS["kdj_oversold"]:
        return "kdj_oversold"
    return ""


def detect_rsi_extreme(ind: dict) -> str:
    """RSI 超买/超卖"""
    rsi = ind.get("rsi", 50)
    if rsi > SIGNAL_THRESHOLDS["rsi_overbought"]:
        return "rsi_overbought"
    if rsi < SIGNAL_THRESHOLDS["rsi_oversold"]:
        return "rsi_oversold"
    return ""


# 信号中文化映射
SIGNAL_LABELS = {
    "macd_golden_cross":      "✅ MACD 金叉",
    "macd_death_cross":       "🔴 MACD 死叉",
    "ma_bullish_align":       "✅ 均线多头排列（5>10 且价格站上5日线）",
    "ma_bearish_align":       "🔴 均线空头排列（5<10 且价格跌破5日线）",
    "breakout_20ma_with_volume": "✅ 放量突破20日均线",
    "volume_surge":           "⚡ 放量（量比>{threshold}）",
    "kdj_overbought":         "⚠️ KDJ 超买（J>{threshold}）短期有回调压力",
    "kdj_oversold":           "💡 KDJ 超卖（J<{threshold}）短期有反弹机会",
    "rsi_overbought":         "⚠️ RSI 超买（>{threshold}）",
    "rsi_oversold":           "💡 RSI 超卖（<{threshold}）",
}


def analyze_signals(ind: dict) -> list:
    """汇总所有信号"""
    signals = []
    for detector in [
        detect_macd_cross, detect_ma_cross, detect_breakout_20ma,
        detect_volume_surge, detect_kdj_extreme, detect_rsi_extreme,
    ]:
        sig = detector(ind)
        if sig:
            signals.append(sig)
    return signals


def format_signal(sig: str) -> str:
    """把信号代码转成中文描述"""
    label = SIGNAL_LABELS.get(sig, sig)
    # 替换阈值占位符
    if "{threshold}" in label:
        if "volume" in sig:
            label = label.format(threshold=SIGNAL_THRESHOLDS["volume_ratio"])
        elif "kdj_overbought" in sig:
            label = label.format(threshold=SIGNAL_THRESHOLDS["kdj_overbought"])
        elif "kdj_oversold" in sig:
            label = label.format(threshold=SIGNAL_THRESHOLDS["kdj_oversold"])
        elif "rsi_overbought" in sig:
            label = label.format(threshold=SIGNAL_THRESHOLDS["rsi_overbought"])
        elif "rsi_oversold" in sig:
            label = label.format(threshold=SIGNAL_THRESHOLDS["rsi_oversold"])
    return label


def signal_direction(sig: str) -> str:
    """信号方向：bull / bear / neutral"""
    if sig.startswith("macd_golden") or sig.startswith("ma_bullish") or "breakout" in sig or "oversold" in sig:
        return "bull"
    if sig.startswith("macd_death") or sig.startswith("ma_bearish") or "overbought" in sig:
        return "bear"
    return "neutral"


def overall_bias(signals: list) -> str:
    """根据信号汇总倾向：看多/看空/中性"""
    if not signals:
        return "中性"
    bull = sum(1 for s in signals if signal_direction(s) == "bull")
    bear = sum(1 for s in signals if signal_direction(s) == "bear")
    if bull > bear:
        return "看多"
    if bear > bull:
        return "看空"
    return "中性"
