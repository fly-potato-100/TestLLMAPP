from pydantic import BaseModel
from typing import Optional, Dict, List
from .chat import ChatInputMessage, ChatModelUsages

# 百炼 API 请求体结构
class BailianPayloadInputMessage(ChatInputMessage): # 可以复用 ChatInputMessage 结构
    pass

class BailianPayloadInput(BaseModel):
    messages: Optional[List[BailianPayloadInputMessage]] = None
    prompt: Optional[str] = None
    session_id: Optional[str] = None
    biz_params: Optional[Dict] = {} # 改为 Optional

class BailianPayload(BaseModel):
    input: BailianPayloadInput
    parameters: Dict = {}
    debug: Dict = {}

# 百炼 API 响应体结构
class BailianUsage(ChatModelUsages):
    pass

class BailianChatOutput(BaseModel): # 重命名以区分前端 ChatOutput
    text: str
    session_id: Optional[str] = None

class BailianResponse(BaseModel):
    output: Optional[BailianChatOutput] = None # 改为 Optional 避免解析错误
    usage: Optional[BailianUsage] = None
    request_id: Optional[str] = None 