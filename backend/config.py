import os
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 统一配置环境变量默认值
CONFIG = {
    # 百炼服务配置
    "BAILIAN_BASE_API_URL": os.getenv("BAILIAN_BASE_API_URL"), # 例如: "https://bailian.aliyuncs.com/v2/app/completion" -> 应该是基础 URL "https://bailian.aliyuncs.com/v2/app"
    "BAILIAN_APP_ID": os.getenv("BAILIAN_APP_ID"),
    "BAILIAN_API_KEY": os.getenv("BAILIAN_API_KEY"),

    # 新增：Coze 服务配置
    "COZE_BASE_URL": os.getenv("COZE_BASE_URL"), # 例如: "https://api.coze.cn/open_api/v1"
    "COZE_API_KEY": os.getenv("COZE_API_KEY"), # Coze 的 Bearer Token
    "COZE_WORKFLOW_ID": os.getenv("COZE_WORKFLOW_ID"), # 要运行的 Workflow ID

    "FASTAPI_HOST": os.getenv("FASTAPI_HOST", "0.0.0.0"),
    "FASTAPI_PORT": int(os.getenv("FASTAPI_PORT", 8000)),
}

# 检查必要的环境变量是否已设置
def check_bailian_vars():
    if CONFIG["BAILIAN_API_KEY"] == "YOUR_API_KEY" or CONFIG["BAILIAN_APP_ID"] == "YOUR_APP_ID":
        logging.warning("请在 .env 文件中设置 BAILIAN_API_KEY 和 BAILIAN_APP_ID")
        return False
    return True 

def check_coze_vars():
    if CONFIG["COZE_API_KEY"] == "YOUR_API_KEY" or CONFIG["COZE_WORKFLOW_ID"] == "YOUR_WORKFLOW_ID":
        logging.warning("请在 .env 文件中设置 COZE_API_KEY 和 COZE_WORKFLOW_ID")
        return False
    return True


print("Configuration loaded:")
# 打印配置时隐藏敏感信息
printable_config = "\n".join(
    f"{k}: {(v[:5] + '****' + v[-4:] if 'KEY' in k and v and len(v) > 9 else v)}"
    for k, v in CONFIG.items()
)
print(printable_config) 