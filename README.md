# Candidate Database

Multi-state political candidate database system that automatically ingests and normalizes candidate filing data from state election boards.

## Supported States

- ✅ **Delaware** - [Delaware/README.md](Delaware/README.md)
- ✅ **Maryland** - [Maryland/README.md](Maryland/README.md)
- ✅ **North Carolina** - [NorthCarolina/README.md](NorthCarolina/README.md)

## Features

### Automated Data Ingestion
- Daily automated updates via GitHub Actions
- Fetches data directly from state election board sources
- Handles CSV files, APIs, and S3 buckets

### Intelligent Deduplication
- Consolidates duplicate records (e.g., NC candidates appearing in multiple counties)
- Fuzzy name matching for candidate identification
- Tracks updates vs. new candidates

### Jurisdiction Arrays (NEW!)
The system now supports **jurisdiction arrays** for candidates running in multiple counties/jurisdictions:
- Single county: `["ALAMANCE"]`
- Multi-county: `["ALAMANCE", "GUILFORD", "ORANGE"]`
- Statewide: `["Statewide"]`

This is especially important for North Carolina, which provides per-county rows in their data.

### Comprehensive Contact & Filing Data
- Multiple phone numbers (primary, secondary, business)
- Mailing addresses
- Email addresses
- Filing dates and election dates
- Party affiliation and office details
- Social media (where available)

## Database Schema

### Core Tables
- `candidates` - Main candidate information
- `candidate_contact_info` - Phone, email, addresses (with `phone_business` support)
- `candidate_filing_info` - Filing dates, election dates, partisan status, term info
- `candidate_identifiers` - External IDs from source systems
- `candidate_social_media` - Social media handles (MD)
- `ingest_runs` - Audit trail of data imports

### Key Fields
- `jurisdiction` (TEXT[]): Array of counties/jurisdictions
- `election_year`: Year of election
- `office_level`: federal, state, judicial, local
- `source_state`: Two-letter state code

## Architecture

Each state follows a consistent pattern:

```
StateName/
├── src/
│   ├── config.py          # State-specific configuration
│   ├── fetcher.py         # Fetches data from state source
│   ├── transformer.py     # Transforms to normalized schema
│   ├── database.py        # Supabase database operations
│   ├── models.py          # Pydantic data models
│   └── main.py            # Orchestration
├── requirements.txt
└── README.md
```

## GitHub Actions Workflows

Automated daily updates:
- `.github/workflows/delaware-update.yml`
- `.github/workflows/maryland-update.yml`
- `.github/workflows/north-carolina-update.yml`

Each workflow:
- Runs daily at 4 AM ET
- Supports manual triggering with dry-run mode
- Uploads logs as artifacts
- Creates GitHub issues on failure

## Quick Start

### Prerequisites
- Python 3.11+
- Supabase account with database
- GitHub repository secrets configured:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`

### Running Locally

```bash
# Example: North Carolina
cd NorthCarolina
pip install -r requirements.txt

# Set environment variables
export SUPABASE_URL="your-supabase-url"
export SUPABASE_KEY="your-service-role-key"
export NC_ELECTION_YEAR="2025"

# Run the update
python -m src.main
```

## Data Sources

- **Delaware**: DE Election Commission
- **Maryland**: MD State Board of Elections CSV exports
- **North Carolina**: NC State Board of Elections S3 bucket
  - URL: `https://s3.amazonaws.com/dl.ncsbe.gov/Elections/{YEAR}/Candidate%20Filing/`

## Recent Updates (October 2025)

### Schema Enhancements
- Added `phone_business` column for states providing business phone numbers
- Added election metadata fields: `election_date`, `is_unexpired`, `has_primary`, `is_partisan`, `term`
- Converted `jurisdiction` from TEXT to TEXT[] array type

### North Carolina Improvements
- Fixed schema mismatches causing complete workflow failure
- Implemented consolidation logic to handle per-county duplicate rows
- Updated to 2025 election data (3,120 candidates vs 17,060 raw rows in 2024)
- Added support for jurisdiction arrays

## Developer Notes

### For AI Context
See [AI_CONTEXT.md](AI_CONTEXT.md) for detailed technical documentation, common issues, and notes for future sessions.

### SQL Migrations
All schema migrations are in the `sql/` directory:
- `add_phone_business_column.sql`
- `convert_jurisdiction_to_array.sql`

### Testing
Run manual workflow triggers:
```bash
gh workflow run north-carolina-update.yml
gh workflow run maryland-update.yml
gh workflow run delaware-update.yml
```

## Useful SQL Queries

### Check Current Data
```sql
SELECT source_state, election_year, COUNT(*) as candidates
FROM candidates
GROUP BY source_state, election_year
ORDER BY source_state, election_year DESC;
```

### View Jurisdiction Arrays
```sql
SELECT full_name, office_name, jurisdiction
FROM candidates
WHERE array_length(jurisdiction, 1) > 1
LIMIT 10;
```

### Multi-County Candidates
```sql
SELECT
  source_state,
  COUNT(*) FILTER (WHERE array_length(jurisdiction, 1) > 1) as multi_county,
  COUNT(*) FILTER (WHERE jurisdiction @> ARRAY['Statewide']) as statewide,
  COUNT(*) as total
FROM candidates
GROUP BY source_state;
```

## Contributing

To add a new state:
1. Create new directory following the pattern: `StateName/`
2. Implement the standard modules (fetcher, transformer, database, etc.)
3. Add GitHub Actions workflow
4. Update this README

## License

[Add license information]

## Support

For issues or questions, please create a GitHub issue.
