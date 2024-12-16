import re
from typing import List, Optional

def is_valid_message(msg: str) -> bool:
	"""过滤消息"""
	# 过滤掉不符合规则的消息
	patterns = [
		r".*YT\d{13,15}\s*(催件|拦截|取消拦截|查重).*",  # 圆通订单号格式
		r".*YT\d{13,15}\s*(到哪里|到那里|退回了吗).*",
		r".*YT\d{13,15}\s*(改地址|改址|更址).*",
		r".*YT\d{13,15}\s*(重量)\s*$",
		# 可以添加更多格式
	]
	for pattern in patterns:
		match = re.search(pattern, msg, re.DOTALL)
		if match:
			return True
	return False

def extract_order_number(text: str) -> Optional[List[str]]:
	"""从文本中提取订单号"""
	# 支持多种订单号格式
	patterns = [
		r'YT\d{13,15}',  # 圆通订单号格式
		# 可以添加更多格式
	]
	order_numbers = []
	for pattern in patterns:
		match = re.findall(pattern, text)
		order_numbers.extend(match)
		
	return order_numbers if order_numbers else None

def is_customer(name: str) -> bool:
        """判断是否自己"""
        if not name:
            return False

        """判断是否是客服"""
        patterns = [
            r"小圆在线.*",
            r"蓝胖子"
		]
        for pattern in patterns:
            match = re.search(pattern, name, re.DOTALL)
            if match:
                return False
        return True

def is_valid_yto_message(msg: str) -> bool:
	"""过滤消息"""
	# 过滤掉不符合规则的消息
	patterns = [
		r'YT\d{13,15}',
		# 可以添加更多格式
	]
	for pattern in patterns:
		match = re.search(pattern, msg, re.DOTALL)
		if match:
			return True
	return False

def filter_yto_message(msg: str) -> str:
	"""过滤消息"""
	return re.sub(r'@\w+', '', msg)
	

# test_msg = "YT7509268682028\nYT7509506091027\nYT7509506091029 催件"
# test_msg = "YT7509268682028 拦截\nYT7509506091027\nYT7509506091029催件"
# test_msg = "YT7509268682028 重量 10"
# print(is_valid_message(test_msg))

# order_numbers = extract_order_number(test_msg)
# print(order_numbers)

# test_name = "蓝胖子"
# print(is_customer(test_name))

# test_msg = "YT7509268682028 拦截\nYT7509506091027\nYT7509506091029催件"
# print(is_valid_yto_message(test_msg))

# test_msg = "@小圆2+ 在线 你好，请问有什么可以帮到您？"
# print(filter_yto_message(test_msg))