import sys
import os
import argparse
import logging
import json
import asyncio
from typing import Union, List, Dict, Optional

from dotenv import load_dotenv

# Use absolute imports assuming the script is run with -m from the project root
from backend.agents.faq_filter_agent.llm_clients import QueryRewriteClient, FAQClassifierClient, DEFAULT_TIMEOUT
from backend.agents.faq_filter_agent.llm_impl.volcano_llm_impl import VolcanoLLMImpl
from backend.agents.faq_filter_agent.llm_impl.bailian_llm_impl import BailianLLMImpl
from backend.agents.faq_filter_agent.exceptions import LLMAPIError, LLMResponseError

# Configure logging ONLY when run as a script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Determine script directory and default paths relative to this test file
script_dir = os.path.dirname(__file__)
default_env_path = os.path.join(script_dir, '..', '..', '..', '.env') # Up to backend/ then root
default_prompts_dir = os.path.join(script_dir, '..', 'prompts')

parser = argparse.ArgumentParser(description="Test Volcano LLM Clients.")
parser.add_argument(
    "client_type",
    choices=['rewrite', 'classify', 'talk'],
    help="Type of client/mode to test."
)
# Arguments for rewrite client
# parser.add_argument("--conversation-file", help="Path to JSON file containing conversation history (for rewrite). Required if client_type is 'rewrite'.")
# parser.add_argument("--context-file", help="Path to JSON file containing context info (for rewrite). Required if client_type is 'rewrite'.")
parser.add_argument("--input-file", help="Path to JSON file containing input data ('conversation' and 'context') for rewrite. Required if client_type is 'rewrite'.")
# Arguments for classify client
# parser.add_argument("--query-file", help="Path to text file containing the query to classify. Required if client_type is 'classify'.")
parser.add_argument("--query", help="The query text to classify. Required if client_type is 'classify'.")
parser.add_argument("--faq-structure-file", help="Path to text file containing the markdown FAQ structure. Required if client_type is 'classify'.")
# Common arguments
parser.add_argument("--model-platform", default='volcano', choices=['volcano', 'bailian'], help="The platform of the model to use. Required for all modes.")
parser.add_argument("--rewrite-prompt", default=os.path.join(default_prompts_dir, 'rewrite_prompt.md'), help="Path to the query rewrite prompt template file.")
parser.add_argument("--classify-prompt", default=os.path.join(default_prompts_dir, 'classify_prompt.md'), help="Path to the FAQ classification prompt template file.")
parser.add_argument("--env-file", default=default_env_path, help=f"Path to the .env file (default: {default_env_path}).")
parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="API request timeout in seconds.")
parser.add_argument("-v", "--verbose", action="store_true", help="Enable DEBUG level logging.")
# Argument for talk mode system prompt (optional)
parser.add_argument("--system-prompt", default="You are a helpful assistant.", help="System prompt to use in talk mode.")

args = parser.parse_args()

# Configure logging (moved after args parsing to use args.verbose)
if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG) # Set root logger level
    logging.info("Verbose logging enabled.")

# Load environment variables
if not os.path.exists(args.env_file):
    logging.error(f".env file not found at: {args.env_file}. Please create it or specify the path using --env-file.")
    print(f"Error: .env file not found at {args.env_file}", file=sys.stderr)
    sys.exit(1)
load_dotenv(dotenv_path=args.env_file)
logging.info(f"Loaded environment variables from: {args.env_file}")

# Load prompt templates only if needed
rewrite_prompt_template = ""
classify_prompt_template = ""
if args.client_type == 'rewrite':
    try:
        with open(args.rewrite_prompt, 'r', encoding='utf-8') as f:
            rewrite_prompt_template = f.read()
    except (FileNotFoundError, IOError) as e:
        logging.error(f"Error loading rewrite prompt {args.rewrite_prompt}: {e}")
        print(f"Error loading rewrite prompt: {e}", file=sys.stderr)
        sys.exit(1)
elif args.client_type == 'classify':
    try:
        with open(args.classify_prompt, 'r', encoding='utf-8') as f:
            classify_prompt_template = f.read()
    except (FileNotFoundError, IOError) as e:
        logging.error(f"Error loading classify prompt {args.classify_prompt}: {e}")
        print(f"Error loading classify prompt: {e}", file=sys.stderr)
        sys.exit(1)

# Function to load data from file
def load_file_content(file_path: Optional[str], is_json: bool = False) -> Union[str, List, Dict, None]:
    if not file_path:
        return None
    # Use absolute path or path relative to CWD, not script dir, for user-provided files
    # resolved_path = os.path.abspath(file_path) 
    resolved_path = file_path # Keep it simple, assume path is correct as given
    try:
        with open(resolved_path, 'r', encoding='utf-8') as f:
            if is_json:
                return json.load(f)
            else:
                return f.read().strip() # Strip leading/trailing whitespace for text files
    except FileNotFoundError:
        logging.error(f"Input file not found: {resolved_path}")
        print(f"Error: Input file not found - {resolved_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from file {resolved_path}: {e}")
        print(f"Error: Invalid JSON in file {resolved_path} - {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        logging.error(f"Error reading input file {resolved_path}: {e}")
        print(f"Error reading file {resolved_path} - {e}", file=sys.stderr)
        sys.exit(1)

async def main_test():
    result = None
    try:

        if args.model_platform == 'volcano':
            # Load common configurations from environment
            API_KEY = os.getenv("VOLCANO_API_KEY")
            API_BASE = os.getenv("VOLCANO_API_BASE")
            # Use VOLCANO_MODEL for all modes now
            VOLCANO_MODEL = os.getenv("VOLCANO_MODEL")
            llm_impl = VolcanoLLMImpl(API_KEY, API_BASE, VOLCANO_MODEL)
        elif args.model_platform == 'bailian':
            # Load common configurations from environment
            API_KEY = os.getenv("BAILIAN_API_KEY")
            API_BASE = os.getenv("BAILIAN_API_BASE")
            # Use BAILIAN_MODEL for all modes now
            BAILIAN_MODEL = os.getenv("BAILIAN_MODEL")
            llm_impl = BailianLLMImpl(API_KEY, API_BASE, BAILIAN_MODEL)
        else:
            raise ValueError(f"Invalid model platform: {args.model_platform}")
        
        if args.client_type == 'rewrite':
            # Validate args
            # if not args.conversation_file or not args.context_file:
            #     parser.error("--conversation-file and --context-file are required for rewrite client.")
            if not args.input_file:
                 parser.error("--input-file is required for rewrite client.")
            
            # Load data
            # conversation = load_file_content(args.conversation_file, is_json=True)
            # context = load_file_content(args.context_file, is_json=True)
            input_data = load_file_content(args.input_file, is_json=True)
            # if not isinstance(conversation, list) or not isinstance(context, dict):
            if not isinstance(input_data, dict) or 'conversation' not in input_data or 'context' not in input_data:
                # logging.error("Invalid format in conversation or context file (expected list and dict respectively).")
                logging.error("Invalid format in input file (expected dict with 'conversation' and 'context' keys).")
                # print("Error: Invalid format in conversation or context file.", file=sys.stderr)
                print("Error: Invalid format in input file.", file=sys.stderr)
                return # Exit async function

            # Run test
            logging.info("--- Testing QueryRewriteClient ---")
            client = QueryRewriteClient(llm_impl, rewrite_prompt_template)
            # result = await client.rewrite_query(conversation, context, timeout=args.timeout)
            result, _ = await client.rewrite_query(input_data, timeout=args.timeout)
            print("\n--- Test Result ---")
            print(json.dumps(result, indent=2, ensure_ascii=False))

        elif args.client_type == 'classify':
             # Validate args
            # if not args.query_file or not args.faq_structure_file:
            #     parser.error("--query-file and --faq-structure-file are required for classify client.")
            if not args.query or not args.faq_structure_file:
                 parser.error("--query and --faq-structure-file are required for classify client.")
            
            # Load data
            # query = load_file_content(args.query_file)
            query = args.query # Use query directly from args
            faq_structure = load_file_content(args.faq_structure_file)
            # if not isinstance(query, str) or not isinstance(faq_structure, str):
            if not isinstance(faq_structure, str): # Only need to check faq_structure now
                 # logging.error("Failed to load query or faq structure as strings.")
                 logging.error("Failed to load faq structure as string from file.")
                 # print("Error: Could not load query or FAQ structure from files.", file=sys.stderr)
                 print("Error: Could not load FAQ structure from file.", file=sys.stderr)
                 return # Exit async function

            # Run test
            logging.info("--- Testing FAQClassifierClient ---")
            client = FAQClassifierClient(llm_impl, classify_prompt_template)
            result, _ = await client.classify_query(query, faq_structure, timeout=args.timeout)
            print("\n--- Test Result ---")
            print(json.dumps(result, indent=2, ensure_ascii=False))

        elif args.client_type == 'talk':
            logging.info(f"--- Starting Talk Mode with model {args.model_platform} --- ")
            print(f"Using model: {args.model_platform}")
            print("Enter your message, or type 'quit' or 'exit' to end.")
            # Simple conversation history for talk mode (optional, could be expanded)
            # history = [] 
            # history.append({"role": "system", "content": args.system_prompt})

            #system_prompt = load_file_content(args.system_prompt)

            while True:
                try:
                    user_input = input("You: ")
                except EOFError:
                    # Handle Ctrl+D or other EOF signals gracefully
                    print("\nExiting talk mode.")
                    break
                if user_input.lower() in ['quit', 'exit']:
                     print("Exiting talk mode.")
                     break
                if not user_input:
                    continue

                # Construct messages for this turn
                # For a simple chat bot, just send the user message
                # For a more stateful chat, you would append user_input to history
                # and send the relevant part of history.
                messages = [
                    #{"role": "system", "content": system_prompt}, # Optional system prompt
                    {"role": "user", "content": user_input}
                ]
                # messages = history + [{"role": "user", "content": user_input}]
                
                print("...calling API...")
                try:
                    # Call API without requesting JSON format
                    assistant_message, _, api_response = await llm_impl.chat_completion(
                        messages=messages,
                        timeout=args.timeout,
                        temperature=0.7,
                        #response_format={"type": "json_object"}
                    )
                    # Print the raw response JSON
                    print("--- Raw API Response ---")
                    print(json.dumps(api_response, indent=2, ensure_ascii=False))
                    print("------------------------")
                    
                    # Extract and print the assistant's message for convenience
                    if assistant_message:
                        print(f"Assistant: {assistant_message}")
                        # Add assistant response to history if maintaining state
                        # history.append({"role": "assistant", "content": assistant_message})
                    else:
                        print("Assistant: (No message content found in response)")

                except (LLMAPIError, LLMResponseError) as e:
                    logging.error(f"API call failed during talk: {e}")
                    print(f"Error: {e}", file=sys.stderr)
                except Exception as e:
                    logging.exception(f"Unexpected error during talk loop: {e}")
                    print(f"An unexpected error occurred: {e}", file=sys.stderr)
                    # Decide whether to break the loop or continue
                    # break

        # Result printing is handled within each mode now for talk mode
        # if result and args.client_type != 'talk':
        #     print("\n--- Test Result ---")
        #     print(json.dumps(result, indent=2, ensure_ascii=False))

    except (LLMAPIError, LLMResponseError) as e:
        logging.error(f"Test initialization or execution failed: {e}", exc_info=args.verbose)
        print(f"\nError: {e}", file=sys.stderr)
    except SystemExit: # Catch SystemExit from parser.error
         pass # Argparse already printed the error
    except Exception as e:
        logging.exception(f"An unexpected error occurred outside the main test loop: {e}")
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)

# Run the async main test function
asyncio.run(main_test()) 