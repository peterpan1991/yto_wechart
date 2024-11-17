from threading import Thread
from config import REDIS_CONFIG, MONITORED_GROUPS
from logger import logger
from models.redis_queue import RedisQueue
from handlers.wechat_handler import WeChatHandler
from handlers.yunda_handler import YundaHandler
from models.order_manager import OrderManager
import time

class MessageBridge:
    def __init__(self, redis_config=None):
        self.redis_queue = RedisQueue(**(redis_config or {}))
        self.wechat = WeChatHandler()
        self.yunda = YundaHandler()
        self.order_manager = OrderManager()
        self.is_running = True
        
        # 配置监控的群列表
        self.monitored_groups = [
            "pl",
            # "订单群1",
            # "订单群2",
            # "订单群3",            
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
                messages = self.wechat.get_messages()
                # for group_id in self.monitored_groups:
                #     if self.wechat.switch_to_group(group_id):
                #         messages = self.wechat.get_messages()
                #         for msg in messages:
                #             # 提取订单号并注册关联
                #             order_number = self.order_manager.extract_order_number(msg.content)
                #             if order_number:
                #                 self.order_manager.register_order(order_number, group_id)
                #                 logger.info(f"从群 {group_id} 提取到订单号: {order_number}")
                            
                #             # 将消息发送到圆通
                #             if msg.content:
                #                 self.redis_queue.put_wechat_message(msg)
                                
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
