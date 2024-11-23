import re
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
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

#pip install undetected-chromedriver 绕过饭自动化监测
#pip install selenium

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
    YTO = "yto"

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
        self.yto_queue = 'yto_messages'

    def put_yto_message(self, message: Message):
        """将圆通消息放入队列"""
        try:
            self.redis_client.rpush(self.yto_queue, json.dumps(message.to_dict()))
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
        self.order_group_map: Dict[str, str] = {}
        # 群ID与订单号的反向映射
        self.group_orders_map: Dict[str, List[str]] = {}
        
    def extract_order_number(self, text: str) -> Optional[str]:
        """从文本中提取订单号"""
        # 支持多种订单号格式
        patterns = [
            r'YT\d{12}',  # 圆通订单号格式
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

class YtoHandler:
    def __init__(self):
        self.driver = None
        self.is_logged_in = False
        
    def init_browser(self):
        """初始化浏览器"""
        try:
            # chrome driver下载地址
            # https://googlechromelabs.github.io/chrome-for-testing/
            print("初始化浏览器...")

            chromedriver_path = "/usr/local/bin/chromedriver"
            service = Service(executable_path=chromedriver_path)
            # options = webdriver.ChromeOptions()
            # options.add_argument('--headless')  # 无头模式
            self.driver = webdriver.Chrome(service=service)                        
                                    
            logger.info("浏览器初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化浏览器失败: {e}")
            return False
            
    def login(self):
        """登录圆通系统"""
        try:
            # self.driver.get("https://kh.yto.net.cn/new/home")  # 替换为实际登录地址
            self.driver.get("https://online.yto.net.cn/#/")
            
            print(f"页面加载中...")

            # 等待登录页面加载
            # WebDriverWait(self.driver, 10).until(
            #     EC.presence_of_element_located((By.ID, "username"))
            # )
            
            # # 输入用户名密码
            # username = self.driver.find_element(By.ID, "username")
            # password = self.driver.find_element(By.ID, "password")
            
            # username.send_keys("your_username")  # 替换为实际用户名
            # password.send_keys("your_password")  # 替换为实际密码
            
            # # 点击登录按钮
            # login_button = self.driver.find_element(By.ID, "login-button")
            # login_button.click()
            
            # # 等待登录成功
            # WebDriverWait(self.driver, 10).until(
            #     EC.presence_of_element_located((By.ID, "dashboard"))
            # )
            
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
            
            # # 找到消息输入框
            # message_input = self.driver.find_element(By.ID, "message-input")
            # message_input.clear()
            # message_input.send_keys(message)
            
            # # 点击发送按钮
            # send_button = self.driver.find_element(By.ID, "send-button")
            # send_button.click()
            
            # logger.info(f"消息已发送到圆通系统: {message}")
            # return True
            
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
            
            print(f"获取圆通消息中...")

            # 等待消息列表加载
            message_elements = WebDriverWait(self.driver, 5).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "message-item"))
            )
            
            for element in message_elements:
                content = element.text
                if content:
                    message = Message(
                        content=content,
                        source=MessageSource.YTO
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
        self.yto = YtoHandler()
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
        if not self.yto.init_browser():
            return False
        return True

    def process_yto_response(self, response_text: str):
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
                # # 处理微信到圆通的消息
                # wechat_message = self.redis_queue.get_wechat_message()
                # if wechat_message:
                #     retry_count = 0
                #     while retry_count < self.max_retries:
                #         if self.yto.send_message(wechat_message['content']):
                #             break
                #         retry_count += 1
                #         if retry_count < self.max_retries:
                #             time.sleep(self.retry_delay)
                #     else:
                #         logger.error("发送消息到圆通失败，已达到最大重试次数")

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
        forward_thread = Thread(target=self.forward_messages)

        forward_thread.start()

        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("接收到退出信号，正在关闭...")
            self.is_running = False

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
    
    # bridge = MessageBridge(redis_config)
    # bridge.run()
    try:
        
        # mac
        # chromedriver_path = "/usr/local/bin/chromedriver"
        # service = Service(executable_path=chromedriver_path)
        # driver = webdriver.Chrome(service=service)

        # windows
        # driver = webdriver.Chrome()
        # driver.get("https://kh.yto.net.cn/new/home")
        # time.sleep(10)

        # 打开浏览器的调试端口
        # chrome --remote-debugging-port=9222

        # 连接到已打开的浏览器
        options = Options()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=options)

        message_elements = driver.find_elements(By.CSS_SELECTOR, ".news-box")
        messages = []
        for elem in message_elements:
            try:

                # 获取消息信息
                # msg_type = "service" if "service-message" in elem.get_attribute("class") else "user"
                # name = elem.find_element(By.XPATH, "//*[text()='小圆-总公司']")
                first_div = elem.find_element(By.XPATH, "./div[1]")
                first_span = first_div.find_element(By.XPATH, "./span[1]") # 获取发送者
                second_span = first_div.find_element(By.XPATH, "./span[2]") # 获取时间

                script = "return arguments[0].innerText;"
                span_text = driver.execute_script(script, second_span)

                print("name:", first_span.text, span_text)
                text = elem.find_element(By.CSS_SELECTOR, ".text-content").text
                time_str = elem.find_element(By.CSS_SELECTOR, ".send-time").text
                
                if text:
                    messages.append({
                        "name": first_span.text,
                        "text": text,
                        "time": span_text
                    })
            except Exception as e:
                logger.error(f"获取消息失败: {e}")
                continue
        
        # 打印最后一条消息
        if messages:
            last_message = messages[-3]
            print(f"最后一条消息：{last_message['name']}, {last_message['text']}, 时间: {last_message['time']}")
        else:
            print("没有获取到任何消息")

        exit()

        while True:
            # 获取消息元素
            print("get message...")
            message_elements = driver.find_elements(By.CSS_SELECTOR, ".news-box")

            print("message_elements", message_elements)
            
            messages = []
            for elem in message_elements:
                try:
                    # 获取消息信息
                    # msg_type = "service" if "service-message" in elem.get_attribute("class") else "user"
                    text = elem.find_element(By.CSS_SELECTOR, ".text-content").text
                    time_str = elem.find_element(By.CSS_SELECTOR, ".send-time").text
                    
                    print("获取到的消息：", text, time_str, text.script())
                    # if text.strip():
                    #     messages.append({
                    #         "type": msg_type,
                    #         "text": text,
                    #         "time": time_str,
                    #         "timestamp": datetime.now().timestamp()
                    #     })
                except Exception:
                    continue
            time.sleep(10)

        # 等待扫码完成

        # 等待页面加载完成
        # WebDriverWait(driver, 10).until(
        #     EC.presence_of_element_located((By.ID, "imLayout"))
        # )
        # while True:
        #     time.sleep(5)



    except Exception as e:
        logger.error(f"chromedriver启动失败: {e}")
        return False

    print("页面加载完成...")
    



if __name__ == "__main__":
    main()