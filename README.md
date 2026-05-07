<div align="center">

<img src="https://img.shields.io/badge/AssetEra-Portfolio%20Intelligence-2962FF?style=for-the-badge&logoColor=white&labelColor=0A1220" height="42"/>

<br/><br/>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38+-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![AWS S3](https://img.shields.io/badge/AWS_S3-Data_Lake-FF9900?style=flat-square&logo=amazons3&logoColor=white)](https://aws.amazon.com/s3)
[![OpenAI](https://img.shields.io/badge/GPT--4o-AI_Advisor-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com)
[![FRED](https://img.shields.io/badge/FRED_API-Macro_Data-00C896?style=flat-square)](https://fred.stlouisfed.org)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

<br/>

**A Bloomberg Terminal-grade portfolio intelligence platform built on a structured S3 data lake.**  
Institutional analytics · AI-powered Q&A · Risk profiling · Real-time market data

<br/>

[**Market Watch**](#-market-watch) · [**Fund Backtester**](#-fund-backtester) · [**Risk Profiler**](#-risk-profiler) · [**AI Advisor**](#-ai-advisor) · [**Stock Research**](#-stock-research) · [**Data Workbench**](#-data-workbench)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Platform Architecture](#-platform-architecture)
- [S3 Data Lake](#-s3-data-lake)
- [Data Pipeline](#-data-pipeline)
- [Feature Pages](#-feature-pages)
- [Quant & ML Methods](#-quant--ml-methods)
- [Setup & Run](#-setup--run)
- [Environment Variables](#-environment-variables)
- [Daily Refresh](#-daily-refresh)
- [Docker](#-docker)
- [Disclaimer](#-disclaimer)

---

## 🌐 Overview

AssetEra is a multi-page Streamlit application that delivers institutional-grade financial analytics through a clean Bloomberg Terminal-inspired interface. It is backed by an **S3-first structured data lake** covering 186 symbols across equities, ETFs, fixed income, and macro series — with 10 years of daily OHLCV history and pre-computed analytics.

<br/>

<table>
<tr>
<td align="center" width="25%">

**📊 Market Watch**<br/>
<sub>Live charts · Candlestick · RSI · MACD · Bollinger · Correlation heatmap</sub>

</td>
<td align="center" width="25%">

**🏦 Fund Backtester**<br/>
<sub>5 model funds · Sharpe · Sortino · Calmar · Max drawdown · Monte Carlo</sub>

</td>
<td align="center" width="25%">

**🧠 Risk Profiler**<br/>
<sub>ML risk scoring · GBT model · Fund matching · GBM simulation</sub>

</td>
<td align="center" width="25%">

**🤖 AI Advisor**<br/>
<sub>GPT-4o streaming · Fund context · Portfolio Q&A · Risk-aware responses</sub>

</td>
</tr>
<tr>
<td align="center" width="25%">

**🔬 Stock Research**<br/>
<sub>Screener · Deep dive · Radar compare · 149 equities · 5 analytics modules</sub>

</td>
<td align="center" width="25%">

**🔧 Data Workbench**<br/>
<sub>CSV/Excel/JSON upload · Auto profiling · Quality scoring · AI summary</sub>

</td>
<td align="center" width="25%">

**📡 FRED Macro**<br/>
<sub>14 series · Yield curve · Rate regime · Inflation regime · Fed Funds</sub>

</td>
<td align="center" width="25%">

**🗄️ S3 Data Lake**<br/>
<sub>raw · curated · features · control · 186 symbols · 10yr history</sub>

</td>
</tr>
</table>

---

## 🏗 Platform Architecture

```mermaid
flowchart TD
    subgraph UI["🖥️  Streamlit App  (pages/)"]
        direction LR
        P0["🏠 app.py\nLanding"]
        P1["📊 Market Watch"]
        P2["🏦 Fund Backtester"]
        P3["🧠 Risk Profiler"]
        P4["🤖 AI Advisor"]
        P5["🔬 Stock Research"]
        P6["🔧 Data Workbench"]
    end

    subgraph BACK["⚙️  Backend  (backend/)"]
        direction LR
        MK["market.py\nOHLCV + metrics"]
        UI2["ui.py\nDesign system"]
        RP["risk_profiler/\nGBT model"]
        AI["ai_advisor/\nGPT-4o wrapper"]
        SR["stock_research/\nanalytics_store"]
        DW["data_workbench/\nprofile + views"]
    end

    subgraph DL["🗄️  Data Layer  (datalayer/)"]
        direction LR
        SCH["schemas.py\nUniverses + contracts"]
        S3C["s3.py\nZone-aware S3 client"]
        ING["ingest/\nequities · etf · fi · fred"]
        FEA["features/\ntechnical · macro"]
        QUE["queue.py\nSQS + local mode"]
        WRK["worker.py\nMessage processor"]
    end

    subgraph STORE["☁️  S3 Data Lake  (assetera-data-prod)"]
        direction TB
        RAW["raw/\nJSON.gz archives"]
        CUR["curated/\nCanonical Parquet"]
        FEAT["features/\nIndicators · Macro"]
        MKT["market/\nCompatibility files"]
        ANA["analytics/\nPre-computed metrics"]
        CTL["control/\nCatalog · Manifests"]
    end

    subgraph EXT["🌐  External APIs"]
        YF["Yahoo Finance\nyfinance"]
        OAI["OpenAI\nGPT-4o"]
        FR["FRED API\nSt. Louis Fed"]
    end

    P1 & P2 --> MK
    P3 --> RP
    P4 --> AI
    P5 --> SR
    P6 --> DW
    P0 & P1 & P3 & P4 & P5 & P6 --> UI2

    MK --> YF
    AI --> OAI
    SR --> ANA & CUR

    ING --> YF
    ING --> FR
    ING --> RAW & CUR
    FEA --> FEAT
    WRK --> ING & FEA
    QUE --> WRK

    S3C --> RAW & CUR & FEAT & MKT & ANA & CTL
    SCH --> ING & QUE

    style UI fill:#0D1525,stroke:#2962FF,color:#E4EAF5
    style BACK fill:#0D1525,stroke:#00C896,color:#E4EAF5
    style DL fill:#0D1525,stroke:#FFB020,color:#E4EAF5
    style STORE fill:#0D1525,stroke:#FF3560,color:#E4EAF5
    style EXT fill:#0D1525,stroke:#7A8BA0,color:#E4EAF5
```

---

## 🗄️ S3 Data Lake

The entire data foundation is a structured **S3 object store** organized into strict zones. Every zone has a defined schema contract and access pattern.

### Zone Layout

```
s3://assetera-data-prod/
│
├── raw/                          ← Source-faithful archives (JSON.gz)
│   ├── equities/source=yfinance/symbol=AAPL/dt=2026-04-20/run_id=.../payload.json.gz
│   ├── etf/source=yfinance/...
│   ├── fixed_income/source=yfinance/...
│   └── macro/source=fred/symbol=DGS10/...
│
├── curated/                      ← Canonical typed Parquet (snappy), one file per symbol
│   ├── equities/source=yfinance/symbol=AAPL/data.parquet
│   ├── etf/source=yfinance/symbol=SPY/data.parquet
│   ├── fixed_income/source=yfinance/symbol=TLT/data.parquet
│   └── macro/source=fred/symbol=DGS10/data.parquet
│
├── features/                     ← Derived indicators in long format
│   ├── equities/feature_set=technical_v1/symbol=AAPL/data.parquet
│   └── macro/feature_set=macro_v1/symbol=DGS10/data.parquet
│         └── COMPOSITE/data.parquet   ← yield curve spreads, regimes
│
├── market/                       ← Compatibility layer for analytics pipeline
│   ├── us_prices.parquet         ← 37 tickers (ETF + FI), 93k rows
│   └── us_equity_prices.parquet  ← 149 equities, 370k rows
│
├── analytics/                    ← Pre-computed analytics (5 modules × 2 markets)
│   ├── returns_US.parquet        ─┐
│   ├── risk_US.parquet            │  US (ETF + FI market)
│   ├── momentum_US.parquet        │  98k rows each
│   ├── zscore_US.parquet          │
│   ├── technical_US.parquet      ─┘
│   ├── returns_US_EQ.parquet     ─┐
│   ├── risk_US_EQ.parquet         │  US_EQ (149 equities)
│   ├── momentum_US_EQ.parquet     │  370k rows each
│   ├── zscore_US_EQ.parquet       │
│   └── technical_US_EQ.parquet   ─┘
│
└── control/                      ← Governance & tracking
    ├── catalog/datasets.json
    ├── runs/date=.../run_id=.../status.json
    ├── manifests/date=.../run_id=.../written_objects.json
    └── quality/date=.../run_id=.../quality_report.json
```

### Universe Coverage

| Asset Class | Count | Source | History |
|---|---|---|---|
| 🟦 US Equities (Large Cap) | 50 | Yahoo Finance | 10 years daily |
| 🟩 US Equities (Mid Cap) | 50 | Yahoo Finance | 10 years daily |
| 🟨 US Equities (Small Cap) | 49 | Yahoo Finance | 10 years daily |
| 🟧 ETFs (Broad · Sector · Intl) | 27 | Yahoo Finance | 10 years daily |
| 🟥 Fixed Income Proxies | 10 | Yahoo Finance | 10 years daily |
| 🟪 FRED Macro Series | 14 | St. Louis Fed | 10 years |
| **Total** | **200** | | |

<details>
<summary><b>📋 Full ticker lists</b></summary>

**Large Cap Equities**
`AAPL` `MSFT` `NVDA` `AMZN` `GOOGL` `META` `TSLA` `AVGO` `JPM` `LLY` `V` `UNH` `XOM` `MA` `JNJ` `PG` `HD` `COST` `MRK` `ABBV` `WMT` `BAC` `NFLX` `CRM` `CVX` `AMD` `ORCL` `PEP` `KO` `TMO` `ACN` `MCD` `CSCO` `WFC` `GE` `NOW` `ADBE` `TXN` `QCOM` `DHR` `PM` `CAT` `AMGN` `INTU` `SPGI` `MS` `GS` `IBM` `RTX` `BRK-B`

**ETFs**
`SPY` `QQQ` `IWM` `DIA` `VTI` `VOO` `XLK` `XLF` `XLV` `XLE` `XLI` `XLY` `XLP` `XLU` `XLB` `XLRE` `EFA` `EEM` `VEA` `VWO` `GLD` `SLV` `USO` `UNG` `AOM` `AOR` `AOA`

**Fixed Income Proxies**
`IEF` `TLT` `SHY` `LQD` `HYG` `BND` `AGG` `MUB` `TIP` `EMB`

**FRED Macro Series**
`DGS1MO` `DGS3MO` `DGS2` `DGS5` `DGS10` `DGS30` `DFF` `SOFR` `CPIAUCSL` `PCEPI` `GDPC1` `UNRATE` `PAYEMS` `BAMLH0A0HYM2`

</details>

---

## 🔄 Data Pipeline

```mermaid
flowchart LR
    subgraph SCHED["⏰ Schedule (daily)"]
        EB["EventBridge\n07:00 IST"]
    end

    subgraph ENQ["📤 Enqueuer"]
        E1["dl_enqueue.py\n--run-inline"]
    end

    subgraph SQS["🔀 SQS Queues"]
        Q1["assetera-ingest-equities"]
        Q2["assetera-ingest-etf"]
        Q3["assetera-ingest-fixed-income"]
        Q4["assetera-ingest-fred"]
    end

    subgraph WORK["⚙️ Workers  (dl_worker.py)"]
        W1["Equity Worker\nyfinance → raw + curated"]
        W2["ETF Worker\nyfinance → raw + curated"]
        W3["FI Worker\nyfinance → raw + curated"]
        W4["FRED Worker\nFRED API → raw + curated"]
    end

    subgraph FEAT["📐 Feature Engine"]
        F1["technical_v1\nRSI · MACD · BB · vol · returns"]
        F2["macro_v1\nYield spreads · Rate regime\nInflation regime"]
    end

    subgraph S3Z["☁️ S3 Zones"]
        R["raw/"]
        C["curated/"]
        FZ["features/"]
        MZ["market/"]
        AZ["analytics/"]
        CTL2["control/"]
    end

    subgraph ANA["📊 Analytics Pipeline"]
        AP["run_analytics.py\nreturns · risk · momentum\nzscore · technical"]
    end

    EB --> E1
    E1 --> Q1 & Q2 & Q3 & Q4
    Q1 --> W1 --> R & C --> F1 --> FZ
    Q2 --> W2 --> R & C
    Q3 --> W3 --> R & C
    Q4 --> W4 --> R & C --> F2 --> FZ
    C --> MZ --> AP --> AZ
    W1 & W2 & W3 & W4 --> CTL2

    style SCHED fill:#111C30,stroke:#7A8BA0
    style SQS fill:#111C30,stroke:#FF9900
    style WORK fill:#111C30,stroke:#00C896
    style FEAT fill:#111C30,stroke:#2962FF
    style S3Z fill:#111C30,stroke:#FFB020
    style ANA fill:#111C30,stroke:#FF3560
```

### Message Contract (SQS)

```json
{
  "run_id":           "20260420T070000Z",
  "job_type":         "ingest",
  "asset_class":      "equities",
  "source":           "yfinance",
  "symbol_or_series": "AAPL",
  "start_date":       "2016-04-17",
  "end_date":         "2026-04-20",
  "interval":         "1d",
  "cap":              "LARGE"
}
```

### Canonical OHLCV Schema (`curated/`)

| Column | Type | Description |
|---|---|---|
| `trade_date` | DATE | Trading date |
| `symbol` | STRING | Ticker symbol |
| `asset_class` | STRING | `equities` · `etf` · `fixed_income` |
| `open` `high` `low` `close` | DOUBLE | OHLC prices |
| `adj_close` | DOUBLE | Adjusted close (split/dividend adjusted) |
| `volume` | DOUBLE | Daily volume |
| `currency` | STRING | `USD` |
| `source` | STRING | `yfinance` |
| `ingested_at_utc` | TIMESTAMP | Ingest timestamp |
| `run_id` | STRING | Run identifier for lineage |

### Features Schema (`features/` — long format)

| Column | Type | Description |
|---|---|---|
| `date` | DATE | As-of date |
| `symbol_or_series` | STRING | Ticker or FRED series ID |
| `feature_set` | STRING | `technical_v1` · `macro_v1` |
| `feature_name` | STRING | `rsi_14` · `macd_line` · `t10y2y_spread` etc. |
| `feature_value` | DOUBLE | Numeric value |
| `window` | STRING | Lookback window e.g. `14d` · `252d` |

<details>
<summary><b>📐 All computed features</b></summary>

**technical_v1** (per equity/ETF/FI symbol)

| Feature | Description |
|---|---|
| `returns_1d` `returns_5d` `returns_21d` `returns_63d` `returns_252d` | Price returns over N days |
| `vol_21d` `vol_63d` | Annualised rolling volatility |
| `rsi_14` | Wilder RSI, 14-period |
| `macd_line` `macd_signal` `macd_hist` | MACD (12/26/9) |
| `bb_upper` `bb_mid` `bb_lower` `bb_pct_b` `bb_width` | Bollinger Bands (20, 2σ) |
| `ma_20` `ma_50` `ma_200` | Simple moving averages |
| `pct_vs_ma50` `pct_vs_ma200` | % above/below moving average |
| `golden_cross` | 1 when MA-50 > MA-200 |
| `atr_14` | Average True Range, normalised |

**macro_v1** (per FRED series + COMPOSITE)

| Feature | Description |
|---|---|
| `mom_1m` `mom_3m` `mom_12m` | Series momentum |
| `zscore_1y` `zscore_3y` | Z-score vs trailing 252 / 756 days |
| `t10y2y_spread` | DGS10 − DGS2 (yield curve) |
| `t10y3m_spread` | DGS10 − DGS3MO |
| `t30y10y_spread` | DGS30 − DGS10 |
| `rate_regime` | Fed Funds Rate rolling percentile |
| `inflation_regime` | CPI YoY rolling percentile |

</details>

---

## 📱 Feature Pages

### 📊 Market Watch

Real-time multi-ticker dashboard with advanced charting.

- Ticker selector across 6 categories (Market ETFs, Sectors, International, Commodities, Bonds, Rates)
- **Candlestick chart** with optional overlays: Bollinger Bands · RSI · MACD · Volume
- **Normalized performance** comparison (index = 100)
- **Correlation heatmap** with color-coded matrix
- CSV export for summary + full timeseries

---

### 🏦 Fund Backtester

Institutional-style fund simulation with 5 model portfolios.

| Fund | Strategy | Risk |
|---|---|---|
| Fund 1 | Conservative (bonds + defensive) | 🟢 Low |
| Fund 2 | Moderately Conservative | 🟡 Low-Med |
| Fund 3 | Balanced (60/40 approach) | 🟡 Medium |
| Fund 4 | Growth (tech + growth tilt) | 🟠 Med-High |
| Fund 5 | Aggressive (high-beta growth) | 🔴 High |

**Metrics computed:** Final value · Total return · CAGR · Sharpe · Sortino · Calmar · Max Drawdown · Beta · Alpha · VaR 95% · CVaR 95% · Upside/Downside Capture

**Benchmarks:** Single ticker · 60/40 Blend · 80/20 Blend · All-Weather

---

### 🧠 Risk Profiler

ML-powered investor risk classification with personalised fund recommendations.

```mermaid
flowchart LR
    Q["Questionnaire\nAge · Income · Horizon\nLoss tolerance · Experience"]
    --> GBT["GradientBoosting\nClassifier\n3,000 training samples"]
    --> S["Risk Score\n1 – 5"]
    --> R["Fund Recommendation\n+ GBM Simulation\n+ Feature Importance"]

    style Q fill:#0D1525,stroke:#2962FF,color:#E4EAF5
    style GBT fill:#0D1525,stroke:#FFB020,color:#E4EAF5
    style S fill:#0D1525,stroke:#00C896,color:#E4EAF5
    style R fill:#0D1525,stroke:#FF3560,color:#E4EAF5
```

- **Risk levels:** Conservative (1) → Aggressive (5)
- **GBM simulation:** Monte Carlo with 1,000 paths, 5th/25th/50th/75th/95th percentile fan chart
- **Session state integration:** risk score flows directly into AI Advisor context

---

### 🤖 AI Advisor

GPT-4o powered portfolio Q&A with full fund and risk context.

- Streams responses token-by-token via OpenAI Chat Completions
- Injects: AssetEra fund definitions · Risk level labels · User's risk score (if profiled)
- Maintains full conversation history in session state
- Example questions grid for quick exploration

---

### 🔬 Stock Research

Institutional-grade equity screener and deep-dive analytics backed by the S3 data lake.

```mermaid
flowchart LR
    subgraph IN["Inputs"]
        MKT["Market selector\nUS ETFs · US Equities"]
        CAP["Cap tier\nLarge · Mid · Small"]
    end

    subgraph SCR["🔍 Screener Tab"]
        FIL["Filter controls\nReturn · Vol · RSI · Sharpe\nMomentum · Golden Cross"]
        TBL["Sortable results table\nAll analytics columns"]
    end

    subgraph DD["🔬 Deep Dive Tab"]
        CND["Candlestick + BB + Volume"]
        RAD["Radar chart\nReturn · Risk · Momentum\nTechnical · Zscore"]
        AHD["Analytics history\nRolling 2yr charts"]
    end

    subgraph CMP["⚖️ Compare Tab"]
        C2["Side-by-side\nradar comparison\n2 tickers"]
    end

    IN --> SCR --> DD
    SCR --> CMP

    style IN fill:#0D1525,stroke:#7A8BA0,color:#E4EAF5
    style SCR fill:#0D1525,stroke:#2962FF,color:#E4EAF5
    style DD fill:#0D1525,stroke:#00C896,color:#E4EAF5
    style CMP fill:#0D1525,stroke:#FFB020,color:#E4EAF5
```

**Pre-computed analytics modules (from S3):**

| Module | Metrics |
|---|---|
| Returns | ret_1d · ret_5d · ret_21d · ret_63d · ret_252d |
| Risk | vol_21d · vol_252d · Sharpe · Sortino · Max DD · Beta · Alpha · VaR · CVaR |
| Momentum | mom_1m · mom_3m · mom_6m · mom_12m · 52w hi/lo · RS vs benchmark |
| Z-Score | z_price · z_ret · z_volume · cross-sectional z |
| Technical | RSI · BB %B · MACD · MA cross · ATR · Golden Cross |

---

### 🔧 Data Workbench

Drag-and-drop file analysis with AI-powered profiling.

- **Supported formats:** CSV · Excel (xlsx) · JSON · Parquet
- **Auto Views:** automatic chart generation (histogram · scatter · line · box · pie)
- **Data Quality:** completeness · duplicate · type consistency scoring
- **AI Summary:** LLM-generated dataset description (requires OpenAI key)
- **Project management:** organize datasets by project, stored in S3

---

## ⚙️ Quant & ML Methods

<details>
<summary><b>📈 Technical Analysis</b></summary>

| Indicator | Method |
|---|---|
| RSI | Wilder's smoothing (EWM α = 1/14) |
| Bollinger Bands | 20-day SMA ± 2σ; %B and bandwidth |
| MACD | EMA(12) − EMA(26); signal = EMA(9); histogram |
| ATR | max(H−L, |H−C₋₁|, |L−C₋₁|) · EWM; normalised by price |
| OBV | Cumulative on-balance volume |
| Moving Averages | SMA 20, 50, 200; % distance from price |

</details>

<details>
<summary><b>📐 Portfolio Risk Analytics</b></summary>

| Metric | Formula |
|---|---|
| Sharpe Ratio | (Rₚ − Rᶠ) / σₚ · √252 |
| Sortino Ratio | (Rₚ − Rᶠ) / σ_downside · √252 |
| Calmar Ratio | CAGR / Max Drawdown |
| Beta | Cov(Rₚ, Rₘ) / Var(Rₘ) |
| Alpha (Jensen) | Rₚ − [Rᶠ + β(Rₘ − Rᶠ)] · 252 |
| VaR 95% | 5th percentile of monthly returns |
| CVaR 95% | Mean of returns below VaR |
| Max Drawdown | max(peak − trough) / peak |

</details>

<details>
<summary><b>🤖 ML Risk Model</b></summary>

| Property | Value |
|---|---|
| Algorithm | `sklearn.GradientBoostingClassifier` |
| Classes | 5 (Conservative → Aggressive) |
| Training data | 3,000 synthetic samples from financial planning heuristics |
| Features | Age · Income · Dependents · Marital status · Employment · Horizon · Loss tolerance · Experience |
| Persistence | `models/risk_model.pkl` (auto-retrains if missing) |
| Output | Risk score 1–5 + class probabilities |

</details>

<details>
<summary><b>📊 Monte Carlo GBM Simulation</b></summary>

Geometric Brownian Motion simulation for portfolio projection:

```
S(t+1) = S(t) · exp[(μ − σ²/2)·Δt + σ·√Δt·Z]
```

Where `Z ~ N(0,1)`, `μ` = expected return, `σ` = volatility, both estimated from historical fund data. Outputs 1,000 simulation paths with fan-chart at 5th / 25th / 50th / 75th / 95th percentiles.

</details>

---

## 🚀 Setup & Run

### Prerequisites

- Python 3.10+
- AWS account with S3 bucket (for data layer)
- OpenAI API key (for AI Advisor)
- FRED API key (for macro data — free at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html))

### 1 · Clone and install

```bash
git clone https://github.com/Anant1213/Invest_helper.git
cd AssetEra

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2 · Configure environment

Create a `.env` file in the project root:

```env
# ── Core ──────────────────────────────────────────────
OPENAI_API_KEY=sk-proj-...

# ── S3 Data Lake ──────────────────────────────────────
DATA_BUCKET=your-s3-bucket-name
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# ── FRED Macro Data ────────────────────────────────────
FRED_API_KEY=your_fred_key

# ── Optional: PostgreSQL fallback ─────────────────────
POSTGRES_URL=postgresql://user:password@host:5432/db
```

### 3 · Populate the data lake

Run the full 10-year backfill (one-time, ~15 minutes):

```bash
# Equities (149 symbols)
.venv/bin/python scripts/dl_enqueue.py --backfill --run-inline --asset-class equities

# ETFs (27 symbols)
.venv/bin/python scripts/dl_enqueue.py --backfill --run-inline --asset-class etf

# Fixed Income proxies (10 symbols)
.venv/bin/python scripts/dl_enqueue.py --backfill --run-inline --asset-class fixed_income

# FRED macro series (14 series)
.venv/bin/python scripts/dl_enqueue.py --backfill --run-inline --asset-class macro

# Build combined market/ files (analytics pipeline input)
.venv/bin/python scripts/dl_build_market_files.py

# Compute all analytics modules (returns · risk · momentum · zscore · technical)
.venv/bin/python scripts/run_analytics.py
```

### 4 · Launch

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## 🌿 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | ✅ For AI Advisor | OpenAI API key (`sk-proj-...`) |
| `DATA_BUCKET` | ✅ For S3 backend | S3 bucket name |
| `AWS_REGION` | ✅ For S3 backend | AWS region e.g. `ap-south-1` |
| `AWS_ACCESS_KEY_ID` | ✅ For S3 backend | AWS static key (or use IAM role) |
| `AWS_SECRET_ACCESS_KEY` | ✅ For S3 backend | AWS static secret |
| `AWS_SESSION_TOKEN` | ⬜ Optional | For temporary STS credentials |
| `FRED_API_KEY` | ✅ For macro data | FRED API key (free) |
| `POSTGRES_URL` | ⬜ Optional | PostgreSQL fallback for market data |
| `QUEUE_EQUITIES` | ⬜ Optional | SQS queue name (default: `assetera-ingest-equities`) |
| `QUEUE_ETF` | ⬜ Optional | SQS queue name (default: `assetera-ingest-etf`) |
| `QUEUE_FIXED_INCOME` | ⬜ Optional | SQS queue name |
| `QUEUE_FRED` | ⬜ Optional | SQS queue name |

---

## ♻️ Daily Refresh

Run these three commands daily (e.g. via cron at 07:00 IST) to keep all data fresh:

```bash
# 1. Fetch today's OHLCV for all symbols + FRED updates
.venv/bin/python scripts/dl_enqueue.py --run-inline

# 2. Rebuild combined market/ files from curated/
.venv/bin/python scripts/dl_build_market_files.py

# 3. Incremental analytics (400-day window is fast)
.venv/bin/python scripts/run_analytics.py --lookback 400
```

**Example crontab (07:15 IST = 01:45 UTC):**

```cron
45 1 * * * cd /path/to/assetera && .venv/bin/python scripts/dl_enqueue.py --run-inline >> /var/log/assetera_ingest.log 2>&1
50 1 * * * cd /path/to/assetera && .venv/bin/python scripts/dl_build_market_files.py >> /var/log/assetera_build.log 2>&1
55 1 * * * cd /path/to/assetera && .venv/bin/python scripts/run_analytics.py --lookback 400 >> /var/log/assetera_analytics.log 2>&1
```

**Using AWS EventBridge (production):**

```bash
# Enqueue to SQS (EventBridge triggers this Lambda/ECS task)
.venv/bin/python scripts/dl_enqueue.py

# Workers poll SQS and process independently
.venv/bin/python scripts/dl_worker.py --asset-class all
```

---

## 🐳 Docker

```bash
docker compose up --build
```

> Ensure `.env` is configured before running compose. Port mapping: `8501:8501`.

---

## 🗂 Project Structure

```text
assetera/
├── app.py                          # Landing page + navigation
│
├── pages/
│   ├── 1_Market_Watch.py
│   ├── 2_Fund_Backtester.py
│   ├── 3_Risk_Profiler.py
│   ├── 4_AI_Advisor.py
│   ├── 5_Research.py
│   └── 6_Data_Workbench.py
│
├── backend/
│   ├── ui.py                       # Bloomberg Terminal CSS + components
│   ├── market.py                   # OHLCV fetch + metrics
│   ├── indicators.py               # RSI, BB, MACD, drawdown, beta
│   ├── market_watch/               # Ticker catalog
│   ├── risk_profiler/              # GBT model + fund mapping
│   ├── ai_advisor/                 # GPT-4o prompt + streaming
│   ├── stock_research/             # Analytics store + pipeline modules
│   ├── data_workbench/             # File ingest + profiling + views
│   └── db/                         # S3 + DuckDB + PostgreSQL adapters
│
├── datalayer/                      # S3-first data layer
│   ├── schemas.py                  # Universe lists + schema contracts
│   ├── s3.py                       # Zone-aware S3 client
│   ├── manifest.py                 # Run tracking (control/ zone)
│   ├── catalog.py                  # Dataset catalog
│   ├── enqueuer.py                 # Message publisher
│   ├── queue.py                    # SQS helpers + local mode
│   ├── worker.py                   # Message processor
│   ├── ingest/                     # equities · etf · fixed_income · fred
│   └── features/                   # technical · macro
│
├── scripts/
│   ├── dl_enqueue.py               # Trigger daily ingest
│   ├── dl_worker.py                # SQS worker loop
│   ├── dl_build_market_files.py    # Rebuild market/ from curated/
│   └── run_analytics.py            # Compute analytics/ from market/
│
├── models/
│   └── risk_model.pkl              # Persisted GBT classifier
│
├── docs/
│   └── S3_DATA_LAYER_IMPLEMENTATION.md
│
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## ⚠️ Disclaimer

AssetEra is an **educational analytics project**. It does not provide licensed financial or investment advice. All analytics, simulations, and AI responses are for informational and educational purposes only. Past performance and simulated outcomes do not guarantee future results. Always consult a qualified financial advisor before making investment decisions.

---

<div align="center">

Built with ❤️ using **Streamlit** · **AWS S3** · **OpenAI GPT-4o** · **FRED API** · **yfinance**

</div>
