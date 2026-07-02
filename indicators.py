"""技术指标计算：MACD / KDJ / RSI / 均线 / 布林带 / 量比"""
import pandas as pd
import numpy as np
from config import INDICATOR_PARAMS


def calc_ma(df: pd.DataFrame, window: int) -> pd.Series:
    """简单移动平均"""
    return df["close"].rolling(window=window).mean()


def calc_macd(df: pd.DataFrame) -> pd.DataFrame:
    """MACD: DIF / DEA / MACD柱"""
    p = INDICATOR_PARAMS["macd"]
    ema_fast = df["close"].ewm(span=p["fast"], adjust=False).mean()
    ema_slow = df["close"].ewm(span=p["slow"], adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=p["signal"], adjust=False).mean()
    macd_bar = (dif - dea) * 2
    return pd.DataFrame({"dif": dif, "dea": dea, "macd": macd_bar})


def calc_kdj(df: pd.DataFrame) -> pd.DataFrame:
    """KDJ 指标"""
    p = INDICATOR_PARAMS["kdj"]
    low_min = df["low"].rolling(window=p["n"], min_periods=1).min()
    high_max = df["high"].rolling(window=p["n"], min_periods=1).max()
    rsv = (df["close"] - low_min) / (high_max - low_min + 1e-9) * 100

    k = rsv.ewm(com=p["m1"] - 1, adjust=False).mean()
    d = k.ewm(com=p["m2"] - 1, adjust=False).mean()
    j = 3 * k - 2 * d
    return pd.DataFrame({"k": k, "d": d, "j": j})


def calc_rsi(df: pd.DataFrame) -> pd.Series:
    """RSI（默认6日）"""
    period = INDICATOR_PARAMS["rsi"]["period"]
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))


def calc_boll(df: pd.DataFrame) -> pd.DataFrame:
    """布林带: 上轨/中轨/下轨"""
    p = INDICATOR_PARAMS["boll"]
    mid = df["close"].rolling(window=p["period"]).mean()
    std = df["close"].rolling(window=p["period"]).std()
    upper = mid + p["std"] * std
    lower = mid - p["std"] * std
    return pd.DataFrame({"upper": upper, "mid": mid, "lower": lower})


def calc_volume_ratio(df: pd.DataFrame) -> float:
    """量比：当日成交量 / 近 N 日平均成交量"""
    days = INDICATOR_PARAMS["volume_ratio"]["days"]
    if len(df) < days + 1:
        return 1.0
    today_vol = df["volume"].iloc[-1]
    avg_vol = df["volume"].iloc[-(days + 1):-1].mean()
    if avg_vol == 0:
        return 1.0
    return round(today_vol / avg_vol, 2)


def compute_all_indicators(df: pd.DataFrame) -> dict:
    """一次性算出所有指标，返回最新值"""
    p = INDICATOR_PARAMS["ma"]
    ma_short = calc_ma(df, p["short"])
    ma_mid = calc_ma(df, p["mid"])
    ma_long = calc_ma(df, p["long"])

    macd = calc_macd(df)
    kdj = calc_kdj(df)
    rsi = calc_rsi(df)
    boll = calc_boll(df)
    vol_ratio = calc_volume_ratio(df)

    return {
        "price": round(df["close"].iloc[-1], 2),
        "ma_short": round(ma_short.iloc[-1], 2) if not np.isnan(ma_short.iloc[-1]) else None,
        "ma_mid": round(ma_mid.iloc[-1], 2) if not np.isnan(ma_mid.iloc[-1]) else None,
        "ma_long": round(ma_long.iloc[-1], 2) if not np.isnan(ma_long.iloc[-1]) else None,
        "macd_dif": round(macd["dif"].iloc[-1], 3),
        "macd_dea": round(macd["dea"].iloc[-1], 3),
        "macd_bar": round(macd["macd"].iloc[-1], 3),
        "macd_prev_bar": round(macd["macd"].iloc[-2], 3) if len(macd) >= 2 else 0,
        "kdj_k": round(kdj["k"].iloc[-1], 2),
        "kdj_d": round(kdj["d"].iloc[-1], 2),
        "kdj_j": round(kdj["j"].iloc[-1], 2),
        "rsi": round(rsi.iloc[-1], 2),
        "boll_upper": round(boll["upper"].iloc[-1], 2) if not np.isnan(boll["upper"].iloc[-1]) else None,
        "boll_mid": round(boll["mid"].iloc[-1], 2) if not np.isnan(boll["mid"].iloc[-1]) else None,
        "boll_lower": round(boll["lower"].iloc[-1], 2) if not np.isnan(boll["lower"].iloc[-1]) else None,
        "volume_ratio": vol_ratio,
        # K线最新一根
        "prev_close": round(df["close"].iloc[-2], 2) if len(df) >= 2 else None,
        "today_high": round(df["high"].iloc[-1], 2),
        "today_low": round(df["low"].iloc[-1], 2),
        "today_open": round(df["open"].iloc[-1], 2),
    }
