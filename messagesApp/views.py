from openai import OpenAI
from decouple import config 
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import os
from dotenv import load_dotenv
from .botClass import Bot
from .models import CustomUser
from .utils import send_message, logger
from django.views.decorators.http import require_POST

import logging
import traceback
import sys

logger = logging.getLogger(__name__)

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

client = OpenAI()

@require_POST
@csrf_exempt
def reply(request):
    logger.debug(f"NEW ITER")
    whatsapp_number = request.POST.get('From').split('whatsapp:')[-1]
    user, created = CustomUser.objects.get_or_create(phone=str(whatsapp_number))
    body = request.POST.get('Body', '')
    logger.debug(f"body found: {body}")
    bot = Bot(user)
    try:
        response = bot.run(body)
        send_message(whatsapp_number, response)
    except Exception as e:
        # Get the current function and line number
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = exc_tb.tb_frame.f_code.co_filename
        line_number = exc_tb.tb_lineno

        # Log the error with full context
        logger.error(
             f"Error in file '{fname}', function '{exc_tb.tb_frame.f_code.co_name}', "
             f"line {line_number}: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        )

    return HttpResponse('')

