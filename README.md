# NTAwesome

Makes data analysis from ZetaView NTA output awesome.

NTAwesome processes ZetaView nanoparticle tracking analysis exports by scanning a folder for matching `.pdf`, `.fcs`, and `.txt` files, grouping complete replicate sets, extracting values from the PDFs, and writing results into `NTAwesome Output`.

This GitHub repository is intended to store the source code and build scripts, not the bundled Python runtimes or sample data folders used for local testing.

## Content

- `app/`
- launcher and setup scripts
- requirements files
- build and packaging scripts
- documentation

For Windows, the verified local build path is described in `BUILDING.md` and `README-Windows.md`.
For macOS Apple Silicon, use `README-macOS.md` as the starting point. 
