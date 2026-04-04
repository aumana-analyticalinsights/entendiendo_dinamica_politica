import os
from pathlib import Path
from urllib.parse import unquote

from dotenv import load_dotenv

load_dotenv()

X_API_KEY = unquote(os.environ["x_API_KEY"])

PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"