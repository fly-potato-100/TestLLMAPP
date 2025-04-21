import logging
import httpx  # 导入 httpx
import json
from fastapi import HTTPException
from typing import List, Optional, Dict

from backend.config import CONFIG
from backend.models.bailian import (
    BailianPayloadInput, BailianPayload, BailianResponse, BailianUsage
)
from backend.models.chat import ChatRequest, ChatResponse, ChatModelUsages, ChatModelUsage

async def call_bailian_api(
    chat_request: ChatRequest
) -> ChatResponse:
    """根据 ChatRequest 调用百炼 API 并返回标准 ChatResponse 格式 (使用 httpx 原生异步调用)。"""
    logging.info("Calling Bailian API service based on ChatRequest (using httpx)")

    # --- 参数提取 --- (保持不变)
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
    # --- 提取结束 ---

    if context_params is None:
        logging.warning("context_params is missing, proceeding without it for Bailian.")

    # --- 构造请求 URL, Headers, Payload --- (保持不变)
    api_url = f"{CONFIG['BAILIAN_BASE_API_URL']}/{CONFIG['BAILIAN_APP_ID']}/completion"
    logging.debug(f"Bailian API URL: {api_url}")
    headers = {
        "Authorization": f"Bearer {CONFIG['BAILIAN_API_KEY']}",
        "Content-Type": "application/json"
    }
    payload_input = BailianPayloadInput()
    payload_input.prompt = json.dumps([msg.model_dump() for msg in conversation], ensure_ascii=False)
    if context_params is not None:
        payload_input.biz_params = context_params
    payload = BailianPayload(input=payload_input)
    payload_dict = payload.model_dump(exclude_none=True)
    logging.debug(f"Bailian request payload: {json.dumps(payload_dict, indent=2, ensure_ascii=False)}")
    # --- 构造结束 ---

    # --- 调用百炼 API (使用 httpx) ---
    async with httpx.AsyncClient() as client:
        try:
            # 使用 httpx.AsyncClient.post
            # 注意：百炼 API 不支持 stream=False 参数，httpx 默认就是非流式
            response = await client.post(
                api_url,
                json=payload_dict,
                headers=headers,
                timeout=60.0  # 设置超时
            )
            logging.debug(f"Bailian API response status code: {response.status_code}")
            response.raise_for_status() # 检查 HTTP 错误

            response_data = response.json()
            logging.debug(
                "Bailian API response content: %s\n",
                json.dumps(response_data, indent=2, ensure_ascii=False)
            )

            # --- 解析和验证响应 --- (保持不变)
            try:
                bailian_response = BailianResponse.model_validate(response_data)
                ai_response_text = bailian_response.output.text if bailian_response.output else "抱歉，未能获取到回复。"
                next_session_id = bailian_response.output.session_id if bailian_response.output else None
                bailian_usage = bailian_response.usage
                logging.info(f"Extracted AI response and next_session_id: '{next_session_id}'")
                logging.debug(f"Raw Bailian usage details: {bailian_usage}")
                return ChatResponse(
                    response_text=ai_response_text,
                    session_id=next_session_id,
                    usages=bailian_usage
                )
            except Exception as pydantic_error:
                logging.error(f"Failed to parse Bailian API response: {pydantic_error}, raw data: {response_data}")
                raise HTTPException(status_code=500, detail="Error parsing AI service response.")
            # --- 解析结束 ---

        # --- 错误处理 (改为 httpx 的异常类型) ---
        except httpx.HTTPStatusError as http_err:
            status_code = http_err.response.status_code
            error_detail = "Unknown API error"
            try:
                error_detail = http_err.response.json()
            except ValueError:
                error_detail = http_err.response.text
            error_message = f"API request failed (status code {status_code}): {error_detail}"
            logging.error(f"HTTP error calling Bailian API: {error_message}")
            raise HTTPException(status_code=status_code, detail="Error calling AI service.")

        except httpx.RequestError as req_err:
            error_message = f"API request connection failed: {req_err}"
            logging.error(error_message)
            raise HTTPException(status_code=503, detail="Could not connect to AI service.")
        except Exception as e:
            logging.exception("An unexpected error occurred while calling Bailian API")
            raise HTTPException(status_code=500, detail="Internal server error calling AI service.")
    # --- 调用结束 --- 