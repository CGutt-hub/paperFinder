"""
Paper source APIs: Semantic Scholar, arXiv, and more
Handles fetching papers from multiple academic databases
"""
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import requests
import arxiv

from config import config

logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """Unified paper representation across all sources"""
    title: str
    authors: List[str]
    abstract: str
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    source: str = ""
    citations: int = 0
    venue: Optional[str] = None
    arxiv_id: Optional[str] = None
    fields: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    # For AI-powered ranking
    relevance_score: float = 0.0
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "year": self.year,
            "doi": self.doi,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "source": self.source,
            "citations": self.citations,
            "venue": self.venue,
            "arxiv_id": self.arxiv_id,
            "fields": self.fields,
            "keywords": self.keywords,
            "relevance_score": self.relevance_score,
        }


class SemanticScholarAPI:
    """
    Semantic Scholar API client
    Excellent for finding papers with citation data and semantic search
    """
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self):
        self.session = requests.Session()
        if config.semantic_scholar_api_key:
            self.session.headers["x-api-key"] = config.semantic_scholar_api_key
        self.session.headers["User-Agent"] = "PaperFinder/1.0"
    
    def search(
        self,
        query: str,
        limit: int = 50,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
        fields_of_study: Optional[List[str]] = None,
        min_citations: int = 0,
        open_access_only: bool = False,
    ) -> List[Paper]:
        """
        Search for papers using Semantic Scholar API
        
        Args:
            query: Search query string
            limit: Maximum number of results
            year_start: Filter papers from this year onwards
            year_end: Filter papers up to this year
            fields_of_study: Filter by fields (e.g., ["Computer Science", "Medicine"])
            min_citations: Minimum citation count
            open_access_only: Only return open access papers
        """
        papers = []
        
        # Build query parameters
        params = {
            "query": query,
            "limit": min(limit, 100),  # API max is 100
            "fields": "title,authors,abstract,year,citationCount,venue,externalIds,openAccessPdf,fieldsOfStudy,url",
        }
        
        # Add year filter
        if year_start or year_end:
            year_filter = ""
            if year_start and year_end:
                year_filter = f"{year_start}-{year_end}"
            elif year_start:
                year_filter = f"{year_start}-"
            else:
                year_filter = f"-{year_end}"
            params["year"] = year_filter
        
        # Add fields of study filter
        if fields_of_study:
            params["fieldsOfStudy"] = ",".join(fields_of_study)
        
        # Add open access filter
        if open_access_only:
            params["openAccessPdf"] = ""
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/paper/search",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            for item in data.get("data", []):
                # Skip papers below citation threshold
                citation_count = item.get("citationCount", 0) or 0
                if citation_count < min_citations:
                    continue
                
                # Extract authors
                authors = [
                    a.get("name", "") 
                    for a in item.get("authors", [])
                ]
                
                # Extract fields of study
                fields = [
                    f.get("category", "") 
                    for f in item.get("fieldsOfStudy", []) or []
                ]
                
                # Get external IDs
                ext_ids = item.get("externalIds", {}) or {}
                
                # Get PDF URL if available
                pdf_info = item.get("openAccessPdf")
                pdf_url = pdf_info.get("url") if pdf_info else None
                
                paper = Paper(
                    title=item.get("title", ""),
                    authors=authors,
                    abstract=item.get("abstract", "") or "",
                    year=item.get("year"),
                    doi=ext_ids.get("DOI"),
                    arxiv_id=ext_ids.get("ArXiv"),
                    url=item.get("url", ""),
                    pdf_url=pdf_url,
                    source="semantic_scholar",
                    citations=citation_count,
                    venue=item.get("venue", ""),
                    fields=fields,
                )
                papers.append(paper)
                
        except requests.RequestException as e:
            logger.error(f"Semantic Scholar API error: {e}")
        
        return papers
    
    def get_recommendations(self, paper_ids: List[str], limit: int = 20) -> List[Paper]:
        """Get paper recommendations based on seed papers"""
        papers = []
        
        try:
            response = self.session.post(
                f"{self.BASE_URL}/paper/batch",
                json={"ids": paper_ids},
                params={"fields": "title,authors,abstract,year,citationCount,venue,externalIds,openAccessPdf,fieldsOfStudy,url"},
                timeout=30
            )
            response.raise_for_status()
            # ... process similar to search
        except requests.RequestException as e:
            logger.error(f"Semantic Scholar recommendations error: {e}")
        
        return papers


class ArxivAPI:
    """
    arXiv API client
    Great for preprints and cutting-edge research
    """
    
    CATEGORY_MAP = {
        "cs": "Computer Science",
        "cs.AI": "Artificial Intelligence",
        "cs.CL": "Computation and Language",
        "cs.CV": "Computer Vision",
        "cs.LG": "Machine Learning",
        "cs.NE": "Neural and Evolutionary Computing",
        "stat.ML": "Machine Learning (Statistics)",
        "physics": "Physics",
        "math": "Mathematics",
        "q-bio": "Quantitative Biology",
        "q-fin": "Quantitative Finance",
        "econ": "Economics",
        "eess": "Electrical Engineering and Systems Science",
    }
    
    def search(
        self,
        query: str,
        limit: int = 50,
        categories: Optional[List[str]] = None,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> List[Paper]:
        """
        Search for papers on arXiv
        
        Args:
            query: Search query
            limit: Maximum results
            categories: arXiv categories to filter (e.g., ["cs.AI", "cs.LG"])
            sort_by: Sort by "relevance", "lastUpdatedDate", or "submittedDate"
            sort_order: "ascending" or "descending"
        """
        papers = []
        
        # Build search query
        search_query = query
        if categories:
            cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
            search_query = f"({query}) AND ({cat_query})"
        
        # Map sort options
        sort_map = {
            "relevance": arxiv.SortCriterion.Relevance,
            "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
            "submittedDate": arxiv.SortCriterion.SubmittedDate,
        }
        order_map = {
            "ascending": arxiv.SortOrder.Ascending,
            "descending": arxiv.SortOrder.Descending,
        }
        
        try:
            search = arxiv.Search(
                query=search_query,
                max_results=limit,
                sort_by=sort_map.get(sort_by, arxiv.SortCriterion.Relevance),
                sort_order=order_map.get(sort_order, arxiv.SortOrder.Descending),
            )
            
            for result in search.results():
                # Extract year from published date
                year = result.published.year if result.published else None
                
                # Get primary category and all categories
                categories = [cat for cat in result.categories]
                
                paper = Paper(
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    abstract=result.summary,
                    year=year,
                    doi=result.doi,
                    arxiv_id=result.entry_id.split("/")[-1],
                    url=result.entry_id,
                    pdf_url=result.pdf_url,
                    source="arxiv",
                    fields=categories,
                    venue="arXiv",
                )
                papers.append(paper)
                
        except Exception as e:
            logger.error(f"arXiv API error: {e}")
        
        return papers


class PaperAggregator:
    """
    Aggregates results from multiple paper sources
    Deduplicates and merges information
    """
    
    def __init__(self):
        self.semantic_scholar = SemanticScholarAPI()
        self.arxiv = ArxivAPI()
    
    def search_all(
        self,
        query: str,
        limit: int = 50,
        sources: Optional[List[str]] = None,
        **kwargs
    ) -> List[Paper]:
        """
        Search across all configured sources
        
        Args:
            query: Search query
            limit: Maximum results per source
            sources: List of sources to search ["semantic_scholar", "arxiv"]
            **kwargs: Additional filters passed to individual sources
        """
        if sources is None:
            sources = ["semantic_scholar", "arxiv"]
        
        all_papers = []
        
        if "semantic_scholar" in sources:
            ss_papers = self.semantic_scholar.search(query, limit=limit, **kwargs)
            all_papers.extend(ss_papers)
            time.sleep(0.5)  # Rate limiting
        
        if "arxiv" in sources:
            arxiv_papers = self.arxiv.search(query, limit=limit)
            all_papers.extend(arxiv_papers)
        
        # Deduplicate based on title similarity or DOI/arXiv ID
        deduped = self._deduplicate(all_papers)
        
        return deduped
    
    def _deduplicate(self, papers: List[Paper]) -> List[Paper]:
        """Remove duplicate papers based on identifiers or title similarity"""
        seen_ids = set()
        seen_titles = set()
        unique_papers = []
        
        for paper in papers:
            # Check by DOI first
            if paper.doi:
                if paper.doi in seen_ids:
                    continue
                seen_ids.add(paper.doi)
            
            # Check by arXiv ID
            if paper.arxiv_id:
                if paper.arxiv_id in seen_ids:
                    continue
                seen_ids.add(paper.arxiv_id)
            
            # Check by normalized title
            normalized_title = paper.title.lower().strip()
            if normalized_title in seen_titles:
                continue
            seen_titles.add(normalized_title)
            
            unique_papers.append(paper)
        
        return unique_papers
