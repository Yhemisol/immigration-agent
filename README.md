# Immigration Intelligence Agent

Crawls USCIS, SEVP, State Department, and Federal Register daily. Uses Claude AI to summarize updates and classify impact by visa category. Sends a formatted HTML report to your Gmail inbox.

## Visa categories tracked
- F1 Students
- STEM OPT
- EB2 NIW
- O1 Visa
- Nigerian Nationals

---

## Local setup

### 1. Clone and install

```bash
cd "Immigration agent"
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your real keys
```

**Getting a Gmail App Password:**
1. Go to [Google Account](https://myaccount.google.com) → Security
2. Enable **2-Step Verification** if not already on
3. Under "2-Step Verification", scroll to **App passwords**
4. Create one for "Mail" → copy the 16-character password
5. Paste it as `GMAIL_APP_PASSWORD` in your `.env`

### 3. Load env vars and run

```bash
export $(cat .env | xargs)
python main.py
```

The HTML report is saved to `output/report_YYYY-MM-DD.html` and emailed to your inbox.

---

## GitHub Actions deployment

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial immigration agent"
git remote add origin https://github.com/YOUR_USERNAME/immigration-agent.git
git push -u origin main
```

### 2. Add secrets

In your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**, add:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Claude API key |
| `GMAIL_FROM` | `rafshakirat@gmail.com` |
| `GMAIL_TO` | `rafshakirat@gmail.com` |
| `GMAIL_APP_PASSWORD` | Your 16-char Gmail app password |

### 3. Enable Actions

- Go to **Actions** tab in your GitHub repo
- Click **Enable workflows** if prompted
- To test immediately: **Actions → Daily Immigration Intelligence Report → Run workflow**

The workflow runs automatically every day at 7:00 AM UTC.

---

## Folder structure

```
immigration-agent/
├── .github/
│   └── workflows/
│       └── daily.yml        # GitHub Actions cron job
├── agent/
│   ├── __init__.py
│   ├── crawlers.py          # Web scrapers for all 4 sources
│   ├── db.py                # SQLite storage + change detection
│   ├── classifier.py        # Claude API summarizer + impact classifier
│   └── reporter.py          # HTML report builder + Gmail sender
├── data/                    # Auto-created; holds immigration.db (gitignored)
├── output/                  # Auto-created; holds HTML reports (gitignored)
├── main.py                  # Orchestrator
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Customisation

- **Change run time**: Edit the cron expression in `.github/workflows/daily.yml`
- **Add more sources**: Add a new function to `agent/crawlers.py` and include it in `crawl_all()`
- **Add visa categories**: Update `VISA_CATEGORIES` in `agent/classifier.py` and the system prompt
- **Change Claude model**: Edit `model=` in `agent/classifier.py`
