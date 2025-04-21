import logging
import httpx  # 导入 httpx
import json
from fastapi import HTTPException
from typing import List, Optional, Dict

from backend.config import CONFIG
from backend.models.chat import ChatRequest, ChatResponse, ChatModelUsages, ChatModelUsage
from backend.models.coze import (
    CozePayload,
    CozeResponse
)

async def call_coze_api(
    chat_request: ChatRequest
) -> ChatResponse:
    """根据 ChatRequest 调用 Coze workflow_run API 并返回标准 ChatResponse 格式 (使用 httpx 原生异步调用)。"""
    logging.info("Calling Coze API service based on ChatRequest (using httpx)")

    # --- 参数提取 --- (与 bailian.py 类似)
    try:
        conversation = chat_request.conversation
        session_id = chat_request.session_id
        context_params = chat_request.context_params or {} # 确保 context_params 是字典

        logging.info(f"Extracted from ChatRequest: session_id='{session_id}', conversation_count={len(conversation)}, context_params={context_params}")
        logging.debug(f"Conversation: {conversation}")

        if not conversation:
            logging.warning("Request input is missing 'conversation' field or it is empty")
            raise HTTPException(status_code=400, detail="Conversation is required in input")

    except AttributeError as e:
        logging.error(f"Error accessing attributes in ChatRequest: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid ChatRequest structure: {e}")
    # --- 提取结束 ---


    # 构造 Coze 请求 URL
    api_url = f"{CONFIG['COZE_BASE_URL']}/workflow/run"
    logging.debug(f"Coze API URL: {api_url}")

    # 构造请求头
    headers = {
        "Authorization": f"Bearer {CONFIG['COZE_API_KEY']}",
        "Content-Type": "application/json",
    }

    # 构造请求体 (使用 Pydantic 模型)
    params = {
        "input": conversation,
        "channel_name": context_params.get("channel_name"),
        "platform_name": context_params.get("platform_name"),
    }

    payload = CozePayload(
        workflow_id=CONFIG['COZE_WORKFLOW_ID'],
        parameters=params
    )

    # 将 Pydantic 模型转为字典用于 requests
    payload_dict = payload.model_dump(exclude_none=True)

    logging.debug(f"Coze request payload: {json.dumps(payload_dict, indent=2, ensure_ascii=False)}")

    # --- 调用 Coze API (使用 httpx) ---
    async with httpx.AsyncClient() as client:
        try:
            # 使用 httpx.AsyncClient.post
            response = await client.post(
                api_url,
                json=payload_dict,
                headers=headers,
                timeout=60.0  # 设置超时
            )
            logging.debug(f"Coze API response status code: {response.status_code}")
            response.raise_for_status() # 检查 HTTP 错误 (4xx, 5xx)

            response_data = response.json()
            logging.debug(
                "Coze API response content: %s\n",
                json.dumps(response_data, indent=2, ensure_ascii=False)
            )

            # --- 解析和验证 Coze 响应 --- (使用 Pydantic)
            try:
                coze_api_response = CozeResponse.model_validate(response_data)

                # 检查 Coze 返回的业务错误
                if coze_api_response.code != 0:
                    logging.error(f"Coze API returned an error(code={coze_api_response.code}): {coze_api_response.msg}")
                    # 可以根据 error_code 决定是否抛出特定状态码的 HTTPException
                    raise HTTPException(status_code=500, detail=coze_api_response.msg)

                # 提取所需信息
                ai_response_json = json.loads(coze_api_response.data)
                logging.debug(f"Coze API response data: {ai_response_json}")

                ai_response_results = ai_response_json["results"]
                ai_response_converted = []
                for result in ai_response_results:
                    ai_response_converted.append({
                        "content": result["output"],
                        'score': 0.9,
                    })
                # 返回标准 ChatResponse 格式
                return ChatResponse(
                    response_text=json.dumps(ai_response_converted),
                )

            except Exception as pydantic_error:
                logging.exception(f"Failed to parse Coze API response: {pydantic_error}, raw data: {response_data}")
                raise HTTPException(status_code=500, detail="Error parsing AI service response.")
            # --- 解析结束 ---

        except httpx.HTTPStatusError as http_err:
            status_code = http_err.response.status_code
            error_detail = "Unknown API error"
            try:
                # 尝试解析 JSON 错误详情
                error_detail = http_err.response.json()
            except ValueError:
                # 如果不是 JSON，则使用原始文本
                error_detail = http_err.response.text
            error_message = f"API request failed (status code {status_code}): {error_detail}"
            logging.error(f"HTTP error calling Coze API: {error_message}")
            raise HTTPException(status_code=status_code, detail="Error calling AI service.")

        except httpx.RequestError as req_err:
            # 处理连接错误、超时等
            error_message = f"API request connection failed: {req_err}"
            logging.error(error_message)
            raise HTTPException(status_code=503, detail="Could not connect to AI service.")
        except Exception as e:
            logging.exception("An unexpected error occurred while calling Coze API")
            raise HTTPException(status_code=500, detail="Internal server error calling AI service.")
    # --- 调用结束 --- 