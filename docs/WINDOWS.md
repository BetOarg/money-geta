# Windows 11 quick start

Run these commands from PowerShell after cloning this repository.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install pytest
python -m pytest
```

## Check a campaign

Copy the example and fill it with campaign-specific evidence:

```powershell
Copy-Item config/campaign.example.json config/campaign.json
python -m scripts.campaign_check --campaign config/campaign.json
```

The supplied example intentionally fails closed until its fields are completed. The permission and credit booleans are operator attestations, not automated proof.

## Allocate a new live session folder

```powershell
python -c "from scripts.session_paths import create_session_dir; print(create_session_dir('jobs', 'campaign-01'))"
```

The helper creates a new unique folder under `jobs/<job-id>/live/`. It does not delete, clean or reuse previous session folders.

Do not put API keys in command history, tracked JSON files, screenshots or commits. Keep credentials in local environment variables or an approved secret manager.
