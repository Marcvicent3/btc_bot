import os
import glob
import logging
import nest_asyncio
import csv
import asyncio
from datetime import datetime
import pandas as pd
from binance.client import Client
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from dotenv import load_dotenv

# Permite anidar loops de asyncio en VS Code Interactive
nest_asyncio.apply()

# Carga variables de entorno
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SUBSCRIBERS_FILE = "subscribers.txt"

# Logging
logging.basicConfig(
    filename="btc_bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Cliente Binance
client = Client(API_KEY, API_SECRET)

# Configuración de trading
SYMBOL = "BTCUSDT"
INTERVAL = Client.KLINE_INTERVAL_5MINUTE
LIMIT = 100
BUY_THRESHOLD = 0.97  # 3% por debajo del último para RECOMPRA


# ─── Gestión de suscriptores ──────────────────────────────
def load_subscribers() -> set[int]:
    if not os.path.exists(SUBSCRIBERS_FILE):
        return set()
    with open(SUBSCRIBERS_FILE, "r") as f:
        return {int(line.strip()) for line in f if line.strip().isdigit()}


def save_subscribers(subs: set[int]):
    with open(SUBSCRIBERS_FILE, "w") as f:
        for cid in sorted(subs):
            f.write(f"{cid}\n")


def add_subscriber(chat_id: int):
    subs = load_subscribers()
    if chat_id not in subs:
        subs.add(chat_id)
        save_subscribers(subs)
        logging.info(f"Subscribed chat {chat_id}")


# ─── Gestión de precios e historial por chat ───────────────
def get_last_buy_file(chat_id: int) -> str:
    return f"last_buy_price_{chat_id}.txt"


def get_history_file(chat_id: int) -> str:
    return f"btc_trades_history_{chat_id}.csv"


def load_last_buy_price(chat_id: int) -> float:
    try:
        with open(get_last_buy_file(chat_id), "r") as f:
            return float(f.read().strip())
    except:
        return 96000.0


def save_last_buy_price(chat_id: int, price: float):
    with open(get_last_buy_file(chat_id), "w") as f:
        f.write(str(price))


def append_to_history(
    chat_id: int,
    timestamp: str,
    signal: str,
    price: float,
    rsi: float,
    change_usd: float,
    change_pct: float,
):
    path = get_history_file(chat_id)
    exists = os.path.isfile(path)
    try:
        with open(path, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            if not exists:
                writer.writerow(
                    ["timestamp", "signal", "price", "RSI", "USD_change", "%_change"]
                )
            writer.writerow([timestamp, signal, price, rsi, change_usd, change_pct])
    except Exception as e:
        logging.error(f"Error writing history for {chat_id}: {e}")


# ─── Comandos de Telegram ──────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    add_subscriber(chat_id)
    await update.message.reply_text(
        "👋 ¡Bienvenido! Has sido suscrito a las señales de BTC.\n"
        "Usa /registrar <precio> para establecer tu referencia.\n"
        "Puedes usar /help para ver todos los comandos."
    )


async def registrar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        val = float(context.args[0])
        save_last_buy_price(chat_id, val)
        add_subscriber(chat_id)
        # Debug info: read back file and list existing files
        content = open(get_last_buy_file(chat_id)).read().strip()
        files = glob.glob("last_buy_price_*.txt")
        logging.info(
            f"Registrar debug for {chat_id}: file={get_last_buy_file(chat_id)}, content={content}"
        )
        await update.message.reply_text(
            f"📝 Registrado precio ${val:.2f} para chat {chat_id}."
        )
        await update.message.reply_text(f"📂 Archivos actuales: {files}")
    except Exception:
        await update.message.reply_text("❌ Uso inválido. Prueba: /registrar 95000")


async def estado_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    price = float(client.get_symbol_ticker(symbol=SYMBOL)["price"])
    last = load_last_buy_price(chat_id)
    du = price - last
    dp = (du / last) * 100
    await update.message.reply_text(
        f"📊 Precio actual BTC: ${price:.2f}\n"
        f"📌 Tu último precio registrado: ${last:.2f}\n"
        f"📈 Cambio: ${du:.2f} ({dp:.2f}%)"
    )


async def historial_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    path = get_history_file(chat_id)
    if os.path.exists(path):
        await context.bot.send_document(chat_id=chat_id, document=InputFile(path))
        await update.message.reply_text("📁 Aquí tienes tu historial.")
    else:
        await update.message.reply_text("❌ Aún no tienes historial.")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    for fn in (get_last_buy_file(chat_id), get_history_file(chat_id)):
        if os.path.exists(fn):
            os.remove(fn)
    subs = load_subscribers()
    subs.discard(chat_id)
    save_subscribers(subs)
    await update.message.reply_text("🔄 Tus datos han sido reiniciados y desuscrito.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(
        "📘 *Comandos disponibles:*\n"
        "/start     – Suscribirse\n"
        "/registrar – Registra tu precio (ej: /registrar 95000)\n"
        "/estado    – Muestra tu estado actual\n"
        "/historial – Descarga tu historial\n"
        "/reset     – Reinicia tus datos y desuscribe\n"
        "/id        – Muestra tu chat ID\n"
        "/myprice   – Muestra tu precio guardado\n"
        "/help      – Esta ayuda\n"
        "/ney       – Comando oculto 🦊"
    )


async def ney_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hola zorrito <3")


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Este chat tiene ID: {chat_id}")


async def myprice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    price = load_last_buy_price(chat_id)
    await update.message.reply_text(f"Tu precio guardado es: ${price:.2f}")


# ─── Lógica de trading ─────────────────────────────────────
def get_data() -> pd.DataFrame:
    klines = client.get_klines(symbol=SYMBOL, interval=INTERVAL, limit=LIMIT)
    df = pd.DataFrame(
        klines,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "trades",
            "taker_buy_vol",
            "taker_buy_quote_vol",
            "ignore",
        ],
    )
    return df.astype({c: float for c in ["open", "high", "low", "close", "volume"]})


def analyze(df: pd.DataFrame, last_price: float):
    df["sma_f"] = SMAIndicator(df["close"], 9).sma_indicator()
    df["sma_s"] = SMAIndicator(df["close"], 21).sma_indicator()
    df["rsi"] = RSIIndicator(df["close"], 14).rsi()
    macd_i = MACD(df["close"])
    df["macd"] = macd_i.macd()
    df["sig_macd"] = macd_i.macd_signal()
    bb = BollingerBands(df["close"])
    df["bb_hi"] = bb.bollinger_hband()
    df["bb_lo"] = bb.bollinger_lband()

    L = df.iloc[-1]
    signal, explain = None, ""
    if (L["close"] < last_price * BUY_THRESHOLD) and (L["rsi"] < 35):
        signal, explain = "RECOMPRA", "Precio >3% bajo y RSI bajo"
    elif (
        L["sma_f"] > L["sma_s"]
        and L["macd"] > L["sig_macd"]
        and L["close"] < L["bb_hi"]
        and L["rsi"] < 70
    ):
        signal, explain = "COMPRA", "Tendencia alcista detectada"
    elif (
        L["sma_f"] < L["sma_s"]
        and L["macd"] < L["sig_macd"]
        and L["close"] > L["bb_lo"]
        and L["rsi"] > 30
    ):
        signal, explain = "VENTA", "Tendencia bajista, considera salir"
    return signal, explain, L["close"], L["rsi"], L["sma_f"], L["sma_s"], L["macd"]


def calc_change(current: float, buy: float):
    diff = current - buy
    return diff, (diff / buy) * 100


async def monitor_loop(bot):
    while True:
        try:
            df = get_data()
            for chat_id in load_subscribers():
                last = load_last_buy_price(chat_id)
                sig, explain, price, rsi, sf, ss, macd = analyze(df, last)
                usd_diff, pct_diff = calc_change(price, last)
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if sig:
                    append_to_history(chat_id, ts, sig, price, rsi, usd_diff, pct_diff)
                    if sig == "COMPRA":
                        save_last_buy_price(chat_id, price)
                    text = (
                        f"[{ts}] 🔔 Señal: {sig}\n{explain}\n\n"
                        f"Precio: ${price:.2f}\nRSI: {rsi:.2f}\n"
                        f"SMA: {sf:.2f}/{ss:.2f}\nMACD: {macd:.2f}\n"
                        f"Cambio: ${usd_diff:.2f} ({pct_diff:.2f}%)"
                    )
                else:
                    text = (
                        f"[{ts}] 🔸 Sin señal clara\n"
                        f"Precio: ${price:.2f}\nRSI: {rsi:.2f}\n"
                        f"Cambio: ${usd_diff:.2f} ({pct_diff:.2f}%)"
                    )
                await bot.send_message(chat_id=chat_id, text=text)
            await asyncio.sleep(300)
        except Exception as e:
            logging.error(f"Monitor error: {e}")
            await asyncio.sleep(60)


# ─── Entrada principal ─────────────────────────────────────
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("registrar", registrar_command))
    app.add_handler(CommandHandler("estado", estado_command))
    app.add_handler(CommandHandler("historial", historial_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ney", ney_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("myprice", myprice_command))
    # Start monitor
    asyncio.create_task(monitor_loop(app.bot))
    # Run bot
    await app.run_polling(close_loop=False)


if __name__ == "__main__":
    asyncio.run(main())
