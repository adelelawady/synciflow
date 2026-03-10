synciflow
=========

`synciflow` is a Python package scaffolded as an empty project, ready to be developed and later published to both GitHub and PyPI.

## Installation

This package is not yet published to PyPI.

Once it is published, you will be able to install it with:

```bash
pip install synciflow
```

## Development

- **Create a virtual environment** (recommended) and install the project in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

- **Run tests** (once you add some):

```bash
pytest
```

## Publishing

1. Build distribution files:

```bash
python -m build
```

2. Upload to PyPI (or TestPyPI):

```bash
python -m twine upload dist/*
```

Remember to set the correct metadata in `pyproject.toml` (project name, description, URLs, author, etc.) before publishing.



How to run
CLI (after installing):

synciflow track <spotify_track_url>
synciflow playlist <spotify_playlist_url>
synciflow sync <spotify_playlist_url>
synciflow serve --host 127.0.0.1 --port 8000
API

Start: synciflow serve
Endpoints:
POST /track/load { "url": "..." }
POST /playlist/load { "url": "..." }
POST /playlist/sync { "url": "..." }
GET /track/{track_id}
GET /track/{track_id}/stream