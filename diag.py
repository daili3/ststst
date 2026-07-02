"""诊断脚本：定位 AkShare 卡在哪"""
import sys
import time
import logging
logging.basicConfig(level=logging.WARNING)

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

log("1. 导入 akshare...")
t = time.time()
import akshare as ak
log(f"   耗时: {time.time()-t:.1f}s")

log("2. 测试日线接口 stock_zh_a_hist...")
t = time.time()
try:
    df = ak.stock_zh_a_hist(
        symbol="000001", period="daily",
        start_date="20260601", end_date="20260702", adjust="qfq",
    )
    log(f"   耗时: {time.time()-t:.1f}s  行数: {len(df)}")
    log(str(df.tail(3)))
except Exception as e:
    log(f"   失败: {e}")

log("3. 测试实时行情 stock_zh_a_spot_em...")
t = time.time()
try:
    df = ak.stock_zh_a_spot_em()
    log(f"   耗时: {time.time()-t:.1f}s  行数: {len(df)}")
except Exception as e:
    log(f"   失败: {e}")

log("完成")
