import json
import os
import requests
from bs4 import BeautifulSoup
from http.server import BaseHTTPRequestHandler

# ==================== НАСТРОЙКИ ====================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "ТВОЙ_ТОКЕН_БОТА")
GROUP_ID = os.environ.get("GROUP_ID", "-1004385760186")

# Список каналов для проверки (без @)
CHANNELS = [
    "trevoga_odessa_noviny",
    "odesa_golovne",
    "odesa_informuee",
    "odessapublic"
]

# Фильтр рекламы
AD_KEYWORDS = [
    "робота", "вакансій", "перейти в канал", "підписників", 
    "запропонувати послуги", "робота одеса", "казино", "підпишись", "реклама"
]

LAST_SENT_TEXT = ""

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def is_ad(text: str) -> bool:
    text_lower = text.lower()
    return any(word in text_lower for word in AD_KEYWORDS)

def send_to_telegram(text: str, chat_id: str = GROUP_ID) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, json=payload, timeout=8)
        return res.status_code == 200
    except Exception as e:
        print(f"Ошибка при отправке в Telegram: {e}")
        return False

def get_latest_post(channel_username: str) -> str:
    url = f"https://t.me/s/{channel_username}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            messages = soup.find_all("div", class_="tgme_widget_message_text")
            
            if messages:
                last_msg = messages[-1]
                for br in last_msg.find_all("br"):
                    br.replace_with("\n")
                return last_msg.get_text().strip()
    except Exception as e:
        print(f"Ошибка парсинга канала {channel_username}: {e}")
        
    return ""

def check_and_send_alerts() -> str:
    global LAST_SENT_TEXT
    status_report = []
    
    for channel in CHANNELS:
        text = get_latest_post(channel)
        
        if text and not is_ad(text):
            if text != LAST_SENT_TEXT:
                success = send_to_telegram(text, chat_id=GROUP_ID)
                if success:
                    LAST_SENT_TEXT = text
                    status_report.append(f"Отправлено новое сообщение из @{channel}")
                    break
            else:
                status_report.append(f"В @{channel} нет новых сообщений")

    return "\n".join(status_report) if status_report else "Новых обновлений не обнаружено."

# ==================== ОСНОВНОЙ ХЭНДЛЕР VERCEL ====================

class handler(BaseHTTPRequestHandler):
    
    # Режим Cron: Вызывается Vercel Cron каждые 60 секунд (GET-запрос)
    def do_GET(self):
        report = check_and_send_alerts()
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(f"OK\n{report}".encode('utf-8'))

    # Режим Webhook: Обрабатывает сообщения в личке от пользователей (POST-запрос)
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            # Проверяем, есть ли входящее сообщение
            if "message" in data:
                chat_id = data["message"]["chat"]["id"]
                chat_type = data["message"]["chat"].get("type", "")

                # Если пишут в ЛИЧКУ (private chat)
                if chat_type == "private":
                    welcome_text = (
                        "👋 <b>Привет! Я бот для оповещения о воздушной тревоге в Одессе.</b>\n\n"
                        "📌 Добавь меня в свою группу и <b>сделай администратором со всеми правами</b>, "
                        "чтобы я мог оперативно присылать предупреждения и отбои тревог!"
                    )
                    send_to_telegram(welcome_text, chat_id=str(chat_id))

            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))
