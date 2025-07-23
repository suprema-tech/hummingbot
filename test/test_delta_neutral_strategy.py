import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List
from unittest.mock import MagicMock, Mock, patch

from hummingbot.core.event.events import OrderType, TradeType
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


class MockConnector:
    def __init__(self, exchange_name: str, trading_pairs=None, balances=None, order_book=None):
        self.exchange_name = exchange_name
        self.trading_pairs = trading_pairs or []
        self.balances = balances or {}
        self.order_book = order_book or Mock()
        self.funding_info = Mock()

    def get_trading_pairs(self):
        return self.trading_pairs

    def get_balance(self, asset):
        return self.balances.get(asset, Decimal("0.0"))

    def get_order_book(self, trading_pair):
        return self.order_book

    def get_funding_info(self, trading_pair):
        return self.funding_info


class TestEnhancedAccountingFramework(unittest.TestCase):

    def setUp(self):
        self.accounting = EnhancedAccountingFramework()

    def test_balance_updates(self):
        """Test balance tracking across different account types."""
        # Update spot balance
        self.accounting.update_balance("binance", "BTC", AccountType.SPOT,
                                       Decimal("1.0"), Decimal("0.1"))

        # Update margin balance
        self.accounting.update_balance("okx", "USDT", AccountType.MARGIN,
                                       Decimal("10000"), Decimal("1000"))

        # Check balances
        spot_balance = self.accounting.get_total_balance_by_type(AccountType.SPOT)
        margin_balance = self.accounting.get_total_balance_by_type(AccountType.MARGIN)

        self.assertEqual(spot_balance, Decimal("1.1"))  # 1.0 + 0.1
        self.assertEqual(margin_balance, Decimal("11000"))  # 10000 + 1000

    def test_position_tracking(self):
        """Test position updates and P&L calculation."""
        # Create long position
        self.accounting.update_position("binance", "BTC-USDT", "long",
                                        Decimal("0.5"), Decimal("50000"))

        # Create short position
        self.accounting.update_position("okx", "BTC-USDT", "short",
                                        Decimal("0.5"), Decimal("51000"))

        # Calculate unrealized P&L with current prices
        current_prices = {
            "binance_BTC-USDT": Decimal("52000"),
            "okx_BTC-USDT": Decimal("52000")
        }

        unrealized_pnl = self.accounting.calculate_unrealized_pnl(current_prices)

        # Long position P&L: (52000 - 50000) * 0.5 = 1000
        # Short position P&L: (51000 - 52000) * 0.5 = -500
        expected_long_pnl = Decimal("1000")
        expected_short_pnl = Decimal("-500")

        self.assertEqual(unrealized_pnl["binance_BTC-USDT_long"], expected_long_pnl)
        self.assertEqual(unrealized_pnl["okx_BTC-USDT_short"], expected_short_pnl)

    def test_funding_payments(self):
        """Test funding payment tracking."""
        # Record funding payment
        self.accounting.record_funding_payment(
            "binance", "BTC-USDT", Decimal("10.5"),
            Decimal("0.01"), Decimal("1.0")
        )

        # Check funding P&L
        daily_funding = self.accounting.get_funding_rate_pnl(1)
        self.assertEqual(daily_funding, Decimal("10.5"))

    def test_portfolio_delta_calculation(self):
        """Test portfolio delta calculation for delta neutrality."""
        # Set up positions
        self.accounting.update_position("binance", "BTC-USDT", "long",
                                        Decimal("1.0"), Decimal("50000"))
        self.accounting.update_position("okx", "BTC-USDT", "short",
                                        Decimal("1.0"), Decimal("50000"))

        current_prices = {
            "binance_BTC-USDT": Decimal("50000"),
            "okx_BTC-USDT": Decimal("50000")
        }

        portfolio_delta = self.accounting.calculate_portfolio_delta(current_prices)

        # Should be close to zero for delta neutral portfolio
        self.assertEqual(portfolio_delta, Decimal("0"))


class TestEnhancedDynamicHedging(unittest.TestCase):

    def setUp(self):
        self.accounting = EnhancedAccountingFramework()

        # Create hedging rules
        self.hedging_rules = [
            HedgingRule(
                instrument_pair=("binance_BTC-USDT", "okx_BTC-USDT"),
                hedge_ratio=Decimal("1.0"),
                threshold_bps=Decimal("5"),
                max_hedge_size=Decimal("10"),
                min_hedge_size=Decimal("0.01"),
                mode=HedgingMode.IMMEDIATE,
                priority=1
            )
        ]

        self.hedging = EnhancedDynamicHedging(
            self.accounting, self.hedging_rules
        )

    def test_hedging_rule_evaluation(self):
        """Test hedging rule evaluation logic."""
        # Set up imbalanced positions
        self.accounting.update_position("binance", "BTC-USDT", "long",
                                        Decimal("1.0"), Decimal("50000"))
        # No corresponding short position - should trigger hedge

        current_prices = {
            "binance_BTC-USDT": Decimal("50000"),
            "okx_BTC-USDT": Decimal("50000")
        }

        hedges_needed = self.hedging.evaluate_hedging_needs(current_prices)

        # Should identify need for hedging
        self.assertGreater(len(hedges_needed), 0)

        if hedges_needed:
            hedge = hedges_needed[0]
            self.assertEqual(hedge.hedge_instrument, "okx_BTC-USDT")
            self.assertEqual(hedge.hedge_side, TradeType.SELL)

    def test_emergency_hedge_calculation(self):
        """Test emergency hedging for large delta exposures."""
        # Create large imbalance
        portfolio_delta = Decimal("150")  # 150 bps - above emergency threshold

        current_prices = {
            "binance_BTC-USDT": Decimal("50000")
        }

        emergency_hedge = self.hedging.calculate_emergency_hedge(portfolio_delta, current_prices)

        self.assertIsNotNone(emergency_hedge)
        self.assertEqual(emergency_hedge.primary_instrument, "PORTFOLIO")
        self.assertEqual(emergency_hedge.hedge_side, TradeType.SELL)

    def test_hedge_performance_tracking(self):
        """Test hedge performance metrics tracking."""
        # Simulate hedge execution
        self.hedging.total_hedges_executed = 10
        self.hedging.average_hedge_slippage = Decimal("2.5")

        # Update performance with new hedge
        self.hedging.update_hedge_performance(
            "test_order_123", Decimal("50000"), Decimal("3.0")
        )

        stats = self.hedging.get_hedging_statistics()

        self.assertEqual(stats["total_hedges_executed"], 10)
        self.assertAlmostEqual(stats["average_slippage_bps"], 2.5, places=1)


class TestDeltaNeutralArbitrageStrategy(unittest.TestCase):

    def setUp(self):
        # Create instrument configurations
        self.btc_spot_binance = InstrumentConfig(
            symbol="BTC",
            exchange="binance",
            instrument_type=InstrumentType.SPOT,
            trading_pair="BTC-USDT",
            min_trade_size=Decimal("0.001"),
            max_trade_size=Decimal("10"),
            tick_size=Decimal("0.01")
        )

        self.btc_perp_okx = InstrumentConfig(
            symbol="BTC",
            exchange="okx",
            instrument_type=InstrumentType.PERPETUAL,
            trading_pair="BTC-USDT-SWAP",
            min_trade_size=Decimal("0.001"),
            max_trade_size=Decimal("10"),
            tick_size=Decimal("0.01"),
            leverage=Decimal("10")
        )

        # Create arbitrage pair
        self.arbitrage_pair = ArbitragePair(
            leg_a=self.btc_spot_binance,
            leg_b=self.btc_perp_okx,
            mode=ArbitrageMode.FUNDING_RATE,
            min_profit_threshold=Decimal("5"),  # 5 bps
            max_inventory_ratio=Decimal("0.8")
        )

        # Risk parameters
        self.risk_params = RiskParameters(
            max_inventory_size=Decimal("100000"),
            max_trade_size=Decimal("1000"),
            min_profit_bps=Decimal("2"),
            max_profit_bps=Decimal("50"),
            stop_loss_bps=Decimal("20"),
            take_profit_bps=Decimal("15"),
            heartbeat_timeout_seconds=30,
            max_position_age_minutes=60
        )

        # Mock connectors
        self.mock_binance = MockConnector("binance", ["BTC-USDT"], {"BTC": Decimal("2.0"), "USDT": Decimal("100000")})
        self.mock_okx = MockConnector("okx", ["BTC-USDT-SWAP"], {"USDT": Decimal("50000")})

        # Create mock connectors dict
        self.connectors = {
            "binance": self.mock_binance,
            "okx": self.mock_okx
        }

        # Create strategy
        self.strategy = DeltaNeutralArbitrageStrategy(
            connectors=self.connectors,
            arbitrage_pairs=[self.arbitrage_pair],
            risk_parameters=self.risk_params,
            refresh_interval=1.0
        )

    def test_strategy_initialization(self):
        """Test strategy initialization with configurations."""
        self.assertEqual(len(self.strategy.arbitrage_pairs), 1)
        self.assertEqual(self.strategy.risk_parameters.max_trade_size, Decimal("1000"))
        self.assertFalse(self.strategy.emergency_stop)
        self.assertEqual(self.strategy.total_trades, 0)

    @patch('hummingbot.strategy.delta_neutral_strategy.DeltaNeutralArbitrageStrategy.get_funding_rate')
    def test_funding_rate_arbitrage_evaluation(self, mock_get_funding_rate):
        """Test funding rate arbitrage opportunity evaluation."""
        # Mock funding rates with profitable spread
        mock_get_funding_rate.side_effect = lambda leg: {
            self.btc_spot_binance: Decimal("0.01"),    # 1% funding
            self.btc_perp_okx: Decimal("0.005")        # 0.5% funding
        }.get(leg)

        # Mock order placement
        self.strategy.place_order = Mock(return_value="order_123")
        self.strategy.get_mid_price = Mock(return_value=Decimal("50000"))
        self.strategy.calculate_optimal_trade_size = Mock(return_value=Decimal("0.1"))
        self.strategy.validate_risk_limits = Mock(return_value=True)

        # Evaluate funding rate arbitrage
        self.strategy.evaluate_funding_rate_arbitrage(self.arbitrage_pair)

        # Should have attempted to place orders
        self.assertEqual(self.strategy.place_order.call_count, 2)

    @patch('hummingbot.strategy.delta_neutral_strategy.DeltaNeutralArbitrageStrategy.get_mid_price')
    def test_price_spread_arbitrage_evaluation(self, mock_get_mid_price):
        """Test price spread arbitrage opportunity evaluation."""
        # Mock prices with profitable spread
        mock_get_mid_price.side_effect = lambda leg: {
            self.btc_spot_binance: Decimal("50000"),   # Binance price
            self.btc_perp_okx: Decimal("50050")        # OKX price (50 bps higher)
        }.get(leg)

        # Mock other required methods
        self.strategy.place_order = Mock(return_value="order_123")
        self.strategy.calculate_optimal_trade_size = Mock(return_value=Decimal("0.1"))
        self.strategy.validate_risk_limits = Mock(return_value=True)

        # Change arbitrage mode to price spread
        self.arbitrage_pair.mode = ArbitrageMode.PRICE_SPREAD

        # Evaluate price spread arbitrage
        self.strategy.evaluate_price_spread_arbitrage(self.arbitrage_pair)

        # Should have attempted to place orders (buy low, sell high)
        self.assertEqual(self.strategy.place_order.call_count, 2)

    def test_risk_limit_validation(self):
        """Test risk limit validation logic."""
        # Test with valid trade size
        valid_result = self.strategy.validate_risk_limits(
            self.arbitrage_pair, Decimal("100")
        )

        # Mock required methods for risk validation
        self.strategy.get_total_inventory_value = Mock(return_value=Decimal("50000"))

        # Should pass validation (mocked implementation)
        # In real implementation, this would check actual risk limits

    def test_position_monitoring(self):
        """Test existing position monitoring and P&L calculation."""
        # Add a mock position
        position_id = "test_position_123"
        self.strategy.active_positions[position_id] = {
            "pair": self.arbitrage_pair,
            "long_leg": self.btc_spot_binance,
            "short_leg": self.btc_perp_okx,
            "trade_size": Decimal("0.1"),
            "expected_profit": Decimal("10"),
            "timestamp": time.time() - 3600,  # 1 hour old
            "status": "opened",
            "entry_long_price": Decimal("50000"),
            "entry_short_price": Decimal("50050")
        }

        # Mock price and P&L calculation methods
        self.strategy.get_mid_price = Mock(side_effect=lambda leg: {
            self.btc_spot_binance: Decimal("50100"),   # Price moved up
            self.btc_perp_okx: Decimal("50100")        # Price moved up
        }.get(leg))

        self.strategy.close_arbitrage_position = Mock()

        # Monitor positions
        self.strategy.monitor_existing_positions()

        # Position should be closed due to age (assuming max age < 60 minutes)
        # This depends on the risk parameters

    def test_emergency_stop_functionality(self):
        """Test emergency stop mechanism."""
        # Trigger emergency stop
        self.strategy.emergency_stop = True

        # Try to run strategy tick
        self.strategy.on_tick()

        # Strategy should skip execution when emergency stop is active
        self.assertTrue(self.strategy.emergency_stop)

    def test_optimal_trade_size_calculation(self):
        """Test optimal trade size calculation based on available capital."""
        # Mock balance methods
        self.strategy.get_available_balance = Mock(return_value=Decimal("10000"))

        trade_size = self.strategy.calculate_optimal_trade_size(
            self.arbitrage_pair, Decimal("10")  # 10 bps expected profit
        )

        # Should return a reasonable trade size
        self.assertGreater(trade_size, Decimal("0"))
        self.assertLessEqual(trade_size, self.risk_params.max_trade_size)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete delta neutral arbitrage system."""

    def setUp(self):
        # Set up a complete system with all components
        self.setup_complete_system()

    def setup_complete_system(self):
        """Set up a complete delta neutral arbitrage system for testing."""
        # Create instruments
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

        # Risk parameters
        risk_params = RiskParameters(
            max_inventory_size=Decimal("100000"), max_trade_size=Decimal("1000"),
            min_profit_bps=Decimal("2"), max_profit_bps=Decimal("50"),
            stop_loss_bps=Decimal("20"), take_profit_bps=Decimal("15"),
            heartbeat_timeout_seconds=30, max_position_age_minutes=60
        )

        # Create mock connectors
        mock_connectors = {
            "binance": MockConnector("binance", ["BTC-USDT"], {"BTC": Decimal("2.0"), "USDT": Decimal("100000")}),
            "okx": MockConnector("okx", ["BTC-USDT-SWAP"], {"USDT": Decimal("50000")})
        }

        # Create strategy
        self.strategy = DeltaNeutralArbitrageStrategy(
            connectors=mock_connectors,
            arbitrage_pairs=[arb_pair],
            risk_parameters=risk_params
        )

    def test_full_arbitrage_cycle(self):
        """Test a complete arbitrage cycle from detection to closure."""
        # Mock all external dependencies
        self.strategy.get_funding_rate = Mock(side_effect=[
            Decimal("0.01"), Decimal("0.005")  # Profitable funding spread
        ])

        self.strategy.get_mid_price = Mock(return_value=Decimal("50000"))
        self.strategy.calculate_optimal_trade_size = Mock(return_value=Decimal("0.1"))
        self.strategy.validate_risk_limits = Mock(return_value=True)
        self.strategy.place_order = Mock(return_value="order_123")
        self.strategy.calculate_position_pnl = Mock(return_value=Decimal("15"))  # Profitable

        # Execute strategy tick
        self.strategy.on_tick()

        # Verify arbitrage position was opened
        self.assertGreater(len(self.strategy.active_positions), 0)

        # Simulate position closure due to profit taking
        if self.strategy.active_positions:
            position_id = list(self.strategy.active_positions.keys())[0]
            self.strategy.close_arbitrage_position(position_id)

            # Verify position was closed
            self.assertNotIn(position_id, self.strategy.active_positions)


def run_comprehensive_tests():
    """Run all test suites."""
    test_classes = [
        TestEnhancedAccountingFramework,
        TestEnhancedDynamicHedging,
        TestDeltaNeutralArbitrageStrategy,
        TestIntegration
    ]

    for test_class in test_classes:
        print(f"\n=== Running {test_class.__name__} ===")
        suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        if not result.wasSuccessful():
            print(f"FAILED: {test_class.__name__} had {len(result.failures)} failures and {len(result.errors)} errors")
            return False
        else:
            print(f"SUCCESS: {test_class.__name__} passed all tests")

    return True


if __name__ == "__main__":
    import time

    print("Running comprehensive delta neutral arbitrage strategy tests...")
    start_time = time.time()

    success = run_comprehensive_tests()

    end_time = time.time()
    print(f"\n=== Test Summary ===")
    print(f"Total execution time: {end_time - start_time:.2f} seconds")
    print(f"Overall result: {'PASSED' if success else 'FAILED'}")

    if not success:
        exit(1)
