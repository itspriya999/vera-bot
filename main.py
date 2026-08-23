import os

import uvicorn

from app.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", settings.host),
        port=int(os.getenv("PORT", settings.port)),
        reload=False,
    )
