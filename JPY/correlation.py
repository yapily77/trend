"""Correlation analysis between Donchian 20 and TD Sequential signals on USDJPY=X.
Measures signal agreement, trade overlap, and TDST filter effectiveness
before combining them.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

import pandas as pd, numpy as np
from scripts.bt.data import DataFeed
from scripts.bt.strategies import DonchianBreakout, TDSequentialBreakout, TDSequentialCounterTrend, TDComboStrategy
from scripts.bt.indicators import td_buy_setup, td_sell_setup, td_buy_countdown, td_sell_countdown, td_st_demand, td_st_supply, donchian_channel

feed = DataFeed()
df = feed.get_data('USDJPY=X', start='1995-01-01', end='2026-05-30')
close = df['Close']; high = df['High']; low = df['Low']

# Generate signals
donchian = DonchianBreakout(period=20).signals(df)
td_breakout = TDSequentialBreakout().signals(df)
td_counter = TDSequentialCounterTrend().signals(df)
td_combo = TDComboStrategy().signals(df)

# TDST levels
demand = td_st_demand(df)
supply = td_st_supply(df)
setup_buy = td_buy_setup(close)
sell_setup = td_sell_setup(close)
buy_cd = td_buy_countdown(df)
sell_cd = td_sell_countdown(df)

# Mask for valid bars (where we have enough history)
valid = pd.Series(True, index=df.index)
valid.iloc[:20] = False  # Donchian needs 20 bars

# ---- 1. Raw signal correlation ----
print("=" * 70)
print("SIGNAL CORRELATION (daily, valid bars only)")
print("=" * 70)
for name, sig in [('Donchian20', donchian), ('TD_Breakout', td_breakout),
                  ('TD_CounterTrend', td_counter), ('TD_Combo', td_combo)]:
    sig = sig.where(valid, np.nan)
    print(f"  {name:16s}: mean={sig.mean():+.3f}  std={sig.std():.3f}  "
          f"long%={100*(sig==1).mean():.1f}%  short%={100*(sig==-1).mean():.1f}%  flat%={100*(sig==0).mean():.1f}%")

print("\nPairwise signal Pearson correlation (valid bars):")
sigs = {'Donchian20': donchian, 'TD_Breakout': td_breakout,
        'TD_CounterTrend': td_counter, 'TD_Combo': td_combo}
sig_df = pd.DataFrame({k: v.where(valid, np.nan) for k, v in sigs.items()})
print(sig_df.corr().round(3).to_string())

# ---- 2. Signal agreement ----
print("\n" + "=" * 70)
print("SIGNAL AGREEMENT (% of bars where both agree on direction)")
print("=" * 70)
for name, sig in [('TD_Breakout', td_breakout), ('TD_CounterTrend', td_counter), ('TD_Combo', td_combo)]:
    agree = ((donchian == sig) & (donchian != 0)).mean()
    both_long = ((donchian == 1) & (sig == 1)).mean()
    both_short = ((donchian == -1) & (sig == -1)).mean()
    conflict = ((donchian == 1) & (sig == -1) | (donchian == -1) & (sig == 1)).mean()
    print(f"  Donchian vs {name:14s}: agree={agree*100:5.1f}%  both_long={both_long*100:5.1f}%  both_short={both_short*100:5.1f}%  conflict={conflict*100:5.1f}%")

# ---- 3. Trade overlap ----
print("\n" + "=" * 70)
print("TRADE OVERLAP (from backtest)")
print("=" * 70)
from scripts.bt.engine import Backtest

def get_trades(strat):
    bt = Backtest(df=df, strategy_instance=strat, capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker='USDJPY=X')
    r = bt.run()
    trades = r['trades']
    if not trades:
        return []
    return [(t['entry_date'], t['exit_date'], t['type']) for t in trades]

dc_trades = get_trades(DonchianBreakout(period=20))
td_trades = get_trades(TDSequentialBreakout())
cc_trades = get_trades(TDSequentialCounterTrend())
co_trades = get_trades(TDComboStrategy())

print(f"  Donchian 20:       {len(dc_trades)} trades")
print(f"  TD Seq Breakout:   {len(td_trades)} trades")
print(f"  TD CounterTrend:   {len(cc_trades)} trades")
print(f"  TD Combo:          {len(co_trades)} trades")

# Overlap: trades with overlapping dates
def overlaps(t1, t2):
    count = 0
    for a, b in [(x, y) for x in t1 for y in t2]:
        if a[0] <= b[1] and b[0] <= a[1]:
            count += 1
    return count

print(f"\n  Donchian/TD_Breakout overlapping trades: {overlaps(dc_trades, td_trades)}")
print(f"  Donchian/TD_CounterTrend overlapping trades: {overlaps(dc_trades, cc_trades)}")
print(f"  Donchian/TD_Combo overlapping trades: {overlaps(dc_trades, co_trades)}")

# ---- 4. TDST filter effectiveness (for the hybrid) ----
# For the hybrid we need TDST values at the TIME of each Donchian breakout bar.
# Build a forward-filled TDST demand/supply series so we can look up TDST at any bar.
demand_ffill = demand.ffill()
supply_ffill = supply.ffill()

# Donchian breakouts (using prior bars to avoid lookahead)
ch = donchian_channel(df, period=20)
prev_upper = ch['upper'].shift(1)
prev_lower = ch['lower'].shift(1)
long_breakout = close > prev_upper
short_breakout = close < prev_lower

# Long breakout aligned with TDST demand (price > most recent TDST demand)
# Only count breakouts where TDST demand exists (i.e., after a completed setup)
long_mask = long_breakout & demand_ffill.notna()
short_mask = short_breakout & supply_ffill.notna()
any_mask = long_mask | short_mask

if long_mask.sum() > 0:
    long_aligned_tdst = (close[long_mask] > demand_ffill[long_mask]).mean()
else:
    long_aligned_tdst = 0.0
if short_mask.sum() > 0:
    short_aligned_tdst = (close[short_mask] < supply_ffill[short_mask]).mean()
else:
    short_aligned_tdst = 0.0
if any_mask.sum() > 0:
    any_aligned = ((long_mask & (close > demand_ffill)) | (short_mask & (close < supply_ffill))).mean()
else:
    any_aligned = 0.0
any_breakout = (long_breakout | short_breakout).mean()
print("\n" + "=" * 70)
print("TDST FILTER EFFECTIVENESS on Donchian breakouts")
print("=" * 70)
print(f"  Donchian long breakout rate:  {long_breakout.mean()*100:.2f}% of bars ({long_breakout.sum()} bars)")
print(f"  Donchian short breakout rate: {short_breakout.mean()*100:.2f}% of bars ({short_breakout.sum()} bars)")
print(f"  Breakouts with valid TDST:    {any_mask.sum()} ({any_mask.mean()*100:.2f}% of all bars)")
if any_mask.sum() > 0:
    print(f"  Long breakouts aligned w/ TDST demand: {long_aligned_tdst*100:.1f}% of TDST-valid long breakouts")
    print(f"  Short breakouts aligned w/ TDST supply: {short_aligned_tdst*100:.1f}% of TDST-valid short breakouts")
    print(f"  Any breakout aligned w/ TDST: {any_aligned*100:.1f}% of TDST-valid breakouts")
    print(f"  => TDST filter would keep {any_aligned*100:.1f}% of breakouts, filter out {(1-any_aligned)*100:.1f}%")
else:
    print("  No breakouts had valid TDST levels")

# ---- 5. Setup completion stats ----
print("\n" + "=" * 70)
print("TD SETUP COMPLETION STATISTICS")
print("=" * 70)
buy_setup_complete = (td_buy_setup(close) >= 9).sum()
sell_setup_complete = (td_sell_setup(close) >= 9).sum()
buy_cd_complete = (td_buy_countdown(df) >= 13).sum()
sell_cd_complete = (td_sell_countdown(df) >= 13).sum()
print(f"  Buy setups completed (9):   {buy_setup_complete}")
print(f"  Sell setups completed (9):  {sell_setup_complete}")
print(f"  Buy countdowns completed (13): {buy_cd_complete}")
print(f"  Sell countdowns completed (13): {sell_cd_complete}")
print(f"  TDST demand levels set:     {demand.notna().sum()}")
print(f"  TDST supply levels set:     {supply.notna().sum()}")
print(f"  Note: {buy_setup_complete + sell_setup_complete} total setups over 29.6 years")

# ---- 6. Return correlation ----
print("\n" + "=" * 70)
print("STRATEGY RETURN CORRELATION")
print("=" * 70)
def equity_curve(strat):
    bt = Backtest(df=df, strategy_instance=strat, capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker='USDJPY=X')
    r = bt.run()
    return r['equity']
eq_dc = equity_curve(DonchianBreakout(period=20))
eq_td = equity_curve(TDSequentialBreakout())
eq_cc = equity_curve(TDSequentialCounterTrend())
eq_co = equity_curve(TDComboStrategy())
daily_ret_dc = eq_dc.pct_change().fillna(0)
daily_ret_td = eq_td.pct_change().fillna(0)
daily_ret_cc = eq_cc.pct_change().fillna(0)
daily_ret_co = eq_co.pct_change().fillna(0)
ret_df = pd.DataFrame({'Donchian20': daily_ret_dc, 'TD_Breakout': daily_ret_td,
                       'TD_CounterTrend': daily_ret_cc, 'TD_Combo': daily_ret_co})
print(ret_df.corr().round(3).to_string())
print("\n  Return correlation close to 1.0 = strategies make/lose money together (redundant)")
print("  Return correlation near 0 or negative = diversification benefit from combining")

# ---- 7. Hybrid simulation: Donchian filtered by TDST ----
print("\n" + "=" * 70)
print("HYBRID SIMULATION: Donchian 20 filtered by TDST demand/supply")
print("=" * 70)

class DonchianWithTDSTFilter(DonchianBreakout):
    """Donchian 20 breakout, but only take signals aligned with TDST levels."""
    def signals(self, df):
        base = super().signals(df)
        demand = td_st_demand(df).ffill()
        supply = td_st_supply(df).ffill()
        sig = pd.Series(0, index=df.index)
        position = 0
        for i in range(len(df)):
            if base.iloc[i] != 0:
                if base.iloc[i] == 1:  # long breakout
                    if pd.notna(demand.iloc[i]) and df['Close'].iloc[i] > demand.iloc[i]:
                        sig.iloc[i] = 1
                    # else: filtered out
                else:  # short breakout
                    if pd.notna(supply.iloc[i]) and df['Close'].iloc[i] < supply.iloc[i]:
                        sig.iloc[i] = -1
            else:
                sig.iloc[i] = 0
        return sig

hybrid_sig = DonchianWithTDSTFilter(period=20).signals(df)
n_hybrid = (hybrid_sig != 0).sum()
n_donchian = (donchian != 0).sum()
print(f"  Donchian 20 signals: {n_donchian}")
print(f"  Hybrid (Donchian+TDST) signals: {n_hybrid}")
print(f"  => TDST filter removes {n_donchian - n_hybrid} signals ({((n_donchian-n_hybrid)/n_donchian)*100:.1f}%)")

bt_hybrid = Backtest(df=df, strategy_instance=DonchianWithTDSTFilter(period=20),
                      capital=100000.0, risk_pct=0.01, slippage_pips=2.0, ticker='USDJPY=X')
r_hybrid = bt_hybrid.run()
folds_hybrid = bt_hybrid.run_walk_forward(is_years=3, oos_years=1)
m_hybrid = r_hybrid['metrics']
oos_hybrid = [f['oos_metrics']['Sharpe'] for f in folds_hybrid]
print(f"  Hybrid Sharpe: {m_hybrid['Sharpe']:+.2f}, Trades: {m_hybrid['Total_Trades']}, DD: {m_hybrid['Max_Drawdown']:.2%}")
print(f"  Hybrid OOS avg Sharpe: {sum(oos_hybrid)/len(oos_hybrid):+.2f}, >=0.4 in {sum(1 for s in oos_hybrid if s>=0.4)}/{len(oos_hybrid)}")

# Save results
results = {
    'signal_correlation': sig_df.corr().round(3).to_dict(),
    'signal_agreement': {
        'donchian_vs_td_breakout': {
            'agree_pct': float(((donchian == td_breakout) & (donchian != 0)).mean()),
            'both_long_pct': float(((donchian == 1) & (td_breakout == 1)).mean()),
            'both_short_pct': float(((donchian == -1) & (td_breakout == -1)).mean()),
            'conflict_pct': float(((donchian == 1) & (td_breakout == -1) | (donchian == -1) & (td_breakout == 1)).mean()),
        },
    },
    'trade_counts': {
        'Donchian20': len(dc_trades),
        'TD_Breakout': len(td_trades),
        'TD_CounterTrend': len(cc_trades),
        'TD_Combo': len(co_trades),
    },
    'trade_overlap': {
        'donchian_vs_td_breakout': overlaps(dc_trades, td_trades),
        'donchian_vs_td_counter_trend': overlaps(dc_trades, cc_trades),
        'donchian_vs_td_combo': overlaps(dc_trades, co_trades),
    },
    'tdst_filter': {
        'long_breakout_rate_pct': float(long_breakout.mean() * 100),
        'short_breakout_rate_pct': float(short_breakout.mean() * 100),
        'breakout_bars_with_valid_tdst': int(any_mask.sum()),
        'long_aligned_tdst_pct': float(long_aligned_tdst * 100),
        'short_aligned_tdst_pct': float(short_aligned_tdst * 100),
        'any_aligned_pct': float(any_aligned * 100),
        'any_breakout_pct': float(any_breakout * 100),
        'filtered_out_pct': float(((1 - any_aligned) * 100) if any_mask.sum() > 0 else 0),
    },
    'td_setup_stats': {
        'buy_setups_completed': int(buy_setup_complete),
        'sell_setups_completed': int(sell_setup_complete),
        'buy_countdowns_completed': int(buy_cd_complete),
        'sell_countdowns_completed': int(sell_cd_complete),
        'tdst_demand_levels': int(demand.notna().sum()),
        'tdst_supply_levels': int(supply.notna().sum()),
    },
    'return_correlation': ret_df.corr().round(3).to_dict(),
    'hybrid_donchian_tdst': {
        'sharpe': float(m_hybrid['Sharpe']),
        'trades': int(m_hybrid['Total_Trades']),
        'maxdd': float(m_hybrid['Max_Drawdown']),
        'avg_oos_sharpe': float(sum(oos_hybrid)/len(oos_hybrid)),
        'folds_geq_4': int(sum(1 for s in oos_hybrid if s>=0.4)),
        'total_folds': int(len(oos_hybrid)),
        'signals_filtered_out_pct': float(((n_donchian - n_hybrid)/n_donchian)*100),
    },
}
with open('JPY/reports/jpy_correlation.json', 'w') as f:
    json.dump(results, f, indent=2, default=str)
print("\nSaved JPY/reports/jpy_correlation.json")
