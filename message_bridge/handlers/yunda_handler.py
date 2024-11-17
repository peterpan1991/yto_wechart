from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from logger import logger
from models.message import Message
from models.message import MessageSource
from typing import Any, Optional, Dict, List

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
