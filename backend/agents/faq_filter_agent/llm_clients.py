import httpx
import asyncio
import json
import logging
import argparse
import sys
import os
from typing import List, Dict, Any, Tuple, Optional, Union

import jinja2 # Import Jinja2

from .exceptions import LLMAPIError, LLMResponseError
from backend.models.chat import ChatModelUsage # 导入 ChatModelUsage

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests
DEFAULT_TIMEOUT = 60.0 # Increased default timeout for potentially longer LLM responses

class VolcanoLLMClient:
    """与火山方舟大模型服务平台交互的异步基类。"""

    def __init__(self, api_key: str, api_base: str, model_name: str):
        """初始化客户端。

        Args:
            api_key: 火山方舟 API 密钥 (AK)。
            api_base: 火山方舟 API 基础 URL (e.g., 'https://ark.cn-beijing.volces.com/api/v3')。
            model_name: 模型 Endpoint ID 或名称。
        """
        if not api_key or not api_base or not model_name:
            raise ValueError("API Key, API Base, and Model Name cannot be empty.")
        self.api_key = api_key
        self.api_base = api_base.rstrip('/')
        self.model_name = model_name
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # 共享的 httpx 客户端实例，推荐在应用级别管理或按需创建
        # self.http_client = httpx.AsyncClient(headers=self.headers, timeout=DEFAULT_TIMEOUT)

    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        timeout: float = DEFAULT_TIMEOUT,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None # For JSON mode
    ) -> Tuple[str, ChatModelUsage, Dict[str, Any]]:
        """内部方法，调用火山方舟 /chat/completions API。

        Returns:
            Tuple[str, ChatModelUsage, Dict[str, Any]]: 一个包含以下内容的元组:
                - 响应消息的内容 (str)
                - 包含模型ID和token使用量的 ChatModelUsage 对象
                - 原始的API响应字典 (Dict[str, Any])
        """
        api_url = f"{self.api_base}/chat/completions"
        request_body = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        # Add optional parameters if provided
        if temperature is not None:
            request_body["temperature"] = temperature
        if top_p is not None:
            request_body["top_p"] = top_p
        if max_tokens is not None:
            request_body["max_tokens"] = max_tokens
        if response_format is not None:
             request_body["response_format"] = response_format

        logger.debug(f"Calling Volcano API: {api_url} with model {self.model_name}")
        # 直接打印完整的 request body
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
            # Log the raw response at DEBUG level
            logger.debug(f"Raw Volcano API response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")

            # Check for errors in the response body *before* trying to extract data
            if 'error' in response_data and response_data['error']:
                error_info = response_data['error']
                error_message = error_info.get('message', json.dumps(error_info))
                logger.error(f"Volcano API returned error in response body: {error_message}")
                raise LLMAPIError(f"API returned error: {error_message}")

            # Extract the desired data
            content = response_data['choices'][0]['message']['content']

            # Extract usage information safely
            usage = ChatModelUsage(
                model_id=response_data['model'],
                input_tokens=response_data['usage']['prompt_tokens'],
                output_tokens=response_data['usage']['completion_tokens']
            )

            # Return the tuple
            return content, usage, response_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response from Volcano API: {response.text}")
            raise LLMResponseError(f"Failed to decode API JSON response: {e}") from e
        except (KeyError, IndexError, TypeError) as e: # Catch potential issues accessing nested data
             logger.error(f"Failed to parse expected data from Volcano API response. Response: {response_data}. Error: {e}")
             raise LLMResponseError(f"Unexpected API response structure: {e}") from e

    # 对于llm的返回的json，如果llm意外的将其包在了```json ... ```中，则需要去掉这些json的包裹
    def remove_json_wrapper(self, content: str) -> str:
        """Remove JSON wrapper from content if present."""
        if content.startswith('```json') and content.endswith('```'):
            return content[len('```json'):-len('```')]
        return content

    # __del__ method to close the client if managed per instance
    # async def close(self):
    #     await self.http_client.aclose()

class QueryRewriteClient(VolcanoLLMClient):
    """使用火山方舟 LLM API 异步重写查询。"""

    def __init__(self, api_key: str, api_base: str, model_name: str, prompt_template: str):
        """初始化客户端。

        Args:
            api_key: 火山方舟 API 密钥。
            api_base: 火山方舟 API 基础 URL。
            model_name: 用于重写的模型 Endpoint ID 或名称。
            prompt_template: rewrite_prompt.md 的内容模板。
        """
        super().__init__(api_key, api_base, model_name)
        self.prompt_template = prompt_template

    async def rewrite_query(
        self,
        input_data: Dict[str, Any], # Merge conversation and context
        timeout: float = DEFAULT_TIMEOUT
    ) -> Tuple[Dict[str, Any], ChatModelUsage]:
        """异步调用 LLM API 来重写查询。

        Args:
            input_data: 包含 'conversation' (对话历史) 和 'context' (上下文信息) 的字典。
            timeout: 请求超时时间 (秒)。

        Returns:
            Tuple[Dict[str, Any], ChatModelUsage]: 一个包含以下内容的元组:
                - 包含 'query_rewrite' 和 'reason' 的字典。
                - 包含模型ID和token使用量的 ChatModelUsage 对象。

        Raises:
            LLMAPIError: 如果 API 调用失败。
            LLMResponseError: 如果输入数据无效、提示格式化失败或 API 响应格式不正确。
        """
        # 1. Extract data and build Prompt
        try:
            # Extract conversation and context from input_data
            conversation = input_data.get('conversation')
            context = input_data.get('context')

            # Validate input data structure
            if not isinstance(conversation, list):
                logger.error(f"Invalid 'conversation' format in input_data: Expected list, got {type(conversation)}")
                raise LLMResponseError("Invalid input data: 'conversation' must be a list.")
            if not isinstance(context, dict):
                 logger.error(f"Invalid 'context' format in input_data: Expected dict, got {type(context)}")
                 raise LLMResponseError("Invalid input data: 'context' must be a dictionary.")

            # Use the prompt template directly as system content
            system_prompt_content = self.prompt_template
            # Pass the input_data dict directly as user content
            messages = [
                {"role": "system", "content": system_prompt_content},
                {"role": "user", "content": json.dumps(input_data, ensure_ascii=False)}
            ]

        except LLMResponseError: # Re-raise validation errors
            raise
        except Exception as e: # Catch other potential errors during validation/setup
            logger.error(f"Error preparing data for query rewrite: {e}", exc_info=True)
            # Use LLMAPIError as it's an issue before the API call itself, but related to input/setup
            raise LLMAPIError(f"Failed to prepare data for rewrite: {e}") from e

        # 2. 调用基类 API 方法 (requesting JSON output)
        try:
            content, usage, response_data = await self._call_api(
                messages=messages,
                timeout=timeout,
                temperature=0.1, # Low temp for deterministic rewrite
                response_format={"type": "json_object"} # Request JSON
            )
        except (LLMAPIError, LLMResponseError):
             raise # Re-raise API or response errors from base class
        except Exception as e:
             logger.exception(f"Unexpected error calling rewrite API: {e}")
             raise LLMAPIError(f"Unexpected error during API call: {e}") from e

        # 3. 解析特定于重写的响应内容
        try:
            result = json.loads(self.remove_json_wrapper(content))
            if not isinstance(result, dict) or 'query_rewrite' not in result or 'reason' not in result:
                logger.error(f"Query rewrite response JSON content is malformed. Parsed: {result}, Original: '{content}'")
                raise LLMResponseError("LLM response content is not the expected rewrite JSON format.")

            logger.info(f"Successfully rewrote query using model {self.model_name}.")
            return result, usage

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from query rewrite response content: '{content}'. Error: {e}")
            raise LLMResponseError(f"Failed to decode JSON from LLM rewrite response: {e}. Content: '{content}'") from e

class FAQClassifierClient(VolcanoLLMClient):
    """使用火山方舟 LLM API 进行异步问题分类。"""

    def __init__(self, api_key: str, api_base: str, model_name: str, prompt_template: str):
        """初始化客户端。

        Args:
            api_key: 火山方舟 API 密钥。
            api_base: 火山方舟 API 基础 URL。
            model_name: 用于分类的模型 Endpoint ID 或名称。
            prompt_template: classify_prompt.md 的内容模板 (Jinja2 格式)。
        """
        super().__init__(api_key, api_base, model_name)
        self.prompt_template = prompt_template
        # Pre-compile the Jinja2 template for efficiency if the template is static
        try:
            self.jinja_template = jinja2.Template(self.prompt_template)
        except jinja2.exceptions.TemplateSyntaxError as e:
             logger.error(f"Invalid Jinja2 template syntax in provided prompt template: {e}")
             # Optionally log template snippet here too
             raise LLMResponseError(f"Invalid Jinja2 template syntax: {e}") from e

    async def classify_query(
        self,
        rewritten_query: str,
        faq_structure_md: str,
        timeout: float = DEFAULT_TIMEOUT
    ) -> Tuple[Dict[str, Any], ChatModelUsage]:
        """异步调用火山方舟 LLM API 对重写后的查询进行分类。

        Args:
            rewritten_query: 重写后的查询字符串。
            faq_structure_md: Markdown 格式的 FAQ 目录结构 (将传递给 Jinja2 模板)。
            timeout: 请求超时时间 (秒)。

        Returns:
            Tuple[Dict[str, Any], ChatModelUsage]: 一个包含以下内容的元组:
                - 包含 'category_key_path' 和 'reason' 的字典的列表。
                - 包含模型ID和token使用量的 ChatModelUsage 对象。

        Raises:
            LLMAPIError: 如果 API 调用失败。
            LLMResponseError: 如果提示格式化失败或 API 响应格式不正确。
        """
        # 1. 构建 Prompt using Jinja2
        try:
            # Render the template using Jinja2
            system_prompt_content = self.jinja_template.render(faq_structure=faq_structure_md, faq_retrieve_num=3)

            # 构建火山方舟需要的 messages 格式
            messages = [
                {"role": "system", "content": system_prompt_content},
                {"role": "user", "content": rewritten_query} # The query to classify
            ]
        except jinja2.exceptions.UndefinedError as e:
             # This error occurs if the template uses a variable not provided in .render()
             logger.error(f"Jinja2 rendering error: Undefined variable {e}. Template expected 'faq_structure'.", exc_info=True)
             raise LLMResponseError(f"Failed to render classification prompt: Undefined variable {e}.") from e
        except Exception as e:
            # Catch other potential Jinja2 errors or general errors
            logger.error(f"Error preparing prompt for FAQ classification using Jinja2: {e}", exc_info=True)
            template_snippet = self.prompt_template[:500] + ("..." if len(self.prompt_template) > 500 else "")
            logger.debug(f"Prompt template snippet: {template_snippet}")
            raise LLMResponseError(f"Failed to prepare classification prompt: {e}") from e

        # 2. 调用基类 API 方法 (requesting JSON output)
        try:
            content, usage, _ = await self._call_api(
                messages=messages,
                timeout=timeout,
                temperature=0.01, # Low temp for classification
                response_format={"type": "json_object"} # Request JSON
            )
        except (LLMAPIError, LLMResponseError):
            raise # Re-raise API or response errors from base class
        except Exception as e:
             logger.exception(f"Unexpected error calling classification API: {e}")
             raise LLMAPIError(f"Unexpected error during API call: {e}") from e

        # 3. 解析特定于分类的响应内容
        try:
            results = json.loads(self.remove_json_wrapper(content))

            if not isinstance(results, list) or not all(isinstance(item, dict) and 'category_key_path' in item and 'reason' in item for item in results):
                logger.error(f"FAQ classification response JSON content is malformed. Parsed: {results}. Original: '{content}'")
                raise LLMResponseError("LLM response content is not the expected classification JSON format ({category_key_path, reason}).")

            logger.info(f"Successfully classified query using model {self.model_name}. Paths: {', '.join([item['category_key_path'] for item in results])}")
            return results, usage

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from FAQ classification response content: '{content}'. Error: {e}")
            raise LLMResponseError(f"Failed to decode JSON from LLM classification response: {e}. Content: '{content}'") from e
