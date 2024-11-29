# config.py
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'password': None,
	'decode_responses': True
}

ORDER_FORMAT = [
	r'YT\d{13,15}',  # 圆通订单号格式
	# 可以添加更多格式
]

MONITORED_GROUPS = {
	"1": 'yto-test'
}

WECHAT_MESSAGE_FORMATS = [
	r".*YT\d{13,15}\s*(催件|拦截|取消拦截|查重|重量).*",  # 圆通订单号格式
	r".*YT\d{13,15}\s*(到哪里|到那里|退回了吗).*",
	r".*YT\d{13,15}\s*(改地址|改址).*",
	# 可以添加更多格式
]

YTO_MESSAGE_FORMATS = [
	r'YT\d{13,15}',  # 圆通订单号格式
	# 可以添加更多格式
]

CUSTOME_SERVICE_PATTERNS = [
	r"小圆在线.*",
	r"蓝胖子"
]

MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒