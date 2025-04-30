import httpx
import json
import logging
import os
from typing import List, Dict, Any, Tuple, Optional, AsyncGenerator

from backend.models.chat import ChatModelUsage
from ..exceptions import LLMAPIError, LLMResponseError
from .base_llm_impl import BaseLLMImpl, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

class BailianLLMImpl(BaseLLMImpl):
    """与阿里百炼大模型服务平台交互的具体实现。"""

    def __init__(self, api_key: str, api_base: str, model_id: str): # Changed api_base to be required and renamed model_name to model_id
        """初始化客户端。

        Args:
            api_key: 百炼 API 密钥。
            api_base: 百炼 API 基础 URL。
            model_id: 百炼模型 ID。
        """
        # Validate inputs
        if not api_key or not api_base or not model_id:
            raise ValueError("API Key, API Base, and Model ID cannot be empty for BailianLLMImpl.")

        self.api_key = api_key
        self.api_base = api_base.rstrip('/') # Ensure no trailing slash
        self.model_id = model_id # Use model_id as provided
        self.headers = {
             # 根据百炼文档设置 Authorization 和 Content-Type
             "Authorization": f"Bearer {self.api_key}",
             "Content-Type": "application/json",
             "Accept": "application/json", # Added Accept header, common practice
        }
        # logger.warning removed as implementation is now added

    def _build_request_body(
        self,
        messages: List[Dict[str, str]],
        is_stream: bool,
        enable_thinking: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """构建调用百炼 API 的请求体。"""
        request_body = {
            "model": self.model_id,
            "messages": messages,
            "stream": is_stream,
            "enable_thinking": enable_thinking,
        }

        # Add optional parameters if provided
        if temperature is not None:
            request_body["temperature"] = temperature
        if top_p is not None:
            request_body["top_p"] = top_p
        if max_tokens is not None:
            # Assuming 'max_tokens' is the correct parameter name for Bailian
            request_body["max_tokens"] = max_tokens
        if response_format is not None:
             # Assuming Bailian supports OpenAI style response_format
             request_body["response_format"] = response_format

        if is_stream:
            request_body["stream_options"] = {"include_usage": True}

        logger.debug(f"Built Bailian Request Body (stream={is_stream}): {json.dumps(request_body, ensure_ascii=False, indent=2)}")
        return request_body

    # Public interface method required by BaseLLMImpl
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        timeout: float = DEFAULT_TIMEOUT,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None
    ) -> Tuple[str, ChatModelUsage, Dict[str, Any]]:
        """
        调用阿里百炼 /chat/completions API。
        根据 model_id 前缀决定使用流式或非流式调用。
        对于流式调用 ('qwen3' 前缀)，会聚合响应内容并返回与非流式兼容的格式。
        """
        model_prefix = self.model_id.split('-', 1)[0]
        is_stream = False
        enable_thinking = os.getenv('QWEN3_ENABLE_THINKING', 'false').lower() == 'true'
        if model_prefix == 'qwen3':
            # qwen3必须启用流式
            is_stream = True
            if enable_thinking:
                # 启用了思考，不能设置 response_format 为 json_object，否则会报错
                response_format = None

        # Build request body first
        request_body = self._build_request_body(
            messages=messages,
            is_stream=is_stream,
            enable_thinking=enable_thinking,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            response_format=response_format
        )

        if is_stream:
            # Use stream implementation and aggregate results
            logger.debug(f"Using stream implementation for model: {self.model_id}")
            full_content = ""
            full_reasoning_content = ""
            final_usage: Optional[ChatModelUsage] = None

            try:
                # Pass only request_body and timeout to the stream method
                stream_generator = self._chat_completion_stream(
                    request_body=request_body,
                    timeout=timeout
                )
                async for content_chunk, reasoning_content_chunk, usage_info in stream_generator:
                    if content_chunk:
                        full_content += content_chunk
                    if reasoning_content_chunk:
                        full_reasoning_content += reasoning_content_chunk
                    if usage_info:
                        final_usage = usage_info

                if final_usage is None:
                    logger.warning(f"Stream for model {self.model_id} finished without providing usage info.")
                    final_usage = ChatModelUsage(model_id=self.model_id, input_tokens=0, output_tokens=0)

                logger.debug(f"Full content from Bailian API(stream): {full_content}")
                logger.debug(f"Full reasoning content from Bailian API(stream): {full_reasoning_content}")
                cleaned_content = self.remove_json_wrapper(full_content)
                # Return an indication that it was streamed, along with aggregated results
                return cleaned_content, final_usage, {
                    "response_type": "streamed", 
                    "full_content": full_content,
                    "full_reasoning_content": full_reasoning_content,
                }

            except (LLMAPIError, LLMResponseError) as e:
                raise e
            except Exception as e:
                 logger.error(f"Unexpected error during stream aggregation for {self.model_id}: {e}", exc_info=True)
                 raise LLMResponseError(f"Failed to aggregate stream response: {e}") from e

        else:
            # Use non-stream implementation
            logger.debug(f"Using non-stream implementation for model: {self.model_id}")
            # Pass only request_body and timeout to the non-stream method
            return await self._chat_completion_non_stream(
                request_body=request_body,
                timeout=timeout
            )

    async def _chat_completion_non_stream(
        self,
        request_body: Dict[str, Any], # Changed parameters
        timeout: float                # Changed parameters
    ) -> Tuple[str, ChatModelUsage, Dict[str, Any]]:
        """调用阿里百炼 /chat/completions API (非流式)。"""
        api_url = f"{self.api_base}/chat/completions"
        # Removed request_body creation, now passed as argument

        logger.debug(f"Calling Bailian API (non-stream): {api_url} with model {self.model_id}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(
                    api_url,
                    headers=self.headers,
                    json=request_body
                )
                response.raise_for_status() # Check for 4xx/5xx errors
            except httpx.TimeoutException as e:
                logger.error(f"Bailian API request timed out to {api_url}: {e}")
                raise LLMAPIError(f"Request timed out after {timeout}s: {e}") from e
            except httpx.RequestError as e:
                logger.error(f"Bailian API request error to {api_url}: {e}")
                raise LLMAPIError(f"Request failed: {e}") from e
            except httpx.HTTPStatusError as e:
                error_detail = e.response.text
                try:
                    error_json = e.response.json()
                    error_detail = error_json.get('error', {}).get('message', error_detail)
                except json.JSONDecodeError:
                    pass
                logger.error(f"Bailian API returned error status {e.response.status_code} from {api_url}: {error_detail}")
                raise LLMAPIError(f"API returned status {e.response.status_code}: {error_detail}") from e

        try:
            response_data = response.json()
            logger.debug(f"Raw Bailian API response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")

            if 'error' in response_data and response_data['error']:
                error_info = response_data['error']
                error_message = error_info.get('message', json.dumps(error_info))
                logger.error(f"Bailian API returned error in response body: {error_message}")
                raise LLMAPIError(f"API returned error: {error_message}")

            if not response_data.get('choices') or not response_data['choices'][0].get('message') or 'content' not in response_data['choices'][0]['message']:
                 logger.error(f"Unexpected response structure from Bailian API. Missing 'choices[0].message.content'. Response: {response_data}")
                 raise LLMResponseError("Unexpected API response structure: Missing content.")

            content = response_data['choices'][0]['message']['content']

            if not response_data.get('usage') or 'prompt_tokens' not in response_data['usage'] or 'completion_tokens' not in response_data['usage']:
                 logger.warning(f"Usage information missing or incomplete in Bailian API response. Response: {response_data}")
                 usage = ChatModelUsage(
                     model_id=response_data.get('model', self.model_id),
                     input_tokens=response_data.get('usage', {}).get('prompt_tokens', 0),
                     output_tokens=response_data.get('usage', {}).get('completion_tokens', 0)
                 )
            else:
                 usage = ChatModelUsage(
                    model_id=response_data.get('model', self.model_id),
                    input_tokens=response_data['usage']['prompt_tokens'],
                    output_tokens=response_data['usage']['completion_tokens']
                 )

            cleaned_content = self.remove_json_wrapper(content)

            # Non-stream returns the actual raw response data
            return cleaned_content, usage, response_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response from Bailian API: {response.text}")
            raise LLMResponseError(f"Failed to decode API JSON response: {e}") from e
        except (KeyError, IndexError, TypeError) as e:
             logger.error(f"Failed to parse expected data from Bailian API response. Response: {response_data}. Error: {e}", exc_info=True)
             raise LLMResponseError(f"Unexpected API response structure: {e}") from e

    async def _chat_completion_stream(
        self,
        request_body: Dict[str, Any], # Changed parameters
        timeout: float                # Changed parameters
    ) -> AsyncGenerator[Tuple[str, str, Optional[ChatModelUsage]], None]:
        """调用阿里百炼 /chat/completions API (流式)。"""
        api_url = f"{self.api_base}/chat/completions"
        # Removed request_body creation, now passed as argument

        logger.debug(f"Calling Bailian API (stream): {api_url} with model {self.model_id}")

        final_usage: Optional[ChatModelUsage] = None
        client = httpx.AsyncClient(timeout=timeout)

        try:
            async with client.stream("POST", api_url, headers=self.headers, json=request_body) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                     error_detail = await e.response.aread()
                     try:
                         error_json = json.loads(error_detail.decode())
                         error_message = error_json.get('error', {}).get('message', error_detail.decode())
                     except Exception:
                         error_message = error_detail.decode() if error_detail else str(e)
                     logger.error(f"Bailian API returned error status {e.response.status_code} from {api_url} during stream: {error_message}")
                     raise LLMAPIError(f"API returned status {e.response.status_code}: {error_message}") from e

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    logger.debug(f"Received line from Bailian API(stream): {line}")

                    line_prefix = "data:"
                    if line.startswith(line_prefix):
                        data_str = line[len(line_prefix):].strip()
                        if data_str == "[DONE]":
                            logger.debug("Bailian stream finished.")
                            break

                        try:
                            chunk_data = json.loads(data_str)

                            choices = chunk_data.get('choices', [])
                            if choices:
                                choice = choices[0]
                                delta = choice.get('delta')
                                if delta:
                                    content_delta = delta.get('content')
                                    reasoning_delta = delta.get('reasoning_content')
                                    if content_delta or reasoning_delta:
                                        yield (content_delta, reasoning_delta, None)

                            usage_data = chunk_data.get('usage')
                            if usage_data and 'prompt_tokens' in usage_data and 'completion_tokens' in usage_data:
                                logger.debug(f"Received usage info: {usage_data}")
                                final_usage = ChatModelUsage(
                                    model_id=chunk_data.get('model', self.model_id),
                                    input_tokens=usage_data['prompt_tokens'],
                                    output_tokens=usage_data['completion_tokens']
                                )

                        except json.JSONDecodeError:
                            logger.error(f"Failed to decode JSON from stream chunk: {data_str}")
                            raise LLMResponseError(f"Failed to decode stream JSON chunk: {data_str}")
                        except (KeyError, IndexError, TypeError) as e:
                            logger.error(f"Failed to parse expected data from stream chunk: {data_str}. Error: {e}", exc_info=True)
                            raise LLMResponseError(f"Unexpected stream chunk structure: {e}. Chunk: {data_str}") from e
                    else:
                         logger.warning(f"Received unexpected line in stream (not starting with 'data:'): {line}")

        except httpx.TimeoutException as e:
            logger.error(f"Bailian API stream request timed out to {api_url}: {e}")
            raise LLMAPIError(f"Stream request timed out after {timeout}s: {e}") from e
        except httpx.RequestError as e:
            logger.error(f"Bailian API stream request error to {api_url}: {e}")
            raise LLMAPIError(f"Stream request failed: {e}") from e
        finally:
            await client.aclose()

        if final_usage:
             yield ("", "", final_usage)
