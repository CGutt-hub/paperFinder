"""
AI-powered semantic search and ranking
Uses OpenAI embeddings to find papers that truly match your interests
"""
import logging
from typing import List, Optional, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from config import config
from paper_sources import Paper

logger = logging.getLogger(__name__)

# Optional OpenAI import
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class AISearchEngine:
    """
    AI-powered search engine using embeddings for semantic similarity
    Can understand concepts, not just keywords
    """
    
    def __init__(self):
        self.client = None
        self.embedding_model = "text-embedding-3-small"
        
        if OPENAI_AVAILABLE and config.has_openai():
            self.client = OpenAI(api_key=config.openai_api_key)
            logger.info("OpenAI client initialized for AI-powered search")
        else:
            logger.warning("OpenAI not configured - falling back to keyword matching")
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding vector for text using OpenAI"""
        if not self.client:
            return None
        
        try:
            # Truncate text if too long (8191 tokens max)
            text = text[:8000]
            
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return None
    
    def compute_paper_embedding(self, paper: Paper) -> Optional[List[float]]:
        """Compute embedding for a paper based on title and abstract"""
        text = f"{paper.title}\n\n{paper.abstract}"
        return self.get_embedding(text)
    
    def rank_papers_by_query(
        self,
        papers: List[Paper],
        query: str,
        top_k: Optional[int] = None,
    ) -> List[Paper]:
        """
        Rank papers by semantic similarity to query using AI embeddings
        
        Args:
            papers: List of papers to rank
            query: Natural language query describing what you're looking for
            top_k: Return only top K results (None for all)
        
        Returns:
            Papers sorted by relevance score (highest first)
        """
        if not self.client:
            # Fallback to simple keyword matching
            return self._rank_by_keywords(papers, query, top_k)
        
        # Get query embedding
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            return self._rank_by_keywords(papers, query, top_k)
        
        query_vec = np.array(query_embedding).reshape(1, -1)
        
        # Compute embeddings and similarities for all papers
        ranked_papers = []
        for paper in papers:
            # Skip papers without abstracts
            if not paper.abstract:
                paper.relevance_score = 0.0
                ranked_papers.append(paper)
                continue
            
            paper_embedding = self.compute_paper_embedding(paper)
            if paper_embedding:
                paper.embedding = paper_embedding
                paper_vec = np.array(paper_embedding).reshape(1, -1)
                similarity = cosine_similarity(query_vec, paper_vec)[0][0]
                paper.relevance_score = float(similarity)
            else:
                paper.relevance_score = 0.0
            
            ranked_papers.append(paper)
        
        # Sort by relevance score
        ranked_papers.sort(key=lambda p: p.relevance_score, reverse=True)
        
        if top_k:
            ranked_papers = ranked_papers[:top_k]
        
        return ranked_papers
    
    def _rank_by_keywords(
        self,
        papers: List[Paper],
        query: str,
        top_k: Optional[int] = None,
    ) -> List[Paper]:
        """Fallback ranking using keyword matching"""
        query_words = set(query.lower().split())
        
        for paper in papers:
            # Simple TF-based scoring
            text = f"{paper.title} {paper.abstract}".lower()
            word_count = sum(1 for word in query_words if word in text)
            paper.relevance_score = word_count / len(query_words) if query_words else 0
        
        papers.sort(key=lambda p: (p.relevance_score, p.citations), reverse=True)
        
        if top_k:
            papers = papers[:top_k]
        
        return papers
    
    def find_similar_papers(
        self,
        reference_paper: Paper,
        candidate_papers: List[Paper],
        top_k: int = 10,
    ) -> List[Paper]:
        """
        Find papers similar to a reference paper
        
        Args:
            reference_paper: The paper to find similar ones to
            candidate_papers: Papers to search through
            top_k: Number of similar papers to return
        """
        if not self.client:
            # Fallback: use title words as query
            return self.rank_papers_by_query(
                candidate_papers, 
                reference_paper.title,
                top_k
            )
        
        # Get reference embedding
        ref_embedding = self.compute_paper_embedding(reference_paper)
        if not ref_embedding:
            return candidate_papers[:top_k]
        
        ref_vec = np.array(ref_embedding).reshape(1, -1)
        
        # Score all candidates
        for paper in candidate_papers:
            if paper.title == reference_paper.title:
                paper.relevance_score = 0  # Exclude the reference itself
                continue
            
            paper_embedding = self.compute_paper_embedding(paper)
            if paper_embedding:
                paper_vec = np.array(paper_embedding).reshape(1, -1)
                similarity = cosine_similarity(ref_vec, paper_vec)[0][0]
                paper.relevance_score = float(similarity)
            else:
                paper.relevance_score = 0
        
        candidate_papers.sort(key=lambda p: p.relevance_score, reverse=True)
        return candidate_papers[:top_k]
    
    def refine_search_query(self, user_query: str) -> str:
        """
        Use AI to expand and refine the search query for better results
        
        Args:
            user_query: User's natural language query
        
        Returns:
            Optimized search query with relevant terms
        """
        if not self.client:
            return user_query
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a research assistant helping to find academic papers.
Given a user's research interest, generate an optimized search query that will find relevant papers.

Include:
- Key technical terms and their synonyms
- Related concepts
- Common abbreviations in the field

Output ONLY the search query, no explanations. Keep it under 100 words."""
                    },
                    {
                        "role": "user",
                        "content": f"Research interest: {user_query}"
                    }
                ],
                max_tokens=150,
                temperature=0.3,
            )
            
            refined = response.choices[0].message.content.strip()
            logger.info(f"Refined query: {refined}")
            return refined
            
        except Exception as e:
            logger.error(f"Error refining query: {e}")
            return user_query
    
    def analyze_research_gap(
        self,
        papers: List[Paper],
        research_interest: str,
    ) -> str:
        """
        Analyze papers to identify research gaps and opportunities
        
        Args:
            papers: List of found papers
            research_interest: User's research interest
        
        Returns:
            Analysis of research gaps
        """
        if not self.client or not papers:
            return "AI analysis not available without OpenAI configuration."
        
        # Prepare summary of papers
        papers_summary = "\n".join([
            f"- {p.title} ({p.year}): {p.abstract[:200]}..."
            for p in papers[:10]  # Limit to top 10 papers
        ])
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a research analyst. Given a list of academic papers and a research interest, 
identify potential research gaps, emerging trends, and opportunities for novel contributions.
Be specific and actionable in your analysis."""
                    },
                    {
                        "role": "user",
                        "content": f"""Research Interest: {research_interest}

Found Papers:
{papers_summary}

Please analyze:
1. Key themes and trends
2. Potential research gaps
3. Opportunities for novel contributions"""
                    }
                ],
                max_tokens=500,
                temperature=0.5,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error analyzing research gap: {e}")
            return "Could not complete analysis."


class MultiDimensionalFilter:
    """
    Filter papers across multiple dimensions simultaneously
    Supports complex queries like "ML papers with high citations from 2022-2024 about transformers"
    """
    
    def __init__(self, ai_engine: Optional[AISearchEngine] = None):
        self.ai_engine = ai_engine or AISearchEngine()
    
    def filter(
        self,
        papers: List[Paper],
        year_range: Optional[Tuple[int, int]] = None,
        min_citations: int = 0,
        max_citations: Optional[int] = None,
        fields: Optional[List[str]] = None,
        has_pdf: bool = False,
        semantic_query: Optional[str] = None,
        semantic_threshold: float = 0.5,
        author_contains: Optional[str] = None,
        venue_contains: Optional[str] = None,
    ) -> List[Paper]:
        """
        Apply multiple filters simultaneously
        
        Args:
            papers: Papers to filter
            year_range: (start_year, end_year) tuple
            min_citations: Minimum citation count
            max_citations: Maximum citation count
            fields: Required fields of study
            has_pdf: Only papers with available PDF
            semantic_query: Semantic similarity filter query
            semantic_threshold: Minimum similarity score (0-1)
            author_contains: Filter by author name substring
            venue_contains: Filter by venue/journal name substring
        """
        filtered = papers
        
        # Year filter
        if year_range:
            start, end = year_range
            filtered = [
                p for p in filtered 
                if p.year and start <= p.year <= end
            ]
        
        # Citation filters
        if min_citations > 0:
            filtered = [p for p in filtered if p.citations >= min_citations]
        
        if max_citations is not None:
            filtered = [p for p in filtered if p.citations <= max_citations]
        
        # Field filter
        if fields:
            fields_lower = [f.lower() for f in fields]
            filtered = [
                p for p in filtered
                if any(f.lower() in fields_lower or 
                       any(fl in f.lower() for fl in fields_lower)
                       for f in p.fields)
            ]
        
        # PDF availability
        if has_pdf:
            filtered = [p for p in filtered if p.pdf_url]
        
        # Author filter
        if author_contains:
            author_query = author_contains.lower()
            filtered = [
                p for p in filtered
                if any(author_query in a.lower() for a in p.authors)
            ]
        
        # Venue filter
        if venue_contains:
            venue_query = venue_contains.lower()
            filtered = [
                p for p in filtered
                if p.venue and venue_query in p.venue.lower()
            ]
        
        # Semantic filter (requires AI)
        if semantic_query and self.ai_engine.client:
            filtered = self.ai_engine.rank_papers_by_query(filtered, semantic_query)
            filtered = [p for p in filtered if p.relevance_score >= semantic_threshold]
        
        return filtered
