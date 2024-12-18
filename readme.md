## 功能

1. 监听微信消息，将微信消息过滤后存入消息队列，记录微信聊天id，订单号，消息内容；
2. 从消息队列取出消息，发送到圆通客服平台；
3. 监听圆通客服消息，将收到的圆通消息存入消息队列，记录订单号，消息内容；
4. 取出圆通消息，根据订单号匹配到对应的微信聊天id，发送消息；

## 问题

1. 当前在新窗口，快速收到两条消息，有一条会被吞掉
2. 需要开启显示群名称
3. 收到的消息如何跟群聊关联？
4. 重复发送相同消息的问题，是否需要过滤？1000条内会过滤。
5. 当初次获取时，因为没有已处理消息，会读取最后3条消息，可能导致消息重复。
6. 当打开圆通页面返回微信消息时，如何找到对应的群聊？遍历所有群聊？
7. 不同群同时收到消息，会不会造成消息混乱
8. 收到消息过滤掉圆通的用户名
9. 如果一个大群频繁收到消息，那么将始终收到这个群的消息

## 优化

1. 已处理消息存入redis，避免脚本重复执行导致数据消失。
2. 每个群设置一个消息队列。
3. 如果网页修改结构代码，需要判断元素是否存在，不存在发微信提醒，结束程序
4. 圆通需不需要选择群聊
5. 圆通和微信群聊的对应关系
6. 假设匹配到消息重量，圆通回复消息重量 100kg，微信又匹配到重量
7. 移除圆通消息中的@昵称

## 注意
1. 群不能以数字结尾
2. 监控群需加入配置文件
3. 微信需保持前台显示
4. 需两台服务器，一台接收微信消息，一台发送微信消息
5. 圆通0点会退出登录

## 运行

pip freeze > requirements.txt
