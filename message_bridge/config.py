# config.py
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'password': None,
	'decode_responses': True,
    'max_connections': 100
}

# 圆通订单号格式
ORDER_FORMAT = [
	r'YT\d{13,15}',  
]

# 监控的会话
MONITORED_GROUPS = {
	"1": 'yto-test',
	"2": 'yto-test2'
	# 可以添加更多会话"
}

# 微信消息格式
WECHAT_MESSAGE_FORMATS = [
	r".*YT\d{13,15}\s*(催件|拦截|取消拦截|查重).*",
	r".*YT\d{13,15}\s*(到哪里|到那里|退回了吗).*",
	r".*YT\d{13,15}\s*(改地址|改址|更址).*",
    r".*YT\d{13,15}\s*(重量)\s*$",
]

# 圆通消息格式
YTO_MESSAGE_FORMATS = [
    r'YT\d{13,15}.*',
	r'YT\d{13,15}\s(test)',
]

# 客服名称格式
CUSTOME_SERVICE_PATTERNS = [
	r"小圆在线.*",
	r"蓝胖子"
]

# 圆通智能客服ID
YTO_SERVICE_ID = "小圆-总公司"

NEW_WECHAT_MESSAGE_COUNT = 5
NEW_YTO_MESSAGE_COUNT = 5

MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒