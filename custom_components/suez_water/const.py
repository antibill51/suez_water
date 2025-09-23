"""Constants for the Suez Water integration."""

from datetime import timedelta

DOMAIN = "suez_water"

CONF_COUNTER_ID = "counter_id"
CONF_FAST_REFRESH_INTERVAL = "fast_refresh_interval"

DATA_REFRESH_INTERVAL = timedelta(hours=12)
FAST_DATA_REFRESH_INTERVAL = timedelta(minutes=15)
