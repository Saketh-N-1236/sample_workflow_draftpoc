# Test Impact Analysis System

A production-ready system for analyzing code changes and automatically selecting relevant tests using AST parsing and semantic search.

## Features

- **Multi-Provider Support**: Connect to GitHub and GitLab repositories via API (no cloning required)
- **Test Analysis**: 8-step pipeline to analyze test repositories and extract metadata
- **Test Selection**: AST-based and semantic search to identify relevant tests for code changes
- **Web Platform**: Modern React frontend with FastAPI backend
- **Vector Search**: Pinecone integration for semantic test matching

## Architecture

```
┌─────────────────┐
│   Web Platform  │  ← React Frontend + FastAPI Backend
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│GitHub │ │GitLab │  ← API Integration (no cloning)
│  API  │ │  API  │
└───────┘ └───────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│  AST  │ │Semantic│  ← Test Selection
│Parser │ │Search  │
└───────┘ └───────┘
```

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- PostgreSQL (for test registry storage)
- Pinecone account (for semantic search)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd sample_workflow
   ```

2. **Set up environment variables**
   ```bash
   # Copy .env.example to .env and configure
   cp .env.example .env
   ```
   
   Required variables:
   ```bash
   # GitHub (for GitHub repositories)
   GITHUB_API_TOKEN=your_token_here
   
   # GitLab (for GitLab repositories)
   GITLAB_API_TOKEN=your_token_here
   
   # Pinecone (for semantic search)
   PINECONE_API_KEY=your_key_here
   PINECONE_INDEX_NAME=test-embeddings
   
   # Database
   DATABASE_URL=postgresql://user:password@localhost:5432/test_impact_analysis
   ```

3. **Install backend dependencies**
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   ```

### Running the Application

1. **Start the backend**
   ```bash
   cd backend
   run_backend.bat
   # Or manually: python -m uvicorn api.main:app --reload --reload-dir . --port 8000
   ```

2. **Start the frontend** (in a new terminal)
   ```bash
   cd frontend
   npm run dev
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Project Structure

```
sample_workflow/
├── frontend/              # React frontend application
│   ├── src/               # Source code (components, pages, services)
│   ├── package.json       # Node.js dependencies
│   └── vite.config.js     # Vite build configuration
├── backend/               # Python backend (FastAPI + all services)
│   ├── api/               # FastAPI routes and models
│   ├── services/          # Business logic (repository, analysis, selection)
│   ├── test_analysis/     # Test analysis pipeline (8-step)
│   ├── git_diff_processor/# Git diff parsing and AST-based test selection
│   ├── semantic_retrieval/# Semantic search engine (Pinecone + Advanced RAG)
│   ├── deterministic/     # Database loading scripts
│   ├── config/            # Application configuration
│   ├── llm/               # LLM abstraction layer (OpenAI/Gemini/Ollama)
│   ├── parsers/           # Code parsers (Tree-sitter)
│   ├── data/              # Extracted test repository data
│   ├── scripts/           # Utility and diagnostic scripts
│   └── requirements.txt   # Python dependencies
├── docs/                  # Documentation and architecture diagrams
├── .env                   # Environment variables (not committed)
└── README.md              # This file
```

## Usage

### 1. Connect Repository

- Open the web platform
- Select provider (GitHub/GitLab) or use auto-detect
- Enter repository URL
- Click "Connect"

### 2. View Changes

- Select a branch (optional)
- View git diff and changed files
- Review statistics

### 3. Run Test Analysis

- Click "Test Analysis" button
- System analyzes local test repository
- Results show test files, functions, and modules

### 4. Select Tests

- Click "Test Selection" button
- System matches code changes against tests
- Results show selected tests with AST and semantic matches

## Configuration

See [backend/README.md](backend/README.md) for detailed configuration options.

## API Endpoints

- `POST /api/repositories/connect` - Connect to repository
- `GET /api/repositories/{id}/branches` - List branches
- `GET /api/repositories/{id}/diff` - Get git diff
- `POST /api/repositories/{id}/analyze` - Run test analysis
- `POST /api/repositories/{id}/select-tests` - Select tests

See http://localhost:8000/docs for full API documentation.

## Development

### Backend Development

```bash
cd backend
python -m uvicorn api.main:app --reload --reload-dir . --port 8000
```

### Frontend Development

```bash
cd frontend
npm run dev
```

## Production Deployment

See [PRODUCTION.md](PRODUCTION.md) for comprehensive production deployment guide.

Quick steps:
1. Set environment variables in production environment
2. Initialize database: `python backend/deterministic/01_create_tables.py`
3. Build frontend: `cd frontend && npm run build`
4. Serve with production server (Gunicorn + Nginx)
5. Configure CORS for production domain

## License

[Your License Here]
