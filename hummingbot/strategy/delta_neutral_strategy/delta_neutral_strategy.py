import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.accounting_framework import EnhancedAccountingFramework
from hummingbot.strategy.dynamic_hedging import EnhancedDynamicHedging
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class ArbitrageMode(Enum):
    FUNDING_RATE = "funding_rate"
    PRICE_SPREAD = "price_spread"
    BASIS_ARBITRAGE = "basis_arbitrage"


class InstrumentType(Enum):
    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURES = "futures"


@dataclass
class InstrumentConfig:
    symbol: str
    exchange: str
    instrument_type: InstrumentType
    trading_pair: str
    min_trade_size: Decimal
    max_trade_size: Decimal
    tick_size: Decimal
    leverage: Optional[Decimal] = None
    expiry_date: Optional[datetime] = None


@dataclass
class ArbitragePair:
    leg_a: InstrumentConfig
    leg_b: InstrumentConfig
    mode: ArbitrageMode
    min_profit_threshold: Decimal
    max_inventory_ratio: Decimal
    enabled: bool = True


@dataclass
class RiskParameters:
    max_inventory_size: Decimal
    max_trade_size: Decimal
    min_profit_bps: Decimal
    max_profit_bps: Decimal
    stop_loss_bps: Optional[Decimal]
    take_profit_bps: Optional[Decimal]
    heartbeat_timeout_seconds: int
    max_position_age_minutes: int
    emergency_stop_enabled: bool = True


class DeltaNeutralArbitrageStrategy(ScriptStrategyBase):
    """
    Enhanced delta-neutral arbitrage strategy supporting multiple exchanges, instruments, and arbitrage modes.
    Supports funding rate arbitrage, price spread arbitrage, and basis arbitrage.
    """

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    def __init__(self,
                 connectors: Dict[str, ConnectorBase],
                 arbitrage_pairs: List[ArbitragePair],
                 risk_parameters: RiskParameters,
                 refresh_interval: float = 1.0):
        super().__init__(connectors)

        # Core components
        self.accounting_framework = EnhancedAccountingFramework()
        self.dynamic_hedging = EnhancedDynamicHedging(self.accounting_framework, [])

        # Strategy configuration
        self.arbitrage_pairs = arbitrage_pairs
        self.risk_parameters = risk_parameters
        self.refresh_interval = refresh_interval

        # State tracking
        self.active_positions: Dict[str, Dict] = {}
        self.order_tracking: Dict[str, Dict] = {}
        self.last_heartbeat: float = time.time()
        self.emergency_stop: bool = False

        # Performance metrics
        self.total_trades: int = 0
        self.total_profit: Decimal = Decimal("0")
        self.funding_rate_cache: Dict[str, Tuple[Decimal, float]] = {}

        self.logger().info(f"Initialized DeltaNeutralArbitrageStrategy with {len(arbitrage_pairs)} pairs")

    def on_tick(self):
        """
        Main strategy execution loop - runs on each tick.
        """
        try:
            if self.emergency_stop:
                self.logger().warning("Emergency stop enabled - skipping tick")
                return

            # Update heartbeat
            self.last_heartbeat = time.time()

            # Monitor existing positions
            self.monitor_existing_positions()

            # Scan for new arbitrage opportunities
            self.scan_arbitrage_opportunities()

            # Update accounting and risk metrics
            self.update_risk_metrics()

        except Exception as e:
            self.logger().error(f"Error in on_tick: {e}")
            if self.risk_parameters.emergency_stop_enabled:
                self.emergency_stop = True

    def scan_arbitrage_opportunities(self):
        """
        Scans all configured arbitrage pairs for profitable opportunities.
        """
        for pair in self.arbitrage_pairs:
            if not pair.enabled:
                continue

            try:
                if pair.mode == ArbitrageMode.FUNDING_RATE:
                    self.evaluate_funding_rate_arbitrage(pair)
                elif pair.mode == ArbitrageMode.PRICE_SPREAD:
                    self.evaluate_price_spread_arbitrage(pair)
                elif pair.mode == ArbitrageMode.BASIS_ARBITRAGE:
                    self.evaluate_basis_arbitrage(pair)

            except Exception as e:
                self.logger().error(f"Error evaluating pair {pair.leg_a.symbol}-{pair.leg_b.symbol}: {e}")

    def evaluate_funding_rate_arbitrage(self, pair: ArbitragePair):
        """
        Evaluates funding rate arbitrage opportunities between perpetual instruments.
        """
        leg_a_funding = self.get_funding_rate(pair.leg_a)
        leg_b_funding = self.get_funding_rate(pair.leg_b)

        if leg_a_funding is None or leg_b_funding is None:
            return

        funding_diff = abs(leg_a_funding - leg_b_funding)

        if funding_diff > pair.min_profit_threshold:
            # Determine which leg pays funding and which receives
            if leg_a_funding > leg_b_funding:
                short_leg = pair.leg_a  # Short the higher funding rate
                long_leg = pair.leg_b   # Long the lower funding rate
            else:
                short_leg = pair.leg_b
                long_leg = pair.leg_a

            self.execute_arbitrage_trade(pair, long_leg, short_leg, funding_diff)

    def evaluate_price_spread_arbitrage(self, pair: ArbitragePair):
        """
        Evaluates price spread arbitrage between different exchanges or instruments.
        """
        leg_a_price = self.get_mid_price(pair.leg_a)
        leg_b_price = self.get_mid_price(pair.leg_b)

        if leg_a_price is None or leg_b_price is None:
            return

        price_diff_bps = abs(leg_a_price - leg_b_price) / min(leg_a_price, leg_b_price) * 10000

        if price_diff_bps > pair.min_profit_threshold:
            if leg_a_price > leg_b_price:
                sell_leg = pair.leg_a
                buy_leg = pair.leg_b
            else:
                sell_leg = pair.leg_b
                buy_leg = pair.leg_a

            self.execute_arbitrage_trade(pair, buy_leg, sell_leg, price_diff_bps)

    def evaluate_basis_arbitrage(self, pair: ArbitragePair):
        """
        Evaluates basis arbitrage between spot and futures instruments.
        """
        if pair.leg_a.instrument_type == InstrumentType.SPOT:
            spot_leg = pair.leg_a
            futures_leg = pair.leg_b
        else:
            spot_leg = pair.leg_b
            futures_leg = pair.leg_a

        spot_price = self.get_mid_price(spot_leg)
        futures_price = self.get_mid_price(futures_leg)

        if spot_price is None or futures_price is None:
            return

        basis = futures_price - spot_price
        annualized_basis = self.calculate_annualized_basis(basis, spot_price, futures_leg.expiry_date)

        if abs(annualized_basis) > pair.min_profit_threshold:
            if basis > 0:  # Futures trading at premium
                sell_leg = futures_leg
                buy_leg = spot_leg
            else:  # Futures trading at discount
                sell_leg = spot_leg
                buy_leg = futures_leg

            self.execute_arbitrage_trade(pair, buy_leg, sell_leg, abs(annualized_basis))

    def execute_arbitrage_trade(self, pair: ArbitragePair, long_leg: InstrumentConfig,
                                short_leg: InstrumentConfig, expected_profit: Decimal):
        """
        Executes a delta-neutral arbitrage trade across two legs.
        """
        # Calculate trade size based on risk parameters and available capital
        trade_size = self.calculate_optimal_trade_size(pair, expected_profit)

        if trade_size <= 0:
            return

        # Check risk limits
        if not self.validate_risk_limits(pair, trade_size):
            self.logger().warning(f"Trade rejected due to risk limits: {pair.leg_a.symbol}-{pair.leg_b.symbol}")
            return

        position_id = f"{pair.leg_a.symbol}_{pair.leg_b.symbol}_{int(time.time())}"

        try:
            # Execute both legs simultaneously
            long_order_id = self.place_order(long_leg, TradeType.BUY, trade_size)
            short_order_id = self.place_order(short_leg, TradeType.SELL, trade_size)

            # Track the arbitrage position
            self.active_positions[position_id] = {
                "pair": pair,
                "long_leg": long_leg,
                "short_leg": short_leg,
                "trade_size": trade_size,
                "expected_profit": expected_profit,
                "long_order_id": long_order_id,
                "short_order_id": short_order_id,
                "timestamp": time.time(),
                "status": "opening"
            }

            self.logger().info(f"Opened arbitrage position {position_id}: Long {long_leg.symbol} / Short {short_leg.symbol}, Size: {trade_size}, Expected profit: {expected_profit} bps")

        except Exception as e:
            self.logger().error(f"Failed to execute arbitrage trade: {e}")

    def monitor_existing_positions(self):
        """
        Monitors existing arbitrage positions for profit taking or risk management.
        """
        positions_to_close = []

        for position_id, position in self.active_positions.items():
            try:
                # Check position age
                age_minutes = (time.time() - position["timestamp"]) / 60
                if age_minutes > self.risk_parameters.max_position_age_minutes:
                    positions_to_close.append(position_id)
                    continue

                # Check current P&L
                current_pnl = self.calculate_position_pnl(position)

                # Take profit condition
                if (self.risk_parameters.take_profit_bps and
                        current_pnl > self.risk_parameters.take_profit_bps):
                    positions_to_close.append(position_id)

                # Stop loss condition
                elif (self.risk_parameters.stop_loss_bps and
                      current_pnl < -self.risk_parameters.stop_loss_bps):
                    positions_to_close.append(position_id)

            except Exception as e:
                self.logger().error(f"Error monitoring position {position_id}: {e}")
                positions_to_close.append(position_id)

        # Close positions that meet exit criteria
        for position_id in positions_to_close:
            self.close_arbitrage_position(position_id)

    def close_arbitrage_position(self, position_id: str):
        """
        Closes an arbitrage position by unwinding both legs.
        """
        if position_id not in self.active_positions:
            return

        position = self.active_positions[position_id]

        try:
            # Close both legs
            self.place_order(position["long_leg"], TradeType.SELL, position["trade_size"])
            self.place_order(position["short_leg"], TradeType.BUY, position["trade_size"])

            # Calculate final P&L
            final_pnl = self.calculate_position_pnl(position)
            self.total_profit += final_pnl
            self.total_trades += 1

            self.logger().info(f"Closed arbitrage position {position_id}: Final P&L: {final_pnl} bps")

            # Remove from active positions
            del self.active_positions[position_id]

        except Exception as e:
            self.logger().error(f"Failed to close position {position_id}: {e}")

    def get_funding_rate(self, instrument: InstrumentConfig) -> Optional[Decimal]:
        """
        Retrieves the current funding rate for a perpetual instrument.
        """
        cache_key = f"{instrument.exchange}_{instrument.symbol}"

        # Check cache (funding rates don't change frequently)
        if cache_key in self.funding_rate_cache:
            rate, timestamp = self.funding_rate_cache[cache_key]
            if time.time() - timestamp < 300:  # 5 minute cache
                return rate

        try:
            connector = self.get_connector(instrument.exchange)
            if hasattr(connector, 'get_funding_info'):
                funding_info = connector.get_funding_info(instrument.trading_pair)
                if funding_info:
                    rate = Decimal(str(funding_info.rate))
                    self.funding_rate_cache[cache_key] = (rate, time.time())
                    return rate
        except Exception as e:
            self.logger().error(f"Error getting funding rate for {instrument.symbol}: {e}")

        return None

    def get_mid_price(self, instrument: InstrumentConfig) -> Optional[Decimal]:
        """
        Retrieves the current mid price for an instrument.
        """
        try:
            connector = self.get_connector(instrument.exchange)
            order_book = connector.get_order_book(instrument.trading_pair)

            if order_book and order_book.best_bid and order_book.best_ask:
                return (order_book.best_bid + order_book.best_ask) / 2

        except Exception as e:
            self.logger().error(f"Error getting mid price for {instrument.symbol}: {e}")

        return None

    def calculate_optimal_trade_size(self, pair: ArbitragePair, expected_profit: Decimal) -> Decimal:
        """
        Calculates the optimal trade size based on available capital and risk parameters.
        """
        # Get available balances for both legs
        leg_a_balance = self.get_available_balance(pair.leg_a)
        leg_b_balance = self.get_available_balance(pair.leg_b)

        # Calculate maximum trade size based on balances
        max_size_a = leg_a_balance * pair.max_inventory_ratio
        max_size_b = leg_b_balance * pair.max_inventory_ratio

        # Take the minimum to ensure both legs can be executed
        max_trade_size = min(max_size_a, max_size_b, self.risk_parameters.max_trade_size)

        # Apply minimum trade size constraints
        min_trade_size = max(pair.leg_a.min_trade_size, pair.leg_b.min_trade_size)

        if max_trade_size < min_trade_size:
            return Decimal("0")

        return max_trade_size

    def calculate_position_pnl(self, position: Dict) -> Decimal:
        """
        Calculates the current P&L of an arbitrage position.
        """
        try:
            long_leg = position["long_leg"]
            short_leg = position["short_leg"]
            trade_size = position["trade_size"]

            current_long_price = self.get_mid_price(long_leg)
            current_short_price = self.get_mid_price(short_leg)

            if current_long_price is None or current_short_price is None:
                return Decimal("0")

            # Calculate P&L in basis points
            long_pnl = (current_long_price - position.get("entry_long_price", current_long_price)) * trade_size
            short_pnl = (position.get("entry_short_price", current_short_price) - current_short_price) * trade_size

            total_pnl = long_pnl + short_pnl

            # Convert to basis points
            avg_price = (current_long_price + current_short_price) / 2
            pnl_bps = (total_pnl / (avg_price * trade_size)) * 10000

            return pnl_bps

        except Exception as e:
            self.logger().error(f"Error calculating position P&L: {e}")
            return Decimal("0")

    def validate_risk_limits(self, pair: ArbitragePair, trade_size: Decimal) -> bool:
        """
        Validates that a trade meets all risk management criteria.
        """
        # Check maximum trade size
        if trade_size > self.risk_parameters.max_trade_size:
            return False

        # Check total inventory limits
        current_inventory = self.get_total_inventory_value()
        if current_inventory + trade_size > self.risk_parameters.max_inventory_size:
            return False

        # Check heartbeat (ensure connectivity)
        if time.time() - self.last_heartbeat > self.risk_parameters.heartbeat_timeout_seconds:
            return False

        return True

    def update_risk_metrics(self):
        """
        Updates risk metrics and triggers emergency stops if necessary.
        """
        try:
            total_balance = self.accounting_framework.get_total_balance()
            total_positions = len(self.active_positions)

            # Log periodic status
            if int(time.time()) % 60 == 0:  # Every minute
                self.logger().info(f"Status - Active positions: {total_positions}, Total balance: {total_balance}, Total trades: {self.total_trades}, Total profit: {self.total_profit} bps")

        except Exception as e:
            self.logger().error(f"Error updating risk metrics: {e}")

    def get_connector(self, exchange: str) -> ConnectorBase:
        """
        Retrieves the connector for a specific exchange.
        """
        for connector_name, connector in self._sb_order_tracker.active_markets.items():
            if exchange.lower() in connector_name.lower():
                return connector
        return None

    def get_available_balance(self, instrument: InstrumentConfig) -> Decimal:
        """
        Gets the available balance for trading an instrument.
        """
        connector = self.get_connector(instrument.exchange)
        if not connector:
            return Decimal("0")

        # For spot trading, get the base asset balance
        # For derivatives, get the quote asset (usually USDT) balance
        if instrument.instrument_type == InstrumentType.SPOT:
            base_asset = instrument.trading_pair.split("USDT")[0] if "USDT" in instrument.trading_pair else instrument.symbol
            return connector.get_available_balance(base_asset)
        else:
            # For derivatives, typically use USDT or USD as collateral
            quote_asset = "USDT" if "USDT" in instrument.trading_pair else "USD"
            return connector.get_available_balance(quote_asset)

    def place_order(self, instrument: InstrumentConfig, trade_type: TradeType, amount: Decimal) -> str:
        """
        Places an order for the specified instrument.
        """
        connector = self.get_connector(instrument.exchange)
        if not connector:
            self.logger().error(f"No connector found for exchange: {instrument.exchange}")
            return None

        try:
            # Get current market price for market orders
            order_book = connector.get_order_book(instrument.trading_pair)
            if not order_book:
                self.logger().error(f"No order book for {instrument.trading_pair}")
                return None

            # Use market orders for immediate execution (typical for arbitrage)
            if trade_type == TradeType.BUY:
                price = order_book.best_ask
            else:
                price = order_book.best_bid

            # Place the order
            order_id = self.buy_with_specific_market(
                connector, instrument.trading_pair, amount, OrderType.MARKET, price
            ) if trade_type == TradeType.BUY else self.sell_with_specific_market(
                connector, instrument.trading_pair, amount, OrderType.MARKET, price
            )

            self.logger().info(f"Placed {trade_type.name} order: {order_id} for {amount} {instrument.trading_pair} at {price}")
            return order_id

        except Exception as e:
            self.logger().error(f"Error placing order for {instrument.trading_pair}: {e}")
            return None

    def get_total_inventory_value(self) -> Decimal:
        """
        Calculates the total value of all inventory across all instruments.
        """
        # Implementation depends on accounting framework
        return self.accounting_framework.get_total_balance()

    def calculate_annualized_basis(self, basis: Decimal, spot_price: Decimal, expiry_date: Optional[datetime]) -> Decimal:
        """
        Calculates the annualized basis for futures arbitrage.
        """
        if expiry_date is None:
            return basis / spot_price * 10000  # Convert to bps

        days_to_expiry = (expiry_date - datetime.now()).days
        if days_to_expiry <= 0:
            return Decimal("0")

        annualized_basis = (basis / spot_price) * (365 / days_to_expiry) * 10000
        return annualized_basis
