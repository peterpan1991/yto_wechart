from enum import Enum
from datetime import datetime

class MessageSource(Enum):
    WECHAT = "wechat"
    YUNDA = "yunda"

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"

class Message:
    def __init__(self, content, source, group_id=None, order_number=None, msg_type=MessageType.TEXT):
        self.content = content
        self.source = source
        self.group_id = group_id
        self.order_number = order_number
        self.type = msg_type
        self.timestamp = datetime.now()

    def to_dict(self):
        return {
            'content': self.content,
            'source': self.source.value,
            'group_id': self.group_id,
            'order_number': self.order_number,
            'type': self.type.value,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            content=data['content'],
            source=MessageSource(data['source']),
            group_id=data.get('group_id'),
            order_number=data.get('order_number'),
            msg_type=MessageType(data['type'])
        )