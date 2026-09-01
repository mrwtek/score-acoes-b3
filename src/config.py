import os
from dotenv import load_dotenv

load_dotenv()

BRAPI_TOKEN = os.getenv("BRAPI_TOKEN")
BOLSAI_TOKEN= os.getenv("BOLSAI_TOKEN")