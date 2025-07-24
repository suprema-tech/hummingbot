from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0004"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD_251226"

BROKER_ID = "x-3QreWesy"


class BinanceDeliveryConfigMap(BaseConnectorConfigMap):
    connector: str = "binance_delivery"
    binance_delivery_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Binance Delivery API key",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )
    binance_delivery_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Binance Delivery API secret",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )


KEYS = BinanceDeliveryConfigMap.model_construct()

OTHER_DOMAINS = ["binance_delivery_testnet"]
OTHER_DOMAINS_PARAMETER = {"binance_delivery_testnet": "binance_delivery_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"binance_delivery_testnet": "BTC-USD_251226"}
OTHER_DOMAINS_DEFAULT_FEES = {"binance_delivery_testnet": [0.02, 0.04]}


class BinanceDeliveryTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "binance_delivery_testnet"
    binance_delivery_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Binance Delivery testnet API key",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )
    binance_delivery_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Binance Delivery testnet API secret",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )
    model_config = ConfigDict(title="binance_delivery")


OTHER_DOMAINS_KEYS = {"binance_delivery_testnet": BinanceDeliveryTestnetConfigMap.model_construct()}
