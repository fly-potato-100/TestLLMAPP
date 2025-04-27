import json
import logging
import os
import sys # Added for stderr output
import argparse # Added for command-line parsing
from typing import List, Dict, Any, Optional, Tuple # Added Tuple
from .exceptions import FAQDataError # Import custom exception

logger = logging.getLogger(__name__)

# TODO: Consider adding custom exceptions from exceptions.py

class FAQDataParser:
    """负责加载、解析和查询 FAQ JSON 数据。"""

    def __init__(self, faq_file_path: str):
        """初始化解析器，加载 FAQ 数据。

        Args:
            faq_file_path: faq_doc.json 文件的路径。

        Raises:
            FAQDataError: 如果加载或解析 FAQ 数据时出错。
        """
        self.faq_file_path = faq_file_path
        self.faq_data: List[Dict[str, Any]] = self._load_faq()

    def _load_faq(self) -> List[Dict[str, Any]]:
        """从 JSON 文件加载 FAQ 数据。"""
        # Check if file exists first for a clearer error message
        if not os.path.exists(self.faq_file_path):
            logger.error(f"FAQ file not found: {self.faq_file_path}")
            raise FAQDataError(f"FAQ file not found: {self.faq_file_path}")

        try:
            with open(self.faq_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                logger.error(f"FAQ data in {self.faq_file_path} is not a list.")
                raise FAQDataError("FAQ data structure is invalid: root element must be a list.")
            logger.debug(f"Successfully loaded FAQ data from {self.faq_file_path}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {self.faq_file_path}: {e}")
            raise FAQDataError(f"Failed to decode JSON from file: {e}") from e
        except IOError as e:
            logger.error(f"Error reading FAQ file {self.faq_file_path}: {e}")
            raise FAQDataError(f"Failed to read FAQ file: {e}") from e
        except Exception as e: # Catch unexpected errors
            logger.exception(f"An unexpected error occurred while loading FAQ file {self.faq_file_path}: {e}") # Use logger.exception for traceback
            raise FAQDataError(f"An unexpected error occurred: {e}") from e

    def get_category_structure_markdown(self, max_depth: int = -1) -> str:
        """生成 Markdown 格式的 FAQ 目录结构字符串。

        Args:
            max_depth: 最大递归层数。-1 表示无限制，正整数 n 表示最大生成 n 层目录。
                       例如，max_depth=1 只生成顶级目录，max_depth=2 生成顶级和二级目录。

        Returns:
            Markdown 格式的目录结构字符串。
        """
        logger.debug(f"Generating category structure markdown with max_depth={max_depth}")
        markdown_structure = self._generate_markdown_recursive(self.faq_data, 0, max_depth)
        logger.debug("Generated category structure markdown.")
        return markdown_structure

    def _generate_markdown_recursive(self, categories: List[Dict[str, Any]], indent_level: int, max_depth: int) -> str:
        """递归辅助函数，生成 Markdown 结构。

        Args:
            categories: 当前层级的 FAQ 类别列表。
            indent_level: 当前的缩进层级 (0-based)。
            max_depth: 最大递归层数限制。

        Returns:
            当前层级及其子层级的 Markdown 结构字符串。
        """
        markdown_str = ""
        indent = "  " * indent_level # 两个空格的缩进
        for category in categories:
            key = category.get('category_key', '?')
            desc = category.get('category_desc', 'N/A')
            markdown_str += f"{indent}- {key}: {desc}\n"

            # Check if sub_category exists and is a non-empty list before recursing
            sub_categories = category.get("sub_category")

            # Recurse only if sub_categories exist and we haven't reached max_depth
            # max_depth == -1 means no limit
            # indent_level + 1 < max_depth means the next level is within the limit
            if isinstance(sub_categories, list) and sub_categories and (max_depth == -1 or indent_level + 1 < max_depth):
                markdown_str += self._generate_markdown_recursive(sub_categories, indent_level + 1, max_depth)
            elif isinstance(sub_categories, list) and sub_categories and max_depth != -1 and indent_level + 1 >= max_depth:
                 # Log a debug message if recursion is stopped due to max_depth
                 logger.debug(f"Stopped recursion at indent_level {indent_level} for category key {key} due to max_depth limit {max_depth}.")

        return markdown_str

    def get_answer_by_key_path(self, key_path: str) -> Tuple[Optional[str], Optional[str]]:
        """根据类别键路径 (e.g., '1.1.2') 查找并返回答案和描述路径。

        Args:
            key_path: LLM 返回的类别键路径字符串。

        Returns:
            一个元组 (answer, description_path)，其中：
            - answer: 对应的答案字符串，如果找不到则为 None。
            - description_path: 'desc1 >>> desc2' 格式的路径字符串，如果路径无效则为 None。
        """
        logger.debug(f"Attempting to find answer and path for key path: {key_path}")
        # desc_trail: List[str] = [] # Removed, trail stored with nodes now
        # breadcrumb_str: Optional[str] = None # Removed

        if not key_path or not isinstance(key_path, str) or len(key_path) == 0:
             logger.warning(f"Invalid key_path received: {key_path}")
             return None, None

        if key_path == "0":
            logger.debug("Key path '0' received, indicating no specific category match.")
            return None, None # 表示未匹配特定类别, 路径也无意义

        keys = key_path.split('.')
        current_level_data = self.faq_data
        # Store nodes and trails encountered during descent
        visited_nodes_with_trails: List[Tuple[Dict[str, Any], List[str]]] = []
        target_node: Optional[Dict[str, Any]] = None # Last successfully matched node before potential .0
        current_desc_trail: List[str] = [] # Trail to the current node during iteration


        try:
            for i, key_str in enumerate(keys):
                if not key_str.isdigit(): # Ensure key is a digit string
                    logger.warning(f"Invalid non-digit key '{key_str}' found in path '{key_path}'")
                    return None, None # Invalid path
                key = int(key_str) # Convert after check

                # Handle .0 ending: Start upward search from parent
                if key == 0:
                    # 到达 .0 结尾，表示父级匹配但子级不匹配
                    if i == len(keys) - 1:
                        logger.debug(f"Path '{key_path}' ends with '.0'. Searching ancestors for answer.")
                        # Start searching upwards from the parent (last visited node)
                        for node, trail in reversed(visited_nodes_with_trails):
                            answer = node.get("answer")
                            if answer is not None:
                                breadcrumb_str = " >>> ".join(trail) + " >>> N/A"
                                logger.debug(f"Found answer in ancestor '{breadcrumb_str}' for path '{key_path}'.")
                                return answer, breadcrumb_str
                        # No answer found in any ancestor
                        logger.warning(f"No answer found in ancestor path for key path ending in .0: {key_path}")
                        # Return None for answer, and None for path as no answer was located.
                        breadcrumb_str = " >>> ".join(current_desc_trail) + " >>> N/A"
                        return None, breadcrumb_str
                    else:
                        # Intermediate .0 like '1.0.2' is invalid
                        logger.warning(f"Invalid path '{key_path}' with intermediate '.0'.")
                        return None, None # Invalid path

                # Normal key processing (non-zero)
                found_in_level = False
                for item in current_level_data:
                    item_key = item.get('category_key')
                    if item_key is None:
                        # logger.debug(f"Skipping item without 'category_key' while processing path '{key_path}'. Item: {item}")
                        continue # Skip items without a key

                    try:
                        item_key_int = int(item_key)
                    except (ValueError, TypeError):
                        logger.warning(f"Non-integer category_key '{item_key}' found in data structure while processing path '{key_path}'. Skipping item.")
                        continue

                    if item_key_int == key:
                        target_node = item # Keep track of the node for this key
                        current_desc_trail.append(item.get('category_desc', 'N/A')) # Add desc to trail for this level
                        # Store this node and its *current* trail snapshot before potentially descending further
                        visited_nodes_with_trails.append((target_node, list(current_desc_trail)))

                        sub_categories = item.get("sub_category")

                        if isinstance(sub_categories, list) and sub_categories:
                             current_level_data = sub_categories # Descend into subcategories
                        elif i < len(keys) - 1: # More keys remaining, but no subcategories found here
                             logger.warning(f"Path '{key_path}' expects subcategories at key '{key}', but none exist or are not a list.")
                             # Path is invalid as it requests deeper level that doesn't exist
                             breadcrumb_str = " >>> ".join(current_desc_trail) + " >>> N/A"
                             return None, breadcrumb_str

                        found_in_level = True
                        break # Found the matching item for this level

                if not found_in_level:
                    logger.warning(f"Key '{key}' not found at level {i} for path '{key_path}'.")
                    breadcrumb_str = " >>> ".join(current_desc_trail) + " >>> N/A"
                    return None, breadcrumb_str

            # Successfully traversed the *entire non-.0* path
            # target_node holds the final node, current_desc_trail holds its path
            final_breadcrumb_str = " >>> ".join(current_desc_trail) if current_desc_trail else None
            if target_node and "answer" in target_node:
                 answer = target_node["answer"]
                 logger.debug(f"Found direct answer for key path '{key_path}'. Trail: '{final_breadcrumb_str}'")
                 return answer, final_breadcrumb_str
            else:
                 # Reached a node without an answer (and path didn't end in .0)
                 logger.warning(f"Path '{key_path}' leads to a node without an 'answer' field. Trail: '{final_breadcrumb_str}'. Node: {target_node}")
                 # Return None for answer, but the path to the node is still valid
                 return None, final_breadcrumb_str

        except Exception as e: # Catch unexpected errors during traversal
            logger.exception(f"An unexpected error occurred while processing path '{key_path}': {e}")
            return None, None
