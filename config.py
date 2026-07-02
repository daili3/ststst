"""配置文件：自选股、指标参数、推送时段"""
import os
from dotenv import load_dotenv

load_dotenv()

# ============ 自选股池 ============
# 低价蓝筹，流动性好，规则派友好
STOCK_LIST = [
    {"code": "000001", "name": "平安银行", "market": "sz"},
    {"code": "600036", "name": "招商银行", "market": "sh"},
    {"code": "601628", "name": "中国人寿", "market": "sh"},
    {"code": "600900", "name": "长江电力", "market": "sh"},
    {"code": "601398", "name": "工商银行", "market": "sh"},
]

# ============ 指标参数 ============
INDICATOR_PARAMS = {
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "ma": {"short": 5, "mid": 10, "long": 20},
    "kdj": {"n": 9, "m1": 3, "m2": 3},
    "rsi": {"period": 6},
    "boll": {"period": 20, "std": 2},
    "volume_ratio": {"days": 5},  # 量比基准：近5日均量
}

# 信号阈值
SIGNAL_THRESHOLDS = {
    "volume_ratio": 1.5,      # 量比 > 1.5 算放量
    "kdj_overbought": 80,     # KDJ J值超买
    "kdj_oversold": 20,       # KDJ J值超卖
    "rsi_overbought": 70,     # RSI超买
    "rsi_oversold": 30,       # RSI超卖
}

# ============ 推送时段 ============
# 每个时段对应的任务类型
SCHEDULE_SLOTS = {
    "pre_open":   {"time": "09:15", "desc": "盘前简报",   "use_realtime": False},
    "open_5min":  {"time": "09:35", "desc": "开盘速报",   "use_realtime": True},
    "mid_morning":{"time": "10:30", "desc": "盘中信号",   "use_realtime": True},
    "noon_open":  {"time": "13:05", "desc": "午盘速报",   "use_realtime": True},
    "tail":       {"time": "14:55", "desc": "尾盘决策",   "use_realtime": True},
}

# ============ Telegram 配置 ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ============ AI 提示词模板（用于手动复制到 AI 网页版）============
AI_PROMPT_TEMPLATE = """基于以下数据简报，请给出操作建议：
1. 买/观/卖 的明确结论
2. 买入价位、止损位、目标位
3. 最大的风险点
4. 如果盘中数据，请结合实时价格判断

请直接给结论，不要复述数据。
"""

# 批量分析提示词（一次性分析多只股票）
AI_PROMPT_BATCH = """你是一位严谨的A股短线交易分析师。以下是多只股票的数据简报，请对每只股票分别给出操作建议。

要求：
1. 每只股票给出：买/观/卖 的明确结论
2. 买入价位、止损位、目标位（具体数字）
3. 最大的风险点（一句话）
4. 如果有实时价格，结合实时价格判断
5. 最后给出"今日重点关注"：挑1-2只最值得操作的，说明理由

格式要求：每只股票用标题分隔，结论先行，不要复述数据。
"""
