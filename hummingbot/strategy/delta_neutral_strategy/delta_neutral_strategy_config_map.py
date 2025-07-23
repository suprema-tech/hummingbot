from decimal import Decimal

from hummingbot.client.config.config_validators import (
    validate_connector,
    validate_decimal,
    validate_derivative,
    validate_int,
    validate_market_trading_pair,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import AllConnectorSettings, required_exchanges, requried_connector_trading_pairs


def exchange_on_validated(value: str) -> None:
    required_exchanges.add(value)


def spot_market_validator(value: str) -> None:
    exchange = delta_neutral_strategy_config_map["spot_exchange"].value
    return validate_market_trading_pair(exchange, value)


def spot_market_on_validated(value: str) -> None:
    requried_connector_trading_pairs[delta_neutral_strategy_config_map["spot_exchange"].value] = [value]


def derivative_market_validator(value: str) -> None:
    exchange = delta_neutral_strategy_config_map["derivative_exchange"].value
    return validate_market_trading_pair(exchange, value)


def derivative_market_on_validated(value: str) -> None:
    requried_connector_trading_pairs[delta_neutral_strategy_config_map["derivative_exchange"].value] = [value]


def spot_market_prompt() -> str:
    connector = delta_neutral_strategy_config_map.get("spot_exchange").value
    example = AllConnectorSettings.get_example_pairs().get(connector)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


def derivative_market_prompt() -> str:
    connector = delta_neutral_strategy_config_map.get("derivative_exchange").value
    example = AllConnectorSettings.get_example_pairs().get(connector)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


# Configuration map for the Delta Neutral Arbitrage Strategy
delta_neutral_strategy_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="delta_neutral_strategy",
    ),
    "spot_exchange": ConfigVar(
        key="spot_exchange",
        prompt="Enter the spot exchange to use for arbitrage (e.g., binance) >>> ",
        prompt_on_new=True,
        validator=validate_connector,
        on_validated=exchange_on_validated,
    ),
    "spot_trading_pair": ConfigVar(
        key="spot_trading_pair",
        prompt=spot_market_prompt,
        prompt_on_new=True,
        validator=spot_market_validator,
        on_validated=spot_market_on_validated,
    ),
    "derivative_exchange": ConfigVar(
        key="derivative_exchange",
        prompt="Enter the derivative exchange to use for arbitrage (e.g., binance_perpetual) >>> ",
        prompt_on_new=True,
        validator=validate_derivative,
        on_validated=exchange_on_validated,
    ),
    "derivative_trading_pair": ConfigVar(
        key="derivative_trading_pair",
        prompt=derivative_market_prompt,
        prompt_on_new=True,
        validator=derivative_market_validator,
        on_validated=derivative_market_on_validated,
    ),
    "arbitrage_mode": ConfigVar(
        key="arbitrage_mode",
        prompt="Enter arbitrage mode (funding_rate, price_spread, basis_arbitrage) >>> ",
        prompt_on_new=True,
        default="funding_rate",
    ),
    "min_profit_bps": ConfigVar(
        key="min_profit_bps",
        prompt="Enter minimum profit threshold in basis points (e.g., 5.0) >>> ",
        type_str="decimal",
        prompt_on_new=True,
        validator=validate_decimal,
        default=Decimal("5.0"),
    ),
    "max_trade_size": ConfigVar(
        key="max_trade_size",
        prompt="Enter maximum trade size in USD (e.g., 1000.0) >>> ",
        type_str="decimal",
        prompt_on_new=True,
        validator=validate_decimal,
        default=Decimal("1000.0"),
    ),
    "max_inventory_size": ConfigVar(
        key="max_inventory_size",
        prompt="Enter maximum total inventory size in USD (e.g., 10000.0) >>> ",
        type_str="decimal",
        validator=validate_decimal,
        default=Decimal("10000.0"),
    ),
    "max_inventory_ratio": ConfigVar(
        key="max_inventory_ratio",
        prompt="Enter maximum inventory ratio (0.0 to 1.0, e.g., 0.8) >>> ",
        type_str="decimal",
        validator=validate_decimal,
        default=Decimal("0.8"),
    ),
    "stop_loss_bps": ConfigVar(
        key="stop_loss_bps",
        prompt="Enter stop loss in basis points (e.g., 25.0, or 0 to disable) >>> ",
        type_str="decimal",
        validator=validate_decimal,
        default=Decimal("25.0"),
    ),
    "take_profit_bps": ConfigVar(
        key="take_profit_bps",
        prompt="Enter take profit in basis points (e.g., 20.0, or 0 to disable) >>> ",
        type_str="decimal",
        validator=validate_decimal,
        default=Decimal("20.0"),
    ),
    "max_position_age_minutes": ConfigVar(
        key="max_position_age_minutes",
        prompt="Enter maximum position age in minutes (e.g., 120) >>> ",
        type_str="int",
        validator=validate_int,
        default=120,
    ),
    "enable_dynamic_hedging": ConfigVar(
        key="enable_dynamic_hedging",
        prompt="Enable dynamic hedging? (Yes/No) >>> ",
        type_str="bool",
        default=True,
    ),
    "hedging_threshold_bps": ConfigVar(
        key="hedging_threshold_bps",
        prompt="Enter hedging threshold in basis points (e.g., 10.0) >>> ",
        type_str="decimal",
        validator=validate_decimal,
        default=Decimal("10.0"),
    ),
    "leverage": ConfigVar(
        key="leverage",
        prompt="Enter leverage for derivative positions (e.g., 10.0) >>> ",
        type_str="decimal",
        validator=validate_decimal,
        default=Decimal("10.0"),
    ),
    "refresh_interval": ConfigVar(
        key="refresh_interval",
        prompt="Enter refresh interval in seconds (e.g., 1.0) >>> ",
        type_str="float",
        default=1.0,
    ),
    "emergency_stop_enabled": ConfigVar(
        key="emergency_stop_enabled",
        prompt="Enable emergency stop? (Yes/No) >>> ",
        type_str="bool",
        default=True,
    ),
    "heartbeat_timeout_seconds": ConfigVar(
        key="heartbeat_timeout_seconds",
        prompt="Enter heartbeat timeout in seconds (e.g., 60) >>> ",
        type_str="int",
        validator=validate_int,
        default=60,
    ),
}
