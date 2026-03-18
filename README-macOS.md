# NTAwesome on macOS Apple Silicon

This repository can be run from source on macOS Apple Silicon, but the polished end-user bundle should be built and tested on a Mac before publishing.

## Run from source

1. Install Python 3.11 on the Mac.
2. In the repo root, create a virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

3. Install the dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-windows.txt
```

4. Run the processor:

```bash
python app/zetaview_plotter.py "/path/to/data/folder"
```

The app itself should live on the local Mac. The measurement data can stay on a mounted network share.

## Before publishing a macOS release

- test on an Apple Silicon Mac
- verify drag/paste path handling for mounted network shares
- decide whether to ship a local Python runtime inside the macOS bundle or require first-run setup
