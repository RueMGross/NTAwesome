# NTAwesome for Windows

This bundle is meant to run locally on a Windows PC, while the measurement data can stay on a network drive.

No separate Python installation is needed when the shared folder already contains its `python\` subfolder.

## What colleagues do

1. Copy or unzip the whole folder to a local Windows path.
2. Double-click `Run-NTAwesome.cmd`.
3. Paste or drag either:
   - the measurement folder path
   - or any one file inside that folder
4. Press Enter.

The app will process matching `.pdf`, `.fcs`, and `.txt` files and create `NTAwesome Output` in the selected data folder.

## Important rule

- Keep the app folder local on the PC.
- The data folder can stay on the network drive.

## Files that must stay together

For normal colleague use:

- `Run-NTAwesome.cmd`
- `app\`
- `python\`

For maintenance or rebuilds:

- `Setup-NTAwesome.cmd`
- `Setup-NTAwesome.ps1`
- `Run-NTAwesome.ps1`
- `Prepare-WindowsRuntime.ps1`
- `requirements-windows.txt`
- `bootstrap\python-portable.zip`

## Build-machine setup

If you need to rebuild the local Python runtime on a Windows build PC:

```bat
Setup-NTAwesome.cmd --force-reinstall
```

The setup script now builds a self-contained local Python from `bootstrap\python-portable.zip` or downloads that ZIP from python.org if it is missing. It does not create a venv from a system Python installation anymore.

After setup, test with:

```bat
Run-NTAwesome.cmd ".\Test data"
```

Then zip and share the whole folder, including the populated `python\` directory.
