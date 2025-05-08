# === Archivo: plotter.py ===
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
    """
    Genera un gráfico compacto y legible de la señal de BTC.
    """
    fig, ax = plt.subplots(figsize=(6, 3), dpi=150)
    x = df.index

    # Precio y SMAs
    ax.plot(x, df["close"], label="Precio de Cierre", linewidth=1.5, color="blue")
    ax.plot(x, df["sma_fast"], label="SMA 9", linewidth=1, color="orange")
    ax.plot(x, df["sma_slow"], label="SMA 21", linewidth=1, color="green")

    # Bandas de Bollinger
    bb = BollingerBands(df["close"])
    ax.fill_between(
        x,
        bb.bollinger_lband(),
        bb.bollinger_hband(),
        color="gray",
        alpha=0.2,
        label="Bandas Bollinger",
    )

    # Precio de compra
    if buy_price is not None and purchase_idx is not None:
        ax.axhline(
            buy_price,
            color="red",
            linestyle="--",
            label=f"Precio compra: ${buy_price:.2f}",
        )
        ax.scatter(purchase_idx, buy_price, color="red", s=50)

    # Niveles recomendados
    if buy_price is not None:
        target_price = buy_price * (1 + target_pct)
        stop_price = buy_price * (1 - stop_pct)
        ax.axhline(
            target_price,
            color="green",
            linestyle="-.",
            label=f"Máx recom. venta: ${target_price:.2f}",
        )
        ax.axhline(
            stop_price,
            color="blue",
            linestyle="-.",
            label=f"Mín recom. compra: ${stop_price:.2f}",
        )

    # Máx/Mín reales
    max_val = df["close"].max()
    min_val = df["close"].min()
    hi = df["close"].idxmax()
    lo = df["close"].idxmin()
    ax.scatter(
        hi,
        max_val,
        marker="^",
        color="darkgreen",
        s=50,
        label=f"▲ Máx actual: ${max_val:.2f}",
    )
    ax.scatter(
        lo,
        min_val,
        marker="v",
        color="darkblue",
        s=50,
        label=f"▼ Mín actual: ${min_val:.2f}",
    )

    # Estética
    ax.set_title("Señal de BTC", fontsize=10)
    ax.set_xlabel("Periodo (5m cada uno)", fontsize=8)
    ax.set_ylabel("Precio (USD)", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize=6)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return buf
