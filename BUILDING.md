# Building NTAwesome

## Windows release bundle

From a Windows build machine in the repo root:

```bat
Build-WindowsBundle.cmd
```

This script will:

1. create `dist\NTAAwesome`
2. copy the app and launcher files into that folder
3. copy `bootstrap\python-portable.zip` if it is already present locally
4. run `Setup-NTAwesome.cmd --force-reinstall` inside the bundle
5. create `dist\NTAAwesome-win.zip`

The resulting zip is the file to upload to GitHub Releases for Windows users.

## macOS Apple Silicon

The repository can be used on macOS Apple Silicon, but the final no-Python-needed bundle should be built and tested on a Mac.

Current recommendation:

1. clone the repo on an Apple Silicon Mac
2. create a local Python 3.11 environment
3. install the dependencies
4. run `app/zetaview_plotter.py` locally with test data that is not committed to git
5. only after that create and publish a macOS release bundle

See [README-macOS.md](/C:/Users/Zen/Desktop/NTA%20Test/README-macOS.md) for the source-run steps.
