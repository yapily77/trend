export const meta = {
  name: "build-trading-plan",
  description: "Build SGD barbell trading plan: $50K, 12-15% CAGR, 50% maxDD, 20yr, XAU/SiMSCI/A50/FX via IBKR",
  phases: [
    { title: "Scout", detail: "Inventory data, code, strategies, regime" },
    { title: "Design", detail: "Generate candidate strategies from multiple lenses" },
    { title: "Evaluate", detail: "Score candidates against constraints" },
    { title: "Synthesize", detail: "Assemble final plan with sizing, risk rules, rollout" }
  ]
}

const CANDIDATES = [
  {id:"MA200_3X_ATR_HALFKELLY_GC=F",lens:"Trend-following",strategy:"MA200",market:"GC=F",timeframe:"daily",entry_signal:"price > MA200 = long",exit:"3x ATR trailing",sizing:"half-Kelly, cap 3%",risk_per_trade:"2-3%",filter:"none",status:"BACKBONE",backtest_ref:"GC=F MA200_HK: ~9.5% CAGR / 33.6% DD","notes":"","notes":""},
  {id:"MA200_3X_ATR_HALFKELLY_SPY",lens:"Trend-following",strategy:"MA200",market:"SPY",timeframe:"daily",entry_signal:"price > MA200 = long",exit:"3x ATR trailing",sizing:"half-Kelly, cap 3%",risk_per_trade:"2-3%",filter:"none",status:"BACKBONE",backtest_ref:"SPY MA200_HK: ~10.8% CAGR / 37% DD","notes":"","notes":""},
  {id:"MA200_3X_ATR_HALFKELLY_N225",lens:"Trend-following",strategy:"MA200",market:"N225",timeframe:"daily",entry_signal:"price > MA200 = long",exit:"3x ATR trailing",sizing:"half-Kelly, cap 3%",risk_per_trade:"2-3%",filter:"none",status:"CANDIDATE",backtest_ref:"N225 MA200_HK_ATR cache: 10.3% CAGR / -21.1% DD","notes":"","notes":""},
  {id:"MA200_3X_ATR_HALFKELLY_GC=F_ADX25",lens:"Trend-following",strategy:"MA200",market:"GC=F",timeframe:"daily",entry_signal:"price > MA200 = long",exit:"3x ATR trailing",sizing:"half-Kelly, cap 3%",risk_per_trade:"2-3%",filter:"ADX(14)>25",status:"CANDIDATE",backtest_ref:"GC=F baseline + ADX","notes":"","notes":""},
  {id:"MA200_3X_ATR_HALFKELLY_SPY_ADX25",lens:"Trend-following",strategy:"MA200",market:"SPY",timeframe:"daily",entry_signal:"price > MA200 = long",exit:"3x ATR trailing",sizing:"half-Kelly, cap 3%",risk_per_trade:"2-3%",filter:"ADX(14)>25",status:"CANDIDATE",backtest_ref:"SPY baseline + ADX","notes":"","notes":""},
  {id:"MA200_3X_ATR_QUARTERKELLY_GC=F_ADX25",lens:"Trend-following",strategy:"MA200",market:"GC=F",timeframe:"daily",entry_signal:"price > MA200 = long",exit:"3x ATR trailing",sizing:"quarter-Kelly, cap 2%",risk_per_trade:"1-2%",filter:"ADX(14)>25",status:"CANDIDATE",backtest_ref:"GC=F baseline quarter-Kelly","notes":"","notes":""},
  {id:"MA200_3X_ATR_HALFKELLY_GC=F_DXY_GATE",lens:"Macro-regime",strategy:"MA200",market:"GC=F",timeframe:"daily",entry_signal:"price > MA200 AND DXY < MA200",exit:"3x ATR trailing",sizing:"half-Kelly, cap 3%",risk_per_trade:"2-3%",filter:"DXY(200) regime gate",status:"CANDIDATE",backtest_ref:"DXY-gated: ~51% CAGR / 19% DD (vs ungated 67% DD)","notes":"","notes":""},
  {id:"MA200_3X_ATR_HALFKELLY_GC=F_DXY_GATE_QK",lens:"Macro-regime",strategy:"MA200",market:"GC=F",timeframe:"daily",entry_signal:"price > MA200 AND DXY < MA200",exit:"3x ATR trailing",sizing:"quarter-Kelly, cap 2%",risk_per_trade:"1-2%",filter:"DXY(200) regime gate",status:"CANDIDATE",backtest_ref:"DXY-gated at quarter-Kelly","notes":"","notes":""},
  {id:"MA200_3X_ATR_HALFKELLY_GC=F_DXY_ADX",lens:"Macro-regime",strategy:"MA200",market:"GC=F",timeframe:"daily",entry_signal:"price > MA200 AND DXY < MA200 AND ADX>25",exit:"3x ATR trailing",sizing:"half-Kelly, cap 3%",risk_per_trade:"2-3%",filter:"DXY + ADX dual",status:"CANDIDATE",backtest_ref:"Stacked dual-filter","notes":"","notes":""},
  {id:"MA200_3X_ATR_HALFKELLY_GC=F_GOLD200_SLOPE",lens:"Macro-regime",strategy:"MA200",market:"GC=F",timeframe:"daily",entry_signal:"price > MA200 AND gold 200d slope > 0",exit:"3x ATR trailing",sizing:"half-Kelly, cap 3%",risk_per_trade:"2-3%",filter:"gold 200d slope gate",status:"CANDIDATE",backtest_ref:"Gold slope as regime filter","notes":"","notes":""},
  {id:"DONCHIAN20_3X_ATR_QK_GC=F_ADX25",lens:"Breakout",strategy:"Donchian20",market:"GC=F",timeframe:"daily",entry_signal:"break > 20d high = long",exit:"3x ATR trailing",sizing:"quarter-Kelly, cap 2%",risk_per_trade:"1-2%",filter:"ADX(14)>25",status:"CANDIDATE",backtest_ref:"Gold/JPY Donchian20 weekly cache","notes":"","notes":""},
  {id:"DONCHIAN20_3X_ATR_QK_SPY_ADX25",lens:"Breakout",strategy:"Donchian20",market:"SPY",timeframe:"daily",entry_signal:"break > 20d high = long",exit:"3x ATR trailing",sizing:"quarter-Kelly, cap 2%",risk_per_trade:"1-2%",filter:"ADX(14)>25",status:"CANDIDATE",backtest_ref:"SPY Donchian20 variant","notes":"","notes":""},
  {id:"DONCHIAN20_3X_ATR_QK_N225_ADX25",lens:"Breakout",strategy:"Donchian20",market:"N225",timeframe:"daily",entry_signal:"break > 20d high = long",exit:"3x ATR trailing",sizing:"quarter-Kelly, cap 2%",risk_per_trade:"1-2%",filter:"ADX(14)>25",status:"CANDIDATE",backtest_ref:"N225 momentum","notes":"","notes":""},
  {id:"VOL_TARGET_10PCT_MA200_GC=F",lens:"Volatility-targeted",strategy:"MA200",market:"GC=F",timeframe:"daily",entry_signal:"price > MA200 = long",exit:"3x ATR trailing",sizing:"vol-target 10% ann vol",risk_per_trade:"1-2%",filter:"none",status:"CANDIDATE",backtest_ref:"gold vol ~14.6%, size ~0.68x","notes":"","notes":""},
  {id:"VOL_TARGET_12PCT_MA200_GC=F",lens:"Volatility-targeted",strategy:"MA200",market:"GC=F",timeframe:"daily",entry_signal:"price > MA200 = long",exit:"3x ATR trailing",sizing:"vol-target 12% ann vol",risk_per_trade:"1-2%",filter:"none",status:"CANDIDATE",backtest_ref:"gold vol ~14.6%","notes":"","notes":""},
  {id:"VOL_TARGET_10PCT_MA200_SPY",lens:"Volatility-targeted",strategy:"MA200",market:"SPY",timeframe:"daily",entry_signal:"price > MA200 = long",exit:"3x ATR trailing",sizing:"vol-target 10% ann vol",risk_per_trade:"1-2%",filter:"none",status:"CANDIDATE",backtest_ref:"SPY vol ~15-18%","notes":"","notes":""},
  {id:"MACRO_DXY_GOLD_JPY_SWITCHER",lens:"Macro-regime",strategy:"MA200",market:"GC=F;XAUUSD;USDJPY",timeframe:"daily",entry_signal:"DXY<MA200 & gold>MA200 => long XAU; JPY<MA200 => long USDJPY",exit:"3x ATR trailing",sizing:"quarter-Kelly per regime, vol-adj",risk_per_trade:"1-2%/regime",filter:"DXY(200)+JPY(200)",status:"CANDIDATE",backtest_ref:"User cited gated 51% CAGR / 19% DD","notes":"","notes":""},
  {id:"MACRO_DXY_GOLD_JPY_SWITCHER_HK",lens:"Macro-regime",strategy:"MA200",market:"GC=F;XAUUSD;USDJPY",timeframe:"daily",entry_signal:"DXY<MA200 & gold>MA200 => long XAU; JPY<MA200 => long USDJPY",exit:"3x ATR trailing",sizing:"half-Kelly per regime",risk_per_trade:"2%/regime",filter:"DXY(200)+JPY(200)",status:"CANDIDATE",backtest_ref:"Same regime, half-Kelly","notes":"","notes":""},
  {id:"MULTI_MOM_XAU_FX_A50_ROTATION",lens:"Multi-asset rotation",strategy:"MOMENTUM_RANK",market:"GC=F;USDJPY;EURUSD;A50",timeframe:"weekly",entry_signal:"1m+3m momentum rank, hold top-2",exit:"3x ATR trailing; monthly rebalance",sizing:"equal-risk-contribution, vol-adj",risk_per_trade:"2%/holding",filter:"none",status:"CANDIDATE",backtest_ref:"Cross-asset momentum persistence","notes":"","notes":""},
  {id:"MEAN_REV_BB_RSI_MA200_GC=F",lens:"Mean-reversion",strategy:"BB_RSI",market:"GC=F",timeframe:"daily",entry_signal:"RSI<30 & price>MA200 = long; RSI>70 & price<MA200 = short",exit:"1.5x ATR stop",sizing:"quarter-Kelly",risk_per_trade:"1%",filter:"MA200 regime",status:"CANDIDATE",backtest_ref:"Gold sideways ~10% CAGR","notes":"","notes":""},
  {id:"MEAN_REV_BB_RSI_MA200_SPY",lens:"Mean-reversion",strategy:"BB_RSI",market:"SPY",timeframe:"daily",entry_signal:"RSI<30 & price>MA200 = long; RSI>70 & price<MA200 = short",exit:"1.5x ATR stop",sizing:"quarter-Kelly",risk_per_trade:"1%",filter:"MA200 regime",status:"CANDIDATE",backtest_ref:"SPY mean-rev within trend","notes":"","notes":""},
  {id:"EVENT_PARABOLIC_FADE_GC=F",lens:"Event/positioning",strategy:"PARABOLIC_RSI",market:"GC=F",timeframe:"daily",entry_signal:"RSI>80 div OR parabolic SAR flip + COT extreme; fade on confirm bar",exit:"1.5x ATR stop",sizing:"quarter-Kelly",risk_per_trade:"1%",filter:"MA200 regime",status:"CANDIDATE",backtest_ref:"User parabolic detection skill","notes":"","notes":""},
  {id:"SCALED_BARBELL_30_70_GC=F",lens:"Scaled barbell",strategy:"BLEND",market:"GC=F",timeframe:"daily",entry_signal:"30% MA200 core + 70% Donchian20/vol/macro blend",exit:"3x ATR trailing all legs",sizing:"core half-Kelly 30%; aggressive Q-K each",risk_per_trade:"2% core / 1% aggr",filter:"DXY regime gate",status:"CANDIDATE",backtest_ref:"GC=F MA200_HK + DXY-gated","notes":"","notes":""},
  {id:"MA200_3X_ATR_HALFKELLY_GC=F_WEEKLY",lens:"Trend-following",strategy:"MA200",market:"GC=F",timeframe:"weekly",entry_signal:"weekly close > MA200 = long",exit:"3x ATR trailing",sizing:"half-Kelly, cap 3%",risk_per_trade:"2-3%",filter:"none",status:"CANDIDATE",backtest_ref:"Gold weekly cache: 6.2% CAGR / 141% DD","notes":"","notes":""},
  {id:"MA200_3X_ATR_HALFKELLY_GC=F_MONTHLY",lens:"Trend-following",strategy:"MA200",market:"GC=F",timeframe:"monthly",entry_signal:"monthly close > MA200 = long",exit:"3x ATR trailing",sizing:"half-Kelly, cap 3%",risk_per_trade:"2-3%",filter:"none",status:"CANDIDATE",backtest_ref:"Gold monthly cache: 4.7% CAGR / 78% DD","notes":"","notes":""},
  {id:"MA200_3X_ATR_HALFKELLY_SPY_200_DONCHIAN_BLEND",lens:"Trend-following",strategy:"BLEND_MA200_DONCHIAN20",market:"SPY",timeframe:"daily",entry_signal:"MA200 AND Donchian20 both long",exit:"3x ATR trailing",sizing:"half-Kelly, cap 3%",risk_per_trade:"2-3%",filter:"ADX(14)>25",status:"CANDIDATE",backtest_ref:"SPY dual-signal confirm","notes":"","notes":""},
  {id:"VOL_TARGET_10PCT_MULTI_GC=F_SPY_N225",lens:"Volatility-targeted",strategy:"MA200",market:"GC=F;SPY;N225",timeframe:"daily",entry_signal:"price > MA200 = long each",exit:"3x ATR trailing",sizing:"equal-vol contrib, 10% target",risk_per_trade:"1-2%/asset",filter:"none",status:"CANDIDATE",backtest_ref:"gold 14.6%, SPY 15-18%, N225 lower"}
]

const CANDIDATES_SUMMARY = CANDIDATES.map(c => `${c.id}|${c.lens}|${c.strategy}|${c.market}|${c.timeframe}|${c.entry_signal}|${c.exit}|${c.sizing}|${c.risk_per_trade}|${c.filter}|${c.status}|${c.backtest_ref}|${c.notes}`).join("\n")

phase('Scout')
const agentScout = await agent(`SCOUT task. Explore /home/yapilwsl/arthityap/trend for the trading plan project. Inventory:

1. DATA: List CSV files in .bt_cache/ for XAU/gold, SiMSCI, A50/FTSE, FX pairs. Note date ranges.
2. CODE: Read scripts/bt/strategies.py, scripts/bt/sizing.py, scripts/bt/cross_asset_scan.py to catalog strategy primitives (MA200, Donchian, KAMA, BB_RSI, etc.) and sizing methods (Half-Kelly, Carver, vol-target).
3. CURRENT RESULTS: Read .bt_cache/cross_asset_scan.json summary; focus on XAU/gold and FX/currency backtest results.
4. REGIME: Read docs/correlation_analysis.md (GOLD/USD vs JPY/USD -0.29), kama-research-results.md memory, vol_profile_stats. What regime for gold/JPY now?
5. GAPS: What is missing for a SGD-denominated barbell (SiMSCI data? SGD FX instruments?)

Return JSON with keys: markets, strategies, regime, gaps.`, {model: 'opus'})
log('SCOUT: ' + (agentScout ? 'done' : 'FAILED'))

phase('Design')
const agentDesign = await agent(`DESIGN task. Generate candidate trading strategy designs for a SGD barbell portfolio ($50K, 12-15% CAGR, 50% maxDD, 20yr, XAU/SiMSCI/A50/FX via IBKR).

USER: ~49M, experienced discretionary trader. Short gold futures 5040->4130 (~9K SGD profit, parabolic detection skill). Post-recovery conservative (BUY only > MA200, now bending to shorts on strong regime signals). Barbell: CPF=safe end, $50K=aggressive end. Strong regime/market sense. Wants to formalize existing edge, not replace it.

Produce candidates across these lenses (each as JSON: id, lens, strategy, market, timeframe, entry_signal, exit, sizing, risk_per_trade, filter, status, backtest_ref, notes):
1. Trend-following (MA200 + 3xATR trailing, user proven style) - GC=F, SPY, N225, ADX-filtered variants, weekly/monthly
2. Breakout (Donchian20, user second proven style) - GC=F, SPY, N225 with ADX>25
3. Mean-reversion (BB/RSI against MA200 regime) - GC=F, SPY
4. Macro-regime (DXY gate, DXY+ADX stack, gold 200d slope, full DXY/gold/JPY switcher)
5. Volatility-targeted (10%/12% ann vol targets) - GC=F, SPY, multi-asset
6. Multi-asset rotation (1m+3m momentum rank XAU/USDJPY/EURUSD/A50)
7. Event/positioning (parabolic/RSI-divergence contrarian fade - formalize user's gold-short edge)
8. Scaled barbell (30% MA200 core + 70% Donchian/vol/macro blend)

Ground in: GC=F MA200_HK ~9.5% CAGR/33.6% DD; SPY ~10.8%/37% DD; DXY-gated gold ~51% CAGR/19% DD; gold vol ~14.6%, USDJPY ~10.1%. Use 'CANDIDATE' or 'BACKBONE' status.`, {model: 'opus'})
log('DESIGN: ' + (agentDesign ? (agentDesign.candidates ? agentDesign.candidates.length + ' candidates' : 'no candidates array') : 'FAILED'))

phase('Evaluate')
const agentEvaluate = await agent(`EVALUATE task. Score these ${CANDIDATES.length} candidates against user constraints.

USER CONSTRAINTS: target 12-15% CAGR (soft: 8-10% if risk controlled); max DD MUST NOT exceed 50%; leverage permitted but prudent (cap 2x gross); SGD-denominated or hedged (XAU=USD, FX=USD pairs, note FX-vs-SGD risk); 20yr horizon; 'die with zero' spend-down; markets XAU/SiMSCI/A50/FX via IBKR.

SCORING (1-5 each):
1. CAGR fit (12-15%): 1=<5%, 5=12-15%+
2. DD fit (max DD <=50%): 1=>50% likely, 5=well under 30%
3. Regime robustness (20yr): 1=overfit, 5=works across regimes
4. Tradability (IBKR, XAU/SiMSCI/A50/FX): 1=hard, 5=easy
5. User alignment (barbell + regime sense + experience): 1=mismatch, 5=natural fit

Weighted total = 0.30*CAGR + 0.25*DD + 0.20*Regime + 0.15*Tradable + 0.10*Alignment

CANDIDATES (id|lens|strategy|market|timeframe|entry_signal|exit|sizing|risk_per_trade|filter|status|backtest_ref|notes):
${CANDIDATES_SUMMARY}

RANK by total descending. Flag FAIL if weighted total < 2.5 or MaxDD likely > 50%. For each FAIL state the failure mode. For top 5 state key risks and verification needs. Return ranked list with scores, pass/fail, failure modes, notes.`, {model: 'opus'})
log('EVALUATE: ' + (agentEvaluate ? (agentEvaluate.ranked ? agentEvaluate.ranked.length + ' scored' : 'no ranked array') : 'FAILED'))

phase('Synthesize')
const agentSynthesize = await agent(`SYNTHESIS task. Assemble the final trading plan for a SGD barbell portfolio ($50K, 12-15% CAGR, 50% maxDD, 20yr, 'die with zero').

USER PROFILE: ~49M, experienced discretionary trader. XAU, SiMSCI, A50, FX via IBKR. Shorted gold 5040->4130 (~9K SGD, parabolic detection skill). Post-recovery conservative (BUY only > MA200, now bending to shorts on strong regime signals). Strong regime sense. Barbell: CPF=safe end, $50K=aggressive end. Unemployed ~2 yrs, confident finding job 2027.

INTEGRATE:
- Candidates that passed evaluation (especially MA200 trend backbone on gold + Donchian breakout + DXY-gated macro + parabolic fade edge)
- User's existing proven edges: MA200 trend, Donchian breakout, parabolic/short detection
- Barbell framing: CPF = safe end (not in scope), $50K = aggressive end (the plan's universe)
- Markets: XAU (USD), SiMSCI (SGD), XinFTSE A50 (SGD), FX (USD pairs) - note SGD conversion
- Constraints: 12-15% CAGR, 50% max DD, 20yr, SGD, IBKR, leverage permitted
- 'Die with zero' goal: spend down over 20 years, systematic withdrawal path

PRODUCE a trading plan as JSON {plan: {asset_allocation, strategies, sizing, risk_rules, entry_exit, rollout, monitoring, risks, expected_outcome}} AND as human-readable markdown.

Honor the user: he is experienced. Frame quant framework as formalizing HIS existing edge (MA200 + Donchian proven instincts, parabolic-short skill). MA200 + Donchian are his natural instincts - build on them. His parabolic detection is a genuine edge - formalize as a signal-confirmation or sizing layer so 'close your eyes' trades become repeatable rather than heroic. The barbell framing (CPF safe, $50K aggressive) is correct mental model. 20yr horizon + 'die with zero' = spend-down portfolio, not perpetual growth. Singapore no CGT favors the trend-following hold periods.`, {model: 'opus'})
log('SYNTHESIS: ' + (agentSynthesize ? 'done' : 'FAILED'))

return {scout: agentScout, design: agentDesign, evaluate: agentEvaluate, synthesize: agentSynthesize}
