from pydantic import BaseModel
from typing import Optional, Dict, List

# 前端请求体结构
class ChatInputMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    conversation: List[ChatInputMessage]
    session_id: Optional[str] = None
    context_params: Optional[Dict] = None

# 后端返回给前端的结构
class ChatModelUsage(BaseModel):
    model_id: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

class ChatModelUsages(BaseModel):
    models: Optional[List[ChatModelUsage]] = None

class ChatResponse(BaseModel):
    response_text: str
    session_id: Optional[str] = None
    usages: Optional[ChatModelUsages] = None 