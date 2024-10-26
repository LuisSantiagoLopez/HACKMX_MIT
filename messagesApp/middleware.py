import logging
import traceback
from django.http import JsonResponse

logger = logging.getLogger(__name__)

class GlobalExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            # Log full traceback for any error
            error_details = traceback.format_exc()
            logger.error(f"Unhandled exception in request: {str(e)}\nTraceback:\n{error_details}")
            return JsonResponse({"error": "An internal server error occurred."}, status=500)
