import logging
from fastapi import APIRouter, HTTPException

# 导入前端请求/响应模型和特定服务的调用函数
from backend.agents.faq_filter_agent.agent import FAQFilterAgent
import backend.config as config
from backend.models.chat import ChatRequest, ChatResponse
from backend.services.bailian import call_bailian_api
from backend.services.coze import call_coze_api # 导入 Coze 服务调用函数

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_proxy(chat_request: ChatRequest):
    """处理聊天请求，将请求路由到相应的后端服务。"""
    logging.info("=========== /chat endpoint received request ==========")
    try:
        # --- 从 chat_request 直接获取要调用的服务，默认为 bailian ---
        service_to_call = "bailian" # 默认值
        if chat_request.service:
            service_to_call = chat_request.service.lower()
            logging.info(f"Service specified in request body: '{service_to_call}'")
        else:
            logging.info("No service specified in request body, defaulting to 'bailian'")

        # --- 根据服务名称调用相应的 API --- (移除原有的 context_params 检查)
        if service_to_call == "bailian":
            logging.info("Routing request to Bailian service.")
            if not config.check_bailian_vars():
                raise HTTPException(status_code=500, detail="Bailian service configuration is missing.")
            return await call_bailian_api(chat_request)

        elif service_to_call == "coze":
            logging.info("Routing request to Coze service.")
            if not config.check_coze_vars():
                raise HTTPException(status_code=500, detail="Coze service configuration is missing.")
            return await call_coze_api(chat_request) # 调用 Coze 服务

        elif service_to_call.startswith("agent:"):
            model_platform = service_to_call.split(":")[1]
            if model_platform == "volcano":
                logging.info("Routing request to Volcano agent.")
            elif model_platform == "bailian":
                logging.info("Routing request to Bailian agent.")
            else:
                raise HTTPException(status_code=400, detail=f"Invalid model platform: {model_platform}")
            faq_filter_agent = FAQFilterAgent(chat_request.context_params, model_platform=model_platform)
            return await faq_filter_agent.process_user_request(chat_request) # 调用 Custom Agent 服务

        else:
             # 如果服务名称无效
             logging.error(f"Unknown service requested: {service_to_call}")
             raise HTTPException(status_code=400, detail=f"Invalid service requested: {service_to_call}")

    except HTTPException as e:
        # 直接重新抛出由服务层或本层抛出的 HTTPException
        # 服务层会处理它们自己的配置、连接、解析等错误
        raise e
    except Exception as e:
        # 捕获未预料的错误
        logging.exception("An unexpected error occurred in /chat endpoint")
        raise HTTPException(status_code=500, detail="Internal server error.") 