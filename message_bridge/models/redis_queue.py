import redis
import json
from logger import logger
from models.message import Message
from typing import Any, Optional, Dict, List
import time

class RedisQueue:
    def __init__(self, host='localhost', port=6379, db=0, password=None):
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True
        )
        self.wechat_queue = 'wechat_messages'
        self.wechat_processed_queue = f"{self.wechat_queue}_processed"
        self.yto_queue = 'yto_messages'
        self.yto_processed_queue = f"{self.yto_queue}_processed"
        self.max_processed_limit = 1000
        self.session_order_queue = 'session_order'
        self.order_to_session_queue = 'order_to_session'

    def put_wechat_message(self, message: Message):
        """将微信消息放入队列"""
        try:
            self.redis_client.rpush(self.wechat_queue, json.dumps(message.to_dict()))
            logger.info(f"消息已加入微信队列: {message.content}")
        except Exception as e:
            logger.error(f"添加微信消息到队列失败: {e}")
            
    def put_wechat_processed_message(self, message: str, session_id: str):
        """将微信消息放入已处理队列"""
        try:
            timestamp = time.time()
            redis_key = f"{self.wechat_processed_queue}_{session_id}"
            self.redis_client.zadd(redis_key, {message: timestamp}, nx=True)
            
            # 检查当前有序集合的大小
            if self.redis_client.zcard(redis_key) > self.max_processed_limit:
                # 移除分数最低的元素（最旧的元素）
                self.redis_client.zremrangebyrank(redis_key, 0, 0)  # 删除排名最低的元素
        except Exception as e:
            logger.error(f"添加微信消息到已处理队列失败: {e}")

    def get_wechat_message(self) -> Optional[dict]:
        """从队列获取微信消息"""
        try:
            data = self.redis_client.lpop(self.wechat_queue)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"从队列获取微信消息失败: {e}")
            return None
    
    def is_message_in_wechat_processed_queue(self, message: str, session_id: str) -> bool:
        """判断消息是否在已处理队列中"""
        try:
            redis_key = f"{self.wechat_processed_queue}_{session_id}"
            score = self.redis_client.zscore(redis_key, message)  # 获取消息的分数
            
            return score is not None  # 如果分数不为 None，则表示消息在有序集合中
        except Exception as e:
            logger.error(f"判断消息是否在已处理队列中失败: {e}")
            return False

    def put_yto_message(self, message: Message):
        """将圆通消息放入队列"""
        try:
            self.redis_client.rpush(self.yto_queue, json.dumps(message.to_dict()))
            logger.info(f"消息已加入圆通队列: {message.content}")
        except Exception as e:
            logger.error(f"添加圆通消息到队列失败: {e}")
    
    def put_yto_processed_message(self, message: str):
        """将圆通消息放入已处理队列"""
        try:
            timestamp = time.time()
            self.redis_client.zadd(self.yto_processed_queue, {message: timestamp}, nx=True)
            
            # 检查当前有序集合的大小
            if self.redis_client.zcard(self.yto_processed_queue) > self.max_processed_limit:
                # 移除分数最低的元素（最旧的元素）
                self.redis_client.zremrangebyrank(self.yto_processed_queue, 0, 0)  # 删除排名最低的元素
        except Exception as e:
            logger.error(f"添加圆通消息到已处理队列失败: {e}")
    
    def get_yto_message(self) -> Optional[dict]:
        """从队列获取圆通消息"""
        try:
            data = self.redis_client.lpop(self.yto_queue)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"从队列获取圆通消息失败: {e}")
            return None
    
    def is_message_in_yto_processed_queue(self, message: str) -> bool:
        """判断消息是否在已处理队列中"""
        try:
            score = self.redis_client.zscore(self.yto_processed_queue, message)  # 获取消息的分数
            
            return score is not None  # 如果分数不为 None，则表示消息在有序集合中
        except Exception as e:
            logger.error(f"判断消息是否在已处理队列中失败: {e}")
            return False
    
    def is_order_in_session(self, session_id: str, order_number: str) -> bool:
        """判断消息是否在已处理队列中"""
        try:
            redis_key = f"{self.session_order_queue}_{session_id}"
            score = self.redis_client.zscore(redis_key, order_number)  # 获取消息的分数
            
            return score is not None  # 如果分数不为 None，则表示消息在有序集合中
        except Exception as e:
            logger.error(f"判断消息是否在已处理队列中失败: {e}")
            return False
    def put_session_order(self, session_id: str, order_number: str):
        """将订单放入微信关联群"""
        try:
            timestamp = time.time()
            redis_key = f"{self.session_order_queue}_{session_id}"
            self.redis_client.zadd(redis_key, {order_number: timestamp}, nx=True)

            # 更新订单到会话的映射
            self.redis_client.hset(self.order_to_session_queue, order_number, session_id)
            
            # 检查当前有序集合的大小
            if self.redis_client.zcard(redis_key) > self.max_processed_limit:
                # 移除分数最低的元素（最旧的元素）
                removed_order = self.redis_client.zrange(redis_key, 0, 0)[0]
                self.redis_client.zremrangebyrank(redis_key, 0, 0)  # 删除排名最低的元素

                 # 从映射中移除被删除的订单
                self.redis_client.hdel(self.order_to_session_queue, removed_order)
        except Exception as e:
            logger.error(f"将订单放入微信关联群失败: {e}")

    def put_orders_to_session(self, session_id: str, order_numbers: List[str]):
        """处理订单列表，将不在会话中的订单添加到会话中"""
        for order_number in order_numbers:
            if not self.is_order_in_session(session_id, order_number):
                self.put_session_order(session_id, order_number)
                print(f"Order {order_number} added to session {session_id}.")
            else:
                print(f"Order {order_number} already in session {session_id}.")
    
    def find_session_id_by_order_number(self, order_number: str) -> Optional[str]:
        """根据订单号查找对应的会话ID"""
        try:
            session_id = self.redis_client.hget(self.order_to_session_queue, order_number)
            return session_id if session_id else None
        except Exception as e:
            logger.error(f"查找订单号对应的会话ID失败: {e}")
            return None