from datetime import datetime
from logger import logger
import uiautomation as auto
import time
# from enum import Enum, auto
from typing import Any, Optional, Dict, List
from models.message import Message
from models.message import MessageSource

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

        hw = self.wx.ListControl(Name='会话')
        we = hw.TextControl(searchDepth=4)

        # 死循环维持，没有超时报错
        while not we.Exists():
            pass
        
        messages = []
        # 存在未读消息
        if we.Name:
            # 点击未读消息
            we.Click(simulateMove=False)
            try:
                message_list = self.wx.ListControl(Name="消息")
                
                if message_list.Exists():
                    items = message_list.GetChildren()
                    # 只获取最后一条消息
                    if items:
                        last_item = items[-1]
                        print(last_item)
                        content = last_item.Name
                        if content:
                            try:
                                message = Message(
                                    content=content,
                                    source=MessageSource.WECHAT,
                                    group_id=self.current_group_id
                                )
                                messages.append(message)
                            except Exception as e:
                                # 如果无法获取时间信息，则直接添加消息
                                message = Message(
                                    content=content,
                                    source=MessageSource.WECHAT,
                                    group_id=self.current_group_id
                                )
                                messages.append(message)
                        
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
