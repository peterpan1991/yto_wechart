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

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('message_bridge.log', encoding='utf-8'),
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

class OrderManager:
    def __init__(self):
        # 订单号与群ID的映射关系
        self.order_group_map: Dict[str, str] = {}
        # 群ID与订单号的反向映射
        self.group_orders_map: Dict[str, List[str]] = {}
        
    def extract_order_number(self, text: str) -> Optional[str]:
        """从文本中提取订单号"""
        # 支持多种订单号格式
        patterns = [
            r'YT\d{12}',  # 圆通订单号格式
            r'YD\d{12}',  # 韵达订单号格式
            r'SF\d{12}',  # 顺丰订单号格式
            # 可以添加更多格式
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        return None
    
    def register_order(self, order_number: str, group_id: str):
        """注册订单号与群的关联"""
        if not order_number or not group_id:
            return
            
        self.order_group_map[order_number] = group_id
        
        if group_id not in self.group_orders_map:
            self.group_orders_map[group_id] = []
        if order_number not in self.group_orders_map[group_id]:
            self.group_orders_map[group_id].append(order_number)
            
        logger.info(f"注册订单 {order_number} 到群 {group_id}")
    
    def get_group_id(self, order_number: str) -> Optional[str]:
        """获取订单号对应的群ID"""
        return self.order_group_map.get(order_number)
    
    def get_group_orders(self, group_id: str) -> List[str]:
        """获取群对应的所有订单号"""
        return self.group_orders_map.get(group_id, [])

class WeChatHandler:
    def __init__(self):
        self.wx = None
        self.last_messages: Dict[str, str] = {}
        self.current_group_id = None
        self.group_cache: Dict[str, auto.WindowControl] = {}
        
    def init_wx(self) -> bool:
        """初始化微信窗口"""
        try:
            self.wx = auto.WindowControl(Name="微信", ClassName="WeChatMainWndForPC")
            if not self.wx.Exists():
                logger.error("请先打开微信!")
                return False
            logger.info("微信窗口初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化微信窗口失败: {e}")
            return False

    def switch_to_group(self, group_id: str) -> bool:
        """切换到指定的群聊"""
        try:
            if self.current_group_id == group_id:
                return True
                
            if group_id in self.group_cache:
                group_item = self.group_cache[group_id]
                if not group_item.Exists():
                    del self.group_cache[group_id]
                else:
                    group_item.Click()
                    self.current_group_id = group_id
                    time.sleep(0.2)
                    return True
            
            # 点击搜索框
            search = self.wx.EditControl(Name="搜索")
            if not search.Exists():
                logger.error("找不到搜索框")
                return False
                
            search.Click()
            time.sleep(0.1)
            search.SendKeys(group_id, waitTime=0.1)
            time.sleep(0.5)
            
            # 点击搜索结果中的群
            group_item = self.wx.ListItemControl(Name=group_id)
            if not group_item.Exists():
                logger.error(f"找不到群: {group_id}")
                return False
                
            self.group_cache[group_id] = group_item
            group_item.Click()
            self.current_group_id = group_id
            time.sleep(0.2)
            return True
            
        except Exception as e:
            logger.error(f"切换群聊失败: {e}")
            return False

    def get_messages(self) -> List[Message]:
        """获取当前群的新消息"""
        messages = []
        try:
            message_list = self.wx.ListControl(Name="消息")
            if message_list.Exists():
                items = message_list.GetChildren()
                for item in items:
                    content = item.Name
                    if content and content != self.last_messages.get(self.current_group_id):
                        message = Message(
                            content=content,
                            source=MessageSource.WECHAT,
                            group_id=self.current_group_id
                        )
                        messages.append(message)
                        
                if messages:
                    self.last_messages[self.current_group_id] = messages[-1].content
                    
        except Exception as e:
            logger.error(f"获取微信消息失败: {e}")
            
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

class YundaHandler:
    def __init__(self):
        self.driver = None
        self.is_logged_in = False
        
    def init_browser(self):
        """初始化浏览器"""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')  # 无头模式
            self.driver = webdriver.Chrome(options=options)
            logger.info("浏览器初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化浏览器失败: {e}")
            return False
            
    def login(self):
        """登录圆通系统"""
        try:
            self.driver.get("https://yunda-login-url")  # 替换为实际登录地址
            
            # 等待登录页面加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            
            # 输入用户名密码
            username = self.driver.find_element(By.ID, "username")
            password = self.driver.find_element(By.ID, "password")
            
            username.send_keys("your_username")  # 替换为实际用户名
            password.send_keys("your_password")  # 替换为实际密码
            
            # 点击登录按钮
            login_button = self.driver.find_element(By.ID, "login-button")
            login_button.click()
            
            # 等待登录成功
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "dashboard"))
            )
            
            self.is_logged_in = True
            logger.info("圆通系统登录成功")
            return True
            
        except Exception as e:
            logger.error(f"登录圆通系统失败: {e}")
            return False
            
    def send_message(self, message: str) -> bool:
        """发送消息到圆通系统"""
        try:
            if not self.is_logged_in:
                if not self.login():
                    return False
            
            # 找到消息输入框
            message_input = self.driver.find_element(By.ID, "message-input")
            message_input.clear()
            message_input.send_keys(message)
            
            # 点击发送按钮
            send_button = self.driver.find_element(By.ID, "send-button")
            send_button.click()
            
            logger.info(f"消息已发送到圆通系统: {message}")
            return True
            
        except Exception as e:
            logger.error(f"发送消息到圆通系统失败: {e}")
            self.is_logged_in = False  # 标记需要重新登录
            return False
            
    def get_messages(self) -> List[Message]:
        """获取圆通系统的新消息"""
        messages = []
        try:
            if not self.is_logged_in:
                if not self.login():
                    return messages
            
            # 等待消息列表加载
            message_elements = WebDriverWait(self.driver, 5).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "message-item"))
            )
            
            for element in message_elements:
                content = element.text
                if content:
                    message = Message(
                        content=content,
                        source=MessageSource.YUNDA
                    )
                    messages.append(message)
                    
        except TimeoutException:
            logger.warning("获取圆通消息超时")
        except Exception as e:
            logger.error(f"获取圆通消息失败: {e}")
            self.is_logged_in = False
            
        return messages

class MessageBridge:
    def __init__(self, redis_config=None):
        self.redis_queue = RedisQueue(**(redis_config or {}))
        self.wechat = WeChatHandler()
        self.yunda = YundaHandler()
        self.order_manager = OrderManager()
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
        if not self.yunda.init_browser():
            return False
        return True

    def process_wechat_messages(self):
        """处理微信消息的线程"""
        while self.is_running:
            try:
                for group_id in self.monitored_groups:
                    if self.wechat.switch_to_group(group_id):
                        messages = self.wechat.get_messages()
                        for msg in messages:
                            # 提取订单号并注册关联
                            order_number = self.order_manager.extract_order_number(msg.content)
                            if order_number:
                                self.order_manager.register_order(order_number, group_id)
                                logger.info(f"从群 {group_id} 提取到订单号: {order_number}")
                            
                            # 将消息发送到圆通
                            if msg.content:
                                self.redis_queue.put_wechat_message(msg)
                                
                time.sleep(1)
            except Exception as e:
                logger.error(f"处理微信消息时出错: {e}")
                time.sleep(1)

    def process_yunda_response(self, response_text: str):
        """处理圆通的回复消息"""
        try:
            # 从回复中提取订单号
            order_number = self.order_manager.extract_order_number(response_text)
            if order_number:
                # 查找对应的群
                group_id = self.order_manager.get_group_id(order_number)
                if group_id:
                    # 发送到对应的群
                    retry_count = 0
                    while retry_count < self.max_retries:
                        if self.wechat.send_message(response_text, group_id):
                            logger.info(f"圆通回复已转发到群 {group_id}")
                            break
                        retry_count += 1
                        if retry_count < self.max_retries:
                            time.sleep(self.retry_delay)
                    else:
                        logger.error(f"发送消息到群 {group_id} 失败，已达到最大重试次数")
                else:
                    logger.warning(f"找不到订单 {order_number} 对应的群")
            else:
                logger.warning(f"圆通回复中没有找到订单号: {response_text}")
        except Exception as e:
            logger.error(f"处理圆通回复时出错: {e}")

    def forward_messages(self):
        """转发消息的线程"""
        while self.is_running:
            try:
                # 处理微信到圆通的消息
                wechat_message = self.redis_queue.get_wechat_message()
                if wechat_message:
                    retry_count = 0
                    while retry_count < self.max_retries:
                        if self.yunda.send_message(wechat_message['content']):
                            break
                        retry_count += 1
                        if retry_count < self.max_retries:
                            time.sleep(self.retry_delay)
                    else:
                        logger.error("发送消息到圆通失败，已达到最大重试次数")

                # 处理圆通到微信的消息
                yunda_messages = self.yunda.get_messages()
                for msg in yunda_messages:
                    self.process_yunda_response(msg.content)

                time.sleep(0.5)
            except Exception as e:
                logger.error(f"转发消息时出错: {e}")
                time.sleep(1)

    def run(self):
        """运行消息桥接服务"""
        if not self.init():
            logger.error("初始化失败，程序退出")
            return

        # 启动处理线程
        wechat_thread = Thread(target=self.process_wechat_messages)
        forward_thread = Thread(target=self.forward_messages)

        wechat_thread.start()
        forward_thread.start()

        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("接收到退出信号，正在关闭...")
            self.is_running = False

        wechat_thread.join()
        forward_thread.join()
        logger.info("程序已退出")

def main():
    # Redis配置
    redis_config = {
        'host': 'localhost',
        'port': 6379,
        'db': 0,
        'password': None
    }
    
    bridge = MessageBridge(redis_config)
    bridge.run()

if __name__ == "__main__":
    main()