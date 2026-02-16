/**
 * Paper Finder - Client-side JavaScript
 * AI-powered academic paper search for GitHub Pages
 */

// ============================================
// Configuration & State
// ============================================

const state = {
    papers: [],
    selectedPapers: new Set(),
    settings: {
        openaiKey: '',
        zoteroKey: '',
        zoteroUser: '',
        zoteroCollection: '',
    },
};

// Load settings from localStorage
function loadSettings() {
    const saved = localStorage.getItem('paperFinderSettings');
    if (saved) {
        try {
            state.settings = { ...state.settings, ...JSON.parse(saved) };
        } catch (e) {
            console.error('Failed to load settings:', e);
        }
    }
    
    // Populate settings form
    document.getElementById('openai-key').value = state.settings.openaiKey || '';
    document.getElementById('zotero-key').value = state.settings.zoteroKey || '';
    document.getElementById('zotero-user').value = state.settings.zoteroUser || '';
}

function saveSettings() {
    state.settings.openaiKey = document.getElementById('openai-key').value.trim();
    state.settings.zoteroKey = document.getElementById('zotero-key').value.trim();
    state.settings.zoteroUser = document.getElementById('zotero-user').value.trim();
    state.settings.zoteroCollection = document.getElementById('zotero-collection').value;
    
    localStorage.setItem('paperFinderSettings', JSON.stringify(state.settings));
    
    const status = document.getElementById('settings-status');
    status.textContent = '✓ settings saved';
    status.className = 'settings-status success';
    setTimeout(() => { status.className = 'settings-status'; }, 3000);
}

// ============================================
// API Clients
// ============================================

/**
 * Semantic Scholar API
 */
const SemanticScholar = {
    BASE_URL: 'https://api.semanticscholar.org/graph/v1',
    
    async search(query, options = {}) {
        const { limit = 30, yearStart, yearEnd, fields = [], minCitations = 0 } = options;
        
        const params = new URLSearchParams({
            query,
            limit: Math.min(limit, 100),
            fields: 'title,authors,abstract,year,citationCount,venue,externalIds,openAccessPdf,fieldsOfStudy,url',
        });
        
        // Year filter
        if (yearStart || yearEnd) {
            const start = yearStart || '';
            const end = yearEnd || '';
            params.set('year', `${start}-${end}`);
        }
        
        // Fields filter
        if (fields.length > 0) {
            params.set('fieldsOfStudy', fields.join(','));
        }
        
        try {
            const response = await fetch(`${this.BASE_URL}/paper/search?${params}`, {
                headers: { 'User-Agent': 'PaperFinder/1.0' }
            });
            
            if (!response.ok) {
                throw new Error(`Semantic Scholar API error: ${response.status}`);
            }
            
            const data = await response.json();
            
            return (data.data || [])
                .filter(paper => (paper.citationCount || 0) >= minCitations)
                .map(paper => this.normalizePaper(paper));
        } catch (error) {
            console.error('Semantic Scholar search failed:', error);
            return [];
        }
    },
    
    normalizePaper(paper) {
        const extIds = paper.externalIds || {};
        const pdfInfo = paper.openAccessPdf;
        
        return {
            id: paper.paperId || Math.random().toString(36),
            title: paper.title || '',
            authors: (paper.authors || []).map(a => a.name),
            abstract: paper.abstract || '',
            year: paper.year,
            doi: extIds.DOI,
            arxivId: extIds.ArXiv,
            url: paper.url || '',
            pdfUrl: pdfInfo?.url || null,
            source: 'semantic_scholar',
            citations: paper.citationCount || 0,
            venue: paper.venue || '',
            fields: (paper.fieldsOfStudy || []).map(f => f.category || f),
            relevanceScore: 0,
        };
    }
};

/**
 * arXiv API (using export.arxiv.org)
 */
const ArXiv = {
    BASE_URL: 'https://export.arxiv.org/api/query',
    
    async search(query, options = {}) {
        const { limit = 30 } = options;
        
        const params = new URLSearchParams({
            search_query: `all:${query}`,
            start: 0,
            max_results: limit,
            sortBy: 'relevance',
            sortOrder: 'descending',
        });
        
        try {
            const response = await fetch(`${this.BASE_URL}?${params}`);
            
            if (!response.ok) {
                throw new Error(`arXiv API error: ${response.status}`);
            }
            
            const text = await response.text();
            return this.parseAtomFeed(text);
        } catch (error) {
            console.error('arXiv search failed:', error);
            return [];
        }
    },
    
    parseAtomFeed(xml) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(xml, 'text/xml');
        const entries = doc.querySelectorAll('entry');
        
        return Array.from(entries).map(entry => {
            const id = entry.querySelector('id')?.textContent || '';
            const arxivId = id.split('/abs/').pop()?.split('v')[0] || '';
            
            const published = entry.querySelector('published')?.textContent;
            const year = published ? new Date(published).getFullYear() : null;
            
            const authors = Array.from(entry.querySelectorAll('author name'))
                .map(n => n.textContent);
            
            const categories = Array.from(entry.querySelectorAll('category'))
                .map(c => c.getAttribute('term'));
            
            const pdfLink = Array.from(entry.querySelectorAll('link'))
                .find(l => l.getAttribute('title') === 'pdf');
            
            return {
                id: arxivId || Math.random().toString(36),
                title: entry.querySelector('title')?.textContent?.replace(/\s+/g, ' ').trim() || '',
                authors,
                abstract: entry.querySelector('summary')?.textContent?.trim() || '',
                year,
                doi: null,
                arxivId,
                url: id,
                pdfUrl: pdfLink?.getAttribute('href') || `https://arxiv.org/pdf/${arxivId}.pdf`,
                source: 'arxiv',
                citations: 0,
                venue: 'arXiv',
                fields: categories,
                relevanceScore: 0,
            };
        });
    }
};

/**
 * OpenAI API for embeddings and AI features
 */
const OpenAI = {
    async getEmbedding(text) {
        if (!state.settings.openaiKey) return null;
        
        try {
            const response = await fetch('https://api.openai.com/v1/embeddings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${state.settings.openaiKey}`,
                },
                body: JSON.stringify({
                    model: 'text-embedding-3-small',
                    input: text.slice(0, 8000),
                }),
            });
            
            if (!response.ok) {
                throw new Error(`OpenAI API error: ${response.status}`);
            }
            
            const data = await response.json();
            return data.data[0].embedding;
        } catch (error) {
            console.error('OpenAI embedding failed:', error);
            return null;
        }
    },
    
    async refineQuery(query) {
        if (!state.settings.openaiKey) return query;
        
        try {
            const response = await fetch('https://api.openai.com/v1/chat/completions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${state.settings.openaiKey}`,
                },
                body: JSON.stringify({
                    model: 'gpt-4o-mini',
                    messages: [
                        {
                            role: 'system',
                            content: `You are a research assistant. Given a research interest, generate an optimized search query with key technical terms, synonyms, and related concepts. Output ONLY the search query, no explanations. Keep it under 100 words.`
                        },
                        { role: 'user', content: `Research interest: ${query}` }
                    ],
                    max_tokens: 150,
                    temperature: 0.3,
                }),
            });
            
            if (!response.ok) {
                throw new Error(`OpenAI API error: ${response.status}`);
            }
            
            const data = await response.json();
            return data.choices[0].message.content.trim();
        } catch (error) {
            console.error('Query refinement failed:', error);
            return query;
        }
    },
    
    cosineSimilarity(a, b) {
        let dotProduct = 0;
        let normA = 0;
        let normB = 0;
        
        for (let i = 0; i < a.length; i++) {
            dotProduct += a[i] * b[i];
            normA += a[i] * a[i];
            normB += b[i] * b[i];
        }
        
        return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
    }
};

/**
 * Zotero API
 */
const Zotero = {
    BASE_URL: 'https://api.zotero.org',
    
    async getCollections() {
        if (!state.settings.zoteroKey || !state.settings.zoteroUser) return [];
        
        try {
            const response = await fetch(
                `${this.BASE_URL}/users/${state.settings.zoteroUser}/collections`,
                {
                    headers: {
                        'Zotero-API-Key': state.settings.zoteroKey,
                        'Zotero-API-Version': '3',
                    }
                }
            );
            
            if (!response.ok) throw new Error(`Zotero API error: ${response.status}`);
            
            const data = await response.json();
            return data.map(c => ({
                key: c.key,
                name: c.data.name,
            }));
        } catch (error) {
            console.error('Failed to fetch Zotero collections:', error);
            return [];
        }
    },
    
    paperToZoteroItem(paper) {
        const itemType = paper.arxivId ? 'preprint' : 'journalArticle';
        
        const item = {
            itemType,
            title: paper.title,
            creators: paper.authors.slice(0, 50).map(name => ({
                creatorType: 'author',
                name,
            })),
            abstractNote: (paper.abstract || '').slice(0, 10000),
            date: paper.year ? String(paper.year) : '',
            url: paper.url,
        };
        
        if (paper.doi) item.DOI = paper.doi;
        if (paper.arxivId) {
            item.repository = 'arXiv';
            item.archiveID = `arXiv:${paper.arxivId}`;
        }
        if (paper.venue) {
            item[itemType === 'journalArticle' ? 'publicationTitle' : 'repository'] = paper.venue;
        }
        if (paper.fields?.length) {
            item.tags = paper.fields.slice(0, 20).map(tag => ({ tag }));
        }
        
        return item;
    },
    
    async addPapers(papers) {
        if (!state.settings.zoteroKey || !state.settings.zoteroUser) {
            return { success: false, error: 'Zotero not configured' };
        }
        
        const items = papers.map(p => {
            const item = this.paperToZoteroItem(p);
            if (state.settings.zoteroCollection) {
                item.collections = [state.settings.zoteroCollection];
            }
            return item;
        });
        
        try {
            const response = await fetch(
                `${this.BASE_URL}/users/${state.settings.zoteroUser}/items`,
                {
                    method: 'POST',
                    headers: {
                        'Zotero-API-Key': state.settings.zoteroKey,
                        'Zotero-API-Version': '3',
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(items),
                }
            );
            
            if (!response.ok) {
                const text = await response.text();
                throw new Error(`Zotero API error: ${response.status} - ${text}`);
            }
            
            const data = await response.json();
            const successCount = Object.keys(data.successful || {}).length;
            const failedCount = Object.keys(data.failed || {}).length;
            
            return { success: true, added: successCount, failed: failedCount };
        } catch (error) {
            console.error('Zotero export failed:', error);
            return { success: false, error: error.message };
        }
    }
};

// ============================================
// Search Logic
// ============================================

async function performSearch() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) return;
    
    // Show loading state
    setStatus('searching semantic scholar and arxiv...', true);
    hideElement('empty-state');
    hideElement('results-section');
    
    // Gather options
    const options = {
        limit: parseInt(document.getElementById('max-results').value) || 30,
        yearStart: parseInt(document.getElementById('year-start').value) || null,
        yearEnd: parseInt(document.getElementById('year-end').value) || null,
        minCitations: parseInt(document.getElementById('min-citations').value) || 0,
        fields: Array.from(document.getElementById('fields').selectedOptions)
            .map(o => o.value)
            .filter(Boolean),
    };
    
    const useSemanticScholar = document.getElementById('source-ss').checked;
    const useArxiv = document.getElementById('source-arxiv').checked;
    const aiRank = document.getElementById('ai-rank').checked;
    const aiRefine = document.getElementById('ai-refine').checked;
    const pdfOnly = document.getElementById('pdf-only').checked;
    
    let searchQuery = query;
    
    // AI query refinement
    if (aiRefine && state.settings.openaiKey) {
        setStatus('refining query with ai...', true);
        searchQuery = await OpenAI.refineQuery(query);
        console.log('Refined query:', searchQuery);
    }
    
    // Search both sources in parallel
    setStatus('fetching papers...', true);
    const searchPromises = [];
    
    if (useSemanticScholar) {
        searchPromises.push(SemanticScholar.search(searchQuery, options));
    }
    if (useArxiv) {
        searchPromises.push(ArXiv.search(searchQuery, options));
    }
    
    const results = await Promise.all(searchPromises);
    let papers = results.flat();
    
    // Deduplicate by title
    const seen = new Set();
    papers = papers.filter(p => {
        const key = p.title.toLowerCase().trim();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });
    
    // Filter by PDF availability
    if (pdfOnly) {
        papers = papers.filter(p => p.pdfUrl);
    }
    
    // AI-powered ranking
    if (aiRank && state.settings.openaiKey && papers.length > 0) {
        setStatus('ranking papers with ai...', true);
        
        const queryEmbedding = await OpenAI.getEmbedding(query);
        
        if (queryEmbedding) {
            // Get embeddings for papers (limit to avoid rate limits)
            const papersToRank = papers.slice(0, 50);
            
            for (let i = 0; i < papersToRank.length; i++) {
                const paper = papersToRank[i];
                const text = `${paper.title}\n\n${paper.abstract}`;
                const embedding = await OpenAI.getEmbedding(text);
                
                if (embedding) {
                    paper.relevanceScore = OpenAI.cosineSimilarity(queryEmbedding, embedding);
                }
                
                // Update progress
                if (i % 5 === 0) {
                    setStatus(`ranking papers with ai... (${i + 1}/${papersToRank.length})`, true);
                }
            }
            
            // Sort by relevance
            papers.sort((a, b) => b.relevanceScore - a.relevanceScore);
        }
    } else {
        // Fallback: sort by citations
        papers.sort((a, b) => b.citations - a.citations);
    }
    
    // Limit results
    papers = papers.slice(0, options.limit);
    
    state.papers = papers;
    state.selectedPapers.clear();
    
    hideStatus();
    displayResults(papers);
}

// ============================================
// UI Functions
// ============================================

function setStatus(message, showSpinner = false) {
    const bar = document.getElementById('status-bar');
    const text = document.getElementById('status-text');
    
    bar.classList.remove('hidden');
    text.textContent = message;
}

function hideStatus() {
    document.getElementById('status-bar').classList.add('hidden');
}

function showElement(id) {
    document.getElementById(id).classList.remove('hidden');
}

function hideElement(id) {
    document.getElementById(id).classList.add('hidden');
}

function displayResults(papers) {
    const container = document.getElementById('results-list');
    const countSpan = document.getElementById('results-count');
    
    countSpan.textContent = `(${papers.length} papers)`;
    
    if (papers.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">no papers found. try different search terms.</p>';
        showElement('results-section');
        return;
    }
    
    container.innerHTML = papers.map((paper, index) => `
        <article class="paper-card" data-index="${index}">
            <div class="paper-header">
                <input type="checkbox" class="paper-checkbox" data-index="${index}">
                <div class="paper-content">
                    <h3 class="paper-title">${escapeHtml(paper.title)}</h3>
                    <div class="paper-meta">
                        ${paper.year ? `<span class="paper-meta-item year">📅 ${paper.year}</span>` : ''}
                        ${paper.citations ? `<span class="paper-meta-item citations">📊 ${paper.citations} citations</span>` : ''}
                        <span class="paper-meta-item">📍 ${paper.source}</span>
                        ${paper.pdfUrl ? '<span class="paper-meta-item">📄 pdf</span>' : ''}
                    </div>
                    <p class="paper-authors">${escapeHtml(paper.authors.slice(0, 5).join(', '))}${paper.authors.length > 5 ? ' et al.' : ''}</p>
                    <p class="paper-abstract">${escapeHtml(paper.abstract?.slice(0, 300) || 'No abstract available')}${paper.abstract?.length > 300 ? '...' : ''}</p>
                    ${paper.fields?.length ? `
                        <div class="paper-tags">
                            ${paper.fields.slice(0, 5).map(f => `<span class="paper-tag">${escapeHtml(f)}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
                ${paper.relevanceScore ? `
                    <div class="paper-score">
                        <span class="paper-score-value">${(paper.relevanceScore * 100).toFixed(0)}%</span>
                        <span class="paper-score-label">match</span>
                    </div>
                ` : ''}
            </div>
        </article>
    `).join('');
    
    showElement('results-section');
    updateExportButton();
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showPaperDetail(index) {
    const paper = state.papers[index];
    if (!paper) return;
    
    const modal = document.getElementById('paper-modal');
    const title = document.getElementById('paper-modal-title');
    const body = document.getElementById('paper-modal-body');
    const pdfLink = document.getElementById('paper-pdf-link');
    const sourceLink = document.getElementById('paper-link');
    
    title.textContent = 'paper details';
    
    body.innerHTML = `
        <h3>title</h3>
        <p style="color: var(--text-primary); font-weight: 500;">${escapeHtml(paper.title)}</p>
        
        <h3>authors</h3>
        <p>${escapeHtml(paper.authors.join(', '))}</p>
        
        <div class="detail-row">
            <span class="detail-label">year:</span>
            <span>${paper.year || 'N/A'}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">citations:</span>
            <span>${paper.citations || 'N/A'}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">venue:</span>
            <span>${escapeHtml(paper.venue) || 'N/A'}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">doi:</span>
            <span>${paper.doi ? `<a href="https://doi.org/${paper.doi}" target="_blank">${paper.doi}</a>` : 'N/A'}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">arxiv:</span>
            <span>${paper.arxivId ? `<a href="https://arxiv.org/abs/${paper.arxivId}" target="_blank">${paper.arxivId}</a>` : 'N/A'}</span>
        </div>
        
        <h3>abstract</h3>
        <p>${escapeHtml(paper.abstract) || 'No abstract available'}</p>
        
        ${paper.fields?.length ? `
            <h3>fields</h3>
            <p>${paper.fields.join(', ')}</p>
        ` : ''}
    `;
    
    // Update links
    if (paper.pdfUrl) {
        pdfLink.href = paper.pdfUrl;
        pdfLink.style.display = '';
    } else {
        pdfLink.style.display = 'none';
    }
    
    sourceLink.href = paper.url || '#';
    
    // Store current paper index for Zotero export
    document.getElementById('paper-add-zotero').dataset.index = index;
    
    modal.classList.remove('hidden');
}

function updateExportButton() {
    const btn = document.getElementById('export-zotero-btn');
    const hasZotero = state.settings.zoteroKey && state.settings.zoteroUser;
    const hasSelection = state.selectedPapers.size > 0;
    
    btn.disabled = !hasZotero || !hasSelection;
    btn.textContent = hasSelection 
        ? `📚 export ${state.selectedPapers.size} to zotero`
        : '📚 export to zotero';
}

function selectAllPapers() {
    const checkboxes = document.querySelectorAll('.paper-checkbox');
    const allSelected = state.selectedPapers.size === state.papers.length;
    
    checkboxes.forEach((cb, i) => {
        cb.checked = !allSelected;
        if (!allSelected) {
            state.selectedPapers.add(i);
        }
    });
    
    if (allSelected) {
        state.selectedPapers.clear();
    }
    
    updateExportButton();
}

async function exportToZotero() {
    if (state.selectedPapers.size === 0) return;
    
    const papers = Array.from(state.selectedPapers).map(i => state.papers[i]);
    
    setStatus(`exporting ${papers.length} papers to zotero...`, true);
    
    const result = await Zotero.addPapers(papers);
    
    hideStatus();
    
    if (result.success) {
        alert(`✓ Added ${result.added} papers to Zotero${result.failed ? ` (${result.failed} failed)` : ''}`);
    } else {
        alert(`Failed to export: ${result.error}`);
    }
}

function downloadJSON() {
    const papers = state.selectedPapers.size > 0
        ? Array.from(state.selectedPapers).map(i => state.papers[i])
        : state.papers;
    
    const blob = new Blob([JSON.stringify(papers, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = 'papers.json';
    a.click();
    
    URL.revokeObjectURL(url);
}

// ============================================
// Theme Toggle
// ============================================

function initTheme() {
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? 'dark' : 'light');
    
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeIcon(theme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateThemeIcon(next);
}

function updateThemeIcon(theme) {
    const btn = document.getElementById('theme-toggle');
    btn.textContent = theme === 'dark' ? '☀️' : '🌙';
}

// ============================================
// Event Listeners
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    initTheme();
    
    // Search
    document.getElementById('search-btn').addEventListener('click', performSearch);
    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    
    // Filters toggle
    document.getElementById('filters-toggle').addEventListener('click', () => {
        const panel = document.getElementById('filters-panel');
        const toggle = document.getElementById('filters-toggle');
        panel.classList.toggle('hidden');
        toggle.classList.toggle('active');
        toggle.querySelector('span').textContent = panel.classList.contains('hidden') 
            ? '▸ advanced filters' 
            : '▾ advanced filters';
    });
    
    // Example searches
    document.querySelectorAll('.example-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('search-input').value = btn.dataset.query;
            performSearch();
        });
    });
    
    // Paper selection
    document.getElementById('results-list').addEventListener('click', (e) => {
        const card = e.target.closest('.paper-card');
        const checkbox = e.target.closest('.paper-checkbox');
        
        if (checkbox) {
            const index = parseInt(checkbox.dataset.index);
            if (checkbox.checked) {
                state.selectedPapers.add(index);
            } else {
                state.selectedPapers.delete(index);
            }
            updateExportButton();
        } else if (card && !checkbox) {
            const index = parseInt(card.dataset.index);
            showPaperDetail(index);
        }
    });
    
    // Select all
    document.getElementById('select-all-btn').addEventListener('click', selectAllPapers);
    
    // Export buttons
    document.getElementById('export-zotero-btn').addEventListener('click', exportToZotero);
    document.getElementById('export-json-btn').addEventListener('click', downloadJSON);
    
    // Settings modal
    document.getElementById('settings-btn').addEventListener('click', () => {
        document.getElementById('settings-modal').classList.remove('hidden');
    });
    
    document.getElementById('settings-close').addEventListener('click', () => {
        document.getElementById('settings-modal').classList.add('hidden');
    });
    
    document.getElementById('settings-save').addEventListener('click', () => {
        saveSettings();
    });
    
    document.getElementById('refresh-collections').addEventListener('click', async () => {
        const select = document.getElementById('zotero-collection');
        const collections = await Zotero.getCollections();
        
        select.innerHTML = '<option value="">my library (root)</option>' +
            collections.map(c => `<option value="${c.key}">${escapeHtml(c.name)}</option>`).join('');
    });
    
    // Paper modal
    document.getElementById('paper-close').addEventListener('click', () => {
        document.getElementById('paper-modal').classList.add('hidden');
    });
    
    document.getElementById('paper-add-zotero').addEventListener('click', async () => {
        const index = parseInt(document.getElementById('paper-add-zotero').dataset.index);
        const paper = state.papers[index];
        
        if (paper) {
            const result = await Zotero.addPapers([paper]);
            if (result.success) {
                alert('✓ Paper added to Zotero');
            } else {
                alert(`Failed: ${result.error}`);
            }
        }
    });
    
    // Modal backdrop close
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', () => {
            backdrop.closest('.modal').classList.add('hidden');
        });
    });
    
    // Theme toggle
    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
});
