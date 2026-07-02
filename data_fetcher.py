"""数据拉取：AkShare 行情 + 资金流 + 公告

注意：AkShare 部分接口调东方财富，本机偶发卡死。
已在所有调用处加 socket 默认超时（30 秒），避免无限等待。
GitHub Actions 环境访问反而更稳定。
"""
import socket
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# 全局 socket 超时：30 秒。避免 AkShare 内部 requests 无限挂起
_DEFAULT_TIMEOUT = 30.0
socket.setdefaulttimeout(_DEFAULT_TIMEOUT)


def get_daily_kline(code: str, market: str, days: int = 60) -> pd.DataFrame:
    """拉日线 K 线（前复权）
    Args:
        code: 股票代码，如 "000001"
        market: "sh" 或 "sz"
        days: 拉取近 N 个交易日
    Returns:
        DataFrame: columns=["date","open","high","low","close","volume","amount"]
    """
    try:
        # AkShare A股日线接口（前复权）
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=(datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"),
            adjust="qfq",
        )
        if df is None or df.empty:
            logger.warning(f"{code} 日线数据为空")
            return pd.DataFrame()

        # 统一列名
        df = df.rename(columns={
            "日期": "date", "开盘": "open", "最高": "high",
            "最低": "low", "收盘": "close", "成交量": "volume", "成交额": "amount",
        })
        df["date"] = pd.to_datetime(df["date"])
        df = df[["date", "open", "high", "low", "close", "volume", "amount"]].tail(days)
        df = df.reset_index(drop=True)
        return df
    except Exception as e:
        logger.error(f"拉取 {code} 日线失败: {e}")
        return pd.DataFrame()


def get_realtime_quote(code: str) -> dict:
    """拉实时行情（盘中用）
    Returns:
        dict: {name, price, change_pct, volume, amount, volume_ratio}
    """
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if row.empty:
            return {}
        r = row.iloc[0]
        return {
            "name": r.get("名称", ""),
            "price": float(r.get("最新价", 0) or 0),
            "change_pct": float(r.get("涨跌幅", 0) or 0),
            "volume": float(r.get("成交量", 0) or 0),
            "amount": float(r.get("成交额", 0) or 0),
            "volume_ratio": float(r.get("量比", 0) or 0),
            "high": float(r.get("最高", 0) or 0),
            "low": float(r.get("最低", 0) or 0),
            "open": float(r.get("今开", 0) or 0),
            "prev_close": float(r.get("昨收", 0) or 0),
        }
    except Exception as e:
        logger.error(f"拉取 {code} 实时行情失败: {e}")
        return {}


def get_fund_flow(code: str, days: int = 5) -> pd.DataFrame:
    """拉个股资金流向（T-1 数据，近 N 日主力净流入）
    Returns:
        DataFrame: columns=["date","main_net","super_large_net","large_net","medium_net","small_net"]
    """
    try:
        df = ak.stock_individual_fund_flow(stock=code, market="sh" if code.startswith("6") else "sz")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns={
            "日期": "date", "主力净流入-净额": "main_net",
            "超大单净流入-净额": "super_large_net",
            "大单净流入-净额": "large_net",
            "中单净流入-净额": "medium_net",
            "小单净流入-净额": "small_net",
        })
        df["date"] = pd.to_datetime(df["date"])
        df = df[["date", "main_net", "super_large_net", "large_net", "medium_net", "small_net"]]
        df = df.tail(days).reset_index(drop=True)
        return df
    except Exception as e:
        logger.error(f"拉取 {code} 资金流失败: {e}")
        return pd.DataFrame()


def get_notices(code: str, days: int = 3) -> list:
    """拉个股公告（近 N 天，只取标题）
    Returns:
        list[str]: 公告标题列表
    """
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = ak.stock_notice_report(symbol=code, start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"))
        if df is None or df.empty:
            return []
        title_col = "标题" if "标题" in df.columns else df.columns[1]
        return df[title_col].head(5).tolist()
    except Exception as e:
        logger.error(f"拉取 {code} 公告失败: {e}")
        return []


def is_trading_day() -> bool:
    """检查今天是否为 A 股交易日"""
    try:
        df = ak.tool_trade_date_hist_sina()
        today = datetime.now().strftime("%Y-%m-%d")
        trade_dates = df["trade_date"].astype(str).tolist()
        return today in trade_dates
    except Exception as e:
        logger.error(f"检查交易日失败，默认按工作日处理: {e}")
        # 兜底：周一到周五当交易日
        return datetime.now().weekday() < 5


if __name__ == "__main__":
    # 快速自测
    print("=== 测试日线 ===")
    print(get_daily_kline("000001", "sz", 10))
    print("\n=== 测试实时 ===")
    print(get_realtime_quote("000001"))
    print("\n=== 测试资金流 ===")
    print(get_fund_flow("000001", 5))
    print("\n=== 测试公告 ===")
    print(get_notices("000001", 3))
    print("\n=== 测试交易日 ===")
    print(is_trading_day())
