import re
from logger import logger
from typing import Any, Optional, Dict, List
from models.redis_queue import RedisQueue

class OrderManager:
    def __init__(self):
        # 订单号与群ID的映射关系
        self.order_session_map: Dict[str, str] = {}
        self.redis_queue = RedisQueue()
        
    def extract_order_number(self, text: str) -> Optional[List[str]]:
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
    
    def register_order(self, order_numbers: List, session_id: str):
        """注册订单号与会话的关联"""
        if not order_numbers or not session_id:
            return

        self.redis_queue.put_orders_to_session(session_id, order_numbers)
    
    def get_session_id(self, order_number: str) -> Optional[str]:
        """获取订单号对应的会话ID"""
        return self.redis_queue.find_session_id_by_order_number(order_number)
    