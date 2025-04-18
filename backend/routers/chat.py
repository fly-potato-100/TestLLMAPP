import logging
from fastapi import APIRouter, HTTPException

# 导入前端请求/响应模型和特定服务的调用函数
from backend.models.chat import ChatRequest, ChatResponse
from backend.services.bailian import call_bailian_api
# from backend.services.coze import call_coze_api # 预留 Coze 服务导入

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_proxy(chat_request: ChatRequest):
    """处理聊天请求，将请求路由到相应的后端服务。"""
    logging.info("=========== /chat endpoint received request ==========")
    try:
        # --- 选择调用哪个后端服务 ---
        # 目前固定调用百炼，将来可以根据 chat_request 中的参数或其他逻辑选择
        service_to_call = "bailian" # 或者 "coze"

        if service_to_call == "bailian":
            # 直接将整个请求传递给服务层处理
            return await call_bailian_api(chat_request)

        elif service_to_call == "coze":
             # coze_response = await call_coze_api(chat_request) # 假设 Coze 服务也接收 ChatRequest
             logging.warning("Coze service call is not implemented yet.")
             raise HTTPException(status_code=501, detail="Coze service not implemented")
        else:
             logging.error(f"Unknown service requested: {service_to_call}")
             raise HTTPException(status_code=400, detail="Invalid service requested")

    except HTTPException as e:
        # 直接重新抛出由服务层或本层抛出的 HTTPException
        raise e
    except Exception as e:
        # 捕获未预料的错误
        logging.exception("An unexpected error occurred in /chat endpoint")
        raise HTTPException(status_code=500, detail="Internal server error.") 