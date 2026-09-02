import os

from dotenv import load_dotenv

load_dotenv()


# Defaults to a local SQLite file so this runs with zero setup — override
# for a real Postgres/etc. database by setting DATABASE_URL.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./incident_assistant.db")

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
