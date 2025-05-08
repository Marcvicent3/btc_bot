# strategy.py
import pandas as pd
import requests
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands
import config
from binance.client import Client
from binance.exceptions import BinanceAPIException


# Función auxiliar para fallback a CoinGecko
def fetch_coingecko_ohlc(limit: int, interval_minutes: int = 5) -> pd.DataFrame:
    # Coingecko devuelve precios cada minuto; pedimos 1 día
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": 1, "interval": "minute"}
    data = requests.get(url, params=params).json()
    prices = data.get("prices", [])  # [ [ts, price], ... ]
    df = pd.DataFrame(prices, columns=["timestamp", "close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    # Resample a 5min OHLC
    ohlc = df["close"].resample(f"{interval_minutes}T").ohlc().dropna()
    ohlc["volume"] = 0.0
    # Limitamos al número de velas deseadas (manteniendo las últimas)
    if len(ohlc) > limit:
        ohlc = ohlc.iloc[-limit:]
    return ohlc


def get_data(limit: int = None) -> pd.DataFrame:
    """
    Devuelve DataFrame con columnas [open, high, low, close, volume].
    Intentamos desde Binance; si falla por región, usamos CoinGecko.
    """
    limit = limit or config.LIMIT
    # 1) Intentar Binance
    try:
        client = Client(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
        klines = client.get_klines(
            symbol=config.SYMBOL, interval=config.INTERVAL, limit=limit
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
        df = df.astype({c: float for c in ["open", "high", "low", "close", "volume"]})
        df.index = pd.to_datetime(df["close_time"], unit="ms")
        return df[["open", "high", "low", "close", "volume"]]
    except BinanceAPIException as e:
        print(f"[Binance] Ping falló ({e}); usando CoinGecko de respaldo.")
    except Exception as e:
        print(f"[Binance] Error inesperado ({e}); usando CoinGecko de respaldo.")

    # 2) Fallback CoinGecko
    df = fetch_coingecko_ohlc(limit=limit, interval_minutes=5)
    return df


def analyze(df: pd.DataFrame, last_price: float):
    """
    Dado el DataFrame, calcula indicadores y devuelve:
    (signal, reason, current_close, rsi, sma_fast, sma_slow, macd)
    """
    # Indicadores
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
    elif (
        (L["sma_fast"] > L["sma_slow"])
        and (L["macd"] > L["macd_sig"])
        and (L["rsi"] < 70)
    ):
        signal, reason = "COMPRA", "Señales alcistas: SMA+ MACD+ RSI<70"
    # Señal de venta: cruces bajistas
    elif (
        (L["sma_fast"] < L["sma_slow"])
        and (L["macd"] < L["macd_sig"])
        and (L["rsi"] > 30)
    ):
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
