"""测试新简报格式（baostock 数据，不走 AkShare）"""
import sys
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from data_fetcher import _fallback_baostock, _fallback_fund_flow_baostock, baostock_logout
from indicators import compute_all_indicators
from signals import analyze_signals, calc_signal_score, score_label
from report import generate_report, generate_summary
from config import STOCK_LIST

print("\n========== 测试新简报格式 ==========\n", flush=True)

all_reports = []
for stock in STOCK_LIST[:3]:  # 只测前3只，省时间
    print(f"--- {stock['code']} {stock['name']} ---", flush=True)
    df = _fallback_baostock(stock["code"], 60)
    if df.empty:
        print("  拉数据失败", flush=True)
        continue
    ind = compute_all_indicators(df)
    signals = analyze_signals(ind)
    score = calc_signal_score(signals, ind)
    print(f"  评分: {score} {score_label(score)}  信号: {signals}", flush=True)
    all_reports.append((stock, signals, ind))

print("\n========== 汇总消息 ==========\n", flush=True)
if all_reports:
    summary = generate_summary(all_reports, "盘前简报")
    print(summary, flush=True)

print("\n========== 第一只详细简报 ==========\n", flush=True)
if all_reports:
    stock, signals, ind = all_reports[0]
    ff = _fallback_fund_flow_baostock(stock["code"], 5)
    report = generate_report(stock, ind, signals, ff, [], "盘前简报", None)
    print(report, flush=True)

baostock_logout()
print("\n完成", flush=True)
