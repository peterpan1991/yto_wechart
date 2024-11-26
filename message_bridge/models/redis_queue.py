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

    def put_wechat_message(self, message: Message):
        """将微信消息放入队列"""
        try:
            self.redis_client.rpush(self.wechat_queue, json.dumps(message.to_dict()))
            logger.info(f"消息已加入微信队列: {message.content}")
        except Exception as e:
            logger.error(f"添加微信消息到队列失败: {e}")
            
    def put_wechat_processed_message(self, message: str, name: str):
        """将微信消息放入已处理队列"""
        try:
            timestamp = time.time()
            self.redis_client.zadd(name, {message: timestamp})
            
            # 检查当前有序集合的大小
            if self.redis_client.zcard(name) > self.max_processed_limit:
                # 移除分数最低的元素（最旧的元素）
                self.redis_client.zremrangebyrank(name, 0, 0)  # 删除排名最低的元素
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
    
    def is_message_in_wechat_processed_queue(self, message: str, name: str) -> bool:
        """判断消息是否在已处理队列中"""
        try:
            score = self.redis_client.zscore(name, message)  # 获取消息的分数
            
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
            self.redis_client.zadd(self.yto_processed_queue, {message: timestamp})
            
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