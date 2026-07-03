"""主入口：拉数据 → 算指标 → 筛信号 → 取Top N → 生成简报 → 推 TG

两阶段策略（避免拉取全量详细数据超时）：
1. 第一阶段：对全部 STOCK_LIST 拉日线 + 算指标 + 算评分（快，每只 1-2 秒）
2. 取评分最高的 TOP_N 只
3. 第二阶段：只对 TOP_N 只拉资金流 + 公告 + 实时行情（慢，每只 5-10 秒）
4. 生成简报推送
"""
import sys
import logging
from datetime import datetime

from config import STOCK_LIST, SCHEDULE_SLOTS, TOP_N
from data_fetcher import (
    get_daily_kline, get_realtime_quote, get_fund_flow,
    get_notices, is_trading_day, baostock_logout,
)
from indicators import compute_all_indicators
from signals import analyze_signals, calc_signal_score, score_label, score_emoji
from report import generate_report, generate_summary, generate_combined_report
from notifier import send_message, send_long_message, send_document, send_codeblock

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def quick_score_one(stock: dict) -> tuple:
    """第一阶段：只拉日线 + 算指标 + 评分（不拉资金流/公告/实时）

    Returns:
        (stock, signals, ind, score) 或 (stock, [], {}, -1) 表示失败
    """
    code, market = stock["code"], stock["market"]
    df = get_daily_kline(code, market, days=60)
    if df.empty:
        logger.warning(f"{code} 无日线数据，跳过")
        return stock, [], {}, -1
    ind = compute_all_indicators(df)
    signals = analyze_signals(ind)
    score = calc_signal_score(signals, ind)
    return stock, signals, ind, score


def fetch_detail_for_top(stock: dict, signals: list, ind: dict, use_realtime: bool) -> tuple:
    """第二阶段：对 Top N 股票拉详细数据（资金流/公告/实时）

    Returns:
        (stock, signals, ind, fund_flow, notices, realtime)
    """
    fund_flow = get_fund_flow(stock["code"])
    notices = get_notices(stock["code"])
    realtime = get_realtime_quote(stock["code"]) if use_realtime else None
    return stock, signals, ind, fund_flow, notices, realtime


def run_slot(slot_key: str) -> int:
    """执行某个时段的完整流程
    Returns:
        int: 0=成功, 1=非交易日跳过, 2=失败
    """
    slot = SCHEDULE_SLOTS[slot_key]
    logger.info(f"========== 执行时段: {slot['desc']} ({slot['time']}) ==========")

    if not is_trading_day():
        logger.info("今日非交易日，跳过")
        return 1

    # ========== 第一阶段：全量评分 ==========
    logger.info(f"第一阶段：对 {len(STOCK_LIST)} 只股票快速评分...")
    scored = []
    for stock in STOCK_LIST:
        try:
            stock, signals, ind, score = quick_score_one(stock)
            if score >= 0:
                scored.append((stock, signals, ind, score))
                logger.info(f"  {stock['code']} {stock['name']} 评分 {score}")
        except Exception as e:
            logger.error(f"{stock['code']} 评分异常: {e}")

    if not scored:
        send_message(f"⚠️ {slot['desc']}：所有股票数据拉取失败，请检查日志")
        return 2

    # 按评分降序排序，取 Top N
    scored.sort(key=lambda x: x[3], reverse=True)
    top_n = scored[:TOP_N]
    logger.info(f"第二阶段：Top {len(top_n)} 已选出 → {[s[1] for s in top_n]}")

    # ========== 第二阶段：对 Top N 拉详细数据 ==========
    all_reports = []   # (stock, signals, ind)
    all_data = []      # (stock, signals, ind, fund_flow, notices, realtime)
    for stock, signals, ind, score in top_n:
        try:
            stock, signals, ind, fund_flow, notices, realtime = fetch_detail_for_top(
                stock, signals, ind, slot["use_realtime"]
            )
            all_reports.append((stock, signals, ind))
            all_data.append((stock, signals, ind, fund_flow, notices, realtime))
        except Exception as e:
            logger.error(f"{stock['code']} 详细数据异常: {e}", exc_info=True)

    if not all_reports:
        send_message(f"⚠️ {slot['desc']}：Top {TOP_N} 详细数据拉取失败")
        return 2

    # ========== 推送 ==========
    # 1. 汇总（Top N 排名 + 全池扫描概况）
    summary = generate_summary(all_reports, slot["desc"], total_pool=len(scored))
    send_message(summary)
    logger.info("汇总已推送")

    # 2. 合并简报（代码块，长按一键复制给 AI）
    combined = generate_combined_report(all_data, slot["desc"])
    send_codeblock(
        combined,
        caption=f"📋 {slot['desc']} Top {len(all_data)} 推荐简报\n长按下方代码块 → 复制 → 粘到 AI 网页版",
    )
    logger.info("合并简报已推送")

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
    try:
        main()
    finally:
        baostock_logout()
