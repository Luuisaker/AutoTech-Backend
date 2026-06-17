import uvicorn
from src.config.server import App
from src.config.settings import settings

application = App()

app = application.server

if __name__ == "__main__":
    uvicorn.run("src.main:app", host=settings.HOST, port=settings.PORT, reload=True)
