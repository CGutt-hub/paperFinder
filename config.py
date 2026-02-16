"""
Configuration loader for Paper Finder
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Application configuration"""
    openai_api_key: Optional[str] = None
    zotero_api_key: Optional[str] = None
    zotero_user_id: Optional[str] = None
    zotero_library_type: str = "user"
    semantic_scholar_api_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            zotero_api_key=os.getenv("ZOTERO_API_KEY"),
            zotero_user_id=os.getenv("ZOTERO_USER_ID"),
            zotero_library_type=os.getenv("ZOTERO_LIBRARY_TYPE", "user"),
            semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
        )
    
    def has_openai(self) -> bool:
        """Check if OpenAI is configured"""
        return bool(self.openai_api_key and self.openai_api_key != "your_openai_api_key_here")
    
    def has_zotero(self) -> bool:
        """Check if Zotero is configured"""
        return bool(
            self.zotero_api_key and 
            self.zotero_user_id and 
            self.zotero_api_key != "your_zotero_api_key_here"
        )


config = Config.from_env()
