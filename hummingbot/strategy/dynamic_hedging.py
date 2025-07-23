import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.accounting_framework import AccountType, EnhancedAccountingFramework


class HedgingMode(Enum):
    IMMEDIATE = "immediate"  # Hedge immediately when threshold is breached
    DELAYED = "delayed"      # Wait for confirmation before hedging
    DYNAMIC = "dynamic"      # Adjust hedging based on market conditions
    AGGRESSIVE = "aggressive"  # Hedge with market orders
    PASSIVE = "passive"      # Hedge with limit orders only


class HedgingStrategy(Enum):
    DELTA_NEUTRAL = "delta_neutral"    # Maintain zero delta
    RISK_PARITY = "risk_parity"        # Equal risk allocation
    VOLATILITY_TARGET = "vol_target"   # Target specific volatility
    FUNDING_OPTIMIZED = "funding_opt"  # Optimize for funding payments


@dataclass
class HedgingRule:
    instrument_pair: Tuple[str, str]  # (primary, hedge)
    hedge_ratio: Decimal
    threshold_bps: Decimal
    max_hedge_size: Decimal
    min_hedge_size: Decimal
    mode: HedgingMode
    priority: int  # Lower number = higher priority
    enabled: bool = True


@dataclass
class HedgeExecution:
    primary_instrument: str
    hedge_instrument: str
    hedge_size: Decimal
    hedge_side: TradeType
    execution_price: Optional[Decimal]
    timestamp: float
    status: str  # "pending", "executed", "failed", "cancelled"
    order_id: Optional[str] = None
    slippage_bps: Optional[Decimal] = None


class EnhancedDynamicHedging:
    """
    Enhanced dynamic hedging module with sophisticated risk management,
    multiple hedging strategies, and cross-exchange coordination.
    """

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    def __init__(self,
                 accounting_framework: EnhancedAccountingFramework,
                 hedging_rules: List[HedgingRule],
                 strategy: HedgingStrategy = HedgingStrategy.DELTA_NEUTRAL,
                 order_executor: Optional[Callable] = None):

        self.accounting_framework = accounting_framework
        self.hedging_rules = {rule.instrument_pair: rule for rule in hedging_rules}
        self.strategy = strategy
        self.order_executor = order_executor

        # Configuration parameters
        self.default_hedging_threshold = Decimal("0.01")  # 1 bps
        self.max_hedge_attempts = 3
        self.hedge_timeout_seconds = 30
        self.slippage_tolerance_bps = Decimal("5")  # 5 bps

        # State tracking
        self.pending_hedges: Dict[str, HedgeExecution] = {}
        self.hedge_history: List[HedgeExecution] = []
        self.last_hedge_check: float = 0
        self.hedge_performance: Dict[str, Dict] = {}

        # Risk limits
        self.max_total_hedge_size: Decimal = Decimal("1000000")  # $1M equivalent
        self.max_single_hedge_size: Decimal = Decimal("100000")   # $100K equivalent
        self.emergency_hedge_threshold: Decimal = Decimal("100")  # 100 bps

        # Performance metrics
        self.total_hedges_executed: int = 0
        self.hedge_success_rate: Decimal = Decimal("0")
        self.average_hedge_slippage: Decimal = Decimal("0")

        self.logger().info(f"Initialized EnhancedDynamicHedging with {len(hedging_rules)} rules")

    def evaluate_hedging_needs(self, current_prices: Dict[str, Decimal]) -> List[HedgeExecution]:
        """
        Evaluates all instruments for hedging needs and returns required hedge executions.
        """
        hedges_needed = []

        # Calculate current portfolio delta and exposures
        portfolio_delta = self.accounting_framework.calculate_portfolio_delta(current_prices)
        risk_metrics = self.accounting_framework.calculate_risk_metrics(current_prices)

        # Check emergency conditions first
        if abs(portfolio_delta) > self.emergency_hedge_threshold:
            emergency_hedge = self.calculate_emergency_hedge(portfolio_delta, current_prices)
            if emergency_hedge:
                hedges_needed.append(emergency_hedge)
                self.logger().warning(f"Emergency hedge triggered: Delta={portfolio_delta} bps")

        # Evaluate each hedging rule
        for rule in self.hedging_rules.values():
            if not rule.enabled:
                continue

            hedge = self.evaluate_hedging_rule(rule, current_prices, risk_metrics)
            if hedge:
                hedges_needed.append(hedge)

        # Sort by priority
        hedges_needed.sort(key=lambda h: self.get_hedge_priority(h))

        return hedges_needed

    def evaluate_hedging_rule(self, rule: HedgingRule, current_prices: Dict[str, Decimal],
                              risk_metrics: Dict[str, Decimal]) -> Optional[HedgeExecution]:
        """
        Evaluates a specific hedging rule and returns hedge execution if needed.
        """
        primary_instrument, hedge_instrument = rule.instrument_pair

        # Get current positions
        primary_position = self.get_net_position(primary_instrument)
        hedge_position = self.get_net_position(hedge_instrument)

        # Calculate ideal hedge position
        ideal_hedge_position = primary_position * rule.hedge_ratio
        hedge_imbalance = ideal_hedge_position - hedge_position

        # Check if hedging is needed
        if abs(hedge_imbalance) < rule.min_hedge_size:
            return None

        # Calculate imbalance in basis points
        primary_price = current_prices.get(primary_instrument)
        if not primary_price or primary_price == 0:
            return None

        imbalance_value = hedge_imbalance * primary_price
        total_position_value = abs(primary_position) * primary_price

        if total_position_value == 0:
            return None

        imbalance_bps = (imbalance_value / total_position_value) * 10000

        # Check threshold
        if abs(imbalance_bps) < rule.threshold_bps:
            return None

        # Determine hedge parameters
        hedge_size = min(abs(hedge_imbalance), rule.max_hedge_size)
        hedge_side = TradeType.BUY if hedge_imbalance > 0 else TradeType.SELL

        # Create hedge execution
        hedge = HedgeExecution(
            primary_instrument=primary_instrument,
            hedge_instrument=hedge_instrument,
            hedge_size=hedge_size,
            hedge_side=hedge_side,
            execution_price=None,
            timestamp=time.time(),
            status="pending"
        )

        self.logger().info(f"Hedge needed: {primary_instrument} -> {hedge_instrument}, "
                           f"Size: {hedge_size}, Side: {hedge_side}, Imbalance: {imbalance_bps:.2f} bps")

        return hedge

    def execute_hedges(self, hedges: List[HedgeExecution]) -> List[bool]:
        """
        Executes a list of hedge orders and returns success status for each.
        """
        results = []

        for hedge in hedges:
            try:
                success = self.execute_single_hedge(hedge)
                results.append(success)

                if success:
                    self.total_hedges_executed += 1
                    self.hedge_history.append(hedge)

            except Exception as e:
                self.logger().error(f"Failed to execute hedge {hedge.hedge_instrument}: {e}")
                hedge.status = "failed"
                results.append(False)

        # Update success rate
        if results:
            successful_hedges = sum(results)
            self.hedge_success_rate = Decimal(str(successful_hedges)) / Decimal(str(len(results)))

        return results

    def execute_single_hedge(self, hedge: HedgeExecution) -> bool:
        """
        Executes a single hedge order.
        """
        if not self.order_executor:
            self.logger().warning("No order executor configured - simulating hedge execution")
            hedge.status = "executed"
            hedge.execution_price = Decimal("100")  # Mock price
            return True

        try:
            # Determine order type based on hedging mode
            rule = self.hedging_rules.get((hedge.primary_instrument, hedge.hedge_instrument))
            if not rule:
                return False

            order_type = OrderType.MARKET if rule.mode == HedgingMode.AGGRESSIVE else OrderType.LIMIT

            # Execute the order
            order_id = self.order_executor(
                instrument=hedge.hedge_instrument,
                trade_type=hedge.hedge_side,
                amount=hedge.hedge_size,
                order_type=order_type
            )

            if order_id:
                hedge.order_id = order_id
                hedge.status = "executed"
                self.pending_hedges[order_id] = hedge
                return True
            else:
                hedge.status = "failed"
                return False

        except Exception as e:
            self.logger().error(f"Error executing hedge: {e}")
            hedge.status = "failed"
            return False

    def calculate_emergency_hedge(self, portfolio_delta: Decimal,
                                  current_prices: Dict[str, Decimal]) -> Optional[HedgeExecution]:
        """
        Calculates an emergency hedge to quickly reduce portfolio delta.
        """
        # Find the most liquid instrument for emergency hedging
        # This is a simplified implementation - in practice, you'd want to consider
        # liquidity, spread, and other factors

        best_hedge_instrument = None
        best_liquidity_score = Decimal("0")

        for instrument in current_prices.keys():
            # Simple liquidity heuristic based on position size and price
            position = self.get_net_position(instrument)
            price = current_prices[instrument]
            liquidity_score = abs(position) * price

            if liquidity_score > best_liquidity_score:
                best_liquidity_score = liquidity_score
                best_hedge_instrument = instrument

        if not best_hedge_instrument:
            return None

        # Calculate hedge size to neutralize 50% of delta (conservative approach)
        hedge_size = abs(portfolio_delta) * Decimal("0.5")
        hedge_size = min(hedge_size, self.max_single_hedge_size)

        hedge_side = TradeType.SELL if portfolio_delta > 0 else TradeType.BUY

        return HedgeExecution(
            primary_instrument="PORTFOLIO",
            hedge_instrument=best_hedge_instrument,
            hedge_size=hedge_size,
            hedge_side=hedge_side,
            execution_price=None,
            timestamp=time.time(),
            status="pending"
        )

    def adjust_hedging(self, instrument: str, current_inventory: Decimal, target_inventory: Decimal):
        """
        Legacy method for backward compatibility - delegates to new hedging logic.
        """
        adjustment_needed = target_inventory - current_inventory

        if abs(adjustment_needed) < self.default_hedging_threshold:
            return

        # Create a temporary hedge execution
        hedge_side = TradeType.BUY if adjustment_needed > 0 else TradeType.SELL
        hedge_size = abs(adjustment_needed)

        hedge = HedgeExecution(
            primary_instrument=instrument,
            hedge_instrument=instrument,  # Self-hedge for legacy compatibility
            hedge_size=hedge_size,
            hedge_side=hedge_side,
            execution_price=None,
            timestamp=time.time(),
            status="pending"
        )

        self.execute_single_hedge(hedge)

    def get_net_position(self, instrument: str) -> Decimal:
        """
        Gets the net position for an instrument across all exchanges.
        """
        net_position = Decimal("0")

        for position in self.accounting_framework.positions.values():
            if position.instrument == instrument:
                if position.side == "long":
                    net_position += position.size
                else:
                    net_position -= position.size

        return net_position

    def get_hedge_priority(self, hedge: HedgeExecution) -> int:
        """
        Determines the priority of a hedge execution (lower = higher priority).
        """
        rule = self.hedging_rules.get((hedge.primary_instrument, hedge.hedge_instrument))
        if rule:
            return rule.priority
        else:
            return 999  # Low priority for non-rule hedges

    def update_hedge_performance(self, order_id: str, execution_price: Decimal, slippage: Decimal):
        """
        Updates hedge performance metrics when an order is filled.
        """
        if order_id in self.pending_hedges:
            hedge = self.pending_hedges[order_id]
            hedge.execution_price = execution_price
            hedge.slippage_bps = slippage

            # Update average slippage
            if self.total_hedges_executed > 0:
                current_avg = self.average_hedge_slippage
                self.average_hedge_slippage = ((current_avg * (self.total_hedges_executed - 1)) + slippage) / self.total_hedges_executed

            del self.pending_hedges[order_id]

    def get_hedging_statistics(self) -> Dict:
        """
        Returns comprehensive hedging performance statistics.
        """
        return {
            "total_hedges_executed": self.total_hedges_executed,
            "hedge_success_rate": float(self.hedge_success_rate),
            "average_slippage_bps": float(self.average_hedge_slippage),
            "pending_hedges": len(self.pending_hedges),
            "active_rules": len([r for r in self.hedging_rules.values() if r.enabled]),
            "recent_hedge_history": [{
                "instrument": h.hedge_instrument,
                "size": float(h.hedge_size),
                "side": h.hedge_side.name,
                "timestamp": h.timestamp,
                "slippage_bps": float(h.slippage_bps) if h.slippage_bps else None
            } for h in self.hedge_history[-10:]]
        }

    def monitor_risk(self, current_prices: Dict[str, Decimal]):
        """
        Enhanced risk monitoring with detailed metrics and alerts.
        """
        risk_metrics = self.accounting_framework.calculate_risk_metrics(current_prices)

        # Check critical risk thresholds
        alerts = []

        if risk_metrics.get("max_margin_utilization", Decimal("0")) > Decimal("0.8"):
            alerts.append("High margin utilization detected")

        if abs(risk_metrics.get("delta_ratio", Decimal("0"))) > Decimal("0.1"):
            alerts.append("Portfolio delta deviation detected")

        if risk_metrics.get("current_drawdown", Decimal("0")) > Decimal("0.05"):
            alerts.append("Drawdown exceeds 5%")

        if alerts:
            for alert in alerts:
                self.logger().warning(f"Risk Alert: {alert}")

        # Log periodic status
        if int(time.time()) % 300 == 0:  # Every 5 minutes
            self.logger().info(f"Risk Status - Total Balance: {risk_metrics.get('total_balance', 0)}, "
                               f"Delta: {risk_metrics.get('portfolio_delta', 0)}, "
                               f"Margin Util: {risk_metrics.get('max_margin_utilization', 0):.2%}")

    def add_hedging_rule(self, rule: HedgingRule):
        """
        Adds a new hedging rule.
        """
        self.hedging_rules[rule.instrument_pair] = rule
        self.logger().info(f"Added hedging rule: {rule.instrument_pair[0]} -> {rule.instrument_pair[1]}")

    def remove_hedging_rule(self, instrument_pair: Tuple[str, str]):
        """
        Removes a hedging rule.
        """
        if instrument_pair in self.hedging_rules:
            del self.hedging_rules[instrument_pair]
            self.logger().info(f"Removed hedging rule: {instrument_pair[0]} -> {instrument_pair[1]}")

    def emergency_stop(self):
        """
        Emergency stop - cancels all pending hedges and disables all rules.
        """
        self.logger().warning("EMERGENCY STOP ACTIVATED - Disabling all hedging rules")

        for rule in self.hedging_rules.values():
            rule.enabled = False

        # Cancel pending hedges if possible
        for hedge in self.pending_hedges.values():
            hedge.status = "cancelled"

        self.pending_hedges.clear()

    def reset_hedging(self):
        """
        Resets hedging state and clears history.
        """
        self.pending_hedges.clear()
        self.hedge_history.clear()
        self.hedge_performance.clear()
        self.total_hedges_executed = 0
        self.hedge_success_rate = Decimal("0")
        self.average_hedge_slippage = Decimal("0")

        self.logger().info("Hedging system reset")


# Maintain backward compatibility
DynamicHedging = EnhancedDynamicHedging
