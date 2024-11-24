from collections import deque
import re
import uiautomation as auto
import time
import logging
import redis
import json
from datetime import datetime
from threading import Thread
from enum import Enum
from typing import Any, Optional, Dict, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys


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
    YTO = "yto"

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"

class Message:
    def __init__(self, content: str, source: MessageSource, session_id: str = None, 
                 order_number: str = None, msg_type: MessageType = MessageType.TEXT):
        self.content = content
        self.source = source
        self.session_id = session_id
        self.order_number = order_number
        self.type = msg_type
        self.timestamp = datetime.now()

    def to_dict(self):
        return {
            'content': self.content,
            'source': self.source.value,
            'session_id': self.session_id,
            'order_number': self.order_number,
            'type': self.type.value,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            content=data['content'],
            source=MessageSource(data['source']),
            session_id=data['session_id'],
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
        self.yto_queue = 'yto_messages'

    def put_wechat_message(self, message: Message):
        """将微信消息放入队列"""
        try:
            self.redis_client.rpush(self.wechat_queue, json.dumps(message.to_dict()))
            logger.info(f"消息已加入微信队列: {message.content}")
        except Exception as e:
            logger.error(f"添加微信消息到队列失败: {e}")

    def get_wechat_message(self) -> Optional[dict]:
        """从队列获取微信消息"""
        try:
            data = self.redis_client.lpop(self.wechat_queue)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"从队列获取微信消息失败: {e}")
            return None
    
    def put_yto_message(self, message: Message):
        """将圆通消息放入队列"""
        try:
            self.redis_client.rpush(self.yto_queue, json.dumps(message.to_dict()))
            logger.info(f"消息已加入圆通队列: {message.content}")
        except Exception as e:
            logger.error(f"添加圆通消息到队列失败: {e}")
    
    def get_yto_message(self) -> Optional[dict]:
        """从队列获取圆通消息"""
        try:
            data = self.redis_client.lpop(self.yto_queue)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"从队列获取圆通消息失败: {e}")
            return None

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
            r'YT\d{13-15}',  # 圆通订单号格式
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
            
        logger.info(f"注册订单 {order_number} 到群 {session_id}")
    
    def get_session_id(self, order_number: str) -> Optional[str]:
        """获取订单号对应的会话ID"""
        return self.order_session_map.get(order_number)
    
    def get_session_orders(self, session_id: str) -> List[str]:
        """获取会话对应的所有订单号"""
        return self.session_orders_map.get(session_id, [])


class WeChatHandler:
    def __init__(self):
        self.wx = None
        self.last_messages: Dict[str, str] = {}
        self.current_session_id = None
        self.group_cache: Dict[str, auto.WindowControl] = {}
        self.max_retries = 3
        self.retry_delay = 0.5
        self.buffer = {}
        self.processed_messages = {}
        self.max_processed_count = 10
        self.new_message = None
        self.last_message_count = 3
        self.monitoring_groups: Dict[str, str] = {}
        
    def init_wx(self) -> bool:
        """初始化微信窗口"""
        try:
            self.wx = auto.WindowControl(Name="微信", ClassName="WeChatMainWndForPC")
            if not self.wx.Exists():
                logger.error("请先打开微信!")
                return False
            logger.info("微信窗口初始化成功")

            """初始化会话列表"""
            if not self.init_groups():
                return False
            return True
        except Exception as e:
            logger.error(f"初始化微信窗口失败: {e}")
            return False
        
    def init_groups(self) -> bool:
        """初始化会话列表"""
        try:
            monitored_groups = {
                1: 'yto-test'
            }
            self.monitoring_groups = monitored_groups

            group_list = self.wx.ListControl(Name="会话")
            if not group_list.Exists():
                logger.error("找不到会话列表")
                return False
                
            self.group_cache = {}
            for item in group_list.GetChildren():
                group_name = item.Name
                session_id = next((k for k, v in self.monitoring_groups.items() if v == group_name), None)
                if group_name and session_id is not None:
                    self.group_cache[session_id] = item
                    
            logger.info(f"会话列表初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"初始化会话列表失败: {e}")
            return False
        
    def get_session_id(self) -> str:
        """获取当前会话的ID"""
        try:
            edit = self.wx.EditControl(RegexName=r"^(?!.*搜索).*")
            if edit.Exists(maxSearchSeconds=1, searchIntervalSeconds=0.3):
                session_id = edit.Name
            else:
                logger.error("找不到当前会话ID")
                return None
                
            return session_id
        except Exception as e: 
            logger.error(f"获取当前会话ID失败: {e}")
            return None

    def switch_to_session(self, session_id: str) -> bool:
        """切换到指定的会话"""
        try:
            if self.current_session_id == session_id:
                return True
                
            if session_id in self.group_cache:
                group_item = self.group_cache[session_id]
                if not group_item.Exists():
                    del self.group_cache[session_id]
                else:
                    group_item.Click()
                    self.current_session_id = session_id
                    time.sleep(0.2)
                    return True
            
        except Exception as e:
            logger.error(f"切换会话失败: {e}")
            return False

    def is_valid_message(self, msg: str) -> bool:
        """过滤消息"""
        # 过滤掉不符合规则的消息
        pattern = r".*YT\d{13,15}\s*(催件|拦截).*"
        return re.match(pattern, msg) is not None

    def try_get_message(self) -> Optional[str]:
        """尝试获取并处理消息，带重试机制"""
        try:
            self.wx.SetActive()  # 激活微信窗口
            session = self.wx.ListControl(Name="会话")
            self.new_message = session.TextControl(searchDepth=3)

            retry_count = 0
            
            while not self.new_message.Exists() and retry_count < self.max_retries:
                time.sleep(0.2)
                retry_count += 1
            
            if self.new_message.Exists():
                self.new_message.Click(simulateMove=False)
                for _ in range(self.max_retries):
                    try:
                        group_name = self.get_session_id()
                        
                        session_id = next((k for k, v in self.monitoring_groups.items() if v == group_name), None)
                        # 判断group在监控群里面 且 在拿到的会话列表里面
                        if session_id is not None and session_id in self.group_cache:
                            
                            if session_id not in self.processed_messages:
                                self.processed_messages[session_id] = deque(maxlen=self.max_processed_count)  # 设置最大长度为
                            
                            if session_id not in self.buffer:
                                self.buffer[session_id] = deque(maxlen=self.max_processed_count)  # 确保 buffer 中存在 session_id

                            msg_list = self.wx.ListControl(Name='消息')
                            if msg_list.Exists():
                                children = msg_list.GetChildren()
                                if children:
                                    # 判断需要获取的消息数量
                                    get_message_count = len(children) if len(children) < self.last_message_count else self.last_message_count
                                    # 判断当前群是否处理过消息，如果没处理过，get_message_count = 1
                                    # 获取最后几条消息
                                    latest_messages = children[-get_message_count:]  # 可以调整获取的消息数量
                                    is_processed = False
                                    for msg_item in latest_messages:
                                        print(f"收到消息: {msg_item.Name}")
                                        if self.is_valid_message(msg_item.Name):
                                            msg_content = msg_item.Name
                                            # 如果消息未处理过，添加到缓冲区
                                            if msg_content and msg_content not in self.processed_messages[session_id]:
                                                self.buffer[session_id].append(msg_content)
                                                self.processed_messages[session_id].append(msg_content)
                                                self.current_session_id = session_id
                                                is_processed = True
                                                logger.info(f"获取到群 {session_id} 的消息: {msg_content}")
                                    
                                    if is_processed:
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
        if self.current_session_id in self.buffer and self.buffer[self.current_session_id]:
            return self.buffer[self.current_session_id].popleft()
        else:
            return None
        
    def get_messages(self) -> List[Message]:
        """获取新消息"""
        messages = []
        
        # 尝试获取新消息
        if self.try_get_message():
            # 处理缓冲区中的所有消息
            while True:
                msg = self.get_next_message()
                print(f"缓冲区消息: {msg}")
                if msg is None:
                    break
                print(f"处理消息: {msg}")
                message = Message(
                    content=msg,
                    source=MessageSource.WECHAT,
                    session_id=self.current_session_id
                )
                messages.append(message)
        
        time.sleep(0.5)  # 适当的循环间隔        
            
        return messages

    def send_message(self, message: str, session_id: str) -> bool:
        """向指定群发送消息"""
        try:
            if not self.switch_to_group(session_id):
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
            logger.info(f"微信消息已发送到群 {session_id}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"发送微信消息失败: {e}")
            return False

class YtoHandler:
    def __init__(self):
        self.driver = None
        self.is_logged_in = False
        
    def init_browser(self):
        """初始化浏览器"""
        try:
            # 打开浏览器的调试端口
            # chrome --remote-debugging-port=9222

            # 连接到已打开的浏览器
            options = Options()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            driver = webdriver.Chrome(options=options)
            logger.info("浏览器初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化浏览器失败: {e}")
            return False
            
    def send_message(self, message: str) -> bool:
        """发送消息到圆通系统"""
        try:
            # # 找到消息输入框
            # 
            message_input = self.driver.find_element(By.ID, "edit-content")
            # 清除输入框，输入框不是input或textarea元素，而是div，contenteditable="true"
            message_input.send_keys(Keys.CONTROL + "a")  # 全选
            message_input.send_keys(Keys.DELETE) 
            # 输入消息
            message_input.send_keys(message)
            
            # # 点击发送按钮
            send_button = self.driver.find_element(By.ID, "button-violet")
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
            
            message_elements = self.driver.find_elements(By.CSS_SELECTOR, ".news-box")
            messages = []
            for elem in message_elements:
                try:

                    # 获取消息信息
                    first_div = elem.find_element(By.XPATH, "./div[1]")
                    sender_span = first_div.find_element(By.XPATH, "./span[1]") # 获取发送者
                    send_time_span = first_div.find_element(By.XPATH, "./span[2]") # 获取时间
                    script = "return arguments[0].innerText;"
                    send_time = self.driver.execute_script(script, send_time_span)
                    content = elem.find_element(By.CSS_SELECTOR, ".text-content").text

                    if(sender_span.text != "小圆-总公司"):
                        logger.info(f"收到来自 {sender_span.text} 的消息: {content}")
                        continue
                    
                    if content:
                        message = Message(
                            content=content,
                            source=MessageSource.YTO
                        )
                        messages.append(message)
                except Exception as e:
                    logger.error(f"获取消息失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"获取圆通消息失败: {e}")
            self.is_logged_in = False
            
        return messages


class MessageBridge:
    def __init__(self, redis_config=None):
        self.redis_queue = RedisQueue(**(redis_config or {}))
        self.wechat = WeChatHandler()
        self.yto = YtoHandler()
        self.order_manager = OrderManager()
        self.is_running = True
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 5  # 秒

    def init(self) -> bool:
        """初始化所有组件"""
        if not self.wechat.init_wx():
            return False
        if not self.yto.init_browser():
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
                        self.order_manager.register_order(order_number, msg.session_id)
                        logger.info(f"从群 {msg.session_id} 提取到订单号: {order_number}")
                    
                    # 将消息发送到圆通
                    if msg.content:
                        self.redis_queue.put_wechat_message(msg)
                                
                time.sleep(1)
            except Exception as e:
                logger.error(f"处理微信消息时出错: {e}")
                time.sleep(1)

    def process_yto_response(self, response_text: str):
        """处理圆通的回复消息"""
        try:
            # 从回复中提取订单号
            order_number = self.order_manager.extract_order_number(response_text)
            if order_number:
                # 查找对应的群
                session_id = self.order_manager.get_session_id(order_number)
                if session_id:
                    # 发送到对应的群
                    retry_count = 0
                    while retry_count < self.max_retries:
                        if self.wechat.send_message(response_text, session_id):
                            logger.info(f"圆通回复已转发到群 {session_id}")
                            break
                        retry_count += 1
                        if retry_count < self.max_retries:
                            time.sleep(self.retry_delay)
                    else:
                        logger.error(f"发送消息到群 {session_id} 失败，已达到最大重试次数")
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
                        if self.yto.send_message(wechat_message['content']):
                            break
                        retry_count += 1
                        if retry_count < self.max_retries:
                            time.sleep(self.retry_delay)
                    else:
                        logger.error("发送消息到圆通失败，已达到最大重试次数")

                # 处理圆通到微信的消息
                yto_messages = self.yto.get_messages()
                for msg in yto_messages:
                    self.process_yto_response(msg.content)

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
        # forward_thread.join()
        logger.info("程序已退出")

def main():

    logger.info("程序启动")

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