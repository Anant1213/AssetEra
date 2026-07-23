# AssetEra — unified backend package

# Load environment variables from the project-root .env before any backend
# submodule (which reads env at import time) is imported. Use an explicit path
# built from __file__ so this works regardless of cwd or exec context.
# override=False (default) so real shell-exported vars win over .env.
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
