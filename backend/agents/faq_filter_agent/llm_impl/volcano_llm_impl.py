import httpx
import json
import logging
from typing import List, Dict, Any, Tuple, Optional

from backend.models.chat import ChatModelUsage
from ..exceptions import LLMAPIError, LLMResponseError # 引用上层目录的 exceptions
from .base_llm_impl import BaseLLMImpl, DEFAULT_TIMEOUT # Updated import

logger = logging.getLogger(__name__)

class VolcanoLLMImpl(BaseLLMImpl): # Inherits from BaseLLMImpl
    """与火山方舟大模型服务平台交互的具体实现。"""

    def __init__(self, api_key: str, api_base: str, model_id: str):
        """初始化客户端。

        Args:
            api_key: 火山方舟 API 密钥 (AK)。
            api_base: 火山方舟 API 基础 URL (e.g., 'https://ark.cn-beijing.volces.com/api/v3')。
            model_id: 模型 ID。
        """
        if not api_key or not api_base or not model_id:
            raise ValueError("API Key, API Base, and Model ID cannot be empty.")
        self.api_key = api_key
        self.api_base = api_base.rstrip('/')
        self.model_id = model_id
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # httpx.AsyncClient 实例现在在 chat_completion 方法内部创建和管理，以确保上下文正确关闭

    # 实现基类的抽象方法
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        timeout: float = DEFAULT_TIMEOUT,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None # For JSON mode
    ) -> Tuple[str, ChatModelUsage, Dict[str, Any]]:
        """调用火山方舟 /chat/completions API。"""
        api_url = f"{self.api_base}/chat/completions"
        request_body = {
            "model": self.model_id,
            "messages": messages,
            "stream": False, # 确保 stream 为 False 以匹配非流式 chat_completion 接口
        }
        # Add optional parameters if provided
        if temperature is not None:
            request_body["temperature"] = temperature
        if top_p is not None:
            request_body["top_p"] = top_p
        if max_tokens is not None:
            # 火山 API 可能叫 max_tokens 或 max_new_tokens，需确认文档
            # 假设是 max_tokens
            request_body["max_tokens"] = max_tokens
        if response_format is not None:
             request_body["response_format"] = response_format # 假设火山支持 OpenAI 风格的 response_format

        logger.debug(f"Calling Volcano API: {api_url} with model {self.model_id}")
        logger.debug(f"Request Body: {json.dumps(request_body, ensure_ascii=False, indent=2)}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(
                    api_url,
                    headers=self.headers,
                    json=request_body
                )
                response.raise_for_status() # Check for 4xx/5xx errors
            except httpx.TimeoutException as e:
                logger.error(f"Volcano API request timed out to {api_url}: {e}")
                raise LLMAPIError(f"Request timed out after {timeout}s: {e}") from e
            except httpx.RequestError as e:
                logger.error(f"Volcano API request error to {api_url}: {e}")
                raise LLMAPIError(f"Request failed: {e}") from e
            except httpx.HTTPStatusError as e:
                error_detail = e.response.text
                try:
                    error_json = e.response.json()
                    error_detail = error_json.get('error', {}).get('message', error_detail)
                except json.JSONDecodeError:
                    pass
                logger.error(f"Volcano API returned error status {e.response.status_code} from {api_url}: {error_detail}")
                raise LLMAPIError(f"API returned status {e.response.status_code}: {error_detail}") from e

        try:
            response_data = response.json()
            logger.debug(f"Raw Volcano API response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")

            if 'error' in response_data and response_data['error']:
                error_info = response_data['error']
                error_message = error_info.get('message', json.dumps(error_info))
                logger.error(f"Volcano API returned error in response body: {error_message}")
                raise LLMAPIError(f"API returned error: {error_message}")

            # 确保按预期结构提取数据
            if not response_data.get('choices') or not response_data['choices'][0].get('message') or 'content' not in response_data['choices'][0]['message']:
                 logger.error(f"Unexpected response structure from Volcano API. Missing 'choices[0].message.content'. Response: {response_data}")
                 raise LLMResponseError("Unexpected API response structure: Missing content.")

            content = response_data['choices'][0]['message']['content']

            if not response_data.get('usage') or 'prompt_tokens' not in response_data['usage'] or 'completion_tokens' not in response_data['usage']:
                 logger.warning(f"Usage information missing or incomplete in Volcano API response. Response: {response_data}")
                 # 可以选择返回默认值或部分信息
                 usage = ChatModelUsage(
                     model_id=response_data.get('model', self.model_id), # 尝试获取模型 ID
                     input_tokens=response_data.get('usage', {}).get('prompt_tokens', 0),
                     output_tokens=response_data.get('usage', {}).get('completion_tokens', 0)
                 )
            else:
                 usage = ChatModelUsage(
                    model_id=response_data['model'],
                    input_tokens=response_data['usage']['prompt_tokens'],
                    output_tokens=response_data['usage']['completion_tokens']
                 )

            # 使用基类的方法移除可能的 JSON 包裹
            cleaned_content = self.remove_json_wrapper(content)

            return cleaned_content, usage, response_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response from Volcano API: {response.text}")
            raise LLMResponseError(f"Failed to decode API JSON response: {e}") from e
        except (KeyError, IndexError, TypeError) as e:
             logger.error(f"Failed to parse expected data from Volcano API response. Response: {response_data}. Error: {e}", exc_info=True)
             raise LLMResponseError(f"Unexpected API response structure: {e}") from e 