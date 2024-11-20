from collections import deque
import re
import uiautomation as auto
import time
import logging
import redis
import json
from datetime import datetime
from threading import Thread
from enum import Enum, auto
from typing import Any, Optional, Dict, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


# 获取当前日期并格式化为字符串
current_date = datetime.now().strftime("%Y-%m-%d")
log_file_name = f"wechat_test_{current_date}.log"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_name, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MessageSource(Enum):
    WECHAT = "wechat"
    YUNDA = "yunda"

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"

class Message:
    def __init__(self, content: str, source: MessageSource, group_id: str = None, 
                 order_number: str = None, msg_type: MessageType = MessageType.TEXT):
        self.content = content
        self.source = source
        self.group_id = group_id
        self.order_number = order_number
        self.type = msg_type
        self.timestamp = datetime.now()

    def to_dict(self):
        return {
            'content': self.content,
            'source': self.source.value,
            'group_id': self.group_id,
            'order_number': self.order_number,
            'type': self.type.value,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            content=data['content'],
            source=MessageSource(data['source']),
            group_id=data['group_id'],
            order_number=data['order_number'],
            msg_type=MessageType(data['type'])
        )

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


class WeChatHandler:
    def __init__(self):
        self.wx = None
        self.last_messages: Dict[str, str] = {}
        self.current_group_id = None
        self.group_cache: Dict[str, auto.WindowControl] = {}
        self.max_retries = 3
        self.retry_delay = 0.5
        self.buffer = deque(maxlen=10)
        self.processed_messages = {}
        self.max_processed_count = 10
        self.new_message = None
        self.last_message_count = 3
        
    def init_wx(self) -> bool:
        """初始化微信窗口"""
        try:
            self.wx = auto.WindowControl(Name="微信", ClassName="WeChatMainWndForPC")
            if not self.wx.Exists():
                logger.error("请先打开微信!")
                return False
            logger.info("微信窗口初始化成功")

            """初始化群聊列表"""
            if not self.init_groups():
                return False
            return True
        except Exception as e:
            logger.error(f"初始化微信窗口失败: {e}")
            return False
        
    def init_groups(self) -> bool:
        """初始化群聊列表"""
        try:
            monitored_groups = [
                'yto-test'
            ]

            group_list = self.wx.ListControl(Name="会话")
            if not group_list.Exists():
                logger.error("找不到群聊列表")
                return False
                
            self.group_cache = {}
            for item in group_list.GetChildren():
                group_id = item.Name
                if group_id and group_id in monitored_groups:
                    self.group_cache[group_id] = item
                    
            logger.info(f"群聊列表初始化成功: {self.group_cache}")
            return True
            
        except Exception as e:
            logger.error(f"初始化群聊列表失败: {e}")
            return False

    def get_session_id(self) -> str:
        """获取当前会话的ID"""
        try:
            edit = self.wx.EditControl(RegexName=r"^(?!.*搜索).*")
            if edit.Exists(maxSearchSeconds=1, searchIntervalSeconds=0.3):
                group_id = edit.Name
            else:
                logger.error("找不到当前会话ID")
                return None
                
            return group_id
        except Exception as e: 
            logger.error(f"获取当前会话ID失败: {e}")
            return None

    def is_valid_message(self, msg_item: auto.Control) -> bool:
        """过滤消息"""
        try:
            if not msg_item.Exists():
                return False    
            
            # 过滤掉不符合规则的消息
            pattern = r".*YT\d{13,15}\s*(催件|拦截).*"
            return re.match(pattern, msg_item.Name) is not None
        except Exception as e:
            logger.error(f"过滤消息失败: {e}")
            return False

    def try_get_message(self) -> Optional[str]:
        """尝试获取并处理消息，带重试机制"""
        try:
            # self.wx.SetActive()  # 激活微信窗口
            session = self.wx.ListControl(Name="会话")
            self.new_message = session.TextControl(searchDepth=3)

            retry_count = 0
            
            while not self.new_message.Exists() and retry_count < self.max_retries:
                time.sleep(0.2)
                retry_count += 1
            
            if self.new_message.Exists():
                for _ in range(self.max_retries):
                    try:
                        group_id = self.get_session_id()

                        if group_id and group_id in self.group_cache:
                            if group_id not in self.processed_messages:
                                self.processed_messages[group_id] = deque(maxlen=self.max_processed_count)  # 设置最大长度为

                            msg_list = self.wx.ListControl(Name='消息')
                            if msg_list.Exists():
                                children = msg_list.GetChildren()
                                if children:
                                    # 判断需要获取的消息数量
                                    get_message_count = len(children) if len(children) < self.last_message_count else self.last_message_count
                                    # 判断当前群是否处理过消息，如果没处理过，get_message_count = 1
                                    # 获取最后几条消息
                                    latest_messages = children[-get_message_count:]  # 可以调整获取的消息数量
                                    for msg_item in latest_messages:
                                        if self.is_valid_message(msg_item):
                                            msg_content = msg_item.Name
                                            # 如果消息未处理过，添加到缓冲区
                                            if msg_content and msg_content not in self.processed_messages[group_id]:
                                                self.buffer[group_id].append(msg_content)
                                                self.processed_messages[group_id].append(msg_content)
                                                self.current_group_id = group_id
                                                logger.info(f"获取到群 {group_id} 的消息: {msg_content}")
                                        
                            return True
                    except Exception as e:
                        print(f"获取消息失败，重试中: {e}")
                        time.sleep(self.retry_delay)
            else:
                print("控件未找到，继续下一次循环")
        
            time.sleep(0.5)  # 适当的循环间隔
        
        except Exception as e:
            print(f"发生错误: {e}")
            time.sleep(1)
    
    def get_next_message(self) -> Optional[str]:
        """从缓冲区获取下一条要处理的消息"""
        if self.current_group_id in self.buffer and self.buffer[self.current_group_id]:
            return self.buffer[self.current_group_id].popleft()
        else:
            return None
        
    def get_messages(self) -> List[Message]:
        """获取新消息"""
        messages = []
        
        # 尝试获取新消息
        if self.try_get_message(self.wx):
            # 处理缓冲区中的所有消息
            while True:
                msg = self.get_next_message()
                if msg is None:
                    break
                print(f"处理消息: {msg}")
                message = Message(
                    content=msg,
                    source=MessageSource.WECHAT,
                    group_id=self.current_group_id
                )
                messages.append(message)
        
        time.sleep(0.5)  # 适当的循环间隔        
            
        return messages

    def send_message(self, message: str, group_id: str) -> bool:
        """向指定群发送消息"""
        try:
            if not self.switch_to_group(group_id):
                return False
                
            edit_box = self.wx.EditControl(Name="输入")
            if not edit_box.Exists():
                logger.error("找不到输入框")
                return False
                
            edit_box.SetValue(message)
            time.sleep(0.1)
            
            send_button = self.wx.ButtonControl(Name="发送(S)")
            if not send_button.Exists():
                logger.error("找不到发送按钮")
                return False
                
            send_button.Click()
            logger.info(f"微信消息已发送到群 {group_id}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"发送微信消息失败: {e}")
            return False

class MessageBridge:
    def __init__(self, redis_config=None):
        self.redis_queue = RedisQueue(**(redis_config or {}))
        self.wechat = WeChatHandler()
        self.is_running = True
        
        # 配置监控的群列表
        self.monitored_groups = [
            "订单群1",
            "订单群2",
            "订单群3"
        ]
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 5  # 秒

    def init(self) -> bool:
        """初始化所有组件"""
        if not self.wechat.init_wx():
            return False
        
        return True

    def process_wechat_messages(self):
        """处理微信消息的线程"""
        while self.is_running:
            try:
                messages = self.wechat.get_messages()
                for msg in messages:
                    # 提取订单号并注册关联
                    order_number = self.order_manager.extract_order_number(msg.content)
                    if order_number:
                        self.order_manager.register_order(order_number, msg.group_id)
                        logger.info(f"从群 {msg.group_id} 提取到订单号: {order_number}")
                    
                    # 将消息发送到圆通
                    if msg.content:
                        self.redis_queue.put_wechat_message(msg)
                                
                time.sleep(1)
            except Exception as e:
                logger.error(f"处理微信消息时出错: {e}")
                time.sleep(1)

    # def forward_messages(self):
    #     """转发消息的线程"""
    #     while self.is_running:
    #         try:
    #             # 处理微信到圆通的消息
    #             wechat_message = self.redis_queue.get_wechat_message()
    #             if wechat_message:
    #                 retry_count = 0
    #                 while retry_count < self.max_retries:
    #                     if self.yunda.send_message(wechat_message['content']):
    #                         break
    #                     retry_count += 1
    #                     if retry_count < self.max_retries:
    #                         time.sleep(self.retry_delay)
    #                 else:
    #                     logger.error("发送消息到圆通失败，已达到最大重试次数")

    #             # 处理圆通到微信的消息
    #             yunda_messages = self.yunda.get_messages()
    #             for msg in yunda_messages:
    #                 self.process_yunda_response(msg.content)

    #             time.sleep(0.5)
    #         except Exception as e:
    #             logger.error(f"转发消息时出错: {e}")
    #             time.sleep(1)

    def run(self):
        """运行消息桥接服务"""
        if not self.init():
            logger.error("初始化失败，程序退出")
            return

        # 启动处理线程
        wechat_thread = Thread(target=self.process_wechat_messages)
        # forward_thread = Thread(target=self.forward_messages)

        wechat_thread.start()
        # forward_thread.start()

        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("接收到退出信号，正在关闭...")
            self.is_running = False

        wechat_thread.join()
        # forward_thread.join()
        logger.info("程序已退出")

def main():

    logger.info("程序启动")

    handler = WeChatHandler()
    if not handler.init_wx():    
        return
    

if __name__ == "__main__":
    main()