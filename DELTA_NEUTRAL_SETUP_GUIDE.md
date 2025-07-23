# Delta Neutral Arbitrage Strategy - Setup Guide

## Overview

The Delta Neutral Arbitrage Strategy automatically identifies and executes arbitrage opportunities across multiple exchanges while maintaining a delta-neutral portfolio. It supports:

- **Funding rate arbitrage** (perpetual contracts)
- **Price spread arbitrage** (cross-exchange)
- **Basis arbitrage** (spot vs futures)
- **Multi-exchange support** (Binance, OKX, Bybit, Deribit, etc.)
- **Comprehensive risk management**
- **Automatic hedging and position management**

## Prerequisites

1. **Hummingbot installed from source** (latest version)
2. **Exchange accounts** with API access enabled
3. **Sufficient capital** for arbitrage opportunities (recommended: $10K+ USDT equivalent)
4. **Trading permissions** on all desired exchanges
5. **Python 3.8+** with required dependencies

## Step-by-Step Setup

### 1. Configure Exchange API Keys

First, set up API keys for your exchanges. You'll need trading permissions enabled.

**For Binance:**
```bash
# In Hummingbot CLI
config binance_api_key
config binance_api_secret
```

**For OKX:**
```bash
config okx_api_key
config okx_secret_key
config okx_passphrase
```

**For other exchanges, follow similar patterns.**

### 2. Create Your Strategy Configuration

Create a configuration file `delta_neutral_config.yml`:

```yaml
# Delta Neutral Arbitrage Configuration
strategy_name: "delta_neutral_arbitrage"

# Exchange Configuration
exchanges:
  binance:
    connector_type: "binance"
    trading_required: true
  okx_spot:
    connector_type: "okx"
    trading_required: true
  okx_perpetual:
    connector_type: "okx_perpetual"
    trading_required: true

# Instruments to Trade
instruments:
  - symbol: "BTC"
    spot_exchange: "binance"
    spot_pair: "BTCUSDT"
    perp_exchange: "okx_perpetual"
    perp_pair: "BTC-USDT-SWAP"
    min_trade_size: 0.001
    max_trade_size: 1.0

  - symbol: "ETH"
    spot_exchange: "binance"
    spot_pair: "ETHUSDT"
    perp_exchange: "okx_perpetual"
    perp_pair: "ETH-USDT-SWAP"
    min_trade_size: 0.01
    max_trade_size: 10.0

# Risk Management Parameters
risk_parameters:
  max_inventory_size: 50000.0        # $50K max total exposure
  max_trade_size: 5000.0             # $5K max per trade
  min_profit_bps: 5.0                # 5 bps minimum profit
  max_profit_bps: 100.0              # 100 bps max expected profit
  stop_loss_bps: 30.0                # 30 bps stop loss
  take_profit_bps: 20.0              # 20 bps take profit
  max_position_age_minutes: 120      # Close positions after 2 hours
  heartbeat_timeout_seconds: 60      # Connection timeout

# Arbitrage Settings
arbitrage_pairs:
  - leg_a_symbol: "BTC"
    leg_a_exchange: "binance"
    leg_b_symbol: "BTC"
    leg_b_exchange: "okx_perpetual"
    mode: "funding_rate"
    min_profit_threshold: 8.0        # 8 bps minimum
    max_inventory_ratio: 0.8         # Use 80% of available balance
    enabled: true

  - leg_a_symbol: "ETH"
    leg_a_exchange: "binance"
    leg_b_symbol: "ETH"
    leg_b_exchange: "okx_perpetual"
    mode: "funding_rate"
    min_profit_threshold: 8.0
    max_inventory_ratio: 0.8
    enabled: true

# Hedging Rules
hedging_rules:
  - primary_instrument: "binance_BTCUSDT"
    hedge_instrument: "okx_perpetual_BTC-USDT-SWAP"
    hedge_ratio: 1.0
    threshold_bps: 15.0              # Hedge when 15 bps imbalance
    max_hedge_size: 0.5
    min_hedge_size: 0.001
    mode: "immediate"
    priority: 1

# Logging Configuration
logging:
  level: "INFO"
  file_path: "logs/delta_neutral_{date}.log"
  max_file_size: "10MB"
  max_files: 7
```

### 3. Run the Strategy

#### Option A: Using the Example Script

```bash
# Navigate to Hummingbot directory
cd /home/cjelsa/hummingbot

# Run the example script
python scripts/delta_neutral_arbitrage_example.py
```

#### Option B: Using Hummingbot CLI (Recommended for Production)

```bash
# Start Hummingbot
./start

# In Hummingbot CLI:
create delta_neutral_arbitrage

# Follow prompts to configure:
# - Select exchanges (binance, okx, etc.)
# - Configure trading pairs
# - Set risk parameters
# - Enable paper trading for testing

# Start the strategy
start
```

### 4. Monitor Your Strategy

#### Real-time Monitoring

```bash
# Check strategy status
status

# View active positions
positions

# Check profit/loss
pnl

# View recent trades
history
```

#### Log Analysis

```bash
# Monitor logs in real-time
tail -f logs/delta_neutral_$(date +%Y%m%d).log

# Search for specific events
grep "arbitrage opportunity" logs/delta_neutral_*.log
grep "ERROR" logs/delta_neutral_*.log
```

## Important Configuration Notes

### 1. Risk Management Settings

**Conservative Settings (Recommended for beginners):**
```yaml
max_inventory_size: 10000.0    # $10K max
max_trade_size: 1000.0         # $1K max per trade
min_profit_bps: 10.0           # 10 bps minimum profit
stop_loss_bps: 20.0            # 20 bps stop loss
```

**Aggressive Settings (For experienced traders):**
```yaml
max_inventory_size: 100000.0   # $100K max
max_trade_size: 10000.0        # $10K max per trade
min_profit_bps: 3.0            # 3 bps minimum profit
stop_loss_bps: 50.0            # 50 bps stop loss
```

### 2. Exchange-Specific Considerations

**Binance:**
- Supports both spot and futures
- Good liquidity for major pairs
- Lower fees with BNB discount

**OKX:**
- Excellent perpetual contracts
- Competitive funding rates
- Good for basis arbitrage

**Deribit:**
- Best for options and structured products
- Higher minimum trade sizes
- Good for volatility arbitrage

### 3. Capital Requirements

**Minimum recommended capital by strategy type:**

- **Funding Rate Arbitrage:** $5K+ USDT equivalent
- **Price Spread Arbitrage:** $10K+ USDT equivalent
- **Basis Arbitrage:** $20K+ USDT equivalent
- **Multi-strategy:** $50K+ USDT equivalent

## Testing and Validation

### 1. Paper Trading (Strongly Recommended)

```bash
# Enable paper trading mode in Hummingbot
config paper_trade_enabled true

# Test strategy with simulated trades
create delta_neutral_arbitrage
# Configure with small amounts
start
```

### 2. Small Live Testing

Start with minimal amounts:
```yaml
max_trade_size: 50.0           # $50 max per trade
min_profit_bps: 20.0           # 20 bps minimum (higher threshold)
```

### 3. Performance Validation

Monitor these metrics:
- **Win rate:** Should be >70% for funding rate arbitrage
- **Average profit per trade:** Should exceed transaction costs
- **Maximum drawdown:** Should be <5% of capital
- **Delta neutrality:** Portfolio delta should stay near zero

## Troubleshooting

### Common Issues

**1. "No arbitrage opportunities found"**
- Check funding rates manually on exchanges
- Verify min_profit_bps isn't too high
- Ensure exchanges are connected properly

**2. "Orders not executing"**
- Verify API keys have trading permissions
- Check account balances
- Ensure trading pairs are active

**3. "High slippage"**
- Reduce max_trade_size
- Use limit orders instead of market orders
- Check market liquidity

**4. "Emergency stop triggered"**
- Review risk parameters
- Check for network connectivity issues
- Verify exchange API status

### Getting Help

**Debug Commands:**
```bash
# Check connector status
status

# View detailed logs
tail -100 logs/hummingbot_logs_$(date +%Y-%m-%d).log

# Test connectivity
ping_exchange binance
ping_exchange okx
```

**Performance Analysis:**
```python
# Run in Python to analyze performance
from hummingbot.strategy.delta_neutral_strategy import DeltaNeutralArbitrageStrategy

# Load your strategy instance and check metrics
strategy = your_strategy_instance
performance = strategy.accounting_framework.export_performance_report()
print(performance)
```

## Security Best Practices

1. **API Key Security:**
   - Use read-only keys for monitoring
   - Enable trading permissions only when needed
   - Rotate API keys regularly
   - Use IP whitelisting

2. **Risk Management:**
   - Start with paper trading
   - Use small position sizes initially
   - Set strict stop losses
   - Monitor positions regularly

3. **Operational Security:**
   - Run on secure, dedicated server
   - Use VPN for exchange connections
   - Keep software updated
   - Backup configuration files

## Next Steps

After successfully running the basic strategy:

1. **Optimize Parameters:** Fine-tune based on performance
2. **Add More Pairs:** Expand to additional trading pairs
3. **Advanced Features:** Implement custom indicators
4. **Portfolio Management:** Scale up capital allocation
5. **Monitoring Tools:** Set up alerting and dashboards

Remember: **Start small, test thoroughly, and gradually scale up** your delta neutral arbitrage operations!
