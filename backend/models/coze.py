from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from .chat import ChatInputMessage, ChatModelUsage # 复用基础消息和 Usage 结构

# Coze workflow_run API 请求体结构
# 参考: https://www.coze.cn/open/docs/developer_guides/workflow_run

# COZE workflow_run API 请求体结构
class CozePayload(BaseModel):
    workflow_id: str
    parameters: Optional[Dict[str, Any]] = None

# Coze workflow_run API 响应体结构
class CozeResponse(BaseModel):
    code: int
    msg: str # 错误信息 
    data: str # 一般是json序列化后的字符串
    token: int # 消耗的token
