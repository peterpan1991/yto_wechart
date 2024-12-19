import random
import re
from threading import Thread
from config import REDIS_CONFIG, MONITORED_GROUPS, PROCESS_TYPE
from logger import logger
from models.redis_queue import RedisQueue
from handlers.wechat_handler import WeChatHandler
from handlers.yto_handler import YtoHandler
from models.order_manager import OrderManager
import time

class MessageBridge:
    def __init__(self):
        self.redis_queue = RedisQueue()
        self.wechat = WeChatHandler(self.redis_queue)
        self.yto = YtoHandler(self.redis_queue)
        self.order_manager = OrderManager(self.redis_queue)
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
                    order_numbers = self.order_manager.extract_order_number(msg.content)
                    if order_numbers:
                        self.order_manager.register_order(order_numbers, msg.session_id)
                        logger.info(f"从群 {msg.session_id} 提取到订单号: {order_numbers}")
                    
                    # 将消息存储到redis
                    if msg.content:
                        # self.redis_queue.put_wechat_message(msg)
                        # wechat_message = self.redis_queue.get_wechat_message()
                        self.yto.send_message(msg.content)
                    
                    time.sleep(random.uniform(3.5, 5.5))
                                
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"处理微信消息时出错: {e}")
                self.is_running = False
    
    def process_yto_messages(self):
        """处理圆通消息的线程"""
        while self.is_running:
            try:
                messages = self.yto.get_messages()
                for msg in messages:
                    # 将消息存储到redis
                    if msg.content:
                        self.redis_queue.put_yto_message(msg)
                                
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"处理微信消息时出错: {e}")
                self.is_running = False

    def process_yto_response(self, response_text: str):
        """处理圆通的回复消息"""
        try:
            # 从回复中提取订单号
            order_numbers = self.order_manager.extract_order_number(response_text)
            if order_numbers:
                # 查找对应的群
                session_id = self.order_manager.get_session_id(order_numbers[0])
                if session_id:
                    # 发送到对应的群
                    self.wechat.send_message(response_text, session_id)
                else:
                    logger.warning(f"找不到订单 {order_numbers[0]} 对应的群")
            else:
                logger.warning(f"圆通回复中没有找到订单号: {response_text}")
        except Exception as e:
            logger.error(f"处理圆通回复时出错: {e}")
            self.is_running = False

    def forward_messages(self):
        """转发消息的线程"""
        while self.is_running:
            try:
                if PROCESS_TYPE == "message_bridge" or PROCESS_TYPE == "wechat_recieve":
                    # 处理微信到圆通的消息
                    wechat_message = self.redis_queue.get_wechat_message()
                    if wechat_message:
                        self.yto.send_message(wechat_message['content'])
                    
                    time.sleep(random.uniform(3.5, 5.5))
                
                if PROCESS_TYPE == "message_bridge" or PROCESS_TYPE == "wechat_send":
                    # 处理圆通到微信的消息
                    yto_messages = self.redis_queue.get_yto_message()
                    if yto_messages:
                        self.process_yto_response(yto_messages['content'])

                    time.sleep(random.uniform(3.5, 5.5))
            except Exception as e:
                logger.error(f"转发消息时出错: {e}")
                self.is_running = False
                
    def process(self):
        while self.is_running:
            try:
                groups = self.wechat.get_groups_to_handle()
                if not groups:
                    # logger.warning("没有需要处理的群")
                    time.sleep(1)
                    continue

                for id, group in groups.items():
                    group_name = re.sub(r'\d+条新消息$', '', group.Name)
                    logger.info(f"处理群: {group.Name}, {id}")
                    wechat_messages = self.wechat.handle_group_message(id, group)
                    for msg in wechat_messages:
                        if not msg.content:
                            continue
                        
                        # 提取订单号并注册关联
                        order_numbers = self.order_manager.extract_order_number(msg.content)
                        if not order_numbers:
                            continue
                        
                        self.order_manager.register_order(order_numbers, msg.session_id)
                        logger.info(f"从群 {msg.session_id} 提取到订单号: {order_numbers}")
                        
                        # 发送消息到圆通
                        self.yto.send_message(msg.content)

                        # 获取圆通消息
                        order_count = len(order_numbers)
                        retry_count = 0
                        send_times = 0
                        max_while_times = 30
                        while_times = 0
                        while True:
                            while_times += 1
                            time.sleep(random.uniform(0.5, 1))
                            yto_messages = self.yto.handle_yto_message()
                            is_send = False
                            for yto_msg in yto_messages:
                                if not yto_msg.content:
                                    continue

                                yto_order_numbers = self.order_manager.extract_order_number(yto_msg.content)
                                if not yto_order_numbers or yto_order_numbers[0] not in order_numbers:
                                    continue

                                # 将消息发送到微信
                                self.wechat.send_message(yto_msg.content, msg.session_id, group_name)
                                is_send = True
                                send_times += 1
                                time.sleep(random.uniform(1, 2))

                            if not is_send:
                                retry_count += 1
                            
                            logger.info(f"获取圆通消息循环次数: {retry_count}, 发送次数: {send_times}")

                            if retry_count >= self.max_retries or send_times >= order_count:
                                break
                                
                            if while_times >= max_while_times:
                                break

                    time.sleep(random.uniform(1, 2))
                time.sleep(random.uniform(1, 2))
            except Exception as e:
                logger.error(f"执行出错: {e}")
                self.is_running = False

    def run(self):

        """运行消息桥接服务"""
        if not self.init():
            logger.error("初始化失败，程序退出")
            return

        time.sleep(10)

        # 启动处理线程
        process_thread = Thread(target=self.process)
        process_thread.start()

        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("接收到退出信号，正在关闭...")
            self.is_running = False

        process_thread.join()

        logger.info("程序已退出")

