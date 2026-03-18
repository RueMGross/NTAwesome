# NTAwesome

Makes data analysis from ZetaView NTA output awesome.

NTAwesome processes ZetaView nanoparticle tracking analysis exports by scanning a folder for matching `.pdf`, `.fcs`, and `.txt` files, grouping complete replicate sets, extracting values from the PDFs, and writing results into `NTAwesome Output`.

This GitHub repository is intended to store the source code and build scripts, not the bundled Python runtimes or sample data folders used for local testing.

## What belongs in GitHub

- `app/`
- launcher and setup scripts
- requirements files
- build and packaging scripts
- documentation

## What stays out of GitHub

- bundled `python/` runtimes
- `Test data/`
- generated `NTAwesome Output/`
- release zip files
- downloaded bootstrap installers or Python archives

## Releases

The recommended distribution model is:

1. Keep this repository source-only.
2. Build platform-specific release bundles from the repo.
3. Upload the ready-to-run bundles to GitHub Releases.

For Windows, the verified local build path is described in `BUILDING.md` and `README-Windows.md`.

For macOS Apple Silicon, use `README-macOS.md` as the starting point. A polished no-Python-needed macOS bundle should be built and tested on a Mac before publishing.
