import logging
import re
from functools import wraps
import traceback

class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        record.msg = re.sub(r'sessionid=[^;]+', 'sessionid=****', str(record.msg))
        record.msg = re.sub(r'csrftoken=[^;]+', 'csrftoken=****', str(record.msg))
        return True

def setup_logging(level=logging.INFO):
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=level
    )
    logger = logging.getLogger(__name__)
    logger.addFilter(SensitiveDataFilter())
    return logger

def log_errors(logger):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                logger.debug(f"Starting {func.__name__} with args: {args}, kwargs: {kwargs}")
                result = await func(*args, **kwargs)
                logger.debug(f"Completed {func.__name__} successfully")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                raise
        return wrapper
    return decorator
