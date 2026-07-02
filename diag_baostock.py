"""本机测试 baostock 降级（绕开 AkShare 卡死）"""
import sys
import time
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

print("=== 测试 baostock 拉日线 ===", flush=True)
from data_fetcher import _fallback_baostock, _fallback_fund_flow_baostock, baostock_logout

t = time.time()
df = _fallback_baostock("000001", 60)
print(f"耗时: {time.time()-t:.1f}s  行数: {len(df)}", flush=True)
if not df.empty:
    print(df.tail(3), flush=True)

print("\n=== 测试 baostock 近似资金流 ===", flush=True)
t = time.time()
ff = _fallback_fund_flow_baostock("000001", 5)
print(f"耗时: {time.time()-t:.1f}s  行数: {len(ff)}", flush=True)
if not ff.empty:
    print(ff, flush=True)

baostock_logout()
print("\n完成", flush=True)
