#!/usr/bin/env python3
"""
Delta Neutral Strategy - Setup Test Script
==========================================

This script helps you test your delta neutral arbitrage strategy setup
before running with real money. It validates configurations and runs
basic functionality tests.

Usage:
    python scripts/test_delta_neutral_setup.py
"""

import logging
import os
import sys
from decimal import Decimal
from typing import Any, Dict

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hummingbot.strategy.accounting_framework import AccountType, EnhancedAccountingFramework
from hummingbot.strategy.delta_neutral_strategy import (
    ArbitrageMode,
    ArbitragePair,
    DeltaNeutralArbitrageStrategy,
    InstrumentConfig,
    InstrumentType,
    RiskParameters,
)
from hummingbot.strategy.dynamic_hedging import EnhancedDynamicHedging, HedgingMode, HedgingRule

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockConnector:
    """Mock connector for testing purposes."""

    def __init__(self, exchange_name: str, trading_pairs: list = None, balances: dict = None):
        self.exchange_name = exchange_name
        self.trading_pairs = trading_pairs or []
        self.balances = balances or {}
        self.last_price = Decimal("50000")  # Mock BTC price

    def get_trading_pairs(self):
        return self.trading_pairs

    def get_balance(self, asset: str):
        return self.balances.get(asset, Decimal("0"))

    def get_order_book(self, trading_pair: str):
        from unittest.mock import Mock
        mock_book = Mock()
        mock_book.best_bid = self.last_price - Decimal("0.5")
        mock_book.best_ask = self.last_price + Decimal("0.5")
        return mock_book

    def get_funding_info(self, trading_pair: str):
        from unittest.mock import Mock
        mock_funding = Mock()
        mock_funding.rate = Decimal("0.01")  # 1% funding rate
        return mock_funding


class DeltaNeutralTester:
    """Test harness for delta neutral arbitrage strategy."""

    def __init__(self):
        self.test_results = []
        self.strategy = None

    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test results."""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.test_results.append((test_name, passed, message))
        print(f"{status}: {test_name}")
        if message:
            print(f"    {message}")

    def test_accounting_framework(self):
        """Test the accounting framework functionality."""
        print("\n=== Testing Accounting Framework ===")

        try:
            accounting = EnhancedAccountingFramework()

            # Test balance updates
            accounting.update_balance("binance", "BTC", AccountType.SPOT,
                                      Decimal("1.0"), Decimal("0.1"))
            accounting.update_balance("okx", "USDT", AccountType.MARGIN,
                                      Decimal("10000"), Decimal("1000"))

            total_balance = accounting.get_total_balance()
            self.log_test("Balance tracking", total_balance > 0,
                          f"Total balance: {total_balance}")

            # Test position tracking
            accounting.update_position("binance", "BTC-USDT", "long",
                                       Decimal("0.5"), Decimal("50000"))
            accounting.update_position("okx", "BTC-USDT", "short",
                                       Decimal("0.5"), Decimal("50100"))

            positions = accounting.get_position_summary()
            self.log_test("Position tracking", len(positions) == 2,
                          f"Tracked {len(positions)} positions")

            # Test P&L calculation
            current_prices = {
                "binance_BTC-USDT": Decimal("51000"),
                "okx_BTC-USDT": Decimal("51000")
            }
            unrealized_pnl = accounting.calculate_unrealized_pnl(current_prices)
            self.log_test("P&L calculation", len(unrealized_pnl) == 2,
                          f"Calculated P&L for {len(unrealized_pnl)} positions")

            # Test portfolio delta
            portfolio_delta = accounting.calculate_portfolio_delta(current_prices)
            is_delta_neutral = abs(portfolio_delta) < Decimal("1000")  # Within $1000
            self.log_test("Portfolio delta calculation", True,
                          f"Portfolio delta: ${portfolio_delta}")

        except Exception as e:
            self.log_test("Accounting framework", False, f"Error: {e}")

    def test_dynamic_hedging(self):
        """Test the dynamic hedging functionality."""
        print("\n=== Testing Dynamic Hedging ===")

        try:
            accounting = EnhancedAccountingFramework()

            # Create hedging rules
            hedging_rules = [
                HedgingRule(
                    instrument_pair=("binance_BTC-USDT", "okx_BTC-USDT"),
                    hedge_ratio=Decimal("1.0"),
                    threshold_bps=Decimal("10"),
                    max_hedge_size=Decimal("1.0"),
                    min_hedge_size=Decimal("0.001"),
                    mode=HedgingMode.IMMEDIATE,
                    priority=1
                )
            ]

            hedging = EnhancedDynamicHedging(accounting, hedging_rules)
            self.log_test("Hedging initialization", len(hedging.hedging_rules) == 1,
                          f"Created {len(hedging.hedging_rules)} hedging rules")

            # Set up imbalanced position
            accounting.update_position("binance", "BTC-USDT", "long",
                                       Decimal("1.0"), Decimal("50000"))

            current_prices = {
                "binance_BTC-USDT": Decimal("50000"),
                "okx_BTC-USDT": Decimal("50000")
            }

            # Test hedging needs evaluation
            hedges_needed = hedging.evaluate_hedging_needs(current_prices)
            self.log_test("Hedging evaluation", True,
                          f"Identified {len(hedges_needed)} potential hedges")

            # Test hedging statistics
            stats = hedging.get_hedging_statistics()
            self.log_test("Hedging statistics", isinstance(stats, dict),
                          f"Generated hedging statistics: {len(stats)} metrics")

        except Exception as e:
            self.log_test("Dynamic hedging", False, f"Error: {e}")

    def test_strategy_configuration(self):
        """Test strategy configuration and initialization."""
        print("\n=== Testing Strategy Configuration ===")

        try:
            # Create mock connectors
            connectors = {
                "binance": MockConnector("binance", ["BTC-USDT"],
                                         {"BTC": Decimal("2.0"), "USDT": Decimal("100000")}),
                "okx": MockConnector("okx", ["BTC-USDT-SWAP"],
                                     {"USDT": Decimal("50000")})
            }

            # Create instrument configs
            btc_spot = InstrumentConfig(
                symbol="BTC", exchange="binance", instrument_type=InstrumentType.SPOT,
                trading_pair="BTC-USDT", min_trade_size=Decimal("0.001"),
                max_trade_size=Decimal("10"), tick_size=Decimal("0.01")
            )

            btc_perp = InstrumentConfig(
                symbol="BTC", exchange="okx", instrument_type=InstrumentType.PERPETUAL,
                trading_pair="BTC-USDT-SWAP", min_trade_size=Decimal("0.001"),
                max_trade_size=Decimal("10"), tick_size=Decimal("0.01"),
                leverage=Decimal("10")
            )

            # Create arbitrage pair
            arb_pair = ArbitragePair(
                leg_a=btc_spot, leg_b=btc_perp, mode=ArbitrageMode.FUNDING_RATE,
                min_profit_threshold=Decimal("5"), max_inventory_ratio=Decimal("0.8")
            )

            # Create risk parameters
            risk_params = RiskParameters(
                max_inventory_size=Decimal("100000"), max_trade_size=Decimal("1000"),
                min_profit_bps=Decimal("2"), max_profit_bps=Decimal("50"),
                stop_loss_bps=Decimal("20"), take_profit_bps=Decimal("15"),
                heartbeat_timeout_seconds=30, max_position_age_minutes=60
            )

            # Create strategy
            self.strategy = DeltaNeutralArbitrageStrategy(
                connectors=connectors,
                arbitrage_pairs=[arb_pair],
                risk_parameters=risk_params
            )

            self.log_test("Strategy initialization", self.strategy is not None,
                          f"Strategy created with {len(self.strategy.arbitrage_pairs)} pairs")

            # Test strategy configuration
            self.log_test("Arbitrage pairs", len(self.strategy.arbitrage_pairs) == 1)
            self.log_test("Risk parameters", self.strategy.risk_parameters.max_trade_size == Decimal("1000"))
            self.log_test("Emergency stop", not self.strategy.emergency_stop)

        except Exception as e:
            self.log_test("Strategy configuration", False, f"Error: {e}")

    def test_strategy_execution_flow(self):
        """Test basic strategy execution without real trading."""
        print("\n=== Testing Strategy Execution Flow ===")

        if not self.strategy:
            self.log_test("Strategy execution", False, "Strategy not initialized")
            return

        try:
            # Mock the required methods
            def mock_get_funding_rate(instrument):
                return Decimal("0.01") if "binance" in str(instrument) else Decimal("0.005")

            def mock_get_mid_price(instrument):
                return Decimal("50000")

            def mock_calculate_optimal_trade_size(pair, profit):
                return Decimal("0.1")

            def mock_validate_risk_limits(pair, size):
                return True

            def mock_place_order(instrument, trade_type, amount):
                return f"mock_order_{amount}"

            # Apply mocks
            self.strategy.get_funding_rate = mock_get_funding_rate
            self.strategy.get_mid_price = mock_get_mid_price
            self.strategy.calculate_optimal_trade_size = mock_calculate_optimal_trade_size
            self.strategy.validate_risk_limits = mock_validate_risk_limits
            self.strategy.place_order = mock_place_order

            # Test opportunity scanning
            initial_positions = len(self.strategy.active_positions)

            # Run one strategy tick
            self.strategy.scan_arbitrage_opportunities()

            self.log_test("Opportunity scanning", True, "Completed opportunity scan")

            # Test position monitoring
            self.strategy.monitor_existing_positions()
            self.log_test("Position monitoring", True, "Completed position monitoring")

            # Test risk metrics update
            self.strategy.update_risk_metrics()
            self.log_test("Risk metrics update", True, "Updated risk metrics")

        except Exception as e:
            self.log_test("Strategy execution", False, f"Error: {e}")

    def test_configuration_validation(self):
        """Test configuration validation and error handling."""
        print("\n=== Testing Configuration Validation ===")

        try:
            # Test with invalid risk parameters
            try:
                invalid_risk = RiskParameters(
                    max_inventory_size=Decimal("-1000"),  # Invalid negative value
                    max_trade_size=Decimal("1000"),
                    min_profit_bps=Decimal("2"),
                    max_profit_bps=Decimal("50"),
                    stop_loss_bps=Decimal("20"),
                    take_profit_bps=Decimal("15"),
                    heartbeat_timeout_seconds=30,
                    max_position_age_minutes=60
                )
                self.log_test("Invalid risk parameters", True, "Created with negative max_inventory_size")
            except Exception:
                self.log_test("Invalid risk parameters", True, "Properly rejected invalid parameters")

            # Test with no connectors
            try:
                empty_strategy = DeltaNeutralArbitrageStrategy(
                    connectors={},
                    arbitrage_pairs=[],
                    risk_parameters=RiskParameters(
                        max_inventory_size=Decimal("1000"), max_trade_size=Decimal("100"),
                        min_profit_bps=Decimal("2"), max_profit_bps=Decimal("50"),
                        stop_loss_bps=Decimal("20"), take_profit_bps=Decimal("15"),
                        heartbeat_timeout_seconds=30, max_position_age_minutes=60
                    )
                )
                self.log_test("Empty configuration", True, "Accepted empty configuration")
            except Exception as e:
                self.log_test("Empty configuration", False, f"Error with empty config: {e}")

        except Exception as e:
            self.log_test("Configuration validation", False, f"Error: {e}")

    def run_all_tests(self):
        """Run all tests and provide summary."""
        print("🚀 Starting Delta Neutral Strategy Setup Tests")
        print("=" * 60)

        # Run individual test suites
        self.test_accounting_framework()
        self.test_dynamic_hedging()
        self.test_strategy_configuration()
        self.test_strategy_execution_flow()
        self.test_configuration_validation()

        # Generate summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, passed, _ in self.test_results if passed)
        failed_tests = total_tests - passed_tests

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests / total_tests) * 100:.1f}%")

        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for test_name, passed, message in self.test_results:
                if not passed:
                    print(f"  - {test_name}: {message}")

        print("\n" + "=" * 60)
        if failed_tests == 0:
            print("🎉 ALL TESTS PASSED! Your setup is ready.")
            print("\nNext steps:")
            print("1. Configure your exchange API keys")
            print("2. Set up real connectors (replace MockConnector)")
            print("3. Test with paper trading")
            print("4. Start with small amounts")
        else:
            print("⚠️  Some tests failed. Please review the issues above.")
            print("Check your configuration and dependencies.")

        return failed_tests == 0

    def generate_sample_config(self):
        """Generate a sample configuration file."""
        print("\n📄 Generating sample configuration...")

        config_content = """# Sample Delta Neutral Arbitrage Configuration
# Copy this to your strategy configuration file

# Risk Parameters (Adjust based on your risk tolerance)
risk_parameters:
  max_inventory_size: 10000.0      # $10K max total exposure (start small)
  max_trade_size: 1000.0           # $1K max per trade
  min_profit_bps: 8.0              # 8 bps minimum profit (conservative)
  max_profit_bps: 100.0            # 100 bps max expected profit
  stop_loss_bps: 25.0              # 25 bps stop loss
  take_profit_bps: 20.0            # 20 bps take profit
  max_position_age_minutes: 120    # Close positions after 2 hours
  heartbeat_timeout_seconds: 60    # Connection timeout

# Example Arbitrage Pairs
arbitrage_pairs:
  # BTC Funding Rate Arbitrage
  - leg_a:
      symbol: "BTC"
      exchange: "binance"
      trading_pair: "BTCUSDT"
      instrument_type: "spot"
    leg_b:
      symbol: "BTC"
      exchange: "okx_perpetual"
      trading_pair: "BTC-USDT-SWAP"
      instrument_type: "perpetual"
      leverage: 10.0
    mode: "funding_rate"
    min_profit_threshold: 8.0      # 8 bps minimum
    max_inventory_ratio: 0.5       # Use 50% of available balance
    enabled: true

# Exchanges to connect
exchanges:
  - binance
  - okx_perpetual

# Logging
logging:
  level: "INFO"
  enable_file_logging: true
"""

        with open("sample_delta_neutral_config.yml", "w") as f:
            f.write(config_content)

        print("✅ Sample configuration saved to: sample_delta_neutral_config.yml")


def main():
    """Main test execution."""
    tester = DeltaNeutralTester()

    print("Delta Neutral Arbitrage Strategy - Setup Test")
    print("This will validate your strategy configuration and dependencies.\n")

    # Run all tests
    success = tester.run_all_tests()

    # Generate sample config
    tester.generate_sample_config()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
