import os
import re
import requests
from bs4 import BeautifulSoup
from http.server import BaseHTTPRequestHandler

# === НАСТРОЙКИ ===
# Вставь сюда токен бота от @BotFather и ID вашей группы
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ТВОЙ_ТОКЕН_БОТА")
GROUP_ID = os.environ.get("GROUP_ID", "-1003770349831")

# Название канала (без символа @)
CHANNEL_USERNAME = "trevoga_odessa_noviny" 

# Слова для фильтрации рекламы
AD_KEYWORDS = ["робота", "вакансій", "перейти в канал", "підписників", "запропонувати послуги", "робота одеса"]

def is_ad(text: str) -> bool:
    """Проверяет, является ли текст рекламой"""
    text_lower = text.lower()
    return any(word in text_lower for word in AD_KEYWORDS)

def send_to_telegram(text: str):
    """Отправляет готовый текст в вашу группу через Telegram Bot API"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # 1. Загружаем публичную веб-страницу канала
            url = f"https://t.me/s/{CHANNEL_USERNAME}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Ищем все блоки с сообщениями
                messages = soup.find_all("div", class_="tgme_widget_message_text")
                
                if messages:
                    # Берем самое последнее сообщение в канале
                    last_msg = messages[-1]
                    
                    # Преобразуем HTML-теги переноса строки <br> в обычный перенос
                    for br in last_msg.find_all("br"):
                        br.replace_with("\n")
                    
                    clean_text = last_msg.get_text().strip()

                    # 2. Проверяем, что это не реклама
                    if not is_ad(clean_text):
                        # 3. Красиво оформляем и отправляем в группу
                        formatted_text = f"🚨 <b>ОПЕРАТИВНА ІНФОРМАЦІЯ</b> 🚨\n\n{clean_text}"
                        send_to_telegram(formatted_text)

            # Ответ для Vercel, что всё прошло успешно
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write('OK'.encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))
