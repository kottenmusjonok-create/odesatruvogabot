import asyncio
import json
import os
from http.server import BaseHTTPRequestHandler
import requests
from telethon import TelegramClient
from telethon.sessions import StringSession

# ==================== НАСТРОЙКИ ====================

API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GROUP_ID = os.environ.get("GROUP_ID", "-1004385760186")

# Список каналов (для публичных — username без @, для приватных — ID с -100...)
TARGET_CHANNELS = [
    "trevoga_odessa_noviny",
    "odesa_golovne",
    "odesa_informuee",
    "odessapublic",
    -1001457356974,  # Важно: число (int) без кавычек
]

AD_KEYWORDS = [
    "робота",
    "вакансій",
    "перейти в канал",
    "підписників",
    "запропонувати послуги",
    "робота одеса",
    "казино",
    "підпишись",
    "реклама",
]


def is_ad(text: str) -> bool:
  text_lower = text.lower()
  return any(word in text_lower for word in AD_KEYWORDS)


def send_to_group(text: str) -> bool:
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
  payload = {
      "chat_id": GROUP_ID,
      "text": text,
      "parse_mode": "HTML",
      "disable_web_page_preview": True,
  }
  try:
    res = requests.post(url, json=payload, timeout=8)
    return res.status_code == 200
  except Exception as e:
    print(f"Ошибка отправки через бота: {e}")
    return False


async def fetch_and_process():
  status_messages = []

  # Инициализация Telethon через полученную StringSession
  client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
  await client.connect()

  if not await client.is_user_authorized():
    await client.disconnect()
    return "Ошибка: Сессия не авторизована!"

  try:
    for channel in TARGET_CHANNELS:
      try:
        messages = await client.get_messages(channel, limit=1)
        if messages:
          msg = messages[0]
          text = msg.text or msg.message or ""

          if text and not is_ad(text):
            if send_to_group(text):
              status_messages.append(f"Успешно переслано из {channel}")
            else:
              status_messages.append(f"Ошибка отправки из {channel}")
          else:
            status_messages.append(f"В {channel} нет подходящего текста/реклама")
      except Exception as e:
        status_messages.append(f"Ошибка чтения {channel}: {str(e)}")
  finally:
    await client.disconnect()

  return "\n".join(status_messages)


# ==================== ХЭНДЛЕР VERCEL ====================


class handler(BaseHTTPRequestHandler):

  def do_GET(self):
    try:
      report = asyncio.run(fetch_and_process())
      self.send_response(200)
      self.send_header("Content-type", "text/plain; charset=utf-8")
      self.end_headers()
      self.wfile.write(f"OK\n{report}".encode("utf-8"))
    except Exception as e:
      self.send_response(500)
      self.end_headers()
      self.wfile.write(f"Error: {str(e)}".encode("utf-8"))

  def do_POST(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b"OK")
