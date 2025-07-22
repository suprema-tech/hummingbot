from decimal import Decimal
from typing import Dict, Union


class AccountingFramework:
    """
    A framework to track cash flow, margin exposure, and unrealized PnL across multiple instrument types.
    """

    def __init__(self):
        self.cash_balance: Dict[str, Decimal] = {}  # Tracks cash balances for spot instruments
        self.margin_balance: Dict[str, Decimal] = {}  # Tracks margin balances for perpetuals and futures
        self.unrealized_pnl: Dict[str, Decimal] = {}  # Tracks unrealized profit and loss

    def update_cash_balance(self, instrument: str, amount: Decimal):
        """Updates the cash balance for a spot instrument."""
        if instrument not in self.cash_balance:
            self.cash_balance[instrument] = Decimal("0")
        self.cash_balance[instrument] += amount

    def update_margin_balance(self, instrument: str, amount: Decimal):
        """Updates the margin balance for a perpetual or futures instrument."""
        if instrument not in self.margin_balance:
            self.margin_balance[instrument] = Decimal("0")
        self.margin_balance[instrument] += amount

    def update_unrealized_pnl(self, instrument: str, pnl: Decimal):
        """Updates the unrealized profit and loss for an instrument."""
        if instrument not in self.unrealized_pnl:
            self.unrealized_pnl[instrument] = Decimal("0")
        self.unrealized_pnl[instrument] += pnl

    def get_total_balance(self) -> Decimal:
        """Calculates the total balance across all instruments."""
        total_cash = sum(self.cash_balance.values())
        total_margin = sum(self.margin_balance.values())
        total_pnl = sum(self.unrealized_pnl.values())
        return total_cash + total_margin + total_pnl

    def normalize_funding_rate(self, funding_rate: Union[float, Decimal], interval_hours: int) -> Decimal:
        """
        Normalizes funding rate to a standard hourly rate.
        :param funding_rate: The funding rate provided by the exchange.
        :param interval_hours: The interval in hours for the funding rate.
        :return: Normalized funding rate as a Decimal.
        """
        return Decimal(funding_rate) / Decimal(interval_hours)

    def reset(self):
        """Resets all balances and PnL tracking."""
        self.cash_balance.clear()
        self.margin_balance.clear()
        self.unrealized_pnl.clear()
