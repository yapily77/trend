import matplotlib.pyplot as plt
import pandas as pd

def plot_equity_curve(
    equity: pd.Series,
    drawdown: pd.Series,
    ticker: str,
    strategy_name: str,
    output_path: str = "equity_curve.png"
):
    """
    Plots the equity curve and drawdown profile.
    Saves the output to the specified image file path.
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    
    # Plot equity curve
    ax1.plot(equity.index, equity.values, label="Portfolio Equity", color="blue", lw=2)
    ax1.set_title(f"Equity Curve & Drawdowns: {strategy_name} on {ticker}")
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.grid(True)
    ax1.legend(loc="upper left")
    
    # Plot drawdown (highlighted in red)
    ax2.fill_between(drawdown.index, drawdown.values, 0, label="Drawdown", color="red", alpha=0.3)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.grid(True)
    ax2.legend(loc="lower left")
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
