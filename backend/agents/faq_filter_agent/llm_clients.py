import json
import logging
import jinja2
from typing import List, Dict, Any, Tuple, Optional

# Removed unused imports like httpx, asyncio, sys, os, argparse
# from .exceptions import LLMAPIError, LLMResponseError # Keep exceptions
from backend.models.chat import ChatModelUsage # Keep chat model usage
from .exceptions import LLMAPIError, LLMResponseError
# 导入基类和常量，现在从 llm_impl 包导入
from .llm_impl.base_llm_impl import BaseLLMImpl, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests - Defined in base_llm_impl now
# DEFAULT_TIMEOUT = 60.0

# --- VolcanoLLMClient class removed ---
# class VolcanoLLMClient:
#    ... (Old code removed) ...
#
#    async def _call_api(...):
#        ... (Old code removed) ...
#
#    def remove_json_wrapper(...):
#        ... (Old code removed) ...


class QueryRewriteClient: # 不再继承 VolcanoLLMClient
    """使用配置的 LLM 实现异步重写查询。"""

    def __init__(self, llm_client: BaseLLMImpl, prompt_template: str): # Updated type hint
        """初始化客户端。

        Args:
            llm_client: 一个实现了 BaseLLMImpl 接口的实例。
            prompt_template: rewrite_prompt.md 的内容模板。
        """

        self.llm_client = llm_client # 存储 LLM 客户端实例
        self.prompt_template = prompt_template
        # 注意：不再需要 super().__init__()

    async def rewrite_query(
        self,
        input_data: Dict[str, Any],
        timeout: float = DEFAULT_TIMEOUT
    ) -> Tuple[Dict[str, Any], ChatModelUsage]:
        """异步调用 LLM API 来重写查询。

        Args:
            input_data: 包含 'conversation' 和 'context' 的字典。
            timeout: 请求超时时间 (秒)。

        Returns:
            Tuple[Dict[str, Any], ChatModelUsage]: 包含 'query_rewrite' 和 'reason' 的字典及 ChatModelUsage。

        Raises:
            LLMAPIError: 如果 API 调用失败。
            LLMResponseError: 如果输入数据无效、提示格式化失败或 API 响应格式不正确。
        """
        # 1. 准备 Prompt (与之前类似)
        try:
            conversation = input_data.get('conversation')
            context = input_data.get('context')

            if not isinstance(conversation, list):
                logger.error(f"Invalid 'conversation' format: Expected list, got {type(conversation)}")
                raise LLMResponseError("Invalid input data: 'conversation' must be a list.")
            if not isinstance(context, dict):
                 logger.error(f"Invalid 'context' format: Expected dict, got {type(context)}")
                 raise LLMResponseError("Invalid input data: 'context' must be a dictionary.")

            system_prompt_content = self.prompt_template
            messages = [
                {"role": "system", "content": system_prompt_content},
                {"role": "user", "content": json.dumps(input_data, ensure_ascii=False)}
            ]

        except LLMResponseError:
            raise
        except Exception as e:
            logger.error(f"Error preparing data for query rewrite: {e}", exc_info=True)
            raise LLMAPIError(f"Failed to prepare data for rewrite: {e}") from e

        # 2. 调用传入的 LLM 客户端的 chat_completion 方法
        try:
            content, usage, _ = await self.llm_client.chat_completion( # 调用注入的客户端实例
                messages=messages,
                timeout=timeout,
                temperature=0.1, # Low temp for deterministic rewrite
                response_format={"type": "json_object"} # Request JSON
            )
        except (LLMAPIError, LLMResponseError):
             raise # Re-raise API or response errors
        except Exception as e:
             # Log the specific LLM client implementation type for better debugging
             client_type = type(self.llm_client).__name__
             logger.exception(f"Unexpected error calling rewrite API via {client_type}: {e}")
             raise LLMAPIError(f"Unexpected error during API call via {client_type}: {e}") from e

        # 3. 解析响应 (与之前类似)
        try:
            # 注意：chat_completion 返回的 content 已经是移除 wrapper 后的
            result = json.loads(content)
            if not isinstance(result, dict) or 'query_rewrite' not in result or 'reason' not in result:
                logger.error(f"Query rewrite response JSON content is malformed. Parsed: {result}, Original Content from LLM: '{content}'")
                raise LLMResponseError("LLM response content is not the expected rewrite JSON format.")

            # 获取模型 ID 从 usage 对象
            model_id = usage.model_id if usage else "unknown"
            logger.info(f"Successfully rewrote query using model {model_id} via {type(self.llm_client).__name__}.")
            return result, usage

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from query rewrite response content: '{content}'. Error: {e}")
            raise LLMResponseError(f"Failed to decode JSON from LLM rewrite response: {e}. Content: '{content}'") from e
        except Exception as e: # Catch any other parsing errors
             logger.error(f"Error parsing rewrite response: {e}. Content: '{content}'", exc_info=True)
             raise LLMResponseError(f"Error parsing rewrite response: {e}") from e


class FAQClassifierClient: # 不再继承 VolcanoLLMClient
    """使用配置的 LLM 实现异步进行问题分类。"""

    def __init__(self, llm_client: BaseLLMImpl, prompt_template: str): # Updated type hint
        """初始化客户端。

        Args:
            llm_client: 一个实现了 BaseLLMImpl 接口的实例。
            prompt_template: classify_prompt.md 的内容模板 (Jinja2 格式)。
        """

        self.llm_client = llm_client # 存储 LLM 客户端实例
        self.prompt_template_str = prompt_template # Store the raw template string
        # Pre-compile the Jinja2 template
        try:
            self.jinja_template = jinja2.Template(self.prompt_template_str)
        except jinja2.exceptions.TemplateSyntaxError as e:
             logger.error(f"Invalid Jinja2 template syntax: {e}")
             raise LLMResponseError(f"Invalid Jinja2 template syntax: {e}") from e
        # 注意：不再需要 super().__init__()

    async def classify_query(
        self,
        rewritten_query: str,
        faq_structure_md: str,
        timeout: float = DEFAULT_TIMEOUT
    ) -> Tuple[List[Dict[str, Any]], ChatModelUsage]: # 返回类型调整为 List of Dicts
        """异步调用 LLM API 对重写后的查询进行分类。

        Args:
            rewritten_query: 重写后的查询字符串。
            faq_structure_md: Markdown 格式的 FAQ 目录结构。
            timeout: 请求超时时间 (秒)。

        Returns:
            Tuple[List[Dict[str, Any]], ChatModelUsage]: 包含分类结果 ({'category_key_path', 'reason'}) 的列表及 ChatModelUsage。

        Raises:
            LLMAPIError: 如果 API 调用失败。
            LLMResponseError: 如果提示格式化失败或 API 响应格式不正确。
        """
        # 1. 构建 Prompt using Jinja2 (与之前类似)
        try:
            system_prompt_content = self.jinja_template.render(faq_structure=faq_structure_md, faq_retrieve_num=3)
            messages = [
                {"role": "system", "content": system_prompt_content},
                {"role": "user", "content": rewritten_query}
            ]
        except jinja2.exceptions.UndefinedError as e:
             logger.error(f"Jinja2 rendering error: Undefined variable {e}.", exc_info=True)
             raise LLMResponseError(f"Failed to render classification prompt: Undefined variable {e}.") from e
        except Exception as e:
            logger.error(f"Error preparing prompt for FAQ classification: {e}", exc_info=True)
            raise LLMResponseError(f"Failed to prepare classification prompt: {e}") from e

        # 2. 调用传入的 LLM 客户端的 chat_completion 方法
        try:
            content, usage, _ = await self.llm_client.chat_completion( # 调用注入的客户端实例
                messages=messages,
                timeout=timeout,
                temperature=0.1, # Low temp for classification
                response_format={"type": "json_object"} # Request JSON
            )
        except (LLMAPIError, LLMResponseError):
            raise # Re-raise API or response errors
        except Exception as e:
             client_type = type(self.llm_client).__name__
             logger.exception(f"Unexpected error calling classification API via {client_type}: {e}")
             raise LLMAPIError(f"Unexpected error during API call via {client_type}: {e}") from e

        # 3. 解析响应 (与之前类似)
        try:
            # content 已经是移除 wrapper 后的
            results = json.loads(content)

            # 验证返回的是列表，且列表内元素符合预期格式
            if not isinstance(results, list) or not all(
                isinstance(item, dict) and
                'category_key_path' in item and isinstance(item['category_key_path'], str) and
                'reason' in item and isinstance(item['reason'], str)
                for item in results
            ):
                logger.error(f"FAQ classification response JSON content is malformed. Expected list of {{'category_key_path': str, 'reason': str}}. Parsed: {results}. Original Content from LLM: '{content}'")
                raise LLMResponseError("LLM response content is not the expected classification JSON format (list of {category_key_path, reason}).")

            model_id = usage.model_id if usage else "unknown"
            paths = ', '.join([item.get('category_key_path', 'N/A') for item in results])
            logger.info(f"Successfully classified query using model {model_id} via {type(self.llm_client).__name__}. Paths: {paths}")
            return results, usage # 直接返回解析后的列表

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from FAQ classification response content: '{content}'. Error: {e}")
            raise LLMResponseError(f"Failed to decode JSON from LLM classification response: {e}. Content: '{content}'") from e
        except Exception as e: # Catch any other parsing errors
             logger.error(f"Error parsing classification response: {e}. Content: '{content}'", exc_info=True)
             raise LLMResponseError(f"Error parsing classification response: {e}") from e
