#!/usr/bin/env python3
"""Stage 1 Regime & Cost Stress Tests for trend-following strategies.

Stress-tests the two strongest surviving strategies:
  1. Gold/JPY baseline  (MA200 + Half-Kelly + 3xATR stop, on gold priced in JPY)
  2. USDJPY Donchian20   (20-day Donchian breakout, ADX-filtered)

Four stress tests:
  STRESS 1 — Regime analysis      (trending ADX>25 vs sideways ADX<=25)
  STRESS 2 — Gold Regime Gate     (price>MA200 & price>MA50 & drawdown>-30%)
  STRESS 3 — Cost sensitivity    (institutional / baseline / retail / adverse)
  STRESS 4 — Parameter stability (ATR-mult and period sweeps)

Output: .bt_cache/stage1_regime_cost.json  +  printed summary tables.
"""
import pandas as pd, numpy as np, json, os, sys, warnings, time
import yfinance as yf
warnings.filterwarnings('ignore')

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, '.bt_cache')
sys.path.insert(0, ROOT)

from scripts.bt.indicators import adx as _adx, donchian_channel, _atr
from scripts.bt.strategies import DonchianBreakout, Strategy
from scripts.bt.engine import Backtest

START = '2000-08-31'
END   = '2026-05-29'
HK    = 0.0781          # half-Kelly (7.81 % risk/trade)
ATR_MULT = 3.0

# ── Data loading ────────────────────────────────────────────────────────────
def load_gold_jpy():
    df = pd.read_csv(os.path.join(CACHE, 'gold_jpy_daily_1971.csv'),
                     index_col=0, parse_dates=True).sort_index()
    df = df.loc[START:END]
    df.columns = ['Open','High','Low','Close']
    return df[['Open','High','Low','Close']]

def _yf_dl(ticker):
    df = yf.download(ticker, start=START, end=END, progress=False, auto_adjust=False)
    if isinstance(df, pd.Series):
        df = df.to_frame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[['Open','High','Low','Close']]

def load_usdjpy():
    path = os.path.join(CACHE, f'USDJPY=X_{START.replace("-","")}_{END.replace("-","")}.csv')
    if os.path.exists(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df[['Open','High','Low','Close']]
    df = _yf_dl('USDJPY=X'); df.to_csv(path); return df[['Open','High','Low','Close']]

def _single_col_to_ohlc(df):
    """Convert a Date+{value} cached CSV to OHLC (synthetic)."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    cols = df.columns.tolist()
    if len(cols) == 1:
        v = cols[0]
        df['Open']=df[v]; df['High']=df[v]; df['Low']=df[v]; df['Close']=df[v]
        return df[['Open','High','Low','Close']]
    return df[['Open','High','Low','Close']]

def _cached_ohlc(prefix):
    files = sorted(f for f in os.listdir(CACHE) if f.startswith(prefix) and f.endswith('.csv'))
    if not files: return None
    df = pd.read_csv(os.path.join(CACHE, files[0]), index_col=0, parse_dates=True)
    df = df.loc[START:END]
    return _single_col_to_ohlc(df)

def load_spy_qqq():
    return {t: _yf_dl(t) for t in ['SPY','QQQ']}

# ── Strategy definitions ────────────────────────────────────────────────────
class MA200Trend(Strategy):
    def __init__(self, period=200): self.period = period
    def signals(self, df):
        s = pd.Series(0.0, index=df.index)
        s[df['Close'] > df['Close'].rolling(self.period).mean()] = 1.0
        return s

class Donchian20Filtered(Strategy):
    def signals(self, df):
        ch = donchian_channel(df, period=20)
        upper, lower = ch['upper'].shift(1), ch['lower'].shift(1)
        close = df['Close']; sig = pd.Series(0, index=df.index); pos=0
        if 'ADX' not in df.columns: df['ADX'] = _adx(df)
        for i in range(len(df)):
            c,u,l = close.iloc[i],upper.iloc[i],lower.iloc[i]
            if pd.isna(u) or pd.isna(l): sig.iloc[i]=0; continue
            if c>u: pos=1
            elif c<l: pos=-1
            if pos!=0:
                adx_val = df['ADX'].iloc[i]
                if pd.notna(adx_val) and adx_val < 25: pos=0
            sig.iloc[i]=pos
        return sig

# ── Gold/JPY baseline: MA200 + half-Kelly + ATR stop ───────────────────────
# All internal bookkeeping in JPY; equity returned in USD-equivalent (normalised).
def gold_jpy_baseline(gold_jpy, usdjpy, commission_pct=0.00002,
                      slippage_frac=0.0005, atr_mult=3.0, ma_period=200,
                      half_kelly=HK, atr_period=14, capital_usd=100_000.0):
    close = gold_jpy['Close']; ma = close.rolling(ma_period).mean()
    atr = _atr(gold_jpy, atr_period)
    usdjpy = usdjpy.reindex(gold_jpy.index).ffill().bfill()
    sig = pd.Series(0.0, index=gold_jpy.index)
    sig[close > ma] = 1.0
    pos = sig.shift(1).fillna(0.0)

    n = len(gold_jpy)
    equity = np.zeros(n)
    cash_JPY = capital_usd * usdjpy.iloc[0]   # initial capital in JPY
    position_oz = 0.0          # gold exposure in troy ounces
    entry_price_JPY = 0.0
    active = False

    for i in range(n):
        c = close.iloc[i]
        a = atr.iloc[i] if pd.notna(atr.iloc[i]) else atr.dropna().iloc[0]
        u = usdjpy.iloc[i]

        # ENTRY on MA200 flip (check first so we can set equity after)
        if not active:
            now_long = pos.iloc[i] > 0
            was_long = pos.iloc[i-1] > 0 if i > 0 else False
            if now_long and not was_long:
                entry_price_JPY = c * (1 + slippage_frac)
                risk_JPY = half_kelly * cash_JPY
                stop_JPY = atr_mult * a
                position_oz = risk_JPY / stop_JPY if stop_JPY > 0 else 0.0
                if position_oz > 0:
                    comm_JPY = commission_pct * position_oz * entry_price_JPY
                    cash_JPY -= comm_JPY
                    active = True
                equity[i] = cash_JPY / u   # equity right after entry (slippage cost)
                continue

        # EXIT via ATR stop
        if active and position_oz > 0:
            stop = entry_price_JPY - atr_mult*a
            if c <= stop:
                pnl_JPY = (c - entry_price_JPY) * position_oz
                comm_JPY = commission_pct * position_oz * c
                cash_JPY += pnl_JPY - comm_JPY
                active=False; position_oz=0.0
                equity[i] = cash_JPY / u
                continue

        # EXIT on MA200 flip to flat
        if active and position_oz > 0:
            now_long = pos.iloc[i] > 0
            if not now_long:
                exit_price = c * (1 - slippage_frac)
                pnl_JPY = (exit_price - entry_price_JPY) * position_oz
                comm_JPY = commission_pct * position_oz * exit_price
                cash_JPY += pnl_JPY - comm_JPY
                active=False; position_oz=0.0
                equity[i] = cash_JPY / u
                continue

        # Mark-to-market (active position held, no exit)
        if active:
            equity[i] = (cash_JPY + (c - entry_price_JPY)*position_oz) / u
        else:
            equity[i] = cash_JPY / u

    equity_s=pd.Series(equity, index=gold_jpy.index)
    daily_ret = equity_s.pct_change().fillna(0.0)
    rm=equity_s.cummax(); dd=(equity_s-rm)/rm
    days=(equity_s.index[-1]-equity_s.index[0]).days/365.25
    cagr = equity_s.iloc[-1]**(1/days)-1 if days>0 else 0.0
    std=daily_ret.std(); sharpe=(daily_ret.mean()/std)*np.sqrt(252) if std>0 else 0.0
    return {'equity':equity_s,'daily_ret':daily_ret,'dd':dd,'cagr':cagr,
            'sharpe':sharpe,'maxdd':float(dd.min())}

# ── Helper ──────────────────────────────────────────────────────────────────
def metrics_from_ret(r):
    r = r.replace([np.inf,-np.inf],np.nan).dropna()
    if len(r)<10 or r.std()==0: return {'cagr':0.0,'sharpe':0.0,'maxdd':0.0,'n':len(r)}
    roll=(1+r).cumprod(); dd=(roll/roll.cummax()-1)
    days=len(r)/252.0
    cagr = roll.iloc[-1]**(1/days)-1 if days>0 else 0.0
    return {'cagr':float(cagr),'sharpe':float((r.mean()/r.std())*np.sqrt(252)),
            'maxdd':float(dd.min()),'n':int(len(r))}

def backtest_equity_ret(df, strategy, ticker='X'):
    """Run Backtest engine and return daily equity returns."""
    bt = Backtest(df=df, strategy_instance=strategy, capital=100000.0,
                  risk_pct=0.01, slippage_pips=2.0, commission_pct=0.00002, ticker=ticker)
    res = bt.run()
    return res['equity'].pct_change().fillna(0.0), res['metrics']

# =====================================================================
#  STRESS TEST 1 — REGIME ANALYSIS
# =====================================================================
def stress_regime(gj_daily_ret, usd_daily_ret):
    """Compute regime metrics for both strategies."""
    out=[]
    # Gold/JPY baseline
    gj_df = load_gold_jpy()
    gj_adx = _adx(gj_df, 14)
    common = gj_daily_ret.index.intersection(gj_adx.index)
    gj_ret_al = gj_daily_ret.loc[common]
    gj_adx_al = gj_adx.loc[common]
    for regime in ['trending','sideways']:
        mask = (gj_adx_al.values>25) if regime=='trending' else (gj_adx_al.values<=25)
        m = metrics_from_ret(gj_ret_al[mask])
        out.append({'market':'Gold/JPY','strategy':'MA200+HK+ATR','regime':regime,
                    'cagr':m['cagr'],'sharpe':m['sharpe'],'maxdd':m['maxdd'],'days':m['n']})
    # USDJPY Donchian20
    usd_df = load_usdjpy()
    usd_adx = _adx(usd_df, 14)
    common2 = usd_daily_ret.index.intersection(usd_adx.index)
    usd_ret_al = usd_daily_ret.loc[common2]
    usd_adx_al = usd_adx.loc[common2]
    for regime in ['trending','sideways']:
        mask = (usd_adx_al.values>25) if regime=='trending' else (usd_adx_al.values<=25)
        m = metrics_from_ret(usd_ret_al[mask])
        out.append({'market':'USDJPY','strategy':'Donchian20','regime':regime,
                    'cagr':m['cagr'],'sharpe':m['sharpe'],'maxdd':m['maxdd'],'days':m['n']})
    return out

# =====================================================================
#  STRESS TEST 2 — GOLD REGIME GATE
# =====================================================================
def stress_gate(df, strategy, ticker, strategy_name):
    """Gate: price>MA200 & price>MA50 & drawdown_from_peak > -30%."""
    close=df['Close']
    ma200=close.rolling(200).mean(); ma50=close.rolling(50).mean()
    peak=close.cummax(); dd_from_peak=(close-peak)/peak
    gate_active=(close>ma200)&(close>ma50)&(dd_from_peak>-0.30)
    gate_active=gate_active.fillna(False)

    if ticker=='Gold/JPY':
        usdjpy_df=load_usdjpy(); gj=load_gold_jpy()
        res=gold_jpy_baseline(gj,usdjpy_df['Close']); ungated_ret=res['daily_ret']
    else:
        ungated_ret,_=backtest_equity_ret(df,strategy,ticker)
    gated_ret=ungated_ret*gate_active.astype(float)
    m_g=metrics_from_ret(gated_ret); m_u=metrics_from_ret(ungated_ret)
    return {
        'market':ticker,'strategy':strategy_name,
        'gated_cagr':m_g['cagr'],'gated_sharpe':m_g['sharpe'],'gated_maxdd':m_g['maxdd'],
        'ungated_cagr':m_u['cagr'],'ungated_sharpe':m_u['sharpe'],'ungated_maxdd':m_u['maxdd'],
        'gate_active_pct':float(gate_active.mean()*100),
        'gate_active_days':int(gate_active.sum()),'total_days':len(df),
    }

# =====================================================================
#  STRESS TEST 3 — COST SENSITIVITY
# =====================================================================
COST = {
    'Institutional':   {'commission_pct':0.00001,'slippage_frac':0.0001,'pips':1},
    'Project Baseline':{'commission_pct':0.00002,'slippage_frac':0.0002,'pips':2},
    'Retail':          {'commission_pct':0.00005,'slippage_frac':0.0005,'pips':5},
    'Adverse Retail':  {'commission_pct':0.00010,'slippage_frac':0.0010,'pips':10},
}
def stress_cost(gold_jpy, usdjpy, usdjpy_df):
    out=[]
    # Gold/JPY baseline
    for name,p in COST.items():
        r=gold_jpy_baseline(gold_jpy,usdjpy,commission_pct=p['commission_pct'],
                            slippage_frac=p['slippage_frac'])
        out.append({'market':'Gold/JPY','strategy':'MA200+HK+ATR','cost_scenario':name,
                    'commission_pct':p['commission_pct'],'slippage_frac':p['slippage_frac'],
                    'cagr':r['cagr'],'sharpe':r['sharpe'],'maxdd':r['maxdd']})
    # USDJPY Donchian20 (native pip-based costs)
    df=usdjpy_df.copy(); strat=DonchianBreakout(period=20)
    for name,p in COST.items():
        bt=Backtest(df=df,strategy_instance=strat,capital=100000.0,risk_pct=0.01,
                    slippage_pips=p['pips'],commission_pct=p['commission_pct'],ticker='USDJPY=X')
        res=bt.run()
        out.append({'market':'USDJPY','strategy':'Donchian20','cost_scenario':name,
                    'commission_pct':p['commission_pct'],'slippage_pips':p['pips'],
                    'cagr':res['metrics']['CAGR'],'sharpe':res['metrics']['Sharpe'],
                    'maxdd':res['metrics']['Max_Drawdown']})
    return out

# =====================================================================
#  STRESS TEST 4 — PARAMETER STABILITY
# =====================================================================
def stress_param(gold_jpy, usdjpy, usdjpy_df):
    out=[]
    for am in [1.0,1.5,2.0,2.5,3.0,3.5,4.0,5.0]:
        r=gold_jpy_baseline(gold_jpy,usdjpy,atr_mult=am)
        out.append({'market':'Gold/JPY','strategy':'MA200+HK+ATR','param':'ATR_mult',
                    'value':am,'cagr':r['cagr'],'sharpe':r['sharpe'],'maxdd':r['maxdd']})
    for per in [10,15,20,25,30,40,50]:
        bt=Backtest(df=usdjpy_df.copy(),strategy_instance=DonchianBreakout(period=per),
                    capital=100000.0,risk_pct=0.01,slippage_pips=2.0,
                    commission_pct=0.00002,ticker='USDJPY=X')
        res=bt.run()
        out.append({'market':'USDJPY','strategy':'Donchian20','param':'Donchian_period',
                    'value':per,'cagr':res['metrics']['CAGR'],
                    'sharpe':res['metrics']['Sharpe'],'maxdd':res['metrics']['Max_Drawdown']})
    for mp in [100,150,200,250,300]:
        r=gold_jpy_baseline(gold_jpy,usdjpy,ma_period=mp)
        out.append({'market':'Gold/JPY','strategy':'MA200+HK+ATR','param':'MA_period',
                    'value':mp,'cagr':r['cagr'],'sharpe':r['sharpe'],'maxdd':r['maxdd']})
    return out

# =====================================================================
#  MAIN
# =====================================================================
def main():
    print("="*70); print("STAGE 1 — REGIME & COST STRESS TESTS"); print("="*70)
    t0=time.time()
    print("\n[Loading data...]")
    gold_jpy=load_gold_jpy()
    usdjpy_df=load_usdjpy()
    usdjpy=usdjpy_df['Close']
    eq=load_spy_qqq()
    cl_f=_cached_ohlc('CL_F'); eurusd=_cached_ohlc('EURUSD_19700101_20260601')
    gbpusd=_cached_ohlc('GBPUSD_19700101_20260601')
    print(f"  Gold/JPY {gold_jpy.shape[0]} bars  {gold_jpy.index[0].date()}→{gold_jpy.index[-1].date()}")
    print(f"  USDJPY   {usdjpy.shape[0]} bars")
    print(f"  SPY/QQQ loaded  CL_F/SPY/GBPUSD cached")

    # Pre-compute daily returns for the two strategies
    print("\n[Computing strategy equity curves...]")
    gj_res = gold_jpy_baseline(gold_jpy, usdjpy)
    gj_daily = gj_res['daily_ret']
    usd_df=load_usdjpy()
    usd_ret, usd_metrics = backtest_equity_ret(usd_df, DonchianBreakout(period=20), 'USDJPY=X')
    print(f"  Gold/JPY baseline: CAGR={gj_res['cagr']*100:+.2f}% Sharpe={gj_res['sharpe']:+.2f} MaxDD={gj_res['maxdd']*100:.1f}%")
    print(f"  USDJPY Donchian20: CAGR={usd_metrics['CAGR']*100:+.2f}% Sharpe={usd_metrics['Sharpe']:+.2f} MaxDD={usd_metrics['Max_Drawdown']*100:.1f}%")

    R={'regime_analysis':[],'gate_analysis':[],'cost_sensitivity':[],'parameter_stability':[]}

    # ── STRESS 1 ──────────────────────────────────────────────────────────
    print("\n"+ "="*70); print("STRESS TEST 1 — REGIME ANALYSIS"); print("="*70)
    reg1=stress_regime(gj_daily, usd_ret); R['regime_analysis'].extend(reg1)
    for r in reg1:
        print(f"  {r['market']:<8s} {r['regime']:<10s}  CAGR={r['cagr']*100:+7.2f}%  Sharpe={r['sharpe']:+6.2f}  MaxDD={r['maxdd']*100:+7.2f}%  days={r['days']}")

    # ── STRESS 2 ──────────────────────────────────────────────────────────
    print("\n"+ "="*70); print("STRESS TEST 2 — GOLD REGIME GATE"); print("="*70)
    gate_mkts=[
        ('Gold/JPY', gold_jpy, None, 'MA200+HK+ATR'),
        ('USDJPY', usdjpy_df, DonchianBreakout(period=20), 'Donchian20'),
        ('SPY', eq['SPY'], DonchianBreakout(period=20), 'Donchian20'),
        ('QQQ', eq['QQQ'], DonchianBreakout(period=20), 'Donchian20'),
        ('CL=F', cl_f, DonchianBreakout(period=20), 'Donchian20'),
        ('EURUSD', eurusd, DonchianBreakout(period=20), 'Donchian20'),
        ('GBPUSD', gbpusd, DonchianBreakout(period=20), 'Donchian20'),
    ]
    for mkt,df,strat,sname in gate_mkts:
        if df is None or df.shape[0]<250: continue
        ga=stress_gate(df,strat,mkt,sname); R['gate_analysis'].append(ga)
        print(f"  {mkt:<8s}  gated_CAGR={ga['gated_cagr']*100:+7.2f}%  ungated_CAGR={ga['ungated_cagr']*100:+7.2f}%  "
              f"gate_active={ga['gate_active_pct']:.1f}%")

    # ── STRESS 3 ──────────────────────────────────────────────────────────
    print("\n"+ "="*70); print("STRESS TEST 3 — COST SENSITIVITY"); print("="*70)
    cost_r=stress_cost(gold_jpy,usdjpy,usdjpy_df); R['cost_sensitivity'].extend(cost_r)
    for r in cost_r:
        if r['strategy']=='MA200+HK+ATR':
            print(f"  {r['market']}  {r['cost_scenario']:<16s}  comm={r['commission_pct']*10000:.1f}bp  slipp={r['slippage_frac']*10000:.0f}bp  CAGR={r['cagr']*100:+7.2f}%  Sharpe={r['sharpe']:+6.2f}")
        else:
            print(f"  {r['market']}  {r['cost_scenario']:<16s}  comm={r['commission_pct']*10000:.1f}bp  slipp={r['slippage_pips']:.0f}pip  CAGR={r['cagr']*100:+7.2f}%  Sharpe={r['sharpe']:+6.2f}")

    # ── STRESS 4 ──────────────────────────────────────────────────────────
    print("\n"+ "="*70); print("STRESS TEST 4 — PARAMETER STABILITY"); print("="*70)
    par_r=stress_param(gold_jpy,usdjpy,usdjpy_df); R['parameter_stability'].extend(par_r)
    for r in par_r:
        print(f"  {r['market']} {r['param']:<14s}  {str(r['value']):<6}  CAGR={r['cagr']*100:+7.2f}%  Sharpe={r['sharpe']:+6.2f}  MaxDD={r['maxdd']*100:+7.2f}%")

    # ── Write output ──────────────────────────────────────────────────────
    out_path=os.path.join(CACHE,'stage1_regime_cost.json')
    with open(out_path,'w') as f: json.dump(R,f,indent=2,default=str)
    print(f"\nWrote {out_path}")
    print(f"Elapsed: {time.time()-t0:.1f}s")

    # ── Verdict ───────────────────────────────────────────────────────────
    print("\n"+ "="*70); print("VERDICT SUMMARY"); print("="*70)
    gj_tr=[r for r in R['regime_analysis'] if r['market']=='Gold/JPY' and r['regime']=='trending']
    gj_sw=[r for r in R['regime_analysis'] if r['market']=='Gold/JPY' and r['regime']=='sideways']
    if gj_tr and gj_sw:
        print(f"  Gold/JPY: trending Sharpe {gj_tr[0]['sharpe']:+.2f} vs sideways {gj_sw[0]['sharpe']:+.2f}")
    us_tr=[r for r in R['regime_analysis'] if r['market']=='USDJPY' and r['regime']=='trending']
    us_sw=[r for r in R['regime_analysis'] if r['market']=='USDJPY' and r['regime']=='sideways']
    if us_tr and us_sw:
        print(f"  USDJPY:   trending Sharpe {us_tr[0]['sharpe']:+.2f} vs sideways {us_sw[0]['sharpe']:+.2f}")
    print("  Gate (delta = gated - ungated CAGR):")
    for ga in R['gate_analysis']:
        d=ga['gated_cagr']-ga['ungated_cagr']; sign='HELP' if d>0 else 'HURT'
        print(f"    {ga['market']:<8s}  {sign:4s} {d*100:+6.2f}%  (active {ga['gate_active_pct']:.1f}%)")
    print("  Cost degradation (Gold/JPY Sharpe vs Institutional):")
    gj_cost=[r for r in R['cost_sensitivity'] if r['strategy']=='MA200+HK+ATR']
    base=gj_cost[0]['sharpe'] if gj_cost else 0
    for r in gj_cost:
        print(f"    {r['cost_scenario']:<16s}  Sharpe {r['sharpe']:+.2f}  (Δ{r['sharpe']-base:+.2f})")

if __name__=='__main__':
    main()
