import logging
import traceback

from twilio.rest import Client
from decouple import config

account_sid = config("TWILIO_ACCOUNT_SID")
auth_token = config("TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)
twilio_number = config('TWILIO_NUMBER')

# Set up logging to a file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("twilio_errors.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def send_message(to_number, body_text):
    try:
        message = client.messages.create(
            from_=f"whatsapp:{twilio_number}",
            body=body_text,
            to=f"whatsapp:{to_number}"
        )

        if message is not None:
            logger.info(f"Message sent to {to_number}: {message.body}")
        else:
            logger.error(f"Failed to create message to {to_number}: Twilio API returned None.")

    except Exception as e:
        # Log the error with traceback details
        error_details = traceback.format_exc()
        logger.error(f"Error sending message to {to_number}: {e}\nTraceback details:\n{error_details}")
