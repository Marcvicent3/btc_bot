import matplotlib.pyplot as plt
from io import BytesIO
from ta.volatility import BollingerBands


def plot_signal(
    df,
    signal_idx: int,
    label: str,
    buy_price: float = None,
    purchase_idx: int = None,
    target_pct: float = 0.02,
    stop_pct: float = 0.02,
):
    plt.figure(figsize=(8, 4))
    plt.plot(df["close"], label="Precio de Cierre", color="blue")
    plt.plot(df["sma_fast"], label="SMA 9 (naranja)", color="orange")
    plt.plot(df["sma_slow"], label="SMA 21 (verde)", color="green")

    # Bollinger Bands (zona típica de precio)
    bb = BollingerBands(df["close"])
    plt.fill_between(
        df.index,
        bb.bollinger_lband(),
        bb.bollinger_hband(),
        color="grey",
        alpha=0.2,
        label="Bollinger Bands",
    )

    # Señal (sólo si es real)
    if label != "NO_SIGNAL":
        plt.scatter(
            signal_idx,
            df["close"].iloc[signal_idx],
            marker="^",
            s=100,
            label=label,
            color="purple",
        )

    # Tu punto de compra
    if buy_price is not None and purchase_idx is not None:
        plt.scatter(
            purchase_idx,
            buy_price,
            marker="o",
            s=80,
            label=f"Tu compra: ${buy_price:.2f}",
            color="red",
        )
        plt.axhline(buy_price, linestyle="--", color="red", label=f"Precio compra")

        # Líneas recomendadas ±2%
        target = buy_price * (1 + target_pct)
        stop = buy_price * (1 - stop_pct)
        plt.axhline(
            target,
            linestyle="-.",
            color="darkgreen",
            label=f"Máx. recom. (vender): ${target:.2f}",
        )
        plt.axhline(
            stop,
            linestyle="-.",
            color="darkred",
            label=f"Mín. recom. (comprar): ${stop:.2f}",
        )

    # Máximo y mínimo reales (con valor en leyenda)
    max_val = df["close"].max()
    hi = df["close"].idxmax()
    plt.scatter(
        hi,
        max_val,
        marker="^",
        s=80,
        label=f"Máximo rec.: ${max_val:.2f}",
        color="darkgreen",
    )
    min_val = df["close"].min()
    lo = df["close"].idxmin()
    plt.scatter(
        lo,
        min_val,
        marker="v",
        s=80,
        label=f"Mínimo rec.: ${min_val:.2f}",
        color="darkblue",
    )

    plt.title("Señal de BTC")
    plt.xlabel("Periodo (5m cada uno)")
    plt.ylabel("Precio (USD)")
    plt.legend(loc="upper left", fontsize="small")

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf
