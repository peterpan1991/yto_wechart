import redis
import json
from logger import logger
from models.message import Message
from typing import Any, Optional, Dict, List

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
        self.yunda_queue = 'yunda_messages'

    def put_wechat_message(self, message: Message):
        """将微信消息放入队列"""
        try:
            self.redis_client.rpush(self.wechat_queue, json.dumps(message.to_dict()))
            logger.info(f"消息已加入微信队列: {message.content}")
        except Exception as e:
            logger.error(f"添加微信消息到队列失败: {e}")

    def put_yunda_message(self, message: Message):
        """将圆通消息放入队列"""
        try:
            self.redis_client.rpush(self.yunda_queue, json.dumps(message.to_dict()))
            logger.info(f"消息已加入圆通队列: {message.content}")
        except Exception as e:
            logger.error(f"添加圆通消息到队列失败: {e}")

    def get_wechat_message(self) -> Optional[dict]:
        """从队列获取微信消息"""
        try:
            data = self.redis_client.lpop(self.wechat_queue)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"从队列获取微信消息失败: {e}")
            return None

    def get_yunda_message(self) -> Optional[dict]:
        """从队列获取圆通消息"""
        try:
            data = self.redis_client.lpop(self.yunda_queue)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"从队列获取圆通消息失败: {e}")
            return None

    def put_message(self, message: Message, queue: str):
        try:
            self.redis_client.rpush(queue, json.dumps(message.to_dict()))
            logger.info(f"消息已加入队列 {queue}: {message.content}")
        except Exception as e:
            logger.error(f"添加消息到队列失败: {e}")

    def get_message(self, queue: str):
        try:
            data = self.redis_client.lpop(queue)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"从队列获取消息失败: {e}")
            return None