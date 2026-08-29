import pandas as pd
from typing import List, Dict

def generate_markdown_report(
    backtest_metrics: Dict,
    walk_forward_folds: List[Dict],
    ticker: str,
    strategy_name: str,
    output_path: str = "backtest_report.md"
) -> str:
    """Generates a detailed systematic backtest report in Markdown."""
    
    # Header
    report = []
    report.append(f"# Systematic Backtest Report: {strategy_name} on {ticker}")
    report.append("\n## Executive Summary")
    report.append("\n| Metric | Value |")
    report.append("|---|---|")
    report.append(f"| **Ticker** | {ticker} |")
    report.append(f"| **Strategy** | {strategy_name} |")
    report.append(f"| **Final Portfolio Value** | ${backtest_metrics['Final_Value']:,.2f} |")
    report.append(f"| **CAGR** | {backtest_metrics['CAGR']:.2%} |")
    report.append(f"| **Max Drawdown** | {backtest_metrics['Max_Drawdown']:.2%} |")
    report.append(f"| **Sharpe Ratio** | {backtest_metrics['Sharpe']:.2f} |")
    report.append(f"| **Profit Factor** | {backtest_metrics['Profit_Factor']:.2f} |")
    report.append(f"| **Total Trades** | {backtest_metrics['Total_Trades']} |")
    
    # Walk-Forward Validation Table
    if walk_forward_folds:
        report.append("\n## Walk-Forward Validation (Expanding In-Sample)")
        report.append("\n| Fold | IS Date Range | IS Sharpe | IS Max DD | OOS Date Range | OOS Sharpe | OOS Max DD |")
        report.append("|---|---|---|---|---|---|---|")
        
        for fold in walk_forward_folds:
            num = fold['fold']
            def _d(x):
                return x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x)
            is_dates = f"{_d(fold['is_start'])} to {_d(fold['is_end'])}"
            oos_dates = f"{_d(fold['oos_start'])} to {_d(fold['oos_end'])}"
            
            is_sharpe = fold['is_metrics']['Sharpe']
            is_dd = fold['is_metrics']['Max_Drawdown']
            oos_sharpe = fold['oos_metrics']['Sharpe']
            oos_dd = fold['oos_metrics']['Max_Drawdown']
            
            report.append(
                f"| {num} | {is_dates} | {is_sharpe:.2f} | {is_dd:.2%} | {oos_dates} | {oos_sharpe:.2f} | {oos_dd:.2%} |"
            )
            
    report_content = "\n".join(report)
    
    with open(output_path, "w") as f:
        f.write(report_content)
        
    return report_content

def export_trade_log(trades: List[Dict], output_path: str = "trade_log.csv") -> pd.DataFrame:
    """Exports the backtest trade history log to a detailed CSV."""
    if not trades:
        df = pd.DataFrame(columns=["Entry Date", "Exit Date", "Type", "Entry Price", "Exit Price", "Size", "P&L", "Holding Period (Days)"])
        df.to_csv(output_path, index=False)
        return df
        
    log_data = []
    for t in trades:
        entry_date = t['entry_date']
        exit_date = t.get('exit_date', pd.Timestamp.now())
        holding_days = (exit_date - entry_date).days
        
        log_data.append({
            "Entry Date": entry_date.strftime("%Y-%m-%d"),
            "Exit Date": exit_date.strftime("%Y-%m-%d") if 'exit_date' in t else "OPEN",
            "Type": t['type'],
            "Entry Price": round(t['entry_price'], 4),
            "Exit Price": round(t['exit_price'], 4) if 'exit_price' in t else 0.0,
            "Size": round(t['size'], 2),
            "P&L": round(t.get('pnl', 0.0), 2),
            "Holding Period (Days)": holding_days
        })
        
    df = pd.DataFrame(log_data)
    df.to_csv(output_path, index=False)
    return df
