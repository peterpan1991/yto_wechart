import uiautomation as auto
import time
import logging
import redis
import json
from datetime import datetime
from threading import Thread
from enum import Enum, auto
from typing import Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MessageSource(Enum):
    WECHAT = "wechat"
    YUNDA = "yunda"

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"

class Message:
    def __init__(self, content: str, source: MessageSource, msg_type: MessageType = MessageType.TEXT):
        self.content = content
        self.source = source
        self.type = msg_type
        self.timestamp = datetime.now()

class RedisQueue:
    def __init__(self, name='message_queue', **redis_kwargs):
        default_kwargs = {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'password': None,
            'decode_responses': True
        }
        redis_kwargs = {**default_kwargs, **redis_kwargs}
        
        self.redis = redis.Redis(**redis_kwargs)
        self.wechat_to_yunda_key = f"queue:wechat_to_yunda"
        self.yunda_to_wechat_key = f"queue:yunda_to_wechat"
        
    def put_wechat_message(self, message: Message) -> bool:
        try:
            message_data = {
                'content': message.content,
                'type': message.type.value,
                'timestamp': message.timestamp.isoformat()
            }
            self.redis.lpush(self.wechat_to_yunda_key, json.dumps(message_data))
            return True
        except Exception as e:
            logger.error(f"添加微信消息到队列失败: {e}")
            return False

    def put_yunda_message(self, message: Message) -> bool:
        try:
            message_data = {
                'content': message.content,
                'type': message.type.value,
                'timestamp': message.timestamp.isoformat()
            }
            self.redis.lpush(self.yunda_to_wechat_key, json.dumps(message_data))
            return True
        except Exception as e:
            logger.error(f"添加圆通消息到队列失败: {e}")
            return False

    def get_wechat_message(self) -> Optional[dict]:
        try:
            message = self.redis.brpop(self.wechat_to_yunda_key, timeout=1)
            if message:
                return json.loads(message[1])
            return None
        except Exception as e:
            logger.error(f"获取微信消息失败: {e}")
            return None

    def get_yunda_message(self) -> Optional[dict]:
        try:
            message = self.redis.brpop(self.yunda_to_wechat_key, timeout=1)
            if message:
                return json.loads(message[1])
            return None
        except Exception as e:
            logger.error(f"获取圆通消息失败: {e}")
            return None

class WeChatHandler:
    def __init__(self):
        self.wx = None
        self.last_message = ""
        
    def init_wx(self) -> bool:
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

    def get_messages(self) -> Optional[str]:
        try:
            message_list = self.wx.ListControl(Name="消息")
            if message_list.Exists():
                last_item = message_list.GetChildren()[-1]
                return last_item.Name
        except Exception as e:
            logger.error(f"获取微信消息失败: {e}")
        return None

    def send_message(self, message: str) -> bool:
        try:
            edit_box = self.wx.EditControl(Name="输入")
            if edit_box.Exists():
                edit_box.SetValue(message)
                time.sleep(0.1)
                send_button = self.wx.ButtonControl(Name="发送(S)")
                if send_button.Exists():
                    send_button.Click()
                    logger.info(f"微信消息已发送: {message}")
                    return True
        except Exception as e:
            logger.error(f"发送微信消息失败: {e}")
        return False

class YundaHandler:
    def __init__(self):
        self.driver = None
        self.last_message = ""
        
    def init_browser(self):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')  # 无头模式
            self.driver = webdriver.Chrome(options=options)
            self.driver.get("https://kf.yto.net.cn/")  # 圆通智能客服页面URL
            logger.info("圆通客服页面初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化圆通客服页面失败: {e}")
            return False

    def get_messages(self) -> Optional[str]:
        try:
            # 等待消息元素出现
            message_elements = WebDriverWait(self.driver, 5).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "message-content"))
            )
            if message_elements:
                last_message = message_elements[-1].text
                return last_message
        except TimeoutException:
            return None
        except Exception as e:
            logger.error(f"获取圆通消息失败: {e}")
        return None

    def send_message(self, message: str) -> bool:
        try:
            # 定位输入框和发送按钮
            input_box = self.driver.find_element(By.ID, "chatInput")
            send_button = self.driver.find_element(By.ID, "sendBtn")
            
            # 输入消息并发送
            input_box.clear()
            input_box.send_keys(message)
            send_button.click()
            
            logger.info(f"圆通消息已发送: {message}")
            return True
        except Exception as e:
            logger.error(f"发送圆通消息失败: {e}")
            return False

class MessageBridge:
    def __init__(self, redis_config=None):
        self.redis_queue = RedisQueue(**(redis_config or {}))
        self.wechat = WeChatHandler()
        self.yunda = YundaHandler()
        self.is_running = True
        
    def init(self) -> bool:
        if not self.wechat.init_wx():
            return False
        if not self.yunda.init_browser():
            return False
        return True

    def process_wechat_messages(self):
        """处理微信消息的线程"""
        while self.is_running:
            try:
                new_message = self.wechat.get_messages()
                if new_message and new_message != self.wechat.last_message:
                    logger.info(f"收到微信消息: {new_message}")
                    message = Message(new_message, MessageSource.WECHAT)
                    self.redis_queue.put_wechat_message(message)
                    self.wechat.last_message = new_message
                time.sleep(1)
            except Exception as e:
                logger.error(f"处理微信消息时出错: {e}")
                time.sleep(1)

    def process_yunda_messages(self):
        """处理圆通消息的线程"""
        while self.is_running:
            try:
                new_message = self.yunda.get_messages()
                if new_message and new_message != self.yunda.last_message:
                    logger.info(f"收到圆通消息: {new_message}")
                    message = Message(new_message, MessageSource.YUNDA)
                    self.redis_queue.put_yunda_message(message)
                    self.yunda.last_message = new_message
                time.sleep(1)
            except Exception as e:
                logger.error(f"处理圆通消息时出错: {e}")
                time.sleep(1)

    def forward_messages(self):
        """转发消息的线程"""
        while self.is_running:
            try:
                # 处理微信到圆通的消息
                wechat_message = self.redis_queue.get_wechat_message()
                if wechat_message:
                    self.yunda.send_message(wechat_message['content'])

                # 处理圆通到微信的消息
                yunda_message = self.redis_queue.get_yunda_message()
                if yunda_message:
                    self.wechat.send_message(yunda_message['content'])

                time.sleep(0.5)
            except Exception as e:
                logger.error(f"转发消息时出错: {e}")
                time.sleep(1)

    def run(self):
        """运行消息桥接系统"""
        if not self.init():
            return

        logger.info("消息桥接系统启动...")

        # 启动处理线程
        wechat_thread = Thread(target=self.process_wechat_messages)
        yunda_thread = Thread(target=self.process_yunda_messages)
        forward_thread = Thread(target=self.forward_messages)

        wechat_thread.daemon = True
        yunda_thread.daemon = True
        forward_thread.daemon = True

        wechat_thread.start()
        yunda_thread.start()
        forward_thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("正在停止系统...")
            self.is_running = False
            wechat_thread.join()
            yunda_thread.join()
            forward_thread.join()
            if self.yunda.driver:
                self.yunda.driver.quit()
            logger.info("系统已停止")

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