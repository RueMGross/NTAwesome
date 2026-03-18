# NTAwesome

NTAwesome processes ZetaView nanoparticle tracking analysis exports by scanning a folder for matching `.pdf`, `.fcs`, and `.txt` files, grouping complete replicate sets, extracting summary values, and writing tables and plots into `NTAwesome Output`.

The project is designed around one practical rule:

- the app bundle should run from a local machine
- the measurement data can stay on a mounted network drive

## What NTAwesome does

Given a folder of ZetaView exports, NTAwesome:

- finds matching `.pdf`, `.fcs`, and `.txt` files
- groups complete replicate sets (`_000`, `_001`, `_002`)
- extracts summary values from the PDF reports
- derives particle size distribution data from the FCS and TXT files
- creates CSV summaries
- creates summary and per-sample PDF plots
- writes all outputs into `NTAwesome Output` in the selected data folder

## Who this repository is for

This repository is the source and build repo for NTAwesome.

It is intended for:

- maintaining the processing script
- building release bundles
- packaging Windows and macOS distributions
- documenting how to run and rebuild the tool

It is not intended to store large bundled Python runtimes or routine measurement datasets.

## Repository layout

- `app/`  
  Main Python processing code
- `Run-NTAwesome.*`  
  End-user launchers for Windows bundles
- `Setup-NTAwesome.*`  
  First-run/runtime setup for Windows bundles
- `requirements-windows.txt`  
  Python dependencies for the current app
- `BUILDING.md`  
  Release/build instructions
- `README-Windows.md`  
  Windows usage and bundle notes
- `README-macOS.md`  
  macOS source-run notes

## Quick start

### Windows users

Use the packaged Windows bundle, not the raw source repo.

1. Copy or unzip the app folder to a **local** Windows path.
2. Run `Run-NTAwesome.cmd`.
3. Paste or drag:
   - the measurement folder path, or
   - any one file inside that folder
4. Press Enter.

Important:

- keep the app itself on the local PC
- the measurement data may stay on a network drive

See `README-Windows.md` for details.

### macOS Apple Silicon

Run from source on a local Mac with Python 3.11.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-windows.txt
python app/zetaview_plotter.py "/path/to/data/folder"
