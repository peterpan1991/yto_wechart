# config.py
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'password': None
}

MONITORED_GROUPS = [
    "订单群1",
    "订单群2",
    "订单群3"
]

MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒