# A股信号分析推送

规则派 A 股信号系统：AkShare 拉数据 → 算技术指标 → 筛信号 → 生成 Markdown 简报 → Telegram 推送。
简报可直接复制到 AI 网页版（DeepSeek/Kimi/通义）获取操作建议，零 API 成本。

## 工作流

```
AkShare 拉数据 → 算 MACD/KDJ/RSI/均线/布林/量比 → 筛信号
                                                      ↓
                                              生成 Markdown 数据简报
                                                      ↓
                                              Telegram 推送（汇总 + 逐只详细）
                                                      ↓
                                              你复制简报 → AI 网页版 → 操作建议
```

## 推送时段（北京时间，仅工作日）

| 时段 | 时间 | 说明 |
|---|---|---|
| 盘前简报 | 09:00 | 昨日 K 线 + 信号 + T-1 资金流 + 公告 |
| 开盘速报 | 09:35 | 实时价 + 量比 |
| 盘中信号 | 10:30 | 实时价 + 信号 |
| 午盘速报 | 13:05 | 实时价 + 信号 |
| 尾盘决策 | 14:55 | 实时价 + 信号（尾盘决策提示） |

> GitHub Actions cron 通常延迟 5-15 分钟，盘前提前到 9:00 触发以抵消延迟。

## 部署步骤（GitHub Actions，零成本）

### 1. 推到 GitHub 公共仓库
```bash
git init
git add .
git commit -m "init: A股信号分析推送"
git branch -M main
git remote add origin https://github.com/<你的用户名>/stock-trade.git
git push -u origin main
```
> **必须公共仓库**：公共仓库 GitHub Actions 无限免费，不占私有仓库的 2000 分钟额度。

### 2. 配置 Secrets
仓库 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`：

| Secret 名称 | 说明 | 获取方式 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | TG Bot Token | Telegram 找 [@BotFather](https://t.me/BotFather)，`/newbot` 创建后获取 |
| `TELEGRAM_CHAT_ID` | 你的 Chat ID | 给你创建的 Bot 发条消息，然后访问 `https://api.telegram.org/bot<TOKEN>/getUpdates` 获取 `chat.id` |

### 3. 启用 Actions
仓库 `Actions` 标签 → `I understand my workflows, go ahead and enable them`

### 4. 手动测试
`Actions` → `A股信号分析推送` → `Run workflow` → 选择 `test` 或 `pre_open` → `Run workflow`

### 5. 验证
几分钟内 Telegram Bot 会收到：
1. 一条汇总消息（5 只股票信号概览）
2. 5 条详细简报（每只一条，可复制给 AI）

## 本地测试

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID

# 测试模式（单股，只打印不推送）
python main.py test

# 完整时段（会推送 TG）
python main.py pre_open
```

## 项目结构

```
StockTrade/
├── main.py                  # 入口：拉数据→算指标→筛信号→生成简报→推 TG
├── config.py                # 自选股、指标参数、推送时段、TG 配置
├── data_fetcher.py          # AkShare 拉行情/资金流/公告
├── indicators.py            # MACD/KDJ/RSI/均线/布林/量比
├── signals.py               # 信号规则 + 中文化映射
├── report.py                # Markdown 简报生成
├── notifier.py              # Telegram 推送
├── requirements.txt
├── .env.example
├── .gitignore
└── .github/workflows/
    └── stock_analysis.yml   # GitHub Actions 定时任务
```

## 自定义

### 改自选股
编辑 `config.py` 的 `STOCK_LIST`：
```python
STOCK_LIST = [
    {"code": "000001", "name": "平安银行", "market": "sz"},
    {"code": "600519", "name": "贵州茅台", "market": "sh"},  # 加这只
]
```

### 改信号阈值
编辑 `config.py` 的 `SIGNAL_THRESHOLDS`：
```python
SIGNAL_THRESHOLDS = {
    "volume_ratio": 2.0,      # 量比阈值调高到 2.0
    "kdj_overbought": 85,     # KDJ 超买阈值调高
}
```

### 加新信号
在 `signals.py` 加检测函数 + 注册到 `analyze_signals` + 加中文化映射。

### 改推送时间
编辑 `.github/workflows/stock_analysis.yml` 的 cron 表达式（UTC 时间）。

## 信号说明

| 信号 | 方向 | 触发条件 |
|---|---|---|
| MACD 金叉 | 看多 | MACD 柱从负转正 |
| MACD 死叉 | 看空 | MACD 柱从正转负 |
| 均线多头排列 | 看多 | 5日线 > 10日线 且 价格站上5日线 |
| 均线空头排列 | 看空 | 5日线 < 10日线 且 价格跌破5日线 |
| 放量突破20日线 | 看多 | 昨在20日线下，今站上 + 量比 > 1.5 |
| 放量 | 中性 | 量比 > 1.5 |
| KDJ 超买 | 看空 | J > 80 |
| KDJ 超卖 | 看多 | J < 20 |
| RSI 超买 | 看空 | RSI(6) > 70 |
| RSI 超卖 | 看多 | RSI(6) < 30 |

## 升级路径（档位 3）

当前是零成本版（手动复制到 AI 网页版）。要升级到全自动：

1. **接 DeepSeek API**：在 `notifier.py` 加个函数，收到简报后调 DeepSeek API 解读，再把 AI 回复推到 TG。月耗约 ¥1.5。
2. **接博查搜索 API**：在 `data_fetcher.py` 加新闻拉取，塞进简报。月耗约 ¥5-10。
3. **加回测**：用历史数据验证信号准确率，在 `config.py` 调阈值。

## 风险提示

- 所有信号仅供参考，不构成投资建议
- AkShare 数据有延迟（15-30 分钟），不适合实时交易
- GitHub Actions cron 不准时，可能延迟 5-15 分钟
- 规则派信号在震荡市容易假信号，需结合 AI 解读和基本面判断

## 数据源

- [AkShare](https://akshare.akfamily.xyz/)：免费开源 A 股数据接口
- [Telegram Bot API](https://core.telegram.org/bots/api)
