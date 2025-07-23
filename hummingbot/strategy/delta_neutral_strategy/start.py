from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.delta_neutral_strategy.delta_neutral_strategy import (
    ArbitrageMode,
    ArbitragePair,
    DeltaNeutralArbitrageStrategy,
    InstrumentConfig,
    InstrumentType,
    RiskParameters,
)


def start(config_map) -> DeltaNeutralArbitrageStrategy:
    """
    Creates and starts a Delta Neutral Arbitrage Strategy instance from configuration.
    """

    # Create spot instrument configuration
    spot_instrument = InstrumentConfig(
        symbol=config_map["spot_trading_pair"].value.split("-")[0],
        exchange=config_map["spot_exchange"].value,
        instrument_type=InstrumentType.SPOT,
        trading_pair=config_map["spot_trading_pair"].value,
        min_trade_size=Decimal("0.001"),  # This should be fetched from exchange info
        max_trade_size=config_map["max_trade_size"].value / Decimal("50000"),  # Rough estimate, should use current price
        tick_size=Decimal("0.01"),  # This should be fetched from exchange info
    )

    # Create derivative instrument configuration
    derivative_instrument = InstrumentConfig(
        symbol=config_map["derivative_trading_pair"].value.split("-")[0],
        exchange=config_map["derivative_exchange"].value,
        instrument_type=InstrumentType.PERPETUAL,  # Assuming perpetual, could be enhanced
        trading_pair=config_map["derivative_trading_pair"].value,
        min_trade_size=Decimal("0.001"),  # This should be fetched from exchange info
        max_trade_size=config_map["max_trade_size"].value / Decimal("50000"),  # Rough estimate
        tick_size=Decimal("0.01"),  # This should be fetched from exchange info
        leverage=config_map["leverage"].value,
    )

    # Create arbitrage pair
    arbitrage_mode = ArbitrageMode(config_map["arbitrage_mode"].value)
    arbitrage_pair = ArbitragePair(
        leg_a=spot_instrument,
        leg_b=derivative_instrument,
        mode=arbitrage_mode,
        min_profit_threshold=config_map["min_profit_bps"].value,
        max_inventory_ratio=config_map["max_inventory_ratio"].value,
        enabled=True,
    )

    # Create risk parameters
    risk_parameters = RiskParameters(
        max_inventory_size=config_map["max_inventory_size"].value,
        max_trade_size=config_map["max_trade_size"].value,
        min_profit_bps=config_map["min_profit_bps"].value,
        max_profit_bps=Decimal("100.0"),  # Default max profit
        stop_loss_bps=config_map["stop_loss_bps"].value if config_map["stop_loss_bps"].value > 0 else None,
        take_profit_bps=config_map["take_profit_bps"].value if config_map["take_profit_bps"].value > 0 else None,
        heartbeat_timeout_seconds=config_map["heartbeat_timeout_seconds"].value,
        max_position_age_minutes=config_map["max_position_age_minutes"].value,
        emergency_stop_enabled=config_map["emergency_stop_enabled"].value,
    )

    # Get connectors (this would be handled by Hummingbot's connector management)
    connectors: Dict[str, ConnectorBase] = {}
    # Note: In production, this would be populated by Hummingbot's market initialization

    # Create strategy instance
    strategy = DeltaNeutralArbitrageStrategy(
        connectors=connectors,
        arbitrage_pairs=[arbitrage_pair],
        risk_parameters=risk_parameters,
        refresh_interval=config_map["refresh_interval"].value,
    )

    return strategy
