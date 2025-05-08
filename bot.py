# === Archivo: bot.py ===
import os
import csv
import logging
import asyncio
from datetime import datetime
from telegram import InputFile
from telegram.ext import CommandHandler, ContextTypes, ApplicationBuilder

import config
import strategy
from plotter import plot_signal
from sentiment import get_sentiment

# Logging
logging.basicConfig(
    filename="btc_bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# — Suscripción y persistencia —
def load_subscribers() -> set[int]:
    if not os.path.exists(config.SUBSCRIBERS_FILE):
        return set()
    with open(config.SUBSCRIBERS_FILE) as f:
        return {int(line.strip()) for line in f if line.strip().isdigit()}


def save_subscribers(subs: set[int]):
    with open(config.SUBSCRIBERS_FILE, "w") as f:
        for cid in sorted(subs):
            f.write(f"{cid}\n")


def add_subscriber(chat_id: int):
    subs = load_subscribers()
    if chat_id not in subs:
        subs.add(chat_id)
        save_subscribers(subs)
        logging.info(f"Subscribed chat {chat_id}")


def get_last_buy_file(chat_id: int) -> str:
    return f"last_buy_price_{chat_id}.txt"


def load_last_buy_price(chat_id: int) -> float:
    try:
        with open(get_last_buy_file(chat_id)) as f:
            return float(f.read().strip())
    except:
        return 96000.0


def save_last_buy_price(chat_id: int, price: float):
    with open(get_last_buy_file(chat_id), "w") as f:
        f.write(str(price))


def get_history_file(chat_id: int) -> str:
    return f"btc_trades_history_{chat_id}.csv"


def append_to_history(
    chat_id: int, ts: str, sig: str, price: float, rsi: float, usd: float, pct: float
):
    path = get_history_file(chat_id)
    exists = os.path.exists(path)
    try:
        with open(path, "a", newline="") as f:
            w = csv.writer(f)
            if not exists:
                w.writerow(
                    ["timestamp", "signal", "price", "RSI", "USD_change", "%_change"]
                )
            w.writerow([ts, sig, price, rsi, usd, pct])
    except Exception as e:
        logging.error(f"Error writing history for {chat_id}: {e}")


# — Comandos —
async def start_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    cid = update.effective_chat.id
    add_subscriber(cid)
    await update.message.reply_text("👋 ¡Bienvenido! Te has suscrito. Usa /help.")


async def registrar_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    cid = update.effective_chat.id
    try:
        val = float(context.args[0])
        save_last_buy_price(cid, val)
        add_subscriber(cid)
        await update.message.reply_text(f"📝 Precio de compra registrado: ${val:.2f}")
    except:
        await update.message.reply_text("❌ Uso: /registrar <precio>")


async def estado_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    cid = update.effective_chat.id
    last = load_last_buy_price(cid)
    df = strategy.get_data()
    price = float(df.iloc[-1]["close"])
    du, dp = price - last, (price - last) / last * 100
    await update.message.reply_text(
        f"📊 Precio BTC: ${price:.2f}\n"
        f"📌 Tu compra: ${last:.2f}\n"
        f"📈 Cambio: {du:+.2f} USD ({dp:+.2f}%)"
    )


async def historial_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    cid = update.effective_chat.id
    path = get_history_file(cid)
    if os.path.exists(path):
        await context.bot.send_document(chat_id=cid, document=InputFile(path))
    else:
        await update.message.reply_text("❌ No hay historial.")


async def reset_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    cid = update.effective_chat.id
    for fn in (get_last_buy_file(cid), get_history_file(cid)):
        if os.path.exists(fn):
            os.remove(fn)
    subs = load_subscribers()
    subs.discard(cid)
    save_subscribers(subs)
    await update.message.reply_text("🔄 Reiniciado y desuscrito.")


async def help_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_markdown(
        "📘 *Comandos:*\n"
        "/start ⇒ Suscribirse\n"
        "/registrar <precio> ⇒ Definir precio compra\n"
        "/estado ⇒ Ver precio y cambio\n"
        "/historial ⇒ Descargar historial\n"
        "/reset ⇒ Reset y desuscribir\n"
        "/compra <USD> ⇒ Estimación BTC\n"
        "/venta <BTC> ⇒ Estimación USD\n"
        "/ney ⇒ ¡Hola zorrito!\n"
        "/help ⇒ Mostrar esta ayuda\n"
    )


async def compra_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    try:
        amt = float(context.args[0])
        df = strategy.get_data()
        price = float(df.iloc[-1]["close"])
        f_bin, f_pay = 0.001, 0.01
        net_bin = amt * (1 - f_bin)
        net_pay = amt * (1 - f_pay)
        btc_bin = net_bin / price
        btc_pay = net_pay / price
        await update.message.reply_markdown(
            f"💰 *Compra {amt:.2f} USD →*\n"
            f"Precio: ${price:.2f}\n"
            f"🏦 Binance: {btc_bin:.6f} BTC\n"
            f"🏪 Paymonade: {btc_pay:.6f} BTC"
        )
    except:
        await update.message.reply_text("❌ Uso: /compra <USD>")


async def venta_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    try:
        btc_amt = float(context.args[0])
        df = strategy.get_data()
        price = float(df.iloc[-1]["close"])
        gross = btc_amt * price
        f_bin, f_pay = 0.001, 0.01
        net_bin = gross * (1 - f_bin)
        net_pay = gross * (1 - f_pay)
        await update.message.reply_markdown(
            f"💵 *Venta {btc_amt:.6f} BTC →*\n"
            f"Precio: ${price:.2f}\n"
            f"🏦 Binance: ${net_bin:.2f}\n"
            f"🏪 Paymonade: ${net_pay:.2f}"
        )
    except:
        await update.message.reply_text("❌ Uso: /venta <BTC>")


async def ney_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text("Hola zorrito <3")


# — Monitor / Señales con IA —
async def monitor_job(context: ContextTypes.DEFAULT_TYPE):
    subs = load_subscribers()
    if not subs:
        return

    df = strategy.get_data()
    idx = len(df) - 1
    for cid in subs:
        last = load_last_buy_price(cid)
        sig, reason, price, rsi, sf, sl, macd = strategy.analyze(df, last)
        du, dp = price - last, (price - last) / last * 100
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        purchase_idx = (df["close"] - last).abs().idxmin()

        # 1️⃣ Gráfico
        buf = plot_signal(
            df, idx, sig or "NO_SIGNAL", buy_price=last, purchase_idx=purchase_idx
        )
        await context.bot.send_photo(chat_id=cid, photo=buf)

        # 2️⃣ Análisis técnico
        target = last * 1.02
        stop = last * 0.98
        potential = (target - price) / price * 100
        tech_map = {
            "COMPRA": "- SMA9↑ sobre SMA21\n- MACD > señal\n- RSI < 70",
            "VENTA": "- SMA9↓ bajo SMA21\n- MACD < señal\n- RSI > 30",
            "RECOMPRA": "- Precio cayó >3%\n- RSI < 35 (sobreventa)",
        }
        tech_exp = tech_map.get(sig, "")

        # 3️⃣ IA refuerza señal
        ia_text = f"Precio {price:.2f}, SMA9 {sf:.2f}, SMA21 {sl:.2f}, MACD {macd:.2f}"
        ia_sent = get_sentiment(ia_text)

        # 4️⃣ Construir mensaje
        msg = (
            f"🚨 *Señal BTC: {sig or 'Monitoreo'}* ({ts})\n\n"
            f"💲 Precio: ${price:.2f}\n"
            f"📌 Compra: ${last:.2f}\n"
            f"📈 Cambio: {du:+.2f} USD ({dp:+.2f}%)\n\n"
            f"🔼 Máx recom. venta: ${target:.2f}\n"
            f"🔽 Mín recom. compra: ${stop:.2f}\n"
            f"💡 Potencial: {potential:.2f}%\n\n"
            f"📝 Explicación técnica:\n{tech_exp}\n\n"
            f"🤖 IA dice: {ia_sent}"
        )

        await context.bot.send_message(chat_id=cid, text=msg, parse_mode="Markdown")

    await asyncio.sleep(300)


# — Arranque de la app —
app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
for name, handler in [
    ("start", start_command),
    ("registrar", registrar_command),
    ("estado", estado_command),
    ("historial", historial_command),
    ("reset", reset_command),
    ("help", help_command),
    ("compra", compra_command),
    ("venta", venta_command),
    ("ney", ney_command),
]:
    app.add_handler(CommandHandler(name, handler))

app.job_queue.run_repeating(monitor_job, interval=300, first=0)

if __name__ == "__main__":
    app.run_polling()
