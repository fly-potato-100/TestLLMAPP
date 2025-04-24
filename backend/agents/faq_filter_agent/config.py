"""Configuration for the Custom Agent module."""

# Example configuration variables (replace with actual loading mechanism e.g., environment variables, .env file)
import os
import logging
# --- LLM Client Configurations ---

from dotenv import load_dotenv
load_dotenv()

# Query Rewrite LLM
REWRITE_API_KEY = os.getenv("VOLCANO_API_KEY", "YOUR_API_KEY")
REWRITE_API_BASE = os.getenv("VOLCANO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
REWRITE_MODEL_NAME = os.getenv("VOLCANO_MODEL", "doubao-1-5-pro-32k-250115")

# FAQ Classifier LLM (Volcano)
CLASSIFY_API_KEY = os.getenv("VOLCANO_API_KEY", "YOUR_API_KEY") # Or specific Volcano env var like VOLC_ACCESS_KEY
CLASSIFY_API_BASE = os.getenv("VOLCANO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3") # Example Volcano endpoint
CLASSIFY_MODEL_NAME = os.getenv("VOLCANO_MODEL", "doubao-1-5-pro-32k-250115") # Example Doubao model

# --- Data and Prompt Paths ---
# Consider making these paths relative to the agent module or configurable
FAQ_FILE_PATH = os.getenv("FAQ_FILE_PATH", "./data/faq_doc.json") # Relative to agent.py if run directly
REWRITE_PROMPT_PATH = os.getenv("REWRITE_PROMPT_PATH", "./prompts/rewrite_prompt.md")
CLASSIFY_PROMPT_PATH = os.getenv("CLASSIFY_PROMPT_PATH", "./prompts/classify_prompt.md")

# --- Other Settings ---
# LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# You might want to add functions here to load config from different sources

def load_configuration():
    """Placeholder function to demonstrate loading config."""
    # In a real app, this might load from .env, validate, etc.
    config = {
        "rewrite_api_key": REWRITE_API_KEY,
        "rewrite_api_base": REWRITE_API_BASE,
        "rewrite_model": REWRITE_MODEL_NAME,
        "classify_api_key": CLASSIFY_API_KEY,
        "classify_api_base": CLASSIFY_API_BASE,
        "classify_model": CLASSIFY_MODEL_NAME,
        "faq_file_path": FAQ_FILE_PATH,
        "rewrite_prompt_path": REWRITE_PROMPT_PATH,
        "classify_prompt_path": CLASSIFY_PROMPT_PATH,
    }
    # Basic check for placeholder keys
    if "YOUR_API_KEY" in config["rewrite_api_key"] or \
       "YOUR_API_KEY" in config["classify_api_key"]:
        rewrite_api_key = config["rewrite_api_key"]
        classify_api_key = config["classify_api_key"]
        logging.warning(f"API keys seem to be placeholders in config.py. Please configure them properly. rewrite_api_key: {rewrite_api_key}, classify_api_key: {classify_api_key}")
    return config

# Example of loading config when the module is imported (optional)
# loaded_config = load_configuration() 