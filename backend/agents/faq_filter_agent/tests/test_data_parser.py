import sys
import os
import argparse
import logging
import json

# Use absolute imports assuming the script is run with -m from the project root
from backend.agents.faq_filter_agent.data_parser import FAQDataParser
from backend.agents.faq_filter_agent.exceptions import FAQDataError

# Configure logging ONLY when run as a script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Determine the default path relative to this script's location
# This script is in tests/, data is in ../data/
script_dir = os.path.dirname(__file__)
default_faq_path = os.path.join(script_dir, "..", "data", "faq_doc.json") 

parser = argparse.ArgumentParser(description="Test FAQDataParser functionality.")
parser.add_argument(
    "--faq-file",
    type=str,
    default=default_faq_path,
    help=f"Path to the FAQ JSON file (default: {default_faq_path})"
)
parser.add_argument(
    "--test-func",
    choices=['markdown', 'answer'],
    required=True,
    help="Function to test: 'markdown' (get category structure) or 'answer' (get answer by key path)."
)
parser.add_argument(
    "--key-path",
    type=str,
    help="The key path (e.g., '1.1.2') to search for when --test-func is 'answer'."
)
parser.add_argument(
    '-v', '--verbose',
    action='store_true',
    help='Enable DEBUG level logging for standalone test.'
)


args = parser.parse_args()

# Adjust log level if verbose flag is set
if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG) # Set root logger level
    logging.info("Verbose logging enabled.")


# Validate arguments
if args.test_func == 'answer' and not args.key_path:
    parser.error("--key-path is required when --test-func is 'answer'")
    sys.exit(1) 

try:
    # Initialize the parser with the specified (or default) FAQ file
    logging.info(f"Initializing FAQDataParser with file: {args.faq_file}")
    parser_instance = FAQDataParser(args.faq_file)
    logging.info("FAQDataParser initialized successfully.")

    # Execute the requested function
    if args.test_func == 'markdown':
        print("\n--- Testing get_category_structure_markdown ---")
        markdown_structure = parser_instance.get_category_structure_markdown()
        print("\nGenerated Markdown Structure:")
        print(markdown_structure) # Print raw string

    elif args.test_func == 'answer':
        print(f"\n--- Testing get_answer_by_key_path for path: '{args.key_path}' ---")
        answer = parser_instance.get_answer_by_key_path(args.key_path)
        print(f"Resulting Answer:")
        # Handle None answer gracefully
        if answer is None:
            print("<No answer found or path invalid/non-leaf>")
        else:
            print(answer)

except FAQDataError as e:
    logging.error(f"Failed to initialize or use FAQDataParser: {e}", exc_info=args.verbose)
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
except SystemExit: # Catch SystemExit from parser.error
    pass # Argparse already printed the error
except Exception as e: # Catch any other unexpected errors during testing
    logging.exception(f"An unexpected error occurred during testing: {e}")
    print(f"An unexpected error occurred: {e}", file=sys.stderr)
    sys.exit(1) 