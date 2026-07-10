import os
import sys
import requests

import chief_env
from telegram_listener_integrity import resolve_role_bot_token

BOT_TOKEN = resolve_role_bot_token("chief")
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
def send_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
    }, timeout=15)
    response.raise_for_status()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python chief_sender.py "your message here"')
        sys.exit(1)

    message = " ".join(sys.argv[1:])
    send_message(message)
    print("Message sent.")
