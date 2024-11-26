import re
from logger import logger
from typing import Any, Optional, Dict, List

class OrderManager:
    def __init__(self):
        # 订单号与群ID的映射关系
        self.order_session_map: Dict[str, str] = {}
        # 群ID与订单号的反向映射
        self.session_orders_map: Dict[str, List[str]] = {}
        
    def extract_order_number(self, text: str) -> Optional[str]:
        """从文本中提取订单号"""
        # 支持多种订单号格式
        patterns = [
            r'YT\d{13,15}',  # 圆通订单号格式
            # 可以添加更多格式
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        return None
    
    def register_order(self, order_number: str, session_id: str):
        """注册订单号与会话的关联"""
        if not order_number or not session_id:
            return
            
        self.order_session_map[order_number] = session_id
        
        if session_id not in self.session_orders_map:
            self.session_orders_map[session_id] = []
        if order_number not in self.session_orders_map[session_id]:
            self.session_orders_map[session_id].append(order_number)
    
    def get_session_id(self, order_number: str) -> Optional[str]:
        """获取订单号对应的会话ID"""
        return self.order_session_map.get(order_number)
    
    def get_session_orders(self, session_id: str) -> List[str]:
        """获取会话对应的所有订单号"""
        return self.session_orders_map.get(session_id, [])