# North Carolina Candidate Data Ingestion

Automated system for fetching and normalizing North Carolina candidate data from the NC State Board of Elections.

## Data Source

- **Primary Source**: NC State Board of Elections Candidate Lists
- **URL**: https://www.ncsbe.gov/results-data/candidate-lists
- **Format**: CSV files hosted on S3
- **Update Frequency**: Daily during filing periods

## Features

- Fetches candidate data from NC BOE S3 bucket
- Normalizes data to common schema
- Deduplicates candidates across runs
- Tracks contact information and filing details
- Automated daily updates via GitHub Actions

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase credentials
   ```

3. Run the ingestion:
   ```bash
   python -m src.main
   ```

## Data Fields

The NC BOE provides comprehensive candidate data including:
- Name (first, middle, last, suffix, nickname)
- Contact info (email, multiple phone numbers, full address)
- Political info (party, office, district)
- Election details (dates, partisan status, primary info)

## Directory Structure

```
NorthCarolina/
├── src/
│   ├── __init__.py
│   ├── config.py          # Configuration and environment
│   ├── nc_fetcher.py      # Fetch CSV from NC BOE
│   ├── transformer.py     # Normalize data
│   ├── database.py        # Supabase operations
│   ├── models.py          # Data models
│   └── main.py            # Main orchestration
├── data/                  # Cached CSV files
├── logs/                  # Application logs
├── requirements.txt
└── README.md
```

## Automated Updates

GitHub Actions workflow runs daily at 4 AM ET to keep data current.
See `.github/workflows/north-carolina-update.yml`
