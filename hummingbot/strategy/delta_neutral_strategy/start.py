from decimal import Decimal

from hummingbot.strategy.delta_neutral_strategy.delta_neutral_strategy import (
    ArbitrageMode,
    ArbitragePair,
    DeltaNeutralArbitrageStrategy,
    InstrumentConfig,
    InstrumentType,
    RiskParameters,
)


def start(self):
    """
    Creates and starts a Delta Neutral Arbitrage Strategy instance from configuration.
    """
    # Get configuration values
    from hummingbot.strategy.delta_neutral_strategy.delta_neutral_strategy_config_map import (
        delta_neutral_strategy_config_map as config_map,
    )

    spot_connector = config_map["spot_exchange"].value.lower()
    spot_market = config_map["spot_trading_pair"].value
    derivative_connector = config_map["derivative_exchange"].value.lower()
    derivative_market = config_map["derivative_trading_pair"].value

    # Initialize markets using Hummingbot framework pattern
    self.initialize_markets([(spot_connector, [spot_market]), (derivative_connector, [derivative_market])])

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

    # Create strategy instance using Hummingbot framework pattern
    self.strategy = DeltaNeutralArbitrageStrategy(
        connectors=self.markets,
        arbitrage_pairs=[arbitrage_pair],
        risk_parameters=risk_parameters,
        refresh_interval=config_map["refresh_interval"].value,
    )
