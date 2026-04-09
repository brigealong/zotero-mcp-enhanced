# MCP Service Step By Step

This page is written for a first-time Windows user.

If you have never used Python, PowerShell, or a virtual environment before, follow the steps exactly in order.

## Goal

At the end of this guide, you will be able to start the MCP service locally and see a success message in the terminal.

## Before You Start

You need:

- Windows
- Python 3.10 or newer
- the repository already downloaded to your computer

You do not need any proprietary OCR software for the first startup test.

## Step 1. Open PowerShell

1. Press the `Windows` key.
2. Type `PowerShell`.
3. Click `Windows PowerShell`.

You should see a terminal window with text like:

```powershell
PS C:\Users\YourName>
```

## Step 2. Go into the MCP service folder

Copy and run this command:

```powershell
cd "C:\path\to\zotero-mcp-enhanced\mcp-service"
```

Replace `C:\path\to\zotero-mcp-enhanced` with the real path on your computer.

After that, the terminal line should end with:

```powershell
\mcp-service>
```

## Step 3. Create a Python virtual environment

Run:

```powershell
python -m venv .venv
```

What this does:

- it creates a small private Python environment for this project
- it keeps this project separate from other Python projects on your computer

If the command succeeds, you usually will not see a long message. That is normal.

## Step 4. Turn on the virtual environment

Run:

```powershell
.venv\Scripts\Activate.ps1
```

If it works, your terminal line will usually change from:

```powershell
PS C:\...\mcp-service>
```

to:

```powershell
(.venv) PS C:\...\mcp-service>
```

That `(.venv)` at the start means the environment is active.

## Step 5. Install the required Python packages

Run:

```powershell
pip install -e .[test]
```

Wait until the installation finishes.

If your computer says this form does not work, use these two commands instead:

```powershell
pip install -e .
pip install pytest
```

## Step 6. Start the MCP service in safe test mode

Run:

```powershell
python -m zotero_mcp_enhanced_service --base-dir . --runner stub
```

Important:

- `--runner stub` means "start in test mode"
- this mode does not require any external OCR engine
- this is the best way to confirm your basic setup is correct

## Step 7. Check whether startup succeeded

If the service starts correctly, the terminal should stay open and show that the process is running.

You should not see an immediate red error traceback.

If you want to stop the service, press:

```text
Ctrl + C
```

## Step 8. Optional: run the test suite

If you want to check that the local Python part is healthy, run:

```powershell
pytest tests
```

If everything is fine, you should see passing tests.

## Common Problems

### Problem: `python` is not recognized

This usually means Python is not installed, or not added to `PATH`.

Fix:

- install Python 3.10 or newer
- during installation, enable the option to add Python to `PATH`
- close PowerShell and open it again

### Problem: PowerShell blocks `Activate.ps1`

Run this command in the same PowerShell window:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Then run again:

```powershell
.venv\Scripts\Activate.ps1
```

### Problem: you do not have any OCR tool installed

That is fine for the first test.

Use:

```powershell
python -m zotero_mcp_enhanced_service --base-dir . --runner stub
```

Do not switch to the real OCR runner until the stub mode works.

## Optional Open-Source OCR Mode

After stub mode works, you can optionally add an open-source OCR runner:

1. Install `OCRmyPDF`.
2. Install `Tesseract OCR`.
3. Make sure both commands are available in PowerShell.
4. Run:

```powershell
python -m zotero_mcp_enhanced_service --base-dir . --runner ocrmypdf
```

If you want a quick environment check, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\probe_ocrmypdf.ps1
```

## Summary

The shortest working command flow is:

```powershell
cd "C:\path\to\zotero-mcp-enhanced\mcp-service"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[test]
python -m zotero_mcp_enhanced_service --base-dir . --runner stub
```
