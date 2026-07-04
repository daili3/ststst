"""报告生成：三段式简报（人话结论 + AI提示词 + 详细数据）+ 合并简报"""
from datetime import datetime
from signals import (
    format_signal, overall_bias, calc_signal_score, score_label, score_emoji,
    trend_description, momentum_description, heat_description, key_levels,
)
from config import AI_PROMPT_TEMPLATE, AI_PROMPT_BATCH, AI_PROMPT_FRIDAY_TAIL


def generate_report(stock: dict, ind: dict, signals: list, fund_flow_df, notices: list,
                    slot_desc: str, realtime: dict = None) -> str:
    """生成三段式简报：
    1. 人话结论（小白看）
    2. AI 提示词（复制用）
    3. 详细数据（AI 吃）
    """
    today = datetime.now().strftime("%Y-%m-%d")
    code, name = stock["code"], stock["name"]

    # 评分
    score = calc_signal_score(signals, ind)
    label = score_label(score)
    emoji = score_emoji(score)

    # 趋势/动能/热度
    trend = trend_description(ind)
    momentum = momentum_description(ind)
    heat = heat_description(ind)
    levels = key_levels(ind)

    # 价格（命名修正：price=最近收盘, prev_close=前日收盘）
    if realtime and realtime.get("price"):
        price_line = f"现价 {realtime['price']} ({realtime['change_pct']:+.2f}%)"
        ohlc_line = f"今开 {realtime['open']} / 高 {realtime['high']} / 低 {realtime['low']} / 昨收 {realtime['prev_close']}"
    else:
        price_line = f"昨收 {ind.get('price')}"
        ohlc_line = f"开 {ind.get('today_open')} / 高 {ind.get('today_high')} / 低 {ind.get('today_low')} / 前收 {ind.get('prev_close')}"

    # 信号
    if signals:
        sig_lines = "\n".join(f"  {format_signal(s)}" for s in signals)
    else:
        sig_lines = "  无明显信号"

    # 资金流
    if fund_flow_df is not None and not fund_flow_df.empty:
        ff_lines = []
        for _, r in fund_flow_df.iterrows():
            d = r["date"].strftime("%m-%d") if hasattr(r["date"], "strftime") else str(r["date"])[:10]
            main = r["main_net"]
            arrow = "🔴" if main < 0 else "🟢"
            if "change_pct" in r:
                ff_lines.append(f"  {d} {arrow} 涨跌 {r['change_pct']:+.2f}% 成交额 {r['amount']/1e8:.2f}亿 近似主力 {main/1e8:+.2f}亿")
            else:
                ff_lines.append(f"  {d} {arrow} 主力净流入 {main / 1e8:+.2f}亿")
        fund_flow_section = "\n".join(ff_lines)
    else:
        fund_flow_section = "  资金流数据暂无"

    # 公告
    if notices:
        notice_section = "\n".join(f"  {n.get('date','')} {n.get('title','')}" for n in notices)
    else:
        notice_section = "  近7日无新公告"

    # 关键价位
    levels_line = f"压力 {levels.get('压力2')} / {levels.get('压力1')}  支撑 {levels.get('支撑1')} / {levels.get('支撑2')}"

    # 一句话建议
    if score >= 70:
        advice = "多信号共振看多，可关注买入机会"
    elif score >= 55:
        advice = "偏多，可小仓位跟进"
    elif score > 45:
        advice = "方向不明，建议观望"
    elif score > 30:
        advice = "偏空，不参与"
    else:
        advice = "弱势明显，回避"

    # ========== 三段式拼接 ==========
    report = f"""{emoji} {name}({code}) | {label} | 评分 {score}/100
{today} {slot_desc}

📌 一句话：{advice}
📈 趋势：{trend}
⚡ 动能：{momentum}
🌡 热度：{heat}
🎯 关键位：{levels_line}
💰 价格：{price_line}
   {ohlc_line}

━━━━━━━━━━━━━━━━━━━━
🤖 复制下面整段给 AI 网页版（DeepSeek/Kimi）获取详细操作建议：
```
{AI_PROMPT_TEMPLATE.strip()}

# {code} {name} 数据简报 {today}
## 价格
- {price_line}
- {ohlc_line}
- 5日 {ind.get('ma_short')} / 10日 {ind.get('ma_mid')} / 20日 {ind.get('ma_long')}
## 技术指标
- MACD: DIF {ind.get('macd_dif')} / DEA {ind.get('macd_dea')} / 柱 {ind.get('macd_bar')}
- KDJ: K {ind.get('kdj_k')} / D {ind.get('kdj_d')} / J {ind.get('kdj_j')}
- RSI(6): {ind.get('rsi')}
- 布林带: 上轨 {ind.get('boll_upper')} / 中轨 {ind.get('boll_mid')} / 下轨 {ind.get('boll_lower')}
- 量比: {ind.get('volume_ratio')}
## 信号
{sig_lines}
## 资金流
{fund_flow_section}
## 公告
{notice_section}
```
"""
    return report


def generate_summary(all_reports: list, slot_desc: str, total_pool: int = None) -> str:
    """生成汇总消息：按评分排名 + 重点关注

    Args:
        all_reports: Top N 股票的 (stock, signals, ind)
        slot_desc: 时段描述
        total_pool: 全量股票池大小（用于显示"从 N 只中选出"）
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # 按评分排序
    ranked = []
    for stock, signals, ind in all_reports:
        score = calc_signal_score(signals, ind)
        ranked.append((stock, signals, ind, score))
    ranked.sort(key=lambda x: x[3], reverse=True)

    header = f"📊 {today} {slot_desc}\n"
    if total_pool and total_pool > len(ranked):
        header += f"从 {total_pool} 只中选出 Top {len(ranked)} | "
    else:
        header += f"共 {len(ranked)} 只 | "

    bull = sum(1 for _, _, _, s in ranked if s >= 55)
    bear = sum(1 for _, _, _, s in ranked if s < 45)
    neutral = len(ranked) - bull - bear
    header += f"🟢偏多 {bull}  ⚪中性 {neutral}  🔴偏空 {bear}\n"
    header += "━━━━━━━━━━━━━━━━━━━━\n"
    header += "🏆 Top 推荐排名：\n\n"

    for i, (stock, signals, ind, score) in enumerate(ranked, 1):
        code, name = stock["code"], stock["name"]
        emoji = score_emoji(score)
        label = score_label(score)
        # 最值得关注：评分最高
        if i == 1:
            mark = "⭐ 重点关注"
        elif i == len(ranked) and score < 45:
            mark = "⚠️ 最弱"
        else:
            mark = ""
        header += f"{i}. {emoji} {name}({code}) {score}分 {label} {mark}\n"

    header += "\n━━━━━━━━━━━━━━━━━━━━\n"
    header += "下方是 Top 推荐的合并简报（代码块），长按复制给 AI 网页版获取操作建议。"

    return header


def generate_combined_report(all_data: list, slot_desc: str, prompt: str = None) -> str:
    """生成合并简报：所有股票数据打包，一次性复制给 AI

    Args:
        all_data: [(stock, signals, ind, fund_flow_df, notices, realtime), ...]
        slot_desc: 时段描述
        prompt: 自定义提示词（默认用 AI_PROMPT_BATCH）
    Returns:
        合并文本，用于发送 TG 文档
    """
    today = datetime.now().strftime("%Y-%m-%d")

    use_prompt = prompt if prompt else AI_PROMPT_BATCH
    text = use_prompt.strip() + "\n\n"
    text += f"# {today} {slot_desc} 合并数据简报（共 {len(all_data)} 只）\n\n"

    for stock, signals, ind, fund_flow_df, notices, realtime in all_data:
        code, name = stock["code"], stock["name"]
        score = calc_signal_score(signals, ind)

        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"# {code} {name} 评分:{score}/100\n"

        # 价格
        if realtime and realtime.get("price"):
            text += f"现价 {realtime['price']} ({realtime['change_pct']:+.2f}%)\n"
            text += f"今开 {realtime['open']} / 高 {realtime['high']} / 低 {realtime['low']} / 昨收 {realtime['prev_close']}\n"
        else:
            text += f"昨收 {ind.get('price')}\n"
            text += f"开 {ind.get('today_open')} / 高 {ind.get('today_high')} / 低 {ind.get('today_low')} / 前收 {ind.get('prev_close')}\n"
        text += f"5日 {ind.get('ma_short')} / 10日 {ind.get('ma_mid')} / 20日 {ind.get('ma_long')}\n"

        # 指标
        text += f"MACD: DIF {ind.get('macd_dif')} / DEA {ind.get('macd_dea')} / 柱 {ind.get('macd_bar')}\n"
        text += f"KDJ: K {ind.get('kdj_k')} / D {ind.get('kdj_d')} / J {ind.get('kdj_j')}\n"
        text += f"RSI(6): {ind.get('rsi')}\n"
        text += f"布林带: 上轨 {ind.get('boll_upper')} / 中轨 {ind.get('boll_mid')} / 下轨 {ind.get('boll_lower')}\n"
        text += f"量比: {ind.get('volume_ratio')}\n"

        # 信号
        if signals:
            sig_text = " / ".join(format_signal(s).strip() for s in signals)
        else:
            sig_text = "无明显信号"
        text += f"信号: {sig_text}\n"

        # 资金流 + 近5日走势小结
        if fund_flow_df is not None and not fund_flow_df.empty:
            ff_parts = []
            changes = []
            for _, r in fund_flow_df.iterrows():
                d = r["date"].strftime("%m-%d") if hasattr(r["date"], "strftime") else str(r["date"])[:10]
                main = r["main_net"]
                arrow = "↓" if main < 0 else "↑"
                if "change_pct" in r:
                    ff_parts.append(f"{d} {arrow}{r['change_pct']:+.2f}% 额{r['amount']/1e8:.1f}亿 主{main/1e8:+.1f}亿")
                    changes.append(float(r["change_pct"]))
                else:
                    ff_parts.append(f"{d} {arrow}主{main/1e8:+.1f}亿")
            text += f"资金流: {' | '.join(ff_parts)}\n"

            # 近5日走势小结（帮 AI 判断趋势）
            if changes:
                up_days = sum(1 for c in changes if c > 0)
                down_days = sum(1 for c in changes if c < 0)
                total_change = sum(changes)
                max_up = max(changes) if changes else 0
                max_down = min(changes) if changes else 0
                summary_parts = []
                summary_parts.append(f"近{len(changes)}日{up_days}涨{down_days}跌")
                summary_parts.append(f"累计{total_change:+.2f}%")
                if max_up > 0:
                    summary_parts.append(f"最大涨幅{max_up:+.2f}%")
                if max_down < 0:
                    summary_parts.append(f"最大跌幅{max_down:+.2f}%")
                text += f"走势小结: {'，'.join(summary_parts)}\n"
        else:
            text += "资金流: 暂无\n"

        # 公告
        if notices:
            notice_strs = [f"{n.get('date','')}「{n.get('type','')}」{n.get('title','')}" for n in notices[:3]]
            text += f"公告: {' / '.join(notice_strs)}\n"
        else:
            text += "公告: 近7日无新公告\n"

        text += "\n"

    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += "请对以上每只股票分别给出：买/观/卖结论 + 买入位 + 止损位 + 目标位 + 最大风险点。"

    return text
