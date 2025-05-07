import os
import glob
import csv
import logging
from datetime import datetime
from telegram import InputFile
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ApplicationBuilder,
)
import asyncio

import config
import strategy
from plotter import plot_signal

# Logging
logging.basicConfig(
    filename="btc_bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# Subscripción y persistencia
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


def get_history_file(chat_id: int) -> str:
    return f"btc_trades_history_{chat_id}.csv"


def load_last_buy_price(chat_id: int) -> float:
    try:
        with open(get_last_buy_file(chat_id)) as f:
            return float(f.read().strip())
    except:
        return 96000.0


def save_last_buy_price(chat_id: int, price: float):
    with open(get_last_buy_file(chat_id), "w") as f:
        f.write(str(price))


def append_to_history(
    chat_id: int, ts: str, sig: str, price: float, rsi: float, usd: float, pct: float
):
    path = get_history_file(chat_id)
    exists = os.path.exists(path)
    try:
        with open(path, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            if not exists:
                writer.writerow(
                    ["timestamp", "signal", "price", "RSI", "USD_change", "%_change"]
                )
            writer.writerow([ts, sig, price, rsi, usd, pct])
    except Exception as e:
        logging.error(f"Error writing history for {chat_id}: {e}")


# ─── Comandos ──────────────────────────────────────────────
async def start_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    cid = update.effective_chat.id
    add_subscriber(cid)
    await update.message.reply_text(
        "👋 Bienvenido! Has sido suscrito.\n"
        "Usa /registrar <precio> para definir tu referencia.\n"
        "Mira /help para más comandos."
    )


async def registrar_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    cid = update.effective_chat.id
    try:
        val = float(context.args[0])
        save_last_buy_price(cid, val)
        add_subscriber(cid)
        await update.message.reply_text(f"📝 Precio registrado: ${val:.2f}")
    except:
        await update.message.reply_text(
            "❌ Uso: /registrar <precio> (ej: /registrar 95000)"
        )


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
        f"📌 Tu referencia: ${last:.2f}\n"
        f"📈 Cambio: ${du:.2f} ({dp:.2f}%)"
    )


async def historial_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    cid = update.effective_chat.id
    path = get_history_file(cid)
    if os.path.exists(path):
        await context.bot.send_document(chat_id=cid, document=InputFile(path))
        await update.message.reply_text("📁 Historial enviado.")
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
    await update.message.reply_text("🔄 Datos reiniciados y desuscrito.")


async def help_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_markdown(
        "📘 *Comandos:*\n"
        "/start ==> Para registrarte y recibir señales.\n"
        "/registrar <precio> ==> Para definir tu precio de referencia.\n"
        "/estado ==> Para ver el precio actual y tu referencia.\n"
        "/historial ==> Para descargar tu historial de operaciones.\n"
        "/reset ==> Para reiniciar tus datos y desuscribirte.\n"
        "/help ==> Para ver esta ayuda.\n"
        "/ney ==> Para un comando especial oculto.\n\n"
    )


async def ney_command(
    update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text("Hola zorrito <3")


# ─── Monitor / Señales ─────────────────────────────────────
async def monitor_job(context: ContextTypes.DEFAULT_TYPE):
    subs = load_subscribers()
    if not subs:
        return

    df = strategy.get_data()
    idx = len(df) - 1

    # Glosario breve
    glossary = (
        "\n\n📘 *Leyenda:*"
        "\n- SMA 9 vs SMA 21: promedios; su cruce indica giro de tendencia."
        "\n- Bollinger Bands: banda gris de volatilidad; fuera → rebote o corrección."
        "\n- Líneas punteadas: niveles ±2% desde tu compra (recomenda./comprar)."
    )

    for cid in subs:
        last = load_last_buy_price(cid)

        # Señal y métricas
        sig, reason, price, rsi, sf, sl, macd = strategy.analyze(df, last)
        du, dp = price - last, (price - last) / last * 100
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Cálculo de máximos/mínimos reales
        max_p = df["close"].max()
        min_p = df["close"].min()

        # Riesgo simple: basado en caída al mínimo
        loss_pct = (min_p - last) / last * 100
        risk = (
            "🟢 BAJO"
            if abs(loss_pct) < 2
            else "🟠 MODERADO" if abs(loss_pct) < 5 else "🔴 ALTO"
        )

        # Índice aproximado de tu compra
        purchase_idx = (df["close"] - last).abs().idxmin()

        # Gráfico
        buf = plot_signal(
            df, idx, sig or "NO_SIGNAL", buy_price=last, purchase_idx=purchase_idx
        )
        await context.bot.send_photo(chat_id=cid, photo=buf)

        # Prepara targets recomendados
        target_price = last * 1.02
        stop_price = last * 0.98

        # Explicación técnica de la señal
        if sig == "COMPRA":
            tech = (
                "\n\n📝 *Explicación señal:*"
                "\n- SMA9 cruzó arriba de SMA21 → inicio de tendencia alcista."
                "\n- MACD > señal → impulso comprador."
                "\n- RSI < 70 → aún no está sobrecomprado."
            )
        elif sig == "VENTA":
            tech = (
                "\n\n📝 *Explicación señal:*"
                "\n- SMA9 cruzó debajo de SMA21 → inicio de tendencia bajista."
                "\n- MACD < señal → impulso vendedor."
                "\n- RSI > 30 → aún no está sobrevendido."
            )
        else:
            tech = ""

        # Construye el mensaje
        header = f"[{ts}] {'🔔 '+sig if sig else '🔸 Sin señal clara'}"
        body = (
            f"\n\n💲 Precio actual: ${price:.2f}"
            f"\n📌 Tu compra: ${last:.2f}"
            f"\n📈 Desde tu compra: ${du:.2f} ({dp:.2f}%)"
            f"\n🔼 Máx. recom. (vender): ${target_price:.2f}"
            f"\n🔽 Mín. recom. (comprar): ${stop_price:.2f}"
            f"\n⚠️ Riesgo: {risk}"
            f"{tech}"
            f"{glossary}"
        )

        await context.bot.send_message(
            chat_id=cid, text=header + body, parse_mode="Markdown"
        )

    await asyncio.sleep(300)


# Creamos y configuramos la app
app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
for cmd, handler in [
    ("start", start_command),
    ("registrar", registrar_command),
    ("estado", estado_command),
    ("historial", historial_command),
    ("reset", reset_command),
    ("help", help_command),
    ("ney", ney_command),
]:
    app.add_handler(CommandHandler(cmd, handler))

# Programar monitor cada 5 minutos
app.job_queue.run_repeating(monitor_job, interval=300, first=0)
