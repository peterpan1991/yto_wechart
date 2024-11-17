import uiautomation as auto
import time
import logging
from queue import PriorityQueue
from threading import Thread
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class MessagePriority(Enum):
    HIGH = 1    # 紧急消息
    NORMAL = 2  # 普通消息
    LOW = 3     # 低优先级消息

@dataclass
class Message:
    content: str                        # 消息内容
    priority: MessagePriority          # 消息优先级
    recipient: str = ""                # 接收者
    retry_count: int = 3               # 重试次数
    timestamp: float = time.time()     # 时间戳

class MessageQueue:
    def __init__(self):
        self.queue = PriorityQueue()
        self.is_running = True
        self.message_cache = set()
        self.min_interval = 2  # 最小发送间隔(秒)

    def add_message(self, message: str, priority: MessagePriority = MessagePriority.NORMAL, recipient: str = ""):
        """添加消息到队列"""
        # 消息去重
        if message in self.message_cache:
            return
            
        msg = Message(content=message, priority=priority, recipient=recipient)
        self.queue.put((priority.value, msg))
        self.message_cache.add(message)
        
        # 缓存清理
        if len(self.message_cache) > 1000:
            self.message_cache.clear()

    def process_messages(self, bot: 'WeChatBot'):
        """处理消息队列"""
        while self.is_running:
            try:
                # 获取优先级最高的消息
                priority, msg = self.queue.get(timeout=1)
                
                # 重试机制
                while msg.retry_count > 0:
                    try:
                        if bot.send_message(msg.content):
                            logger.info(f"消息发送成功: {msg.content}")
                            break
                        msg.retry_count -= 1
                        time.sleep(1)
                    except Exception as e:
                        logger.error(f"发送失败: {e}")
                        msg.retry_count -= 1
                        if msg.retry_count <= 0:
                            logger.error(f"消息发送失败，已达到最大重试次数: {msg.content}")
                
                # 控制发送频率
                time.sleep(self.min_interval)
                
            except Exception as e:
                if not isinstance(e, TimeoutError):
                    logger.error(f"消息处理错误: {e}")
                time.sleep(0.1)

    def stop(self):
        """停止消息队列处理"""
        self.is_running = False

class WeChatBot:
    def __init__(self):
        self.wx = None
        self.last_message = ""
        self.message_queue = MessageQueue()
        self.queue_thread = None
        
    def init_wx(self):
        """初始化微信窗口"""
        self.wx = auto.WindowControl(Name="微信", ClassName="WeChatMainWndForPC")
        if not self.wx.Exists():
            logger.error("请先打开微信!")
            return False
        return True
    
    def get_messages(self):
        """获取当前聊天窗口的最新消息"""
        try:
            message_list = self.wx.ListControl(Name="消息")
            if message_list.Exists():
                last_item = message_list.GetChildren()[-1]
                message_text = last_item.Name
                return message_text
        except Exception as e:
            logger.error(f"获取消息失败: {str(e)}")
        return None

    def send_message(self, message):
        """发送消息"""
        try:
            edit_box = self.wx.EditControl(Name="输入")
            if edit_box.Exists():
                edit_box.SetValue(message)
                send_button = self.wx.ButtonControl(Name="发送(S)")
                if send_button.Exists():
                    send_button.Click()
                    return True
        except Exception as e:
            logger.error(f"发送消息失败: {str(e)}")
        return False

    def analyze_message(self, message: str) -> MessagePriority:
        """分析消息优先级"""
        if any(keyword in message for keyword in ["紧急", "急", "important"]):
            return MessagePriority.HIGH
        if any(keyword in message for keyword in ["请问", "咨询"]):
            return MessagePriority.NORMAL
        return MessagePriority.LOW

    def generate_reply(self, message: str, priority: MessagePriority) -> str:
        """根据消息优先级生成回复"""
        if priority == MessagePriority.HIGH:
            return "我现在有事不在，如果紧急请拨打: 10086 [自动回复]"
        elif priority == MessagePriority.NORMAL:
            return "您好，我现在不在，稍后回复您。[自动回复]"
        else:
            return "我已收到消息，稍后回复。[自动回复]"

    def start_queue_processing(self):
        """启动消息队列处理线程"""
        self.queue_thread = Thread(target=self.message_queue.process_messages, args=(self,))
        self.queue_thread.daemon = True
        self.queue_thread.start()

    def run(self):
        """主运行循环"""
        if not self.init_wx():
            return

        logger.info("微信自动回复已启动...")
        self.start_queue_processing()
        
        try:
            while True:
                new_message = self.get_messages()
                
                if new_message and new_message != self.last_message:
                    logger.info(f"收到新消息: {new_message}")
                    
                    # 分析消息优先级
                    priority = self.analyze_message(new_message)
                    
                    # 生成回复
                    reply = self.generate_reply(new_message, priority)
                    
                    # 添加到消息队列
                    self.message_queue.add_message(reply, priority)
                    
                    self.last_message = new_message
                    
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("正在停止程序...")
            self.message_queue.stop()
            if self.queue_thread:
                self.queue_thread.join()
            logger.info("程序已停止")
        except Exception as e:
            logger.error(f"运行错误: {str(e)}")

def main():
    bot = WeChatBot()
    bot.run()

if __name__ == "__main__":
    main()