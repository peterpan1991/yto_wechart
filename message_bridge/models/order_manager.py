import re
from logger import logger

class OrderManager:
    def __init__(self):
        self.order_group_map = {}
        self.group_orders_map = {}

    def extract_order_number(self, text):
        patterns = [r'YT\d{12}', r'YD\d{12}', r'SF\d{12}']
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        return None

    def register_order(self, order_number, group_id):
        if order_number and group_id:
            self.order_group_map[order_number] = group_id
            self.group_orders_map.setdefault(group_id, []).append(order_number)
            logger.info(f"注册订单 {order_number} 到群 {group_id}")

    def get_group_id(self, order_number):
        return self.order_group_map.get(order_number)

    def get_group_orders(self, group_id):
        return self.group_orders_map.get(group_id, [])