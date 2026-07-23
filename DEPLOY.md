# Deploying AssetEra to Railway

AssetEra is a **Streamlit** app (persistent server + WebSockets). Railway runs it
from the `Dockerfile` in this repo. The image binds to Railway's injected `$PORT`,
runs headless, and exposes a health check at `/_stcore/health`.

## Prerequisites

- A [Railway](https://railway.app) account
- This GitHub repo: `https://github.com/Anant1213/AssetEra`
- Live credentials for: AWS S3, OpenAI, FRED, and a **working** Postgres URL
  (the old Supabase instance is dead — provision a new one, e.g. Railway Postgres
  or a fresh Supabase project).

## 1 · Create the project from GitHub

1. Railway dashboard → **New Project** → **Deploy from GitHub repo**.
2. Authorize Railway for your GitHub account and pick **`Anant1213/AssetEra`**.
3. Railway detects `railway.json` + `Dockerfile` and builds automatically.
   No build/start command needed — the Dockerfile's `CMD` handles it.

## 2 · Set environment variables

Railway → your service → **Variables** → add each of these (values from your
local `.env`, which is intentionally **not** in the repo):

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | AI Advisor (GPT-4o-mini) |
| `DATA_BUCKET` | S3 data-lake bucket name |
| `AWS_ACCESS_KEY_ID` | S3 access |
| `AWS_SECRET_ACCESS_KEY` | S3 access |
| `AWS_REGION` | e.g. `ap-south-1` |
| `FRED_API_KEY` | Macro series |
| `POSTGRES_URL` | Portfolio Builder persistence — **must be a live DB** |

> Do **not** set `PORT` — Railway injects it and the container reads it.
>
> Tip: if you add a **Railway Postgres** plugin, reference its connection
> string with `POSTGRES_URL=${{Postgres.DATABASE_URL}}` in the Variables tab.

## 3 · Generate a public URL

Service → **Settings** → **Networking** → **Generate Domain**.
Railway maps the domain to the container's `$PORT`. Open it and verify each page
(Market Watch, Fund Backtester, Portfolio Builder, Risk Profiler, AI Advisor,
Research, Data Workbench).

## 4 · Continuous deploys

Railway redeploys automatically on every push to `main`. To deploy a change:
`git push origin main` → Railway rebuilds the image and rolls it out.

## Local sanity check (optional)

```bash
docker build -t assetera .
docker run --rm -p 8501:8501 --env-file .env assetera
# open http://localhost:8501
```

## Notes

- `data_cache/` and `models/*.pkl` are **not** shipped in the image (see
  `.dockerignore`); the app rehydrates price data from S3 / yfinance and
  retrains the small risk model on first run (~3 s).
- Health check path is `/_stcore/health` (Streamlit's built-in endpoint).
