
import os
from pathlib import Path
from dotenv import load_dotenv

# Find the project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load environment variables from the project's .env file
load_dotenv(PROJECT_ROOT / ".env")

# Jira configuration
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

# LLM configuration (to be configured later)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Validate required Jira settings
required_settings = {
    "JIRA_BASE_URL": JIRA_BASE_URL,
    "JIRA_EMAIL": JIRA_EMAIL,
    "JIRA_API_TOKEN": JIRA_API_TOKEN,
    "JIRA_PROJECT_KEY": JIRA_PROJECT_KEY,
}

missing_settings = [
    name for name, value in required_settings.items()
    if not value
]

if missing_settings:
    raise ValueError(
        f"Missing environment variables: {', '.join(missing_settings)}"
    )
