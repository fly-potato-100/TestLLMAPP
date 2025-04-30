"""Configuration for the Custom Agent module."""

# Example configuration variables (replace with actual loading mechanism e.g., environment variables, .env file)
import os
import logging
# --- LLM Client Configurations ---

from dotenv import load_dotenv
load_dotenv()

# You might want to add functions here to load config from different sources

class Config:
    def __init__(self):
        self.volcano_api_key = os.getenv("VOLCANO_API_KEY", "YOUR_API_KEY")
        self.volcano_api_base = os.getenv("VOLCANO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
        self.volcano_model = os.getenv("VOLCANO_MODEL", "doubao-1-5-pro-32k-250115")
        self.bailian_api_key = os.getenv("BAILIAN_API_KEY", "YOUR_API_KEY")
        self.bailian_api_base = os.getenv("BAILIAN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.bailian_model = os.getenv("BAILIAN_MODEL", "qwen-plus")
        self.faq_file_path = os.getenv("FAQ_FILE_PATH", "./backend/agents/faq_filter_agent/data/faq_doc.json")
        self.rewrite_prompt_path = os.getenv("REWRITE_PROMPT_PATH", "./backend/agents/faq_filter_agent/prompts/rewrite_prompt.md")
        self.classify_prompt_path = os.getenv("CLASSIFY_PROMPT_PATH", "./backend/agents/faq_filter_agent/prompts/classify_prompt.md")

    def get_model_config(self, model_platform: str):
        if model_platform == "volcano":
            return self.volcano_api_key, self.volcano_api_base, self.volcano_model
        elif model_platform == "bailian":
            return self.bailian_api_key, self.bailian_api_base, self.bailian_model
        else:
            raise ValueError(f"Invalid model platform: {model_platform}")

def load_configuration():
    """Placeholder function to demonstrate loading config."""
    # In a real app, this might load from .env, validate, etc.
    config = Config()
    # Basic check for placeholder keys
    if "YOUR_API_KEY" in config.volcano_api_key or \
       "YOUR_API_KEY" in config.bailian_api_key:
        volcano_api_key = config.volcano_api_key
        bailian_api_key = config.bailian_api_key
        logging.warning(f"API keys seem to be placeholders in config.py. Please configure them properly. volcano_api_key: {volcano_api_key}, bailian_api_key: {bailian_api_key}")
    return config

# Example of loading config when the module is imported (optional)
# loaded_config = load_configuration() 