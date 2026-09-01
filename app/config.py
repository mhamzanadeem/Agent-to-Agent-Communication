import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME = os.getenv(
        "APP_NAME",
        "A2A Marketing Agent System",
    )

    HOST = os.getenv(
        "HOST",
        "0.0.0.0",
    )

    PORT = int(
        os.getenv(
            "PORT",
            "8000",
        )
    )

    GROQ_API_KEY = os.getenv(
        "GROQ_API_KEY",
        "",
    )

    GROQ_MODEL = os.getenv(
        "GROQ_MODEL",
        "llama-3.3-70b-versatile",
    )

    A2A_BASE_URL = os.getenv(
        "A2A_BASE_URL",
        "http://localhost:8000",
    )


settings = Settings()