# My Trading Strategy Concept

## Goal
Develop two frameworks, one for delta neutral arbitrage and one for delta neutral liquidity providing (i.e. quoting) strategies. Every strategy can run multiple arbs/pairs/instruments with distinct parameters.
Delta neutral arbitrage strategies can be perpetual funding rate strategies, selecting perps from different exchanges based on criteria like funding rate difference and price difference. The legs can be different instrument types (ie spot, perps, dated futures) and on different exchanges (OKX spot and OKX futures or Deribit and Binance).

Delta neutral liquidity providing strategies are strategies that provide liquidity in the form of quoting in one leg and hedges with limit  (or market) orders in another leg. The legs can be different instrument types (ie spot, perps, dated futures) and on different exchanges (OKX spot and OKX futures or Deribit and Binance).

The difference between the two is basically that quoting strategies always have (passive) orders in the market and when executed a hedge is done in another ticker/instrument/exchange.

## Strategies
Assess if a current strategy like XEMM or perpetual arbitrage or one other off the shelve strategy can be serve as base for our two strategies

## Market
Run on OKX, Bybit, Binance, Hyperliquid, Backpack and/or Deribit, cross-exchange, using spot, perpetuals or (dated) futures. Other exchanges can be added. CEX's first but at a later stage add DEX's where thena.fi would be the first.

## Signal Input
Order book data (bids, asks, sizes, last trades), perpetual instrument funding rates, futures expiration dates, futures basis, and date calculations)

## Execution Logic
Everything needs to be granularly parameterized. Leverage hummingbots execution logic. Slippage and low latency timing are critical

## Risk Management
As many parameters as possible: max inventory size, max trade size, min profit, max profit, dynamic skew based on inventory, take profits, take loss, heartbeat cancel on disconnect, cancel and unwinds in and after crashes or errors. etc.)
Preferably when starting the strategy would find executed orders/positions pertaining to the strategy and continue where it left off. This can be achieved with orderId logging.
Be extra vigilant in the fact that we want to use all sort of intsrumet types interchangeably which has consequences for cash- and profit calculations. Spot is cash in/out while perps and futures are only margin. To have a delta neutral hedge it is not enough to follow the cash trail
