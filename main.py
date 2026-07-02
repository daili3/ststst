"""主入口：拉数据 → 算指标 → 筛信号 → 生成简报 → 推 TG"""
import sys
import logging
from datetime import datetime

from config import STOCK_LIST, SCHEDULE_SLOTS
from data_fetcher import (
    get_daily_kline, get_realtime_quote, get_fund_flow,
    get_notices, is_trading_day,
)
from indicators import compute_all_indicators
from signals import analyze_signals
from report import generate_report, generate_summary
from notifier import send_message, send_long_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def analyze_one_stock(stock: dict, use_realtime: bool) -> tuple:
    """分析单只股票，返回 (stock, signals, ind, report_text)"""
    code, market = stock["code"], stock["market"]
    logger.info(f"分析 {code} {stock['name']} ...")

    # 1. 拉日线（60 个交易日，足够算所有指标）
    df = get_daily_kline(code, market, days=60)
    if df.empty:
        logger.warning(f"{code} 无日线数据，跳过")
        return stock, [], {}, None

    # 2. 算指标
    ind = compute_all_indicators(df)

    # 3. 盘中拉实时行情覆盖
    realtime = None
    if use_realtime:
        realtime = get_realtime_quote(code)

    # 4. 筛信号
    signals = analyze_signals(ind)

    return stock, signals, ind, realtime


def run_slot(slot_key: str) -> int:
    """执行某个时段的完整流程
    Returns:
        int: 0=成功, 1=非交易日跳过, 2=失败
    """
    slot = SCHEDULE_SLOTS[slot_key]
    logger.info(f"========== 执行时段: {slot['desc']} ({slot['time']}) ==========")

    # 非交易日跳过
    if not is_trading_day():
        logger.info("今日非交易日，跳过")
        return 1

    all_reports = []
    for stock in STOCK_LIST:
        try:
            stock, signals, ind, realtime = analyze_one_stock(stock, slot["use_realtime"])
            if ind:
                all_reports.append((stock, signals, ind, realtime))
        except Exception as e:
            logger.error(f"{stock['code']} 分析异常: {e}", exc_info=True)

    if not all_reports:
        send_message(f"⚠️ {slot['desc']}：所有股票数据拉取失败，请检查日志")
        return 2

    # 5. 推送汇总
    summary = generate_summary(
        [(s, sig, ind) for s, sig, ind, _ in all_reports],
        slot["desc"],
    )
    send_message(summary)
    logger.info("汇总已推送")

    # 6. 逐只推送详细简报
    for stock, signals, ind, realtime in all_reports:
        fund_flow = get_fund_flow(stock["code"])
        notices = get_notices(stock["code"])
        report = generate_report(
            stock, ind, signals, fund_flow, notices,
            slot_desc=slot["desc"], realtime=realtime,
        )
        send_long_message(report)
        logger.info(f"{stock['code']} 简报已推送")

    logger.info(f"========== {slot['desc']} 完成 ==========")
    return 0


def main():
    """入口：通过命令行参数指定时段
    用法:
        python main.py pre_open      # 盘前简报
        python main.py open_5min     # 开盘速报
        python main.py mid_morning   # 盘中信号
        python main.py noon_open     # 午盘速报
        python main.py tail          # 尾盘决策
        python main.py test          # 测试模式（单股 + 盘前）
    """
    if len(sys.argv) < 2:
        print("用法: python main.py <slot_key|test>")
        print(f"可选时段: {list(SCHEDULE_SLOTS.keys())}")
        sys.exit(1)

    arg = sys.argv[1]

    # 测试模式：单股快速验证
    if arg == "test":
        logger.info("=== 测试模式 ===")
        stock = STOCK_LIST[0]
        df = get_daily_kline(stock["code"], stock["market"], 60)
        if df.empty:
            print("拉数据失败")
            sys.exit(2)
        ind = compute_all_indicators(df)
        signals = analyze_signals(ind)
        realtime = get_realtime_quote(stock["code"])
        fund_flow = get_fund_flow(stock["code"])
        notices = get_notices(stock["code"])
        report = generate_report(
            stock, ind, signals, fund_flow, notices,
            slot_desc="测试", realtime=realtime,
        )
        print(report)
        print(f"\n信号: {signals}")
        print(f"指标: {ind}")
        return

    if arg not in SCHEDULE_SLOTS:
        print(f"未知时段: {arg}")
        print(f"可选: {list(SCHEDULE_SLOTS.keys())}")
        sys.exit(1)

    code = run_slot(arg)
    sys.exit(code)


if __name__ == "__main__":
    main()
