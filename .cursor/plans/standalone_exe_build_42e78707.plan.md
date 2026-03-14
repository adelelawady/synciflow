---
name: Standalone exe build
overview: Add a one-command standalone Windows exe build to the project using pyproject.toml, the hatch-pyinstaller plugin, and a small entry script so that `hatch build --target pyinstaller` produces a production executable.
todos: []
isProject: false
---

# Standalone exe build from pyproject.toml (one command)

## Goal

Build a production standalone Windows executable with a single command, configured entirely via [pyproject.toml](c:\Users\adel\KONSOL\workspace\synciflow\pyproject.toml).

## Approach

Use the **hatch-pyinstaller** Hatch plugin so that:

- One command builds the exe: `**hatch build --target pyinstaller`**
- All build options live in `pyproject.toml` under `[tool.hatch.build.targets.pyinstaller]`
- Output goes to the standard Hatch `dist/` directory

## Key details

- **Entry point**: The app is exposed as a console script `synciflow = "synciflow.cli.main:run"`. PyInstaller expects a script file. The hatch-pyinstaller plugin looks for a script named like the project in the project root (`synciflow.py`) if `scriptname` is not set.
- **Frontend**: The server serves the UI from `synciflow/frontend` via `resources.files("synciflow") / "frontend"` ([server.py](c:\Users\adel\KONSOL\workspace\synciflow\src\synciflow\api\server.py) lines 54–65). That directory must be bundled as package data so the exe can serve the UI when running `serve`.
- **Dependencies**: Heavy stack (FastAPI, uvicorn, typer, sqlmodel, syncify-py, yt-dlp, selenium, etc.). The plugin option `require-runtime-dependencies = true` is required so PyInstaller can find installed packages.

## Implementation plan

### 1. Add entry script for PyInstaller

Create a minimal script at the **project root** so the plugin can use it as the main script (plugin default is a file named like the project in the root):

- **File**: `synciflow.py` (repository root)
- **Content**: Call the existing CLI entry point:

```python
from synciflow.cli.main import run
if __name__ == "__main__":
    run()
```

No change to [src/synciflow/cli/main.py](c:\Users\adel\KONSOL\workspace\synciflow\src\synciflow\cli\main.py) is required.

### 2. Extend pyproject.toml

- **Build system**: Add `hatch-pyinstaller` to `[build-system] requires` (alongside `hatchling`). The plugin pulls in PyInstaller as a dependency.
- **New section** `[tool.hatch.build.targets.pyinstaller]` with:
  - `require-runtime-dependencies = true` so the built exe has access to all project dependencies.
  - **One-file exe**: `flags = ["--onefile", "--clean"]` for a single production exe (optional: `--onedir` for faster startup and easier debugging).
  - **Console app**: `flags` should include `--console` (or omit `--windowed`) so the CLI and `serve` output are visible.
  - **Package data for frontend**: Use PyInstaller’s data collection so `synciflow/frontend` is inside the bundle. With hatch-pyinstaller, use the list form for multi-value options, e.g. `collect-data = ["synciflow=src/synciflow/frontend"]` (exact path may depend on how the plugin runs; alternative is `synciflow=synciflow/frontend` if run from an environment where the package is installed). If the exe fails to find the frontend, add a PyInstaller hook or a short spec-file step to include `synciflow/frontend` explicitly.
  - **Name**: Set `name = "synciflow"` (or leave default) so the exe is `synciflow.exe`.
  - **Optional**: `log-level = "WARN"` to reduce build noise.

### 3. Optional: hidden imports and hooks

If the first build misses modules (e.g. typer subcommands, uvicorn, or server dependencies), add to the same section:

- `hiddenimport` (or the plugin’s equivalent list option) for any missing modules reported by the exe at runtime.
- If needed, a **PyInstaller hook** (e.g. in `hooks/` or via `--additional-hooks-dirs`) to ensure `synciflow.frontend` and all server dependencies are collected.

### 4. One command to build

From the project root (with the project’s environment activated and dependencies installed):

```bash
hatch build --target pyinstaller
```

Output: `dist/synciflow.exe` (onefile) or, if using `--onedir`, `dist/synciflow/` with `synciflow.exe` and dependencies beside it.

### 5. Documentation

- In [README.md](c:\Users\adel\KONSOL\workspace\synciflow\README.md), add a short “Building a standalone executable” section:
  - Install dependencies (e.g. `uv sync` or `pip install -e .`).
  - Run: `hatch build --target pyinstaller`.
  - Note where the exe is (`dist/`) and that it is Windows-only from this build (Linux/macOS would need their own build or a different target).

## Notes

- **Platform**: This setup is for a **Windows** exe. Building on Linux/macOS with the same command may produce a binary for the current OS depending on PyInstaller; cross-compilation is not supported by PyInstaller.
- **Selenium / webdriver-manager**: These may download browser drivers at runtime; no change needed for the exe build.
- **Runtimes**: The exe will still require any external runtimes (e.g. ffmpeg) to be available on the PATH or configured per your app’s design; PyInstaller only bundles Python and the packages you collect.

## Summary


| Item          | Action                                                                                                                                                                            |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Entry script  | Add `synciflow.py` at repo root calling `synciflow.cli.main:run`                                                                                                                  |
| Build backend | Add `hatch-pyinstaller` to `[build-system] requires` in pyproject.toml                                                                                                            |
| Exe config    | Add `[tool.hatch.build.targets.pyinstaller]` with `require-runtime-dependencies`, `flags` (e.g. `--onefile`, `--clean`, `--console`), and `collect-data` for `synciflow/frontend` |
| Build command | `hatch build --target pyinstaller`                                                                                                                                                |
| Docs          | Short “Standalone exe” section in README                                                                                                                                          |


No new top-level build scripts are required; the single command is `**hatch build --target pyinstaller`**, with all configuration in `pyproject.toml`.