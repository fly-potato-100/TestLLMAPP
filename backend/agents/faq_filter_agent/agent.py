import json
import logging
import os # Added os import
from typing import List, Dict, Any, Optional

# Import the necessary classes from other modules
# Use relative import based on project structure
from .data_parser import FAQDataParser
from .llm_clients import QueryRewriteClient, FAQClassifierClient
from ...models.chat import ChatRequest, ChatResponse, ChatCandidate, ChatModelUsages # Adjusted import path
from . import config # Import config module
from .exceptions import ConfigurationError, PromptLoadError # Import custom exceptions

# TODO: Consider adding custom exceptions from exceptions.py

# Setup logger for this module
logger = logging.getLogger(__name__)

# Determine the directory of the current agent.py file
# This helps resolve relative paths in config.py correctly
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

class FAQFilterAgent:
    """AI Agent 的主入口和协调器。"""

    def __init__(self, context_params: Dict[str, Any] = None):
        """初始化 Agent，从 config.py 加载配置并创建依赖项。"""
        logger.info("Initializing FAQFilterAgent...")

        try:
            # Load configuration
            # Assuming config defines paths relative to the 'faq_filter_agent' directory
            cfg = config.load_configuration()

            # Resolve absolute paths for files based on AGENT_DIR
            faq_file_path = os.path.join(AGENT_DIR, cfg['faq_file_path'])
            if context_params is not None and context_params.get('channel_name') is not None:
                channel_name = context_params['channel_name']
                # 同目录下查看是否存在指定channel的faq文件
                channel_specific_faq_file_path = faq_file_path.replace('.json', f'-{channel_name}.json')
                if os.path.exists(channel_specific_faq_file_path):
                    faq_file_path = channel_specific_faq_file_path
                else:
                    logger.debug(f"Channel-specific FAQ file not found: {channel_specific_faq_file_path}")
                    logger.debug(f"Using default FAQ file: {faq_file_path}")
            rewrite_prompt_path = os.path.join(AGENT_DIR, cfg['rewrite_prompt_path'])
            classify_prompt_path = os.path.join(AGENT_DIR, cfg['classify_prompt_path'])

            # Load prompts
            try:
                with open(rewrite_prompt_path, 'r', encoding='utf-8') as f:
                    rewrite_prompt = f.read()
                with open(classify_prompt_path, 'r', encoding='utf-8') as f:
                    classify_prompt = f.read()
                logger.debug("Successfully loaded prompt files.")
            except FileNotFoundError as e:
                logger.error(f"Prompt file not found: {e}")
                raise PromptLoadError(f"Required prompt file not found: {e}") from e
            except IOError as e:
                 logger.error(f"Error reading prompt file: {e}")
                 raise PromptLoadError(f"Could not read prompt file: {e}") from e

            # Initialize components
            self.faq_parser = FAQDataParser(faq_file_path=faq_file_path)
            self.rewrite_client = QueryRewriteClient(
                api_key=cfg['rewrite_api_key'],
                api_base=cfg['rewrite_api_base'],
                model_name=cfg['rewrite_model'],
                prompt_template=rewrite_prompt
            )
            self.classifier_client = FAQClassifierClient(
                api_key=cfg['classify_api_key'],
                api_base=cfg['classify_api_base'],
                model_name=cfg['classify_model'],
                prompt_template=classify_prompt
            )
            logger.info("FAQFilterAgent initialized successfully.")

        except KeyError as e:
            logger.error(f"Missing configuration key: {e}")
            raise ConfigurationError(f"Missing required configuration key: {e}") from e
        except (ConfigurationError, PromptLoadError) as e:
            # Re-raise exceptions related to config/prompt loading
            logger.error(f"Failed to initialize FAQFilterAgent due to error: {e}")
            raise
        except Exception as e:
            # Catch any other unexpected errors during initialization
            logger.exception(f"Unexpected error during FAQFilterAgent initialization: {e}")
            raise ConfigurationError(f"An unexpected error occurred during agent initialization: {e}") from e

    async def process_user_request(self, chat_request: ChatRequest) -> ChatResponse:
        """处理用户请求的完整流程。

        Args:
            chat_request: 包含对话历史和上下文信息的请求对象。

        Returns:
            一个包含响应文本和会话 ID 的响应对象。
        """
        logger.info(f"--- FAQFilterAgent: process_user_request called (Session ID: {chat_request.session_id}) ---")


        # Extract conversation history and context from ChatRequest
        # Convert ChatInputMessage objects to the dict format expected by rewrite_client
        conversation_dicts = [{"role": msg.role, "content": msg.content} for msg in chat_request.conversation]
        context = chat_request.context_params or {} # Use context_params if available

        # Prepare input data for the rewrite client
        rewrite_input_data = {
            "conversation": conversation_dicts,
            "context": context
        }

        # 1. 查询重写 (Query Rewrite)
        try:
            rewritten_data, rewritten_usage = await self.rewrite_client.rewrite_query(input_data=rewrite_input_data)
            if not rewritten_data or 'query_rewrite' not in rewritten_data:
                logger.error("Failed to rewrite query: LLM did not return expected 'query_rewrite' field.")
                # TODO: Handle rewrite failure more gracefully
                return ChatResponse(
                    response_text="Failed to understand the query context.",
                    session_id=chat_request.session_id
                )

            rewritten_query = rewritten_data['query_rewrite']
            rewrite_reason = rewritten_data.get('reason', 'N/A')
            logger.info(f"Rewritten Query: {rewritten_query}")
            logger.info(f"Rewrite Reason: {rewrite_reason}")

        except Exception as e: # Catch potential errors during rewrite API call
             logger.exception(f"Error during query rewrite: {e}")
             return ChatResponse(
                 response_text="An error occurred while processing your query context.",
                 session_id=chat_request.session_id
             )

        # 2. 获取 FAQ 目录结构
        try:
            faq_structure_md = self.faq_parser.get_category_structure_markdown()
            if not faq_structure_md:
                 logger.error("Failed to get FAQ structure: Parser returned empty structure.")
                 # TODO: Handle FAQ loading/parsing failure
                 return ChatResponse(
                     response_text="Failed to load internal knowledge base.",
                     session_id=chat_request.session_id
                 )
        except Exception as e:
            logger.exception(f"Error getting FAQ structure: {e}")
            return ChatResponse(
                 response_text="An error occurred accessing internal knowledge base.",
                 session_id=chat_request.session_id
            )

        # 3. 问题分类 (Classification)
        try:
            classification_data, classification_usage = await self.classifier_client.classify_query(rewritten_query, faq_structure_md)
            if not classification_data or 'category_key_path' not in classification_data:
                logger.error("Failed to classify query: LLM did not return expected 'category_key_path' field.")
                # TODO: Handle classification failure
                return ChatResponse(
                    response_text="Failed to classify the query. Wrong-format response from LLM.",
                    session_id=chat_request.session_id
                )

            category_key_path = classification_data['category_key_path']
            classification_reason = classification_data.get('reason', 'N/A')
            logger.info(f"Classification Path: {category_key_path}")
            logger.info(f"Classification Reason: {classification_reason}")
        except Exception as e:
            logger.exception(f"Error during query classification: {e}")
            return ChatResponse(
                 response_text="An error occurred while classifying your query.",
                 session_id=chat_request.session_id
             )

        # 4. 答案检索
        try:
            # Attempt to get the answer using the classified path
            final_answer, breadcrumb_str = self.faq_parser.get_answer_by_key_path(category_key_path)
        except Exception as e:
             logger.exception(f"Error during answer retrieval for path '{category_key_path}': {e}")
             return ChatResponse(
                  response_text="An error occurred while retrieving the answer.",
                  session_id=chat_request.session_id
              )
        
        # 5. 返回结果
        # 定义保底答案
        fallback_answer = "<保底话术>未找到具体答案。"
        # 将所有使用量合并到usages中
        usages = ChatModelUsages(models=[rewritten_usage, classification_usage])
        if breadcrumb_str is not None:
            # breadcrumb_str不为空表明类别键路径是有效的，但未匹配到具体答案
            logger.info(f"Retrieved Answer by path: {breadcrumb_str}, answer_size: { 'N/A' if final_answer is None else len(final_answer)}") # Log snippet
            final_answer = final_answer or fallback_answer
            candidate = ChatCandidate(
                content=final_answer, 
                score=1.0, 
                reason=f"分类路径：{category_key_path}（{breadcrumb_str}）\n分类依据：{classification_reason}"
                )
            return ChatResponse(
                response_text=json.dumps([candidate.model_dump()]),
                session_id=chat_request.session_id,
                usages=usages
            )
        else:
            # 未找到具体答案
            logger.info("No specific answer found for the query.")
            candidate = ChatCandidate(
                content=fallback_answer, 
                score=0.0, 
                reason=f"依据：{classification_reason}"
            )
            return ChatResponse(
                response_text=json.dumps([candidate.model_dump()]),
                session_id=chat_request.session_id,
                usages=usages
            )   