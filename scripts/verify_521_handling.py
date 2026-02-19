
import logging
import sys
import os

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_polling_service import email_polling_service
from logger import setup_logger

# Configure logging to stdout so we can see it
logger = setup_logger("verification")
logging.basicConfig(level=logging.INFO)

print("Starting verification of 521 error handling...")

# Run polling
result = email_polling_service.poll_all_accounts()

print(f"Result: {result}")

if result.get("success") is False and "521" in result.get("error", ""):
    print("SUCCESS: Error 521 was caught and handled gracefully.")
elif result.get("success") is False and "Web server is down" in result.get("error", ""):
    print("SUCCESS: Error 521 (Web server is down) was caught and handled gracefully.")
else:
    print("FAILURE: Did not catch the specific 521 error as expected, or server is back up.")
