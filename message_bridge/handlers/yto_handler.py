from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from logger import logger
from models.message import Message
from models.message import MessageSource
from typing import Any, Optional, Dict, List
from models.redis_queue import RedisQueue
from collections import deque
import time
import re

class YtoHandler:
    def __init__(self):
        self.driver = None
        self.max_processed_count = 10
        self.buffer = deque(maxlen=self.max_processed_count)
        self.current_session_id = None
        self.redis_queue = RedisQueue()
        
    def init_browser(self):
        """初始化浏览器"""
        try:
            # 打开浏览器的调试端口
            # chrome --remote-debugging-port=9222

            # 连接到已打开的浏览器
            options = Options()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            self.driver = webdriver.Chrome(options=options)
            logger.info("浏览器初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化浏览器失败: {e}")
            return False
    def is_valid_message(self, msg: str) -> bool:
        """过滤消息"""
        # 过滤掉不符合规则的消息
        pattern = r".*YT\d{13,15}\s*(test).*"
        return re.match(pattern, msg) is not None
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
            # send_button = self.driver.find_element(By.ID, "button-violet")
            # send_button.click()
            
            logger.info(f"消息已发送到圆通系统: {message}")
            return True
            
        except Exception as e:
            logger.error(f"发送消息到圆通系统失败: {e}")
            self.is_logged_in = False  # 标记需要重新登录
            return False
    
    def try_get_message(self) -> Optional[str]:
        """尝试获取并处理消息，带重试机制"""
        try:
            
            message_elements = self.driver.find_elements(By.CSS_SELECTOR, ".news-box")

            #获取最后10条，避免数据过多
            last_news_message_elements = message_elements[-10:]

            for msg_item in last_news_message_elements:
                try:

                    # 获取消息信息
                    first_div = msg_item.find_element(By.XPATH, "./div[1]")
                    sender_span = first_div.find_element(By.XPATH, "./span[1]") # 获取发送者
                    send_time_span = first_div.find_element(By.XPATH, "./span[2]") # 获取时间
                    script = "return arguments[0].innerText;"
                    send_time = self.driver.execute_script(script, send_time_span)
                    msg_content = msg_item.find_element(By.CSS_SELECTOR, ".text-content").text

                    # if(sender_span.text != "小圆-总公司"):
                        # logger.info(f"收到来自 {sender_span.text} 的消息: {msg_content}")
                        # continue
                    
                    if self.is_valid_message(msg_content):
                        # 如果消息未处理过，添加到缓冲区
                        if msg_content and self.redis_queue.is_message_in_yto_processed_queue(msg_content) is False:
                            self.buffer.append(msg_content)
                            self.redis_queue.put_yto_processed_message(msg_content)
                            # self.current_session_id = session_id
                            logger.info(f"获取到yto消息: {msg_content}")
                            return True
                    

                except Exception as e:
                    logger.error(f"获取消息失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"获取圆通消息失败: {e}")
            self.is_logged_in = False
            
    def get_next_message(self) -> Optional[str]:
        """从缓冲区获取下一条要处理的消息"""
        if self.buffer:
            return self.buffer.popleft()
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
                if msg is None:
                    break
                print(f"处理消息: {msg}")
                message = Message(
                    content=msg,
                    source=MessageSource.YTO,
                    # session_id=self.current_session_id
                )
                messages.append(message)
        
        time.sleep(5)  # 适当的循环间隔

        return messages
