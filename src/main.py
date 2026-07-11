import logging
import uvicorn
from src.config.server import App
from src.config.settings import settings

# Filter out static file access logs for /uploads
class UploadsAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "/uploads/" not in message

# Apply filter to uvicorn access logger
logging.getLogger("uvicorn.access").addFilter(UploadsAccessFilter())

application = App()

app = application.server

if __name__ == "__main__":
    uvicorn.run("src.main:app", host=settings.HOST, port=settings.PORT, reload=True)
