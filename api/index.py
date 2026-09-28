import os
import json
import requests
from bs4 import BeautifulSoup
from http.server import BaseHTTPRequestHandler
from upstash_redis import Redis

# Подключаем Redis
redis = Redis.from_env()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "ТВОЙ_ТОКЕН_БОТА")
CHANNEL_USERNAME = "trevoga_odessa_noviny"

AD_KEYWORDS = ["робота", "вакансій", "перейти в канал", "підписників", "запропонувати послуги", "робота одеса"]

def is_ad(text: str) -> bool:
    text_lower = text.lower()
    return any(word in text_lower for word in AD_KEYWORDS)

def add_chat_id(chat_id: int):
    """Добавляет ID чата в множества (Set) в Redis."""
    redis.sadd("registered_chats", str(chat_id))

def get_all_chats() -> list:
    """Получает список всех зарегистрированных чатов."""
    chats = redis.smembers("registered_chats")
    result = []
    for c in chats:
        if isinstance(c, bytes):
            result.append(c.decode('utf-8'))
        else:
            result.append(str(c))
    return result

def broadcast_message(text: str):
    """Рассылает сообщение по всем сохраненным чатам."""
    chats = get_all_chats()
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    for chat_id in chats:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, json=payload, timeout=3)
        except Exception as e:
            print(f"Ошибка отправки в чат {chat_id}: {e}")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Обработка Webhook от Telegram (когда бота добавляют в чат)."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            # Если бота добавили в группу или ему написали в личку
            if "message" in data:
                chat_id = data["message"]["chat"]["id"]
                add_chat_id(chat_id)
            elif "my_chat_member" in data:
                chat_id = data["my_chat_member"]["chat"]["id"]
                add_chat_id(chat_id)

            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write('OK'.encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

    def do_GET(self):
        """Проверка канала раз в минуту и рассылка по всем чатам."""
        try:
            url = f"https://t.me/s/{CHANNEL_USERNAME}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                messages = soup.find_all("div", class_="tgme_widget_message")
                
                if messages:
                    last_msg = messages[-1]
                    link_tag = last_msg.find("a", class_="tgme_widget_message_date")
                    post_id = link_tag['href'] if link_tag else None

                    text_div = last_msg.find("div", class_="tgme_widget_message_text")
                    
                    if post_id and text_div:
                        last_saved_id = redis.get("last_post_id")
                        if isinstance(last_saved_id, bytes):
                            last_saved_id = last_saved_id.decode('utf-8')

                        # Если появился НОВЫЙ пост
                        if str(last_saved_id) != str(post_id):
                            for br in text_div.find_all("br"):
                                br.replace_with("\n")
                            
                            clean_text = text_div.get_text().strip()

                            if not is_ad(clean_text):
                                formatted_text = f"🚨 <b>ОПЕРАТИВНА ІНФОРМАЦІЯ</b> 🚨\n\n{clean_text}"
                                # Отправляем во ВСЕ чаты
                                broadcast_message(formatted_text)
                                redis.set("last_post_id", post_id)

            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write('OK'.encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))
