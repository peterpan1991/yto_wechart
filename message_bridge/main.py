from services.message_bridge import MessageBridge

def main():
    bridge = MessageBridge()
    bridge.run()

if __name__ == "__main__":
    main()