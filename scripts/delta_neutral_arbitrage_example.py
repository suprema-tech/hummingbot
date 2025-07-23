#!/usr/bin/env python3
"""
Delta Neutral Arbitrage Strategy - Practical Example
====================================================

This script demonstrates how to set up and run the delta neutral arbitrage strategy.
Follow the steps below to configure and start your strategy.

Author: AI Assistant
Date: 2025-01-23
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase

# Import the delta neutral strategy components
from hummingbot.strategy.delta_neutral_strategy import (
    ArbitrageMode,
    ArbitragePair,
    DeltaNeutralArbitrageStrategy,
    InstrumentConfig,
    InstrumentType,
    RiskParameters,
)
from hummingbot.strategy.dynamic_hedging import HedgingMode, HedgingRule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'delta_neutral_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DeltaNeutralArbitrageBot:
    """
    Main bot class that orchestrates the delta neutral arbitrage strategy.
    """

    def __init__(self):
        self.strategy = None
        self.connectors = {}
        self.is_running = False

    def setup_connectors(self) -> Dict[str, ConnectorBase]:
        """
        Set up exchange connectors.

        In a real implementation, you would:
        1. Import actual connector classes (e.g., BinanceExchange, OkxPerpetualDerivative)
        2. Configure API keys from environment variables or config files
        3. Initialize connectors with proper authentication

        For this example, we'll show the structure with mock connectors.
        """
        logger.info("Setting up exchange connectors...")

        # Example configuration - replace with actual connector initialization
        connectors = {
            # Spot exchanges
            "binance": None,  # BinanceExchange(api_key, api_secret, trading_required=True)
            "okx_spot": None,  # OkxExchange(api_key, api_secret, passphrase, trading_required=True)

            # Derivative exchanges
            "okx_perp": None,  # OkxPerpetualDerivative(api_key, api_secret, passphrase, trading_required=True)
            "binance_perp": None,  # BinancePerpetualDerivative(api_key, api_secret, trading_required=True)
            "bybit": None,  # BybitPerpetualDerivative(api_key, api_secret, trading_required=True)
            "deribit": None,  # DeribitPerpetualDerivative(client_id, client_secret, trading_required=True)
        }

        logger.warning("Connectors are set to None - replace with actual connector initialization!")
        return connectors

    def create_instrument_configs(self) -> list:
        """
        Create instrument configurations for the assets you want to trade.
        """
        logger.info("Creating instrument configurations...")

        instruments = [
            # Bitcoin instruments
            InstrumentConfig(
                symbol="BTC",
                exchange="binance",
                instrument_type=InstrumentType.SPOT,
                trading_pair="BTCUSDT",  # Use exchange-specific format
                min_trade_size=Decimal("0.00001"),  # 0.00001 BTC minimum
                max_trade_size=Decimal("10.0"),     # 10 BTC maximum per trade
                tick_size=Decimal("0.01"),          # $0.01 price increments
            ),

            InstrumentConfig(
                symbol="BTC",
                exchange="okx_perp",
                instrument_type=InstrumentType.PERPETUAL,
                trading_pair="BTC-USDT-SWAP",
                min_trade_size=Decimal("0.00001"),
                max_trade_size=Decimal("10.0"),
                tick_size=Decimal("0.1"),
                leverage=Decimal("10.0"),  # 10x leverage for perpetuals
            ),

            # Ethereum instruments
            InstrumentConfig(
                symbol="ETH",
                exchange="binance",
                instrument_type=InstrumentType.SPOT,
                trading_pair="ETHUSDT",
                min_trade_size=Decimal("0.0001"),
                max_trade_size=Decimal("100.0"),
                tick_size=Decimal("0.01"),
            ),

            InstrumentConfig(
                symbol="ETH",
                exchange="okx_perp",
                instrument_type=InstrumentType.PERPETUAL,
                trading_pair="ETH-USDT-SWAP",
                min_trade_size=Decimal("0.0001"),
                max_trade_size=Decimal("100.0"),
                tick_size=Decimal("0.01"),
                leverage=Decimal("10.0"),
            ),
        ]

        logger.info(f"Created {len(instruments)} instrument configurations")
        return instruments

    def create_arbitrage_pairs(self, instruments: list) -> list:
        """
        Create arbitrage pairs from your instruments.
        Each pair defines a potential arbitrage opportunity.
        """
        logger.info("Creating arbitrage pairs...")

        # Find instruments by symbol and exchange
        def find_instrument(symbol: str, exchange: str) -> InstrumentConfig:
            for inst in instruments:
                if inst.symbol == symbol and inst.exchange == exchange:
                    return inst
            return None

        arbitrage_pairs = [
            # BTC Funding Rate Arbitrage: Binance Spot vs OKX Perpetual
            ArbitragePair(
                leg_a=find_instrument("BTC", "binance"),      # Spot leg
                leg_b=find_instrument("BTC", "okx_perp"),     # Perpetual leg
                mode=ArbitrageMode.FUNDING_RATE,
                min_profit_threshold=Decimal("5.0"),          # 5 bps minimum profit
                max_inventory_ratio=Decimal("0.8"),           # Use max 80% of available balance
                enabled=True
            ),

            # ETH Funding Rate Arbitrage: Binance Spot vs OKX Perpetual
            ArbitragePair(
                leg_a=find_instrument("ETH", "binance"),
                leg_b=find_instrument("ETH", "okx_perp"),
                mode=ArbitrageMode.FUNDING_RATE,
                min_profit_threshold=Decimal("5.0"),
                max_inventory_ratio=Decimal("0.8"),
                enabled=True
            ),

            # You can add more pairs for price spread arbitrage across different exchanges
            # ArbitragePair(
            #     leg_a=find_instrument("BTC", "binance"),
            #     leg_b=find_instrument("BTC", "bybit"),  # If you have Bybit configured
            #     mode=ArbitrageMode.PRICE_SPREAD,
            #     min_profit_threshold=Decimal("3.0"),  # 3 bps for price spreads
            #     max_inventory_ratio=Decimal("0.5"),
            #     enabled=False  # Disabled by default
            # ),
        ]

        # Filter out pairs with None instruments
        valid_pairs = [pair for pair in arbitrage_pairs if pair.leg_a and pair.leg_b]

        logger.info(f"Created {len(valid_pairs)} valid arbitrage pairs")
        return valid_pairs

    def create_risk_parameters(self) -> RiskParameters:
        """
        Define risk management parameters.
        Adjust these based on your risk tolerance and account size.
        """
        logger.info("Setting up risk parameters...")

        return RiskParameters(
            # Position size limits
            max_inventory_size=Decimal("50000.0"),        # $50K max total inventory
            max_trade_size=Decimal("5000.0"),             # $5K max per trade

            # Profit targets
            min_profit_bps=Decimal("2.0"),                # 2 bps minimum profit to trade
            max_profit_bps=Decimal("100.0"),              # 100 bps maximum expected profit

            # Stop loss and take profit
            stop_loss_bps=Decimal("30.0"),                # 30 bps stop loss
            take_profit_bps=Decimal("20.0"),              # 20 bps take profit

            # Timeouts and safety
            heartbeat_timeout_seconds=60,                 # 60 second heartbeat timeout
            max_position_age_minutes=120,                 # Close positions after 2 hours max
            emergency_stop_enabled=True,                  # Enable emergency stop functionality
        )

    def create_hedging_rules(self) -> list:
        """
        Create dynamic hedging rules for risk management.
        """
        logger.info("Setting up hedging rules...")

        return [
            HedgingRule(
                instrument_pair=("binance_BTCUSDT", "okx_perp_BTC-USDT-SWAP"),
                hedge_ratio=Decimal("1.0"),              # 1:1 hedge ratio
                threshold_bps=Decimal("10.0"),           # Hedge when 10 bps out of balance
                max_hedge_size=Decimal("1.0"),           # Max 1 BTC hedge size
                min_hedge_size=Decimal("0.001"),         # Min 0.001 BTC hedge size
                mode=HedgingMode.IMMEDIATE,              # Hedge immediately when triggered
                priority=1,                              # High priority
                enabled=True
            ),

            HedgingRule(
                instrument_pair=("binance_ETHUSDT", "okx_perp_ETH-USDT-SWAP"),
                hedge_ratio=Decimal("1.0"),
                threshold_bps=Decimal("10.0"),
                max_hedge_size=Decimal("10.0"),          # Max 10 ETH hedge size
                min_hedge_size=Decimal("0.01"),          # Min 0.01 ETH hedge size
                mode=HedgingMode.IMMEDIATE,
                priority=2,                              # Lower priority than BTC
                enabled=True
            ),
        ]

    def setup_strategy(self):
        """
        Initialize the complete strategy with all components.
        """
        logger.info("Setting up delta neutral arbitrage strategy...")

        # Set up all components
        self.connectors = self.setup_connectors()
        instruments = self.create_instrument_configs()
        arbitrage_pairs = self.create_arbitrage_pairs(instruments)
        risk_parameters = self.create_risk_parameters()

        if not arbitrage_pairs:
            raise ValueError("No valid arbitrage pairs configured!")

        # Create the strategy
        self.strategy = DeltaNeutralArbitrageStrategy(
            connectors=self.connectors,
            arbitrage_pairs=arbitrage_pairs,
            risk_parameters=risk_parameters,
            refresh_interval=1.0  # Check for opportunities every second
        )

        logger.info("Strategy setup complete!")
        return self.strategy

    async def run_strategy(self, duration_minutes: int = None):
        """
        Run the strategy for a specified duration or indefinitely.

        Args:
            duration_minutes: How long to run (None = run indefinitely)
        """
        if not self.strategy:
            raise ValueError("Strategy not set up! Call setup_strategy() first")

        logger.info(f"Starting delta neutral arbitrage strategy...")
        if duration_minutes:
            logger.info(f"Running for {duration_minutes} minutes")
        else:
            logger.info("Running indefinitely (Ctrl+C to stop)")

        self.is_running = True
        start_time = datetime.now()

        try:
            while self.is_running:
                # Run one strategy tick
                self.strategy.on_tick()

                # Check if we should stop
                if duration_minutes:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    if elapsed >= duration_minutes:
                        logger.info(f"Completed {duration_minutes} minute run")
                        break

                # Wait before next tick
                await asyncio.sleep(self.strategy.refresh_interval)

        except KeyboardInterrupt:
            logger.info("Received stop signal, shutting down gracefully...")
        except Exception as e:
            logger.error(f"Strategy error: {e}")
            self.strategy.emergency_stop = True
        finally:
            await self.shutdown()

    async def shutdown(self):
        """
        Gracefully shutdown the strategy.
        """
        logger.info("Shutting down strategy...")
        self.is_running = False

        if self.strategy:
            # Close any open positions
            for position_id in list(self.strategy.active_positions.keys()):
                try:
                    self.strategy.close_arbitrage_position(position_id)
                except Exception as e:
                    logger.error(f"Error closing position {position_id}: {e}")

            # Get final performance report
            performance = self.strategy.accounting_framework.export_performance_report()
            logger.info(f"Final Performance Report: {performance}")

        logger.info("Shutdown complete")

    def get_status(self) -> dict:
        """
        Get current strategy status and performance metrics.
        """
        if not self.strategy:
            return {"error": "Strategy not initialized"}

        return {
            "is_running": self.is_running,
            "active_positions": len(self.strategy.active_positions),
            "total_trades": self.strategy.total_trades,
            "total_profit": float(self.strategy.total_profit),
            "emergency_stop": self.strategy.emergency_stop,
            "arbitrage_pairs": len(self.strategy.arbitrage_pairs),
            "accounting_report": self.strategy.accounting_framework.export_performance_report()
        }


def main():
    """
    Main function to run the delta neutral arbitrage bot.
    """
    print("=== Delta Neutral Arbitrage Strategy ===")
    print("Starting setup...")

    # Create and configure the bot
    bot = DeltaNeutralArbitrageBot()

    try:
        # Setup strategy
        strategy = bot.setup_strategy()
        print(f"Strategy configured with {len(strategy.arbitrage_pairs)} arbitrage pairs")

        # Show current status
        status = bot.get_status()
        print(f"Status: {status}")

        print("\nStrategy is ready!")
        print("To run the strategy:")
        print("1. Configure your exchange API keys")
        print("2. Replace None connectors with actual exchange connectors")
        print("3. Test with small amounts first")
        print("4. Monitor logs and performance metrics")

        # Uncomment to run the strategy (after proper connector setup)
        # asyncio.run(bot.run_strategy(duration_minutes=60))  # Run for 1 hour

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        print(f"Error: {e}")
        print("\nMake sure to:")
        print("1. Set up exchange connectors properly")
        print("2. Configure API keys and permissions")
        print("3. Test with paper trading first")


if __name__ == "__main__":
    main()
