import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')


@dataclass
class Settings:
    workspace: Path = ROOT / '.workspaces'
    api_key: str = field(default_factory=lambda: os.getenv('GEMINI_API_KEY', ''), repr=False)
    model: str = field(default_factory=lambda: os.getenv('GEMINI_MODEL', 'gemini-3.6-flash'))
    mock_ai: bool = field(default_factory=lambda: os.getenv('DEV_MODE_MOCK_AI', 'true').lower() == 'true')
    development: bool = field(default_factory=lambda: os.getenv('DEVELOPMENT', 'true').lower() == 'true')
    max_upload: int = field(default_factory=lambda: int(os.getenv('MAX_UPLOAD_MB', '5')) * 1024**2)
    max_extracted: int = field(default_factory=lambda: int(os.getenv('MAX_EXTRACTED_MB', '20')) * 1024**2)
    max_file: int = field(default_factory=lambda: int(os.getenv('MAX_FILE_KB', '256')) * 1024)
    max_files: int = field(default_factory=lambda: int(os.getenv('MAX_FILES', '100')))
    timeout: int = field(default_factory=lambda: int(os.getenv('TEST_TIMEOUT_SECONDS', '45')))
    ttl: int = field(default_factory=lambda: int(os.getenv('PROJECT_TTL_SECONDS', '7200')))
    image: str = field(default_factory=lambda: os.getenv('SANDBOX_IMAGE', 'devpilot-runner:local'))
    origins: tuple[str, ...] = ('http://localhost:5173', 'http://127.0.0.1:5173')
