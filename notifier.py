"""Telegram 推送"""
import requests
import logging
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

TG_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(text: str, disable_preview: bool = True) -> bool:
    """发送单条 TG 消息
    Args:
        text: 消息文本（支持 Markdown）
        disable_preview: 是否禁用链接预览
    Returns:
        bool: 是否发送成功
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram 配置缺失：TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 为空")
        return False

    # Telegram 消息上限 4096 字符，超长截断
    if len(text) > 4000:
        text = text[:4000] + "\n...(内容过长已截断)"

    url = TG_API.format(token=TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": disable_preview,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200 and resp.json().get("ok"):
            return True
        logger.error(f"TG 发送失败: {resp.status_code} {resp.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"TG 发送异常: {e}")
        return False


def send_long_message(text: str) -> bool:
    """发送长消息（按段落分多条）
    Telegram 单条上限 4096 字符
    """
    if len(text) <= 4000:
        return send_message(text)

    # 按 ## 标题分段
    sections = text.split("\n## ")
    if len(sections) <= 1:
        # 无法按标题分，硬切
        for i in range(0, len(text), 4000):
            send_message(text[i:i + 4000])
        return True

    # 第一段是头部
    send_message(sections[0])
    for sec in sections[1:]:
        send_message("## " + sec)
    return True
