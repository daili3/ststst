"""测试合并简报格式"""
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from data_fetcher import _fallback_baostock, _fallback_fund_flow_baostock, baostock_logout
from indicators import compute_all_indicators
from signals import analyze_signals
from report import generate_combined_report, generate_summary
from config import STOCK_LIST

print("\n========== 测试合并简报 ==========\n", flush=True)

all_reports = []
all_data = []
for stock in STOCK_LIST[:3]:
    print(f"--- {stock['code']} {stock['name']} ---", flush=True)
    df = _fallback_baostock(stock["code"], 60)
    if df.empty:
        continue
    ind = compute_all_indicators(df)
    signals = analyze_signals(ind)
    ff = _fallback_fund_flow_baostock(stock["code"], 5)
    all_reports.append((stock, signals, ind))
    all_data.append((stock, signals, ind, ff, [], None))

print("\n========== 汇总消息 ==========\n", flush=True)
print(generate_summary(all_reports, "盘前简报"), flush=True)

print("\n========== 合并简报（文件内容）==========\n", flush=True)
combined = generate_combined_report(all_data, "盘前简报")
print(combined, flush=True)
print(f"\n[合并简报总长度: {len(combined)} 字符]", flush=True)

baostock_logout()
print("\n完成", flush=True)
