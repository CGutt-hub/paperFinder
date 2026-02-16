# Paper Finder 🔬📚

**AI-Powered Academic Paper Search Tool with Zotero Integration**

Find exactly the papers you need using semantic search, multi-dimensional filtering, and push them directly to your Zotero library.

**Live Demo**: [cgutt-hub.github.io/paperFinder](https://cgutt-hub.github.io/paperFinder)

## Two Ways to Use

1. **Web Version** (recommended) - No installation needed, runs in your browser
2. **CLI Version** - Python command-line tool for power users

## Features

- **🔍 Multi-Source Search**: Search Semantic Scholar and arXiv simultaneously
- **🤖 AI-Powered Ranking**: Uses OpenAI embeddings to rank papers by semantic relevance
- **📊 Multi-Dimensional Filtering**: Filter by year, citations, fields, PDF availability, and more
- **📚 Zotero Integration**: Push papers directly to your Zotero library with one command
- **🎯 Query Refinement**: AI expands your search terms for better results
- **📈 Research Analysis**: Identify research gaps and trends in any field

## Installation

```bash
# Navigate to the project directory
cd Desktop/paper-finder

# Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. Copy the example config file:
   ```bash
   copy .env.example .env
   ```

2. Edit `.env` and add your API keys:

   ```env
   # Required for AI features (semantic ranking, query refinement)
   OPENAI_API_KEY=your_openai_key
   
   # Required for Zotero integration
   ZOTERO_API_KEY=your_zotero_key
   ZOTERO_USER_ID=your_user_id
   ```

### Getting API Keys

- **OpenAI**: https://platform.openai.com/api-keys
- **Zotero**: 
  1. Go to https://www.zotero.org/settings/keys
  2. Create a new key with read/write access
  3. Your User ID is shown on the same page

## Usage

### Basic Search

```bash
# Simple search
python paper_finder.py search "transformer attention mechanisms"

# With filters
python paper_finder.py search "deep learning" --year-start 2022 --min-citations 50

# Search specific sources
python paper_finder.py search "quantum computing" --sources arxiv

# Save results to file
python paper_finder.py search "CRISPR applications" -o results.json
```

### Advanced Search Options

```bash
python paper_finder.py search "machine learning healthcare" \
    --year-start 2021 \
    --year-end 2024 \
    --min-citations 100 \
    --fields "Computer Science" \
    --pdf-only \
    --ai-refine \
    -n 30
```

### Push to Zotero

```bash
# Push specific papers (after searching)
python paper_finder.py push --indices 1,2,3

# Push all papers to a new collection
python paper_finder.py push --indices all --collection "ML Papers 2024"

# Skip duplicates already in library
python paper_finder.py push --indices all --no-duplicates
```

### Research Analysis

```bash
# Analyze research landscape and identify gaps
python paper_finder.py analyze "quantum machine learning"
```

### List Zotero Collections

```bash
python paper_finder.py collections
```

### Check Configuration

```bash
python paper_finder.py status
```

## Command Reference

| Command | Description |
|---------|-------------|
| `search` | Search for papers across multiple sources |
| `push` | Push found papers to Zotero |
| `analyze` | AI analysis of research landscape |
| `collections` | List Zotero collections |
| `status` | Check API configuration status |

### Search Options

| Option | Description |
|--------|-------------|
| `-n, --limit` | Maximum number of results (default: 20) |
| `-ys, --year-start` | Filter papers from this year |
| `-ye, --year-end` | Filter papers up to this year |
| `-c, --min-citations` | Minimum citation count |
| `-f, --fields` | Fields of study (can use multiple) |
| `-s, --sources` | Sources: semantic_scholar, arxiv |
| `--ai-rank/--no-ai-rank` | Use AI ranking (default: on) |
| `--ai-refine/--no-ai-refine` | AI query expansion |
| `--pdf-only` | Only papers with available PDF |
| `-o, --output` | Save results to JSON file |
| `-v, --verbose` | Show abstracts in output |

## How It Works

### Semantic Search

1. Your query is optionally refined by AI to include related terms
2. Papers are fetched from Semantic Scholar and arXiv
3. Each paper is embedded using OpenAI's text-embedding-3-small model
4. Papers are ranked by cosine similarity to your query
5. Multi-dimensional filters narrow down results

### Zotero Integration

Papers are converted to Zotero's format with:
- Proper item type (journalArticle, preprint)
- Authors, abstract, year, venue
- DOI and arXiv ID when available
- PDF links attached automatically
- Tags from fields of study

## Examples

### Find Recent High-Impact ML Papers

```bash
python paper_finder.py search "large language models reasoning" \
    --year-start 2023 \
    --min-citations 100 \
    --ai-refine
```

### Survey a Research Area

```bash
python paper_finder.py search "federated learning privacy" -n 50 -v -o survey.json
python paper_finder.py analyze "federated learning privacy"
```

### Build a Reading List

```bash
python paper_finder.py search "reinforcement learning robotics" --pdf-only
python paper_finder.py push --indices 1-10 --collection "RL Robotics Reading List"
```

## Troubleshooting

### Rate Limiting

If you hit rate limits:
- Semantic Scholar: Get an API key at https://www.semanticscholar.org/product/api
- Wait a few seconds between searches

### No Results

- Try broader search terms
- Use `--ai-refine` to expand your query
- Check if filters are too restrictive

### Zotero Errors

- Verify your API key has write permissions
- Check your User ID is correct
- Ensure you're using `user` library type (not `group`)

## License

MIT License
