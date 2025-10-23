# North Carolina Candidate Data Ingestion

Automated system for fetching and normalizing North Carolina candidate data from the NC State Board of Elections.

## Data Source

- **Primary Source**: NC State Board of Elections Candidate Lists
- **URL**: https://www.ncsbe.gov/results-data/candidate-lists
- **S3 URL Pattern**: `https://s3.amazonaws.com/dl.ncsbe.gov/Elections/{YEAR}/Candidate%20Filing/Candidate_Listing_{YEAR}.csv`
- **Current Year**: 2025 (update to 2026 when midterm filing opens)
- **Format**: CSV files hosted on S3
- **Update Frequency**: Daily during filing periods

## Features

- Fetches candidate data from NC BOE S3 bucket
- **Consolidates duplicate records** - NC provides one row per candidate per county
- Normalizes data to common schema with **jurisdiction arrays**
- Deduplicates candidates across runs
- Tracks comprehensive contact information (3 phone fields) and filing details
- Automated daily updates via GitHub Actions

## NC-Specific Data Handling

### Jurisdiction Arrays
North Carolina's CSV format includes one row per candidate per county. For example:
- A **US President** candidate appears 100 times (once for each NC county)
- A **State Senate** candidate appears multiple times (once per county in their district)
- A **Mayor** candidate appears once (single municipality)

The system **consolidates these duplicates** and stores jurisdictions as arrays:
- Single county: `["ALAMANCE"]`
- Multi-county district: `["ALAMANCE", "GUILFORD", "ORANGE"]`
- Statewide race: `["Statewide"]` (for candidates appearing in 50+ counties)

### Three Phone Numbers
NC provides three phone fields:
- `phone` → stored as `phone_primary`
- `office_phone` → stored as `phone_secondary`
- `business_phone` → stored as `phone_business`

### Election Metadata
NC provides additional filing metadata:
- `election_date` - Date of the election
- `is_unexpired` - Whether filling unexpired term
- `has_primary` - Whether race has primary
- `is_partisan` - Whether race is partisan
- `term` - Term length/description

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
- **Name**: first, middle, last, suffix, nickname
- **Contact Info**: email, 3 phone numbers (primary, office, business), full address
- **Political Info**: party, office, district
- **Election Details**: candidacy date, election date, partisan status, primary info, term length
- **Jurisdiction**: County/counties where candidate is running (stored as array after consolidation)

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

## Data Volume

- **2025 Data**: 3,121 raw rows → 3,120 unique candidates (local elections only)
- **2024 Data** (reference): 17,060 raw rows → would be ~2,500 unique after consolidation
- **2026 Data** (future): Will include federal and state races with multi-county arrays

## Configuration

Key configuration in `src/config.py`:
```python
ELECTION_YEAR = 2025  # Update annually
NC_CSV_URL = f"https://s3.amazonaws.com/.../Candidate_Listing_{ELECTION_YEAR}.csv"
```

## Technical Notes

### Consolidation Algorithm
The `_consolidate_candidates()` method in `transformer.py`:
1. Groups candidates by `(full_name, office_name, party, election_date)`
2. Collects all unique counties for each group
3. If 50+ counties → stores as `["Statewide"]`
4. Otherwise → stores as sorted array of county names
5. Merges contact info taking first non-null value

### Deduplication Key
External IDs generated as: `{name}_{office}_{election_date}` (without jurisdiction)
This ensures the same candidate across multiple counties has the same ID.
