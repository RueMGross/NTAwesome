# NTAAwesome Windows Bundle

This is the folder to zip and share with colleagues.

No separate Python installation is needed when this folder still contains its `python\` subfolder.

## For colleagues

1. Copy or unzip this whole folder to a local Windows folder.
2. Double-click `Run-NTAwesome.cmd`.
3. Paste or drag:
   - the measurement folder path
   - or any one file inside that folder
4. Press Enter.

The app runs locally from this folder. The measurement data can stay on the network drive.

## Required files

For normal use, keep these together:

- `Run-NTAwesome.cmd`
- `app\`
- `python\`

For repair or rebuilds, also keep:

- `Setup-NTAwesome.cmd`
- `Setup-NTAwesome.ps1`
- `Run-NTAwesome.ps1`
- `Prepare-WindowsRuntime.ps1`
- `requirements-windows.txt`
- `bootstrap\python-portable.zip`

## Important notes

- Do not run the app from a network drive.
- Do not delete the `python\` folder.
- If `python\` is missing, run `Setup-NTAwesome.cmd` to rebuild it from the bundled portable Python ZIP.
