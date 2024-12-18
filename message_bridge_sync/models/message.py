from enum import Enum
from datetime import datetime

class MessageSource(Enum):
    WECHAT = "wechat"
    YTO = "yto"

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"

class Message:
    def __init__(self, content: str, source: MessageSource, session_id: str = None, 
                 order_number: str = None, msg_type: MessageType = MessageType.TEXT):
        self.content = content
        self.source = source
        self.session_id = session_id
        self.order_number = order_number
        self.type = msg_type
        self.timestamp = datetime.now()

    def to_dict(self):
        return {
            'content': self.content,
            'source': self.source.value,
            'session_id': self.session_id,
            'order_number': self.order_number,
            'type': self.type.value,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            content=data['content'],
            source=MessageSource(data['source']),
            session_id=data['session_id'],
            order_number=data['order_number'],
            msg_type=MessageType(data['type'])
        )
