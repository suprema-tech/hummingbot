import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Union


class AccountType(Enum):
    SPOT = "spot"
    MARGIN = "margin"
    FUTURES = "futures"
    PERPETUAL = "perpetual"


@dataclass
class PositionEntry:
    instrument: str
    exchange: str
    account_type: AccountType
    size: Decimal
    entry_price: Decimal
    timestamp: float
    side: str  # "long" or "short"
    leverage: Optional[Decimal] = None
    funding_payments: Decimal = field(default_factory=lambda: Decimal("0"))
    realized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    unrealized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class BalanceEntry:
    asset: str
    exchange: str
    account_type: AccountType
    available: Decimal
    locked: Decimal
    total: Decimal
    last_updated: float


@dataclass
class FundingPayment:
    instrument: str
    exchange: str
    payment: Decimal
    rate: Decimal
    timestamp: float
    position_size: Decimal


class EnhancedAccountingFramework:
    """
    Enhanced accounting framework for delta-neutral strategies with comprehensive tracking
    of cash, margin, positions, funding payments, and risk metrics across multiple exchanges.
    """

    def __init__(self):
        # Balance tracking by exchange and account type
        self.balances: Dict[str, BalanceEntry] = {}  # key: f"{exchange}_{asset}_{account_type}"

        # Position tracking
        self.positions: Dict[str, PositionEntry] = {}  # key: f"{exchange}_{instrument}_{side}"

        # Funding payments history
        self.funding_payments: List[FundingPayment] = []

        # Trade history for P&L calculation
        self.trade_history: List[Dict] = []

        # Risk metrics cache
        self.risk_metrics: Dict[str, Decimal] = {}
        self.last_risk_update: float = 0

        # Performance tracking
        self.daily_pnl: Dict[str, Decimal] = {}  # key: date string
        self.cumulative_pnl: Decimal = Decimal("0")
        self.max_drawdown: Decimal = Decimal("0")
        self.peak_balance: Decimal = Decimal("0")

        # Configuration
        self.funding_rate_history_days: int = 30
        self.risk_update_interval: float = 60  # seconds

    def update_balance(self, exchange: str, asset: str, account_type: AccountType,
                       available: Decimal, locked: Decimal):
        """
        Updates balance information for a specific asset on an exchange.
        """
        key = f"{exchange}_{asset}_{account_type.value}"
        total = available + locked

        self.balances[key] = BalanceEntry(
            asset=asset,
            exchange=exchange,
            account_type=account_type,
            available=available,
            locked=locked,
            total=total,
            last_updated=time.time()
        )

    def update_position(self, exchange: str, instrument: str, side: str,
                        size: Decimal, entry_price: Decimal, leverage: Optional[Decimal] = None):
        """
        Updates position information for an instrument.
        """
        key = f"{exchange}_{instrument}_{side}"

        if key in self.positions:
            # Update existing position
            position = self.positions[key]
            # Calculate weighted average entry price for size changes
            if size != position.size:
                total_value = position.size * position.entry_price + (size - position.size) * entry_price
                position.entry_price = total_value / size if size != 0 else entry_price
            position.size = size
            position.leverage = leverage
        else:
            # Create new position
            account_type = self.determine_account_type(instrument)
            self.positions[key] = PositionEntry(
                instrument=instrument,
                exchange=exchange,
                account_type=account_type,
                size=size,
                entry_price=entry_price,
                timestamp=time.time(),
                side=side,
                leverage=leverage
            )

    def record_funding_payment(self, exchange: str, instrument: str, payment: Decimal,
                               rate: Decimal, position_size: Decimal):
        """
        Records a funding payment for a perpetual position.
        """
        funding = FundingPayment(
            instrument=instrument,
            exchange=exchange,
            payment=payment,
            rate=rate,
            timestamp=time.time(),
            position_size=position_size
        )

        self.funding_payments.append(funding)

        # Update position funding payments
        for side in ["long", "short"]:
            key = f"{exchange}_{instrument}_{side}"
            if key in self.positions:
                self.positions[key].funding_payments += payment

    def calculate_unrealized_pnl(self, current_prices: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """
        Calculates unrealized P&L for all positions based on current market prices.
        """
        unrealized_pnl = {}

        for key, position in self.positions.items():
            price_key = f"{position.exchange}_{position.instrument}"
            if price_key in current_prices:
                current_price = current_prices[price_key]

                if position.side == "long":
                    pnl = (current_price - position.entry_price) * position.size
                else:  # short
                    pnl = (position.entry_price - current_price) * position.size

                position.unrealized_pnl = pnl
                unrealized_pnl[key] = pnl

        return unrealized_pnl

    def get_total_balance_by_type(self, account_type: AccountType) -> Decimal:
        """
        Gets total balance for a specific account type across all exchanges.
        """
        total = Decimal("0")
        for balance in self.balances.values():
            if balance.account_type == account_type:
                total += balance.total
        return total

    def get_total_balance(self) -> Decimal:
        """
        Calculates total portfolio value including cash, margin, and unrealized P&L.
        """
        total_cash = self.get_total_balance_by_type(AccountType.SPOT)
        total_margin = self.get_total_balance_by_type(AccountType.MARGIN)
        total_futures = self.get_total_balance_by_type(AccountType.FUTURES)
        total_perpetual = self.get_total_balance_by_type(AccountType.PERPETUAL)

        total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
        total_funding = sum(pos.funding_payments for pos in self.positions.values())

        return total_cash + total_margin + total_futures + total_perpetual + total_unrealized + total_funding

    def calculate_portfolio_delta(self, current_prices: Dict[str, Decimal]) -> Decimal:
        """
        Calculates the overall portfolio delta (should be near zero for delta-neutral strategies).
        """
        total_delta = Decimal("0")

        for position in self.positions.values():
            price_key = f"{position.exchange}_{position.instrument}"
            if price_key in current_prices:
                current_price = current_prices[price_key]

                # Calculate position delta (simplified - assumes delta = 1 for spot/perps)
                if position.side == "long":
                    delta = position.size * current_price
                else:
                    delta = -position.size * current_price

                total_delta += delta

        return total_delta

    def calculate_margin_utilization(self) -> Dict[str, Decimal]:
        """
        Calculates margin utilization by exchange.
        """
        utilization = {}

        # Group positions by exchange
        exchange_positions = {}
        for position in self.positions.values():
            if position.exchange not in exchange_positions:
                exchange_positions[position.exchange] = []
            exchange_positions[position.exchange].append(position)

        for exchange, positions in exchange_positions.items():
            total_margin_used = Decimal("0")
            total_margin_available = Decimal("0")

            # Calculate used margin
            for position in positions:
                if position.leverage and position.leverage > 0:
                    margin_used = (position.size * position.entry_price) / position.leverage
                    total_margin_used += margin_used

            # Get available margin from balances
            for balance in self.balances.values():
                if (balance.exchange == exchange and
                        balance.account_type in [AccountType.MARGIN, AccountType.FUTURES, AccountType.PERPETUAL]):
                    total_margin_available += balance.total

            if total_margin_available > 0:
                utilization[exchange] = total_margin_used / total_margin_available
            else:
                utilization[exchange] = Decimal("0")

        return utilization

    def get_funding_rate_pnl(self, days: int = 1) -> Decimal:
        """
        Calculates P&L from funding rate payments over the specified period.
        """
        cutoff_time = time.time() - (days * 24 * 60 * 60)

        total_funding = sum(
            payment.payment for payment in self.funding_payments
            if payment.timestamp >= cutoff_time
        )

        return total_funding

    def calculate_risk_metrics(self, current_prices: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """
        Calculates comprehensive risk metrics.
        """
        if time.time() - self.last_risk_update < self.risk_update_interval:
            return self.risk_metrics

        metrics = {}

        # Portfolio value
        total_balance = self.get_total_balance()
        metrics["total_balance"] = total_balance

        # Delta exposure
        portfolio_delta = self.calculate_portfolio_delta(current_prices)
        metrics["portfolio_delta"] = portfolio_delta
        metrics["delta_ratio"] = portfolio_delta / total_balance if total_balance > 0 else Decimal("0")

        # Margin utilization
        margin_util = self.calculate_margin_utilization()
        metrics["max_margin_utilization"] = max(margin_util.values()) if margin_util else Decimal("0")

        # Unrealized P&L
        unrealized_pnl = self.calculate_unrealized_pnl(current_prices)
        metrics["total_unrealized_pnl"] = sum(unrealized_pnl.values())

        # Funding P&L
        metrics["daily_funding_pnl"] = self.get_funding_rate_pnl(1)
        metrics["weekly_funding_pnl"] = self.get_funding_rate_pnl(7)

        # Performance metrics
        if total_balance > self.peak_balance:
            self.peak_balance = total_balance

        if self.peak_balance > 0:
            drawdown = (self.peak_balance - total_balance) / self.peak_balance
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown
            metrics["current_drawdown"] = drawdown
            metrics["max_drawdown"] = self.max_drawdown

        self.risk_metrics = metrics
        self.last_risk_update = time.time()

        return metrics

    def get_position_summary(self) -> Dict[str, Dict]:
        """
        Gets a summary of all current positions.
        """
        summary = {}

        for key, position in self.positions.items():
            if position.size != 0:  # Only include non-zero positions
                summary[key] = {
                    "instrument": position.instrument,
                    "exchange": position.exchange,
                    "side": position.side,
                    "size": position.size,
                    "entry_price": position.entry_price,
                    "unrealized_pnl": position.unrealized_pnl,
                    "funding_payments": position.funding_payments,
                    "leverage": position.leverage
                }

        return summary

    def normalize_funding_rate(self, funding_rate: Union[float, Decimal], interval_hours: int) -> Decimal:
        """
        Normalizes funding rate to a standard hourly rate.
        """
        return Decimal(str(funding_rate)) / Decimal(str(interval_hours))

    def determine_account_type(self, instrument: str) -> AccountType:
        """
        Determines the account type based on instrument characteristics.
        """
        instrument_lower = instrument.lower()

        if "perp" in instrument_lower or "perpetual" in instrument_lower:
            return AccountType.PERPETUAL
        elif any(month in instrument_lower for month in ["jan", "feb", "mar", "apr", "may", "jun",
                                                         "jul", "aug", "sep", "oct", "nov", "dec"]):
            return AccountType.FUTURES
        elif "margin" in instrument_lower:
            return AccountType.MARGIN
        else:
            return AccountType.SPOT

    def export_performance_report(self) -> Dict:
        """
        Exports a comprehensive performance report.
        """
        return {
            "total_balance": self.get_total_balance(),
            "cumulative_pnl": self.cumulative_pnl,
            "max_drawdown": self.max_drawdown,
            "total_funding_pnl": sum(fp.payment for fp in self.funding_payments),
            "active_positions": len([p for p in self.positions.values() if p.size != 0]),
            "total_trades": len(self.trade_history),
            "position_summary": self.get_position_summary(),
            "recent_funding_payments": self.funding_payments[-10:] if self.funding_payments else []
        }

    def reset(self):
        """
        Resets all accounting data (use with caution).
        """
        self.balances.clear()
        self.positions.clear()
        self.funding_payments.clear()
        self.trade_history.clear()
        self.risk_metrics.clear()
        self.daily_pnl.clear()
        self.cumulative_pnl = Decimal("0")
        self.max_drawdown = Decimal("0")
        self.peak_balance = Decimal("0")


# Maintain backward compatibility
AccountingFramework = EnhancedAccountingFramework
