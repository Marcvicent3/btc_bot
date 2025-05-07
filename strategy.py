import pandas as pd
from binance.client import Client
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands
import config

# Cliente de Binance
client = Client(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)


def get_data() -> pd.DataFrame:
    """Obtiene las últimas velas de Binance y retorna DataFrame."""
    klines = client.get_klines(
        symbol=config.SYMBOL, interval=config.INTERVAL, limit=config.LIMIT
    )
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
    """Calcula SMA, RSI, MACD, BB y devuelve señal + explicación + métricas."""
    df["sma_fast"] = SMAIndicator(df["close"], window=9).sma_indicator()
    df["sma_slow"] = SMAIndicator(df["close"], window=21).sma_indicator()
    df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
    macd_ind = MACD(df["close"])
    df["macd"] = macd_ind.macd()
    df["macd_sig"] = macd_ind.macd_signal()
    bb = BollingerBands(df["close"])
    df["bb_hi"] = bb.bollinger_hband()
    df["bb_lo"] = bb.bollinger_lband()

    L = df.iloc[-1]
    signal, reason = None, ""

    # Señal de recompra si baja >3% y RSI bajo
    if (L["close"] < last_price * config.BUY_THRESHOLD) and (L["rsi"] < 35):
        signal, reason = "RECOMPRA", "Precio >3% bajo y RSI bajo"
    # Señal de compra: cruces alcistas
    elif L["sma_fast"] > L["sma_slow"] and L["macd"] > L["macd_sig"] and L["rsi"] < 70:
        signal, reason = "COMPRA", "Señales alcistas: SMA+ MACD+ RSI<70"
    # Señal de venta: cruces bajistas
    elif L["sma_fast"] < L["sma_slow"] and L["macd"] < L["macd_sig"] and L["rsi"] > 30:
        signal, reason = "VENTA", "Señales bajistas: SMA- MACD- RSI>30"

    return (
        signal,
        reason,
        L["close"],
        L["rsi"],
        L["sma_fast"],
        L["sma_slow"],
        L["macd"],
    )
