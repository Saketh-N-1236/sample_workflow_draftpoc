# Test Impact Analysis Web Platform

Production-ready web platform for test impact analysis with GitHub and GitLab integration.

## Features

- ✅ **GitHub & GitLab Support**: Connect to repositories via API (no cloning)
- ✅ **Branch Management**: List and select branches
- ✅ **Diff Viewing**: View code changes with statistics
- ✅ **Test Analysis**: 8-step pipeline for test repository analysis
- ✅ **Test Selection**: AST and semantic-based test selection
- ✅ **Modern UI**: React frontend with responsive design

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- Environment variables configured (see [CONFIGURATION.md](CONFIGURATION.md))

### Installation

1. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   ```

3. **Configure environment**
   - Create `.env` file in project root
   - Add `GITHUB_API_TOKEN` and/or `GITLAB_API_TOKEN`
   - See [CONFIGURATION.md](CONFIGURATION.md) for details

### Running

**Backend:**
```bash
python -m uvicorn api.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm run dev
```

**Access:**
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Project Structure

```
web_platform/
├── api/                    # FastAPI application
│   ├── main.py            # Application entry point
│   ├── models/            # Pydantic models
│   └── routes/            # API endpoints
├── frontend/              # React application
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── pages/        # Page components
│   │   └── services/     # API client
│   └── package.json
├── services/              # Business logic
│   ├── git_service.py    # Git operations
│   ├── github_service.py # GitHub API
│   ├── gitlab_service.py # GitLab API
│   ├── analysis_service.py
│   └── selection_service.py
└── requirements.txt      # Python dependencies
```

## API Endpoints

### Repositories

- `POST /api/repositories/connect` - Connect to repository
- `GET /api/repositories/{id}` - Get repository info
- `GET /api/repositories/{id}/branches` - List branches
- `GET /api/repositories/{id}/diff` - Get git diff

### Analysis

- `POST /api/repositories/{id}/analyze` - Run test analysis
- `GET /api/repositories/{id}/analysis/status` - Get analysis status

### Selection

- `POST /api/repositories/{id}/select-tests` - Select tests
- `GET /api/repositories/{id}/results` - Get results

## Configuration

See [CONFIGURATION.md](CONFIGURATION.md) for environment variables and setup.

## Development

### Backend

```bash
# Development with auto-reload
python -m uvicorn api.main:app --reload --port 8000

# Production (no reload)
python -m uvicorn api.main:app --port 8000
```

### Frontend

```bash
cd frontend
npm run dev      # Development
npm run build    # Production build
```

## Troubleshooting

### Token Issues

- Check `.env` file location (should be in project root)
- Verify token format (no quotes, no spaces)
- Restart server after changing `.env`
- Use `/api/debug/env` endpoint to verify loading

### API Errors

- Check server logs for detailed error messages
- Verify token has correct scopes
- Ensure repository URL is correct format

## License

[Your License Here]
