import logging
import requests
import json
from fastapi import HTTPException
from typing import List, Optional, Dict

from backend.config import CONFIG
from backend.models.bailian import (
    BailianPayloadInput, BailianPayload, BailianResponse, BailianUsage
)
from backend.models.chat import ChatRequest, ChatResponse, ChatModelUsages, ChatModelUsage

async def call_bailian_api(
    chat_request: ChatRequest # 直接接收 ChatRequest 对象
) -> ChatResponse:
    """根据 ChatRequest 调用百炼 API 并返回标准 ChatResponse 格式。"""
    logging.info("Calling Bailian API service based on ChatRequest")

    # --- 从原 routers/chat.py 移动过来的参数提取和检查逻辑 ---
    try:
        conversation = chat_request.conversation
        session_id = chat_request.session_id
        context_params = chat_request.context_params

        logging.info(f"Extracted from ChatRequest: session_id='{session_id}', conversation_count={len(conversation)}, context_params={context_params}")
        logging.debug(f"Conversation: {conversation}")

        if not conversation:
            logging.warning("Request input is missing 'conversation' field or it is empty")
            raise HTTPException(status_code=400, detail="Conversation is required in input")

    except AttributeError as e:
        logging.error(f"Error accessing attributes in ChatRequest: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid ChatRequest structure: {e}")
    # --- 移动逻辑结束 ---

    if context_params is None:
        logging.warning("context_params is missing, proceeding without it for Bailian.")

    # 构造百炼平台请求 URL
    api_url = f"{CONFIG['BAILIAN_BASE_API_URL']}/{CONFIG['BAILIAN_APP_ID']}/completion"
    logging.debug(f"Bailian API URL: {api_url}")

    # 构造请求头
    headers = {
        "Authorization": f"Bearer {CONFIG['BAILIAN_API_KEY']}",
        "Content-Type": "application/json"
    }

    # 构造请求体 (使用 Pydantic 模型)
    payload_input = BailianPayloadInput()
    # 注意：当前实现总是使用 prompt 字段，即使 messages 字段可能更合适
    # 未来可以根据 app_id 或配置决定使用 prompt还是 messages
    payload_input.prompt = json.dumps([msg.model_dump() for msg in conversation], ensure_ascii=False)
    # payload_input.messages = conversation # 备选

    # 暂时禁用 session_id，根据原始代码逻辑
    # if session_id:
    #     payload_input.session_id = session_id

    if context_params is not None:
        payload_input.biz_params = context_params
    # else: # 检查逻辑已移到函数开头
        # 如果原始 API 强制要求 biz_params，这里应该重新引入错误
        # logging.warning("biz_params is missing, which might be required.")
        # raise HTTPException(status_code=400, detail="biz_params is required")
        # pass # 假设 biz_params 是可选的

    payload = BailianPayload(input=payload_input)

    # 将 Pydantic 模型转为字典用于 requests
    payload_dict = payload.model_dump(exclude_none=True)

    logging.debug(f"Bailian request payload: {json.dumps(payload_dict, indent=2, ensure_ascii=False)}")

    try:
        # 调用百炼平台API (仍然使用同步 requests)
        # 考虑未来换成 httpx 以支持异步调用
        response = requests.post(
            api_url,
            json=payload_dict,
            headers=headers,
            stream=False
        )
        logging.debug(f"Bailian API response status code: {response.status_code}")
        response.raise_for_status() # 检查 HTTP 错误

        response_data = response.json()
        logging.debug(
            "Bailian API response content: %s\n",
            json.dumps(response_data, indent=2, ensure_ascii=False)
        )

        # 使用 Pydantic 解析和验证响应
        try:
            bailian_response = BailianResponse.model_validate(response_data)

            ai_response_text = bailian_response.output.text if bailian_response.output else "抱歉，未能获取到回复。"
            next_session_id = bailian_response.output.session_id if bailian_response.output else None
            bailian_usage = bailian_response.usage # 这是 BailianUsage 类型

            logging.info(f"Extracted AI response and next_session_id: '{next_session_id}'")
            logging.debug(f"Raw Bailian usage details: {bailian_usage}")

            # 返回标准 ChatResponse 格式，使用转换后的 chat_usages
            return ChatResponse(
                response_text=ai_response_text,
                session_id=next_session_id,
                usages=bailian_usage
            )

        except Exception as pydantic_error:
            logging.error(f"Failed to parse Bailian API response: {pydantic_error}, raw data: {response_data}")
            raise HTTPException(status_code=500, detail="Error parsing AI service response.")

    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code
        error_detail = "Unknown API error"
        try:
            error_detail = http_err.response.json()
        except ValueError:
            error_detail = http_err.response.text
        error_message = f"API request failed (status code {status_code}): {error_detail}"
        logging.error(f"HTTP error calling Bailian API: {error_message}")
        # 根据需要，可以自定义异常类型或直接抛出 HTTPException
        raise HTTPException(status_code=status_code, detail="Error calling AI service.")

    except requests.exceptions.RequestException as req_err:
        error_message = f"API request connection failed: {req_err}"
        logging.error(error_message)
        raise HTTPException(status_code=503, detail="Could not connect to AI service.") 