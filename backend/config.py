import os
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 统一配置环境变量默认值
CONFIG = {
    "BAILIAN_API_KEY": os.getenv("BAILIAN_API_KEY", "YOUR_API_KEY"),
    "BAILIAN_APP_ID": os.getenv("BAILIAN_APP_ID", "YOUR_APP_ID"),
    "BAILIAN_BASE_API_URL": os.getenv("BAILIAN_API_URL", "https://dashscope.aliyuncs.com/api/v1/apps"),
    "FASTAPI_HOST": os.getenv("FASTAPI_HOST", "0.0.0.0"),
    "FASTAPI_PORT": int(os.getenv("FASTAPI_PORT", 8000)),
}

# 检查必要的环境变量是否已设置
def check_env_vars():
    if CONFIG["BAILIAN_API_KEY"] == "YOUR_API_KEY" or CONFIG["BAILIAN_APP_ID"] == "YOUR_APP_ID":
        logging.warning("请在 .env 文件中设置 BAILIAN_API_KEY 和 BAILIAN_APP_ID")

# 在模块加载时执行检查
check_env_vars() 