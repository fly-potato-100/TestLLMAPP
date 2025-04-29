# AI Agent - 游戏客服 FAQ 筛选器

## 概述

本模块实现了一个 AI Agent，旨在根据玩家与客服的对话历史和提供的 FAQ 文档，自动筛选并返回最相关的 FAQ 答案。其核心功能是理解玩家意图，利用大型语言模型（LLM）进行问题分类，并从结构化的 FAQ 数据中检索答案。

该模块设计为可被上层服务（如 `backend/app.py`）集成使用，同时也支持独立的测试和开发。

## 核心工作流

1.  **输入**: 接收玩家与客服的对话历史 (`conversation`) 以及一些额外的上下文信息 (`context`，例如渠道、平台）。
2.  **查询重写 (Query Rewrite)**: 使用一个专门的小型 LLM，结合对话历史和上下文，将用户的原始问题重写为一个清晰、独立且包含必要背景信息的查询语句 (`query_rewrite`)。
3.  **FAQ 目录提取**: 从 `data/faq_doc.json` 文件中解析 FAQ 数据，并提取出 Markdown 格式的目录结构，其中包含类别键 (`category_key`) 和类别描述 (`category_desc`)。
4.  **问题分类 (Classification)**: 使用火山方舟 Doubao LLM，根据重写后的查询 (`query_rewrite`) 和 FAQ 目录结构，判断查询最符合哪个具体的 FAQ 类别。LLM 被要求输出一个 JSON，包含类别键路径 (`category_key_path`，例如 `1.1.2`、`1.2.0` 或 `0`) 和分类依据 (`reason`)。
5.  **答案检索**: 根据 LLM 返回的 `category_key_path`，在 `data/faq_doc.json` 中查找并提取对应的最终答案 (`answer`)。
6.  **输出**: 返回检索到的答案。如果分类失败或找不到答案，则返回相应的提示信息（错误处理在当前 Demo 阶段较为简化）。

## 主要组件

*   **`agent.py` (`FAQFilterAgent`)**: Agent 的主入口和协调器，负责编排整个工作流程。
*   **`data_parser.py` (`FAQDataParser`)**: 负责加载、解析 `data/faq_doc.json` 文件，提供获取 Markdown 目录结构和根据 `category_key_path` 查询答案的功能。
*   **`llm_clients.py`**:
    *   `QueryRewriteClient`: 封装与执行查询重写任务的小型 LLM 的 API 交互。
    *   `FAQClassifierClient`: 封装与执行问题分类任务的火山方舟 Doubao LLM 的 API 交互。
*   **`prompts/`**: 存放用于指导 LLM 的 Prompt 模板文件。
    *   `rewrite_prompt.md`: 查询重写任务的 Prompt。
    *   `classify_prompt.md`: 问题分类任务的 Prompt。
*   **`data/`**: 存放数据文件。
    *   `faq_doc.json`: 结构化的 FAQ 知识库。

## 配置

（可选）未来可能需要配置项，例如：
*   LLM API Keys 和 Endpoints。
*   FAQ 文件路径。
*   模型名称。
这些可以通过配置文件 (`config.py`)、环境变量或由调用方传入。

## 使用

上层服务（如 `backend`）可以通过导入 `FAQFilterAgent` 类并调用其处理方法（例如 `process_user_request`）来使用此模块。

## 测试

建议在 `backend/agents/faq_filter_agent/tests` 目录下为各组件编写单元测试，模拟 LLM API 调用和文件读取，以实现独立的模块测试。 