"""报告生成：Markdown 数据简报（用于喂给 AI 网页版）"""
from datetime import datetime
from signals import format_signal, overall_bias
from config import AI_PROMPT_TEMPLATE


def generate_report(stock: dict, ind: dict, signals: list, fund_flow_df, notices: list,
                    slot_desc: str, realtime: dict = None) -> str:
    """生成单只股票的数据简报

    Args:
        stock: {"code","name","market"}
        ind: 指标字典
        signals: 信号列表
        fund_flow_df: 资金流 DataFrame
        notices: 公告标题列表
        slot_desc: 时段描述，如 "盘前简报"
        realtime: 实时行情 dict（盘中用），None 表示盘前
    """
    today = datetime.now().strftime("%Y-%m-%d")
    code, name = stock["code"], stock["name"]
    bias = overall_bias(signals)

    # 价格部分
    if realtime and realtime.get("price"):
        price_line = f"- 实时价: {realtime['price']} ({realtime['change_pct']:+.2f}%)"
        ohlc_line = (f"- 今开: {realtime['open']}  最高: {realtime['high']}  "
                     f"最低: {realtime['low']}  昨收: {realtime['prev_close']}")
    else:
        price_line = f"- 前收: {ind.get('price')}"
        ohlc_line = (f"- 昨开: {ind.get('today_open')}  昨高: {ind.get('today_high')}  "
                     f"昨低: {ind.get('today_low')}  昨收: {ind.get('prev_close')}")

    # 信号部分
    if signals:
        sig_lines = "\n".join(f"- {format_signal(s)}" for s in signals)
    else:
        sig_lines = "- 无明显信号"

    # 资金流部分
    if fund_flow_df is not None and not fund_flow_df.empty:
        ff_lines = []
        for _, r in fund_flow_df.iterrows():
            d = r["date"].strftime("%m-%d") if hasattr(r["date"], "strftime") else str(r["date"])[:10]
            main = r["main_net"]
            arrow = "🔴" if main < 0 else "🟢"
            ff_lines.append(f"- {d} {arrow} 主力净流入: {main / 1e8:+.2f}亿")
        fund_flow_section = "\n".join(ff_lines)
    else:
        fund_flow_section = "- 资金流数据暂无"

    # 公告部分
    if notices:
        notice_section = "\n".join(f"- {n}" for n in notices)
    else:
        notice_section = "- 近3日无新公告"

    report = f"""# {code} {name} 信号简报
**日期**: {today}  **时段**: {slot_desc}  **综合倾向**: {bias}

## 价格
{price_line}
{ohlc_line}
- 5日均价: {ind.get('ma_short')}  10日均价: {ind.get('ma_mid')}  20日均价: {ind.get('ma_long')}

## 技术指标
- MACD: DIF {ind.get('macd_dif')} / DEA {ind.get('macd_dea')} / 柱 {ind.get('macd_bar')}
- KDJ: K {ind.get('kdj_k')} / D {ind.get('kdj_d')} / J {ind.get('kdj_j')}
- RSI(6): {ind.get('rsi')}
- 布林带: 上轨 {ind.get('boll_upper')} / 中轨 {ind.get('boll_mid')} / 下轨 {ind.get('boll_lower')}
- 量比: {ind.get('volume_ratio')}

## 信号
{sig_lines}

## 近{len(fund_flow_df) if fund_flow_df is not None and not fund_flow_df.empty else 0}日资金流
{fund_flow_section}

## 近3日公告
{notice_section}

---
**操作建议请复制以下提示词给 AI 网页版（如 DeepSeek/Kimi）**：
```
{AI_PROMPT_TEMPLATE.strip()}
```
"""
    return report


def generate_summary(all_reports: list, slot_desc: str) -> str:
    """生成汇总消息（先发汇总，再发详细简报）"""
    today = datetime.now().strftime("%Y-%m-%d")
    header = f"📊 {today} {slot_desc}\n共分析 {len(all_reports)} 只 | "

    bull = sum(1 for _, s, _ in all_reports if any(x.startswith("✅") or "💡" in x for x in [format_signal(sig) for sig in s]))
    bear = sum(1 for _, s, _ in all_reports if any(x.startswith("🔴") or "⚠️" in x for x in [format_signal(sig) for sig in s]))
    neutral = len(all_reports) - bull - bear

    header += f"看多信号: {bull} | 看空信号: {bear} | 中性: {neutral}\n\n"

    for stock, signals, ind in all_reports:
        code, name = stock["code"], stock["name"]
        bias = overall_bias(signals)
        emoji = "🟢" if bias == "看多" else ("🔴" if bias == "看空" else "⚪")
        sig_text = " / ".join(format_signal(s) for s in signals) if signals else "无信号"
        header += f"{emoji} {name}({code}): {bias} | {sig_text}\n"

    header += "\n详细简报见后续消息，复制给 AI 网页版即可获取操作建议。"
    return header
