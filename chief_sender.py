import os
import sys
import requests

def _load_env_file() -> None:
    env_path = "/home/openclaw/.chief.env"
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


_load_env_file()
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
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
