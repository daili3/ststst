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


# ============ 信号评分系统（0-100）============
# 每个信号对评分的贡献（正=看多，负=看空）
SIGNAL_SCORES = {
    "macd_golden_cross":         +15,
    "macd_death_cross":          -15,
    "ma_bullish_align":          +12,
    "ma_bearish_align":          -12,
    "breakout_20ma_with_volume": +18,
    "volume_surge":              +0,   # 放量本身无方向
    "kdj_overbought":            -10,
    "kdj_oversold":              +10,
    "rsi_overbought":            -10,
    "rsi_oversold":              +10,
}


def calc_signal_score(signals: list, ind: dict) -> int:
    """计算 0-100 信号评分
    50 为中性，>50 看多，<50 看空
    综合信号分 + 趋势分（价格与均线关系）
    """
    score = 50  # 基准

    # 1. 信号加分/减分
    for sig in signals:
        score += SIGNAL_SCORES.get(sig, 0)

    # 2. 趋势分：价格相对 20 日均线
    price = ind.get("price")
    ma_long = ind.get("ma_long")
    if price and ma_long:
        deviation = (price - ma_long) / ma_long * 100
        # 偏离 20 日线 ±5% 给 ±10 分
        if deviation > 5:
            score += 10
        elif deviation > 2:
            score += 5
        elif deviation < -5:
            score -= 10
        elif deviation < -2:
            score -= 5

    # 3. MACD 柱方向
    macd_bar = ind.get("macd_bar", 0)
    if macd_bar > 0:
        score += 3
    elif macd_bar < 0:
        score -= 3

    # 限制在 0-100
    return max(0, min(100, int(score)))


def score_label(score: int) -> str:
    """评分转标签"""
    if score >= 70:
        return "强烈看多"
    if score >= 55:
        return "偏多"
    if score > 45:
        return "中性"
    if score > 30:
        return "偏空"
    return "看空"


def score_emoji(score: int) -> str:
    """评分转 emoji"""
    if score >= 70:
        return "🟢"
    if score >= 55:
        return "🟢"
    if score > 45:
        return "⚪"
    if score > 30:
        return "🔴"
    return "🔴"


def trend_description(ind: dict) -> str:
    """趋势人话描述"""
    ma_s, ma_m, ma_l = ind.get("ma_short"), ind.get("ma_mid"), ind.get("ma_long")
    price = ind.get("price")
    if not all([ma_s, ma_m, ma_l, price]):
        return "数据不足"

    if ma_s > ma_m > ma_l and price > ma_s:
        return "上涨趋势（多头排列）"
    if ma_s < ma_m < ma_l and price < ma_s:
        return "下跌趋势（空头排列）"
    if ma_s > ma_m and price > ma_s:
        return "反弹中（5日线上穿）"
    if ma_s < ma_m and price < ma_s:
        return "调整中（5日线下行）"
    return "震荡"


def momentum_description(ind: dict) -> str:
    """动能人话描述（MACD）"""
    dif, dea, bar = ind.get("macd_dif", 0), ind.get("macd_dea", 0), ind.get("macd_bar", 0)
    prev_bar = ind.get("macd_prev_bar", 0)

    if dif > dea and bar > 0:
        if bar > prev_bar:
            return "多头动能增强"
        return "多头但动能减弱"
    if dif < dea and bar < 0:
        if bar < prev_bar:
            return "空头动能增强"
        return "空头但动能减弱"
    return "动能平衡"


def heat_description(ind: dict) -> str:
    """热度人话描述（量比）"""
    vr = ind.get("volume_ratio", 1.0)
    if vr >= 2.0:
        return f"明显放量（量比{vr}，资金活跃）"
    if vr >= 1.5:
        return f"温和放量（量比{vr}）"
    if vr >= 0.8:
        return f"成交正常（量比{vr}）"
    return f"缩量（量比{vr}，没人玩）"


def key_levels(ind: dict) -> dict:
    """关键价位"""
    return {
        "压力1": ind.get("ma_short"),
        "压力2": ind.get("ma_mid"),
        "支撑1": ind.get("ma_long"),
        "支撑2": ind.get("boll_lower"),
        "上轨": ind.get("boll_upper"),
    }
