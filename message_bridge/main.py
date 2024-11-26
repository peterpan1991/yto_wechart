from services.message_bridge import MessageBridge

def main():
    # 打开浏览器的调试端口
    # chrome --remote-debugging-port=9222
    
    bridge = MessageBridge()
    bridge.run()

if __name__ == "__main__":
    main()