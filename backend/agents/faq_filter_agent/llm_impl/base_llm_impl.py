import abc
import logging
from typing import List, Dict, Any, Tuple, Optional

from backend.models.chat import ChatModelUsage # 保持对通用模型的引用
from ..exceptions import LLMAPIError, LLMResponseError # 引用上层目录的 exceptions

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests
DEFAULT_TIMEOUT = 60.0

class BaseLLMImpl(abc.ABC):
    """与 LLM 服务交互的抽象基类。"""

    @abc.abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        timeout: float = DEFAULT_TIMEOUT,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None # For JSON mode
    ) -> Tuple[str, ChatModelUsage, Dict[str, Any]]:
        """
        与 LLM 进行聊天补全交互的核心方法。

        Args:
            messages: 对话消息列表，格式遵循 OpenAI 风格 [{ "role": "user/system/assistant", "content": "..." }]。
            timeout: 请求超时时间 (秒)。
            temperature: 控制生成文本的随机性。
            top_p: 控制核心采样的概率阈值。
            max_tokens: 生成响应的最大 token 数量。
            response_format: 指定响应格式，例如 {"type": "json_object"}。

        Returns:
            Tuple[str, ChatModelUsage, Dict[str, Any]]: 一个包含以下内容的元组:
                - 响应消息的内容 (str)
                - 包含模型ID和token使用量的 ChatModelUsage 对象
                - 原始的API响应字典 (Dict[str, Any])

        Raises:
            LLMAPIError: 如果 API 调用失败 (网络错误, 超时, 服务端错误等)。
            LLMResponseError: 如果 API 响应格式不正确或无法解析。
        """
        raise NotImplementedError

    def remove_json_wrapper(self, content: str) -> str:
        """
        (可选实现) 从 LLM 返回的内容中移除可能的 markdown JSON 包裹。
        子类可以根据需要覆盖或使用此默认实现。
        """
        content = content.strip()
        if content.startswith('```json') and content.endswith('```'):
            logger.debug("Removing ```json wrapper from LLM response.")
            return content[len('```json'):-len('```')].strip()
        elif content.startswith('```') and content.endswith('```'):
            logger.debug("Removing ``` wrapper from LLM response.")
            return content[len('```'):-len('```')].strip()
        return content 