"""
Zotero integration for Paper Finder
Pushes found papers directly into your Zotero library
"""
import logging
from typing import List, Optional, Dict, Any
import requests

from config import config
from paper_sources import Paper

logger = logging.getLogger(__name__)

# Optional pyzotero import
try:
    from pyzotero import zotero
    PYZOTERO_AVAILABLE = True
except ImportError:
    PYZOTERO_AVAILABLE = False


class ZoteroClient:
    """
    Zotero API client for managing your reference library
    Supports adding papers, creating collections, and more
    """
    
    def __init__(self):
        self.client = None
        self.library_id = config.zotero_user_id
        self.library_type = config.zotero_library_type
        
        if PYZOTERO_AVAILABLE and config.has_zotero():
            self.client = zotero.Zotero(
                self.library_id,
                self.library_type,
                config.zotero_api_key
            )
            logger.info("Zotero client initialized")
        else:
            logger.warning("Zotero not configured - papers won't be pushed to library")
    
    def is_available(self) -> bool:
        """Check if Zotero client is configured and available"""
        return self.client is not None
    
    def get_collections(self) -> List[Dict[str, Any]]:
        """Get all collections in the library"""
        if not self.client:
            return []
        
        try:
            collections = self.client.collections()
            return [
                {
                    "key": c["key"],
                    "name": c["data"]["name"],
                    "parent": c["data"].get("parentCollection"),
                }
                for c in collections
            ]
        except Exception as e:
            logger.error(f"Error fetching collections: {e}")
            return []
    
    def create_collection(self, name: str, parent_key: Optional[str] = None) -> Optional[str]:
        """
        Create a new collection in Zotero
        
        Args:
            name: Collection name
            parent_key: Parent collection key (for nested collections)
        
        Returns:
            Collection key if successful, None otherwise
        """
        if not self.client:
            return None
        
        try:
            template = {
                "name": name,
            }
            if parent_key:
                template["parentCollection"] = parent_key
            
            result = self.client.create_collections([template])
            if result and "successful" in result:
                return list(result["successful"].values())[0]["key"]
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
        
        return None
    
    def paper_to_zotero_item(self, paper: Paper) -> Dict[str, Any]:
        """
        Convert Paper object to Zotero item template
        
        Args:
            paper: Paper object to convert
        
        Returns:
            Zotero item dictionary
        """
        # Determine item type
        if paper.arxiv_id:
            item_type = "preprint"
        else:
            item_type = "journalArticle"
        
        # Create the item template
        item = {
            "itemType": item_type,
            "title": paper.title,
            "creators": [
                {"creatorType": "author", "name": author}
                for author in paper.authors[:50]  # Limit to 50 authors
            ],
            "abstractNote": paper.abstract[:10000] if paper.abstract else "",  # Zotero limit
            "date": str(paper.year) if paper.year else "",
            "url": paper.url or "",
            "accessDate": "",
        }
        
        # Add DOI if available
        if paper.doi:
            item["DOI"] = paper.doi
        
        # Add arXiv ID if available
        if paper.arxiv_id:
            item["repository"] = "arXiv"
            item["archiveID"] = f"arXiv:{paper.arxiv_id}"
        
        # Add venue/journal
        if paper.venue:
            if item_type == "journalArticle":
                item["publicationTitle"] = paper.venue
            else:
                item["repository"] = paper.venue
        
        # Add tags for fields of study
        if paper.fields:
            item["tags"] = [{"tag": field} for field in paper.fields[:20]]
        
        return item
    
    def add_paper(
        self,
        paper: Paper,
        collection_key: Optional[str] = None,
        attach_pdf: bool = True,
    ) -> Optional[str]:
        """
        Add a single paper to Zotero
        
        Args:
            paper: Paper to add
            collection_key: Collection to add the paper to
            attach_pdf: Whether to attach the PDF if available
        
        Returns:
            Item key if successful, None otherwise
        """
        if not self.client:
            logger.warning("Zotero not configured")
            return None
        
        try:
            # Convert paper to Zotero item
            item = self.paper_to_zotero_item(paper)
            
            # Add to collection if specified
            if collection_key:
                item["collections"] = [collection_key]
            
            # Create the item
            result = self.client.create_items([item])
            
            if result and "successful" in result and result["successful"]:
                item_key = list(result["successful"].values())[0]["key"]
                logger.info(f"Added paper to Zotero: {paper.title[:50]}...")
                
                # Attach PDF if available and requested
                if attach_pdf and paper.pdf_url:
                    self._attach_pdf(item_key, paper.pdf_url, paper.title)
                
                return item_key
            else:
                logger.error(f"Failed to add paper: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error adding paper to Zotero: {e}")
            return None
    
    def add_papers(
        self,
        papers: List[Paper],
        collection_key: Optional[str] = None,
        attach_pdfs: bool = True,
        create_collection_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add multiple papers to Zotero
        
        Args:
            papers: List of papers to add
            collection_key: Existing collection to add papers to
            attach_pdfs: Whether to attach PDFs when available
            create_collection_name: Create a new collection with this name
        
        Returns:
            Summary of added papers
        """
        if not self.client:
            return {"error": "Zotero not configured", "added": 0, "failed": 0}
        
        # Create collection if requested
        if create_collection_name:
            collection_key = self.create_collection(create_collection_name)
            if collection_key:
                logger.info(f"Created collection: {create_collection_name}")
        
        added = []
        failed = []
        
        for paper in papers:
            item_key = self.add_paper(paper, collection_key, attach_pdfs)
            if item_key:
                added.append({"title": paper.title, "key": item_key})
            else:
                failed.append({"title": paper.title, "reason": "API error"})
        
        return {
            "added": len(added),
            "failed": len(failed),
            "added_items": added,
            "failed_items": failed,
            "collection_key": collection_key,
        }
    
    def _attach_pdf(self, item_key: str, pdf_url: str, title: str) -> bool:
        """
        Attach a PDF to an existing Zotero item
        
        Args:
            item_key: Parent item key
            pdf_url: URL to the PDF
            title: PDF title
        
        Returns:
            True if successful
        """
        if not self.client:
            return False
        
        try:
            # Create linked URL attachment (doesn't download the file)
            attachment = {
                "itemType": "attachment",
                "parentItem": item_key,
                "linkMode": "linked_url",
                "title": f"{title[:50]}... (PDF)",
                "url": pdf_url,
                "contentType": "application/pdf",
            }
            
            result = self.client.create_items([attachment])
            return bool(result and "successful" in result and result["successful"])
            
        except Exception as e:
            logger.warning(f"Could not attach PDF: {e}")
            return False
    
    def search_library(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Search existing items in Zotero library
        
        Args:
            query: Search query
            limit: Maximum results
        
        Returns:
            List of matching items
        """
        if not self.client:
            return []
        
        try:
            items = self.client.items(q=query, limit=limit)
            return [
                {
                    "key": item["key"],
                    "title": item["data"].get("title", ""),
                    "type": item["data"].get("itemType", ""),
                    "creators": item["data"].get("creators", []),
                    "date": item["data"].get("date", ""),
                }
                for item in items
            ]
        except Exception as e:
            logger.error(f"Error searching Zotero: {e}")
            return []
    
    def check_duplicates(self, papers: List[Paper]) -> List[Paper]:
        """
        Check which papers are already in the library
        
        Args:
            papers: Papers to check
        
        Returns:
            List of papers NOT already in the library
        """
        if not self.client:
            return papers
        
        new_papers = []
        
        for paper in papers:
            # Search by title
            existing = self.search_library(paper.title[:50], limit=5)
            
            # Check for exact match
            is_duplicate = any(
                item["title"].lower().strip() == paper.title.lower().strip()
                for item in existing
            )
            
            if not is_duplicate:
                new_papers.append(paper)
            else:
                logger.info(f"Skipping duplicate: {paper.title[:50]}...")
        
        return new_papers
