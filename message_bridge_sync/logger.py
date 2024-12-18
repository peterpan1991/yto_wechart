# logger.py
import logging
from datetime import datetime

# 获取当前日期并格式化为字符串
current_date = datetime.now().strftime("%Y-%m-%d")
log_file_name = f"logs/wechat_test_{current_date}.log"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_name, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)