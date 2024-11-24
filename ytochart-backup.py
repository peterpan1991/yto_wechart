import numpy as np
import pandas as pd
import uiautomation as automation
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import requests

#绑定微信主窗口
wx = automation.WindowControl(Name='微信', searchDepth=1) #searchDepth=1参数指定在查找窗口时搜索直接子级窗口

#切换窗口
wx.ListControl()
wx.SwitchToThisWindow() #ListControl()方法用于列出所有子级窗口，而SwitchToThisWindow()方法则将焦点切换到微信主窗口
#寻找会话控件绑定
hw=wx.ListControl(Name='会话')
#通过pd读取数据
df=pd.read_csv('./yto_wechart/回复数据.csv', encoding='utf-8')
print(df)

# driver = webdriver.Chrome()
# #打开圆通客服
# driver.get("https://online.yto.net.cn/#/")
# time.sleep(1)

while True:
    # 从查找未读消息
    we = hw.TextControl(searchDepth=4)

    # 死循环维持，没有超时报错
    while not we.Exists():
        pass

    # 存在未读消息
    if we.Name:
        # 点击未读消息
        we.Click(simulateMove=False)

        wx.TextControl(SubName="yto-test").RightClick()
        exit()

        # 读取最后一条消息
        last_msg = wx.ListControl(Name='消息').GetChildren()[-1].Name

        # input_element = driver.find_element(By.CLASS_NAME, 'textarea')
        # if(input_element):
        #     init_msgs = driver.find_elements(By.CLASS_NAME, "top-center")
        #     input_element.send_keys(last_msg, Keys.ENTER)
        #     time.sleep(3)
        #     current_msgs = driver.find_elements(By.CLASS_NAME, "top-center")
        #     for index,msg in enumerate(current_msgs):
        #         if msg not in init_msgs and index > len(init_msgs):
        #             print("text:", msg.text)

        # # 判断关键字
        msg = df.apply(lambda x: x['回复内容'] if x['关键词'] in last_msg else None, axis=1)
        # # 数据筛选，移除空数据
        msg.dropna(axis=0, how='any', inplace=True)
        # # 做成列表
        ar = np.array(msg).tolist()
        # # 能够匹配到数据时
        print(f"test: {ar[0][:5]}")
        if ar:
            # 将数据输入
            # 替换换行符号
            # wx.SendKeys(ar[0]+'{Enter}', waitTime=1)
            # 通过消息匹配检索会话栏的联系人
            wx.TextControl(SubName="yto-test").RightClick()
        # 没有匹配到数据时
        else:
            pass

    time.sleep(10)