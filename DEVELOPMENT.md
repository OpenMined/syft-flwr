# Development Guide

This guide covers setting up a development environment for syft-flwr.

## Prerequisites

- **Python**: 3.12 or higher (< 3.14)
- **uv**: Fast Python package manager ([install instructions](https://docs.astral.sh/uv/getting-started/installation/))
- **just**: Command runner (optional, but recommended) - `brew install just` or `cargo install just`

## Installation

```bash
# Clone the repository
git clone https://github.com/OpenMined/syft-flwr.git
cd syft-flwr

# Create virtual environment and install dependencies
uv venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
uv pip install -e .
uv sync --group dev
```

## Running Tests

### Unit Tests

```bash
# Using just (recommended)
just test-unit

# Or directly with pytest
uv run pytest tests/ -v -n auto --ignore=tests/integration/syft-client

# With coverage
uv run pytest tests/ -v -n auto --cov=syft_flwr --cov-report=term-missing --ignore=tests/integration/syft-client
```

### Integration Tests (Google Drive)

Integration tests require Google OAuth credentials. These tests are marked as `slow` and excluded from CI by default.

```bash
# Using just (recommended)
just test-integration

# Or directly with pytest
pytest tests/integration/syft-client -v -s

# Run only slow tests (integration tests)
pytest -m slow -v -s

# Skip slow tests when running all tests
pytest -m "not slow" -v

# Single Data Owner test only
pytest tests/integration/syft-client/fl_diabetes_one_do_test.py -v -s

# Two Data Owners test only
pytest tests/integration/syft-client/fl_diabetes_two_dos_test.py -v -s
```

### All Tests

```bash
# Run both unit and integration tests
just test
```

See [Google OAuth Setup](#google-oauth-setup-for-integration-tests) below for credential setup.

## Google OAuth Setup (for Integration Tests)

Integration tests use Google Drive as the transport layer, requiring OAuth credentials for each participant (Data Owners and Data Scientist).

### Step-by-Step Setup

#### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing one)
3. Note your project name for later

#### 2. Enable Google Drive API

1. Go to "APIs & Services" → "Library"
2. Search for "Google Drive API"
3. Click "Enable"

#### 3. Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
2. Choose **"External"** (or "Internal" if using Google Workspace)
3. Fill in required fields:
   - App name (e.g., "SyftBox Integration Tests")
   - User support email
   - Developer contact email
4. Add scopes: `https://www.googleapis.com/auth/drive`
5. Add your test user emails (DO1, DO2, DS emails)
6. Save

#### 4. Publish OAuth App (Important for CI/CD)

While in "Testing" mode, OAuth tokens expire after **7 days**. To make tokens persistent:

1. Go to "APIs & Services" → "OAuth consent screen" → "Audience"
2. Click **"PUBLISH APP"**
3. Confirm the prompt

Once published, refresh tokens won't expire unless manually revoked.

> **Note**: For "External" apps, Google may require verification for sensitive scopes, but for personal/testing use with your own accounts, this is usually not enforced.

#### 5. Create OAuth Credentials

Create credentials for each participant (DO1, DO2, DS):

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: **Desktop app**
4. Name it (e.g., "DO1 Client", "DO2 Client", "DS Client")
5. Click "Create"
6. Download the JSON file
7. Save as `do1.json`, `do2.json`, or `ds.json` in `credentials/`

### Required Files

```
credentials/
├── do1.json              # Data Owner 1 OAuth credentials
├── do2.json              # Data Owner 2 OAuth credentials
├── ds.json               # Data Scientist OAuth credentials
├── token_do1.json        # Auto-generated on first run
├── token_do2.json        # Auto-generated on first run
├── token_ds.json         # Auto-generated on first run
└── .env                  # Environment variables
```

### Credential File Structure

Each downloaded JSON file will look like:

```json
{
  "installed": {
    "client_id": "xxx.apps.googleusercontent.com",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_secret": "xxx",
    "redirect_uris": ["http://localhost"]
  }
}
```

### Environment Variables (.env)

Create `credentials/.env`:

```bash
# Data Owner 1
SYFT_EMAIL_DO1="do1@gmail.com"
SYFT_CRED_FNAME_DO1="do1.json"
SYFT_TOKEN_FNAME_DO1="token_do1.json"

# Data Owner 2
SYFT_EMAIL_DO2="do2@gmail.com"
SYFT_CRED_FNAME_DO2="do2.json"
SYFT_TOKEN_FNAME_DO2="token_do2.json"

# Data Scientist
SYFT_EMAIL_DS="ds@gmail.com"
SYFT_CRED_FNAME_DS="ds.json"
SYFT_TOKEN_FNAME_DS="token_ds.json"
```

### Token Generation

Token files are generated automatically when you first run the tests:

1. Run `just test-integration`
2. A browser window opens for each user to authenticate
3. Complete the OAuth flow for each account
4. Tokens are saved to `credentials/token_*.json`

### Security Notes

- **Never commit** credential files or tokens to git (they're in `.gitignore`)
- Credentials are scoped to Google Drive only
- Tokens can be revoked at https://myaccount.google.com/permissions

## CI/CD

### Automated Tests (GitHub Actions)

Unit tests run automatically on push/PR to main branch across:
- OS: Ubuntu, Windows, macOS
- Python: 3.10, 3.11, 3.12

### Integration Tests in CI

Integration tests can be triggered manually via GitHub Actions. Required secrets:

| Secret Name | Content |
|-------------|---------|
| `GDRIVE_CRED_DO1` | Contents of `do1.json` |
| `GDRIVE_CRED_DO2` | Contents of `do2.json` |
| `GDRIVE_CRED_DS` | Contents of `ds.json` |
| `GDRIVE_TOKEN_DO1` | Contents of `token_do1.json` |
| `GDRIVE_TOKEN_DO2` | Contents of `token_do2.json` |
| `GDRIVE_TOKEN_DS` | Contents of `token_ds.json` |
| `EMAIL_DO1` | DO1 email address |
| `EMAIL_DO2` | DO2 email address |
| `EMAIL_DS` | DS email address |

To run: Go to Actions → "Integration Tests (Google Drive)" → "Run workflow"

## Useful Commands

```bash
# List all available commands
just

# Run unit tests only
just test-unit

# Run integration tests only (requires Google OAuth credentials)
just test-integration

# Run all tests (unit + integration)
just test

# Clean up generated files
just clean

# Show current version
just show-version

# Bump version (patch/minor/major)
just bump patch
just bump minor
just bump major

# Dry run version bump
just bump-dry patch

# Build wheel
just build

# Update notebook dependencies
just update-notebook-deps

# Update notebook lock files (after PyPI publish)
just update-notebook-locks
```

## Code Quality

### Linting

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for issues
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run on all files
uv run pre-commit run --all-files
```

## Project Structure

```
syft-flwr/
├── src/syft_flwr/          # Main package source
├── tests/
│   ├── unit/               # Unit tests (run in CI)
│   └── integration/
│       ├── simulation/     # Simulation tests
│       └── syft-client/    # Google Drive integration tests
├── notebooks/              # Example notebooks
├── credentials/            # OAuth credentials (gitignored)
├── scripts/
│   └── test.sh            # Test runner script
└── .github/workflows/      # CI/CD workflows
```

## Releasing

See [RELEASE.md](RELEASE.md) for the complete release process.
