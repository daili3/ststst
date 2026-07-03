"""数据拉取：AkShare 行情 + 资金流 + 公告

AkShare 内部 requests 不吃 socket 超时，用 threading 强制硬超时 + 重试。
GitHub Actions 环境访问东财偶发慢，但通常能成功。
baostock 作为降级方案，全局复用登录。
"""
import socket
import threading
import time
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# 全局 socket 超时（兜底）
socket.setdefaulttimeout(30.0)

# baostock 全局登录复用（避免反复 login/logout）
_BS_LOGGED_IN = False


def _ensure_baostock_login():
    """全局复用 baostock 登录"""
    global _BS_LOGGED_IN
    if _BS_LOGGED_IN:
        return True
    try:
        import baostock as bs
        lg = bs.login()
        if lg.error_code == "0":
            _BS_LOGGED_IN = True
            return True
        logger.error(f"baostock 登录失败: {lg.error_msg}")
        return False
    except Exception as e:
        logger.error(f"baostock 登录异常: {e}")
        return False


def baostock_logout():
    """进程结束时调用"""
    global _BS_LOGGED_IN
    if _BS_LOGGED_IN:
        try:
            import baostock as bs
            bs.logout()
            _BS_LOGGED_IN = False
        except Exception:
            pass


def _run_with_timeout(func, args=(), kwargs=None, timeout: float = 60.0):
    """线程级硬超时：AkShare 内部 requests 不吃 socket 超时，用线程强制
    Returns: func 的返回值，或超时返回 None
    """
    if kwargs is None:
        kwargs = {}
    result = [None]
    error = [None]

    def worker():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        # 线程还在跑，超时了
        logger.warning(f"调用超时({timeout}s): {func.__name__}")
        return None
    if error[0]:
        raise error[0]
    return result[0]


def _retry(func, args=(), kwargs=None, retries: int = 2, timeout: float = 60.0, delay: float = 3.0):
    """带重试 + 硬超时的调用包装"""
    if kwargs is None:
        kwargs = {}
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = _run_with_timeout(func, args, kwargs, timeout)
            if r is not None:
                return r
            logger.warning(f"{func.__name__} 第 {attempt + 1} 次返回空，重试")
        except Exception as e:
            last_err = e
            logger.warning(f"{func.__name__} 第 {attempt + 1} 次失败: {e}")
        if attempt < retries:
            time.sleep(delay)
    logger.error(f"{func.__name__} {retries + 1} 次均失败: {last_err}")
    return None


def get_daily_kline(code: str, market: str, days: int = 60) -> pd.DataFrame:
    """拉日线 K 线（前复权），带硬超时 + 重试"""
    try:
        df = _retry(
            ak.stock_zh_a_hist,
            kwargs={
                "symbol": code,
                "period": "daily",
                "start_date": (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d"),
                "end_date": datetime.now().strftime("%Y%m%d"),
                "adjust": "qfq",
            },
            retries=2,
            timeout=45.0,
        )
        if df is None or (hasattr(df, "empty") and df.empty):
            logger.warning(f"{code} 日线数据为空，尝试 baostock 降级")
            return _fallback_baostock(code, days)
        if not hasattr(df, "empty"):
            logger.error(f"{code} 返回类型异常: {type(df)}")
            return pd.DataFrame()

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


def _fallback_baostock(code: str, days: int) -> pd.DataFrame:
    """降级：用 baostock 拉日线（更稳，复用全局登录）"""
    try:
        import baostock as bs
        if not _ensure_baostock_login():
            return pd.DataFrame()

        bs_code = f"sh.{code}" if code.startswith("6") else f"sz.{code}"
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")

        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=start, end_date=end,
            frequency="d", adjustflag="2",
        )
        if rs.error_code != "0":
            logger.error(f"baostock 查询失败: {rs.error_msg}")
            return pd.DataFrame()

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", "amount"])
        for c in ["open", "high", "low", "close", "volume", "amount"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        df = df.tail(days).reset_index(drop=True)
        logger.info(f"{code} baostock 降级成功，{len(df)} 行")
        return df
    except ImportError:
        logger.error("baostock 未安装，无法降级")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"baostock 降级失败: {e}")
        return pd.DataFrame()


def get_realtime_quote(code: str) -> dict:
    """拉实时行情（盘中用）"""
    try:
        df = _retry(
            ak.stock_zh_a_spot_em,
            timeout=60.0,
            retries=1,
        )
        if df is None or df.empty:
            return {}
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
    """拉个股资金流向
    AkShare 在境外 IP 经常失败，降级用 baostock 拿成交量+涨跌幅做近似
    """
    try:
        df = _retry(
            ak.stock_individual_fund_flow,
            kwargs={"stock": code, "market": "sh" if code.startswith("6") else "sz"},
            timeout=45.0,
            retries=1,
        )
        if df is not None and not df.empty:
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
        # AkShare 失败，降级 baostock
        logger.info(f"{code} AkShare 资金流失败，用 baostock 近似")
        return _fallback_fund_flow_baostock(code, days)
    except Exception as e:
        logger.error(f"拉取 {code} 资金流失败: {e}")
        return _fallback_fund_flow_baostock(code, days)


def _fallback_fund_flow_baostock(code: str, days: int) -> pd.DataFrame:
    """baostock 无真实资金流，用成交量+涨跌幅做近似主力动向（复用全局登录）"""
    try:
        import baostock as bs
        if not _ensure_baostock_login():
            return pd.DataFrame()
        bs_code = f"sh.{code}" if code.startswith("6") else f"sz.{code}"
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,preclose,close,volume,amount",
            start_date=start, end_date=end, frequency="d",
        )
        if rs.error_code != "0":
            return pd.DataFrame()
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["date", "preclose", "close", "volume", "amount"])
        for c in ["preclose", "close", "volume", "amount"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        df["change_pct"] = (df["close"] - df["preclose"]) / df["preclose"] * 100
        df["main_net"] = df["amount"] * df["change_pct"].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0)) * 0.3
        df = df[["date", "main_net", "volume", "amount", "change_pct"]].tail(days).reset_index(drop=True)
        logger.info(f"{code} baostock 近似资金流成功，{len(df)} 行")
        return df
    except Exception as e:
        logger.error(f"baostock 近似资金流失败: {e}")
        return pd.DataFrame()


def get_notices(code: str, days: int = 7) -> list:
    """拉个股公告（近 N 天）
    用 stock_individual_notice_report（东财接口，按 security + 日期范围查询）
    返回 [{"title": ..., "type": ..., "date": ...}, ...]
    """
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = _retry(
            ak.stock_individual_notice_report,
            kwargs={
                "security": code,
                "begin_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
            },
            timeout=30.0,
            retries=1,
        )
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        # 列名: 代码 / 名称 / 公告标题 / 公告类型 / 公告日期 / 网址
        result = []
        for _, row in df.head(5).iterrows():
            result.append({
                "title": str(row.get("公告标题", "")).strip(),
                "type": str(row.get("公告类型", "")).strip(),
                "date": str(row.get("公告日期", "")).strip(),
            })
        return result
    except Exception as e:
        logger.error(f"拉取 {code} 公告失败: {e}")
        return []


def is_trading_day() -> bool:
    """检查今天是否为 A 股交易日"""
    try:
        df = _retry(
            ak.tool_trade_date_hist_sina,
            timeout=20.0,
            retries=1,
        )
        if df is None or df.empty:
            # 兜底：周一到周五当交易日
            return datetime.now().weekday() < 5
        today = datetime.now().strftime("%Y-%m-%d")
        trade_dates = df["trade_date"].astype(str).tolist()
        return today in trade_dates
    except Exception as e:
        logger.error(f"检查交易日失败，默认按工作日处理: {e}")
        return datetime.now().weekday() < 5
