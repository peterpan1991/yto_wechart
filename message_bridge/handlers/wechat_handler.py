from datetime import datetime
from logger import logger
import uiautomation as auto
import time
# from enum import Enum, auto
from typing import Any, Optional, Dict, List
from models.message import Message
from models.message import MessageSource
from models.redis_queue import RedisQueue
from collections import deque
import re
from config import CUSTOME_SERVICE_PATTERNS, WECHAT_MESSAGE_FORMATS, MONITORED_GROUPS

class WeChatHandler:
    def __init__(self):
        self.wx = None
        self.last_messages: Dict[str, str] = {}
        self.current_session_id = None
        self.group_cache: Dict[str, auto.WindowControl] = {}
        self.max_retries = 3
        self.retry_delay = 0.5
        self.buffer = {}
        self.max_processed_count = 10
        self.new_message = None
        self.last_message_count = 3
        self.monitoring_groups: Dict[str, str] = {}
        self.redis_queue = RedisQueue()
        
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
            monitored_groups = MONITORED_GROUPS
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
            # if self.current_session_id == session_id:
            #     return True

            if session_id in self.group_cache:
                group_item = self.group_cache[session_id]
                if not group_item.Exists():
                    del self.group_cache[session_id]
                else:
                    group_item.Click(simulateMove=False)
                    self.current_session_id = session_id
                    time.sleep(0.2)
                    return True
            
        except Exception as e:
            logger.error(f"切换会话失败: {e}")
            return False

    def is_valid_message(self, msg: str) -> bool:
        """过滤消息"""
        # 过滤掉不符合规则的消息
        patterns = WECHAT_MESSAGE_FORMATS
        for pattern in patterns:
            match = re.search(pattern, msg, re.DOTALL)
            if match:
                return True
        return False

    def is_customer(self, name: str) -> bool:
        """判断是否自己"""
        if not name:
            return False

        """判断是否是客服"""
        patterns = CUSTOME_SERVICE_PATTERNS
        for pattern in patterns:
            match = re.search(pattern, name, re.DOTALL)
            if match:
                return False
        return True

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
                                        sender_name = msg_item.TextControl().Name
                                        # 过滤圆通客服
                                        print(f"发送人: {msg_item.TextControl().Name}")
                                        print(f"收到消息: {msg_item.Name}")
                                        if self.is_valid_message(msg_item.Name) and self.is_customer(sender_name):
                                            msg_content = msg_item.Name
                                            # 如果消息未处理过，添加到缓冲区
                                            if msg_content and self.redis_queue.is_message_in_wechat_processed_queue(msg_content, session_id) is False:
                                                self.buffer[session_id].append(msg_content)
                                                self.redis_queue.put_wechat_processed_message(msg_content, session_id)
                                                self.current_session_id = session_id
                                                is_processed = True
                                    
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
                if msg is None:
                    break
                print(f"处理yto消息: {msg}")
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
            if not self.switch_to_session(session_id):
                return False
            
            self.wx.SendKeys(message+'{Enter}', waitTime=1)

            # edit_box = self.wx.EditControl(Name="输入")
            # if not edit_box.Exists():
            #     logger.error("找不到输入框")
            #     return False
                
            # edit_box.SetValue(message)
            time.sleep(0.1)
            
            # send_button = self.wx.ButtonControl(Name="发送(S)")
            # if not send_button.Exists():
            #     logger.error("找不到发送按钮")
            #     return False
                
            # send_button.Click()
            logger.info(f"微信消息已发送到群 {session_id}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"发送微信消息失败: {e}")
            return False