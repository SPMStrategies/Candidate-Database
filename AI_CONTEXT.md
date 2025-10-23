# AI Context - Candidate Database Project

**Last Updated**: October 22, 2025
**Session Summary**: Fixed North Carolina workflow issues and implemented deduplication

---

## Project Overview

Multi-state candidate database system that ingests candidate filing data from state election boards into a normalized Supabase database. Currently supports:
- ✅ **Delaware** (DE)
- ✅ **Maryland** (MD)
- ✅ **North Carolina** (NC)

Each state has its own ingestion workflow that runs daily via GitHub Actions.

---

## Recent Changes (October 2025)

### 1. North Carolina Workflow Fixed

**Problem**: NC workflow was failing completely.

**Root Causes Identified**:
1. Schema mismatches - NC provides fields that didn't exist in database
2. Wrong election year - pulling 2024 data instead of 2025
3. Massive duplication - NC's CSV has one row per candidate per county (17K rows → should be ~3K candidates)

**Solutions Implemented**:

#### Schema Additions
- Added `phone_business` to `candidate_contact_info` table
- Added 5 columns to `candidate_filing_info`: `election_date`, `is_unexpired`, `has_primary`, `is_partisan`, `term`
- Converted `jurisdiction` from TEXT to TEXT[] array type

#### NC Configuration Updates
- Changed `NC_ELECTION_YEAR` from 2024 → 2025 in:
  - `NorthCarolina/src/config.py`
  - `.github/workflows/north-carolina-update.yml`

#### Deduplication Logic
- Added `_consolidate_candidates()` method in `NorthCarolina/src/transformer.py`
- Groups candidates by `(full_name, office_name, party, election_date)`
- Merges jurisdiction data into arrays
- Takes first non-null contact info across duplicates
- Result: 3,121 raw rows → 3,120 unique candidates

---

## Key Architecture Patterns

### State Ingestion Structure
Each state follows this pattern:
```
StateName/
├── src/
│   ├── config.py          # State-specific configuration
│   ├── fetcher.py         # Fetches data from state source
│   ├── transformer.py     # Transforms to normalized schema
│   ├── database.py        # Supabase operations
│   ├── models.py          # Data models
│   └── main.py            # Orchestration
├── requirements.txt
└── README.md
```

### Workflow Pattern
1. **Fetch** raw data from state source (CSV, API, etc.)
2. **Transform** to normalized schema
3. **Stage** candidates in temp table
4. **Deduplicate** against existing candidates
5. **Insert/Update** database
6. **Log** ingest run metadata

---

## Database Schema Key Points

### Jurisdiction Field (Important!)
- **Type**: `TEXT[]` (PostgreSQL array)
- **Purpose**: Store multiple counties/jurisdictions for candidates
- **Values**:
  - Single county: `["ALAMANCE"]`
  - Multi-county: `["ALAMANCE", "GUILFORD", "ORANGE"]`
  - Statewide: `["Statewide"]`
  - None: `NULL`

### Contact Info Tables
- `candidate_contact_info`:
  - `phone_primary`, `phone_secondary`, `phone_business` (NC provides 3 phone fields)
  - Mailing address fields

### Filing Info Tables
- `candidate_filing_info`:
  - Standard: `filing_date`, `filing_type`, `filing_status`
  - NC-specific: `election_date`, `is_unexpired`, `has_primary`, `is_partisan`, `term`

---

## State-Specific Notes

### North Carolina
- **Data Source**: NC State Board of Elections S3 bucket
- **URL Pattern**: `https://s3.amazonaws.com/dl.ncsbe.gov/Elections/{YEAR}/Candidate%20Filing/Candidate_Listing_{YEAR}.csv`
- **Current Year**: 2025 (update to 2026 when midterm filing opens in early 2026)
- **Data Structure**: One row per candidate per county
- **Consolidation**: Required - use deduplication key without jurisdiction
- **2025 Data**: 3,120 local candidates (municipal elections only)
- **2026 Data**: Will include federal/state races with multi-county arrays

### Maryland
- **Data Source**: MD BOE CSV files
- **Deduplication**: Uses shared `Maryland.src.deduplication` module
- **Special Fields**: `candidate_gender`, social media fields

### Delaware
- **Data Source**: DE election API/files
- **Structure**: Simpler than NC, less duplication issues

---

## SQL Migrations Applied

1. `sql/add_phone_business_column.sql` - Added phone_business field
2. `sql/add_election_date_column.sql` - Added 5 NC filing fields (not used - combined into one)
3. `sql/convert_jurisdiction_to_array.sql` - Converted jurisdiction to TEXT[]

---

## GitHub Actions Workflows

### North Carolina Update
- **File**: `.github/workflows/north-carolina-update.yml`
- **Schedule**: Daily at 4 AM ET (`cron: '0 9 * * *'`)
- **Manual Trigger**: Supports dry_run and debug inputs
- **Timeout**: 30 minutes
- **Environment Variables**:
  - `NC_ELECTION_YEAR`: 2025 (update annually)
  - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`: From secrets

### Similar Workflows
- `delaware-update.yml`
- `maryland-update.yml`

---

## Common Issues & Solutions

### Issue: Schema Mismatch Errors
**Symptom**: `PGRST204: Could not find column X`
**Solution**: Add missing column to database, update transformer to use it

### Issue: Massive Duplication
**Symptom**: Row count 10x higher than expected
**Solution**: Implement consolidation logic that groups by candidate identity (without jurisdiction)

### Issue: Wrong Election Year
**Symptom**: Pulling old candidate data
**Solution**: Update `ELECTION_YEAR` config and workflow env var

### Issue: View Dependency on Column Change
**Symptom**: `cannot alter type of a column used by a view`
**Solution**: `DROP VIEW IF EXISTS ... CASCADE` before ALTER COLUMN

---

## Data Flow Example (NC)

```
NC BOE S3 CSV (17,060 rows)
  ↓ fetch
Raw DataFrame (17,060 rows)
  ↓ transform
Transformed List (17,060 candidate dicts)
  ↓ consolidate (NEW!)
Consolidated List (3,120 unique candidates)
  ↓ stage
Staging Table (3,120 rows)
  ↓ deduplicate
Categorized: {new: X, update: Y, review: Z}
  ↓ insert/update
Candidates Table (3,120 NC records)
```

---

## TODO / Future Improvements

1. **2026 Update**: Change NC to 2026 when candidate filing opens (likely March 2026)
2. **View Recreation**: The `candidates_full` view was dropped - may need to recreate if needed
3. **Cross-State Deduplication**: Currently only deduplicates within each state
4. **OCD Division IDs**: NC transformer has TODO for mapping districts to OCD IDs
5. **Additional States**: Framework ready to add more states (VA, PA, etc.)

---

## Quick Reference Commands

### Check NC Data Status
```sql
SELECT election_year, COUNT(*) as candidate_count
FROM candidates
WHERE source_state = 'NC'
GROUP BY election_year
ORDER BY election_year DESC;
```

### View Jurisdiction Arrays
```sql
SELECT full_name, office_name, jurisdiction
FROM candidates
WHERE source_state = 'NC'
  AND array_length(jurisdiction, 1) > 1
LIMIT 10;
```

### Delete Old Data
```sql
DELETE FROM candidates
WHERE source_state = 'NC' AND election_year = 2024;
```

### Trigger Manual Workflow
```bash
gh workflow run north-carolina-update.yml
```

---

## Key Files to Review Next Time

1. `NorthCarolina/src/transformer.py` - Consolidation logic
2. `.github/workflows/north-carolina-update.yml` - Workflow config
3. `sql/` - All schema migrations
4. `Maryland/src/deduplication.py` - Shared deduplication module

---

## Notes for AI

- User prefers arrays over JSON strings for multi-value fields
- "Statewide" is preferred over NULL for statewide candidates
- Federal candidates are NOT always statewide (e.g., US House districts)
- Always check for dependent views before altering column types
- Consolidation should happen BEFORE database insertion, not after
- Election years should be current/upcoming, not historical
