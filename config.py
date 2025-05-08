import os
from dotenv import load_dotenv
from binance.client import Client

# Carga variables de entorno desde .env
load_dotenv()

# Claves de API
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Ficheros locales
SUBSCRIBERS_FILE = "subscribers.txt"

# Parámetros de trading
SYMBOL = "BTCUSDT"
INTERVAL = Client.KLINE_INTERVAL_5MINUTE
LIMIT = 100
BUY_THRESHOLD = 0.97  # 3% por debajo → recompra
