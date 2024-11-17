import uiautomation as automation
from collections import deque
from typing import Optional
import time

class MessageBuffer:
    def __init__(self, max_size=10):
        self.buffer = deque(maxlen=max_size)
        self.processed_messages = set()
        self.max_retries = 3
        self.retry_delay = 0.5

    def try_get_message(self, wechat_window) -> Optional[str]:
        """尝试获取并处理消息，带重试机制"""
        for _ in range(self.max_retries):
            try:
                msg_list = wechat_window.ListControl(Name='消息')
                if msg_list.Exists():
                    children = msg_list.GetChildren()
                    if children:
                        # 获取最后几条消息
                        latest_messages = children[-3:]  # 可以调整获取的消息数量
                        for msg_item in latest_messages:
                            msg_content = msg_item.Name
                            # 如果消息未处理过，添加到缓冲区
                            if msg_content and msg_content not in self.processed_messages:
                                self.buffer.append(msg_content)
                                self.processed_messages.add(msg_content)
                                
                        # 为防止集合无限增长，限制处理过的消息记录数量
                        if len(self.processed_messages) > 1000:
                            self.processed_messages.clear()
                            
                return True
            except Exception as e:
                print(f"获取消息失败，重试中: {e}")
                time.sleep(self.retry_delay)
        return False

    def get_next_message(self) -> Optional[str]:
        """从缓冲区获取下一条要处理的消息"""
        return self.buffer.popleft() if self.buffer else None

# 使用示例
def main():
    message_buffer = MessageBuffer()

    # 找到微信窗口
    wechat_window = automation.WindowControl(Name="微信")
    if not wechat_window.Exists():
        print("微信窗口未找到，请确保微信已运行")
        exit()

    wechat_window.SetActive()  # 激活微信窗口
    hw = wechat_window.ListControl(Name="会话")

    while True:
        try:
            we = hw.TextControl(searchDepth=3)
            retry_count = 0
            max_retries = 3
            
            # 带重试的等待控件出现
            while not we.Exists() and retry_count < max_retries:
                time.sleep(0.2)
                retry_count += 1
            
            if we.Exists():
                print(f"we: {we.Name}")
                wechat_window.SetActive()
                we.Click(simulateMove=False)
                
                # 尝试获取新消息
                if message_buffer.try_get_message(wechat_window):
                    # 处理缓冲区中的所有消息
                    while True:
                        msg = message_buffer.get_next_message()
                        if msg is None:
                            break
                        print(f"处理消息: {msg}")
                
            else:
                print("控件未找到，继续下一次循环")
            
            time.sleep(0.5)  # 适当的循环间隔
            
        except Exception as e:
            print(f"发生错误: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()

# 找到微信窗口
# wechat_window = automation.WindowControl(Name="微信")
# if not wechat_window.Exists():
#     print("微信窗口未找到，请确保微信已运行")
#     exit()

# wechat_window.SetActive()  # 激活微信窗口

# 打印控件层次结构
# print("微信控件层次结构:")
# automation.WalkControl(wechat_window, depth=10)

# for child in wechat_window.ListControl(Name="会话").GetChildren():
#     print(f"控件类型: {child.ControlType}, 控件名称: {child.Name}")

# # for child in wechat_window.ListControl(Name="消息").GetChildren():
# #     print(f"控件类型: {child.ControlType}, 控件名称: {child.Name}, child: {child}")

# firstItem = wechat_window.ListControl(Name="会话").GetChildren()[0]
# print(f"第一条：{firstItem.Name}")

# thirdItem = wechat_window.ListControl(Name="会话").GetChildren()[2]
# print(f"第三条：{thirdItem.Name}")
# thirdItem.Click(simulateMove=False)

# hw = wechat_window.ListControl(Name="会话")

# while True:
#     we = hw.TextControl(searchDepth=3)
#     while not we.Exists():
#         pass
#     print(f"we: {we.Name}")
#     wechat_window.SetActive()
#     we.Click(simulateMove=False)
#     # 读取最后一条消息
#     last_msg = wechat_window.ListControl(Name='消息').GetChildren()[-1].Name
#     print(f"last msg: {last_msg}")
#     # firstItem.Click(simulateMove=False)
#     time.sleep(2)