# Maryland Candidate Database Update System

Automated system for fetching and updating Maryland candidate data from the Maryland State Board of Elections into a Supabase database.

## Features

- **Automated Data Fetching**: Downloads latest candidate CSVs from Maryland BOE
- **Data Transformation**: Normalizes Maryland data to match database schema
- **Smart Deduplication**: Uses fuzzy matching to prevent duplicate candidates
- **Incremental Updates**: Only processes changes, tracks data sources
- **GitHub Actions Integration**: Runs nightly via GitHub Actions
- **Comprehensive Logging**: Detailed logs for debugging and audit trails
- **Dry Run Mode**: Test changes without modifying the database

## Database Schema

The system populates the following tables:
- `candidates` - Core candidate information
- `candidate_contact_info` - Mailing addresses and phone numbers  
- `candidate_social_media` - Social media accounts
- `candidate_filing_info` - Filing dates and status
- `candidate_sources` - Track data provenance
- `candidate_matches` - Deduplication decisions
- `ingest_runs` - Audit trail of update runs
- `normalized_candidates_stage` - Staging area for processing

## Setup

### 1. Environment Variables

Copy `.env.example` to `.env` and fill in your Supabase credentials:

```bash
cp .env.example .env
```

Required variables:
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase anon or service role key

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. GitHub Actions Setup

Add the following secrets to your GitHub repository:
- `SUPABASE_URL`
- `SUPABASE_KEY`

Go to: Settings → Secrets and variables → Actions

## Usage

### Manual Run (Local)

```bash
# Run update
cd Maryland
python -m src.main

# Dry run (no database changes)
DRY_RUN=true python -m src.main

# Debug mode
DEBUG=true python -m src.main
```

### GitHub Actions

The workflow runs automatically every night at 3 AM ET. You can also trigger it manually:

1. Go to Actions tab in your GitHub repository
2. Select "Update Maryland Candidates" workflow
3. Click "Run workflow"
4. Optionally enable dry run or debug mode

### Manual GitHub Actions Trigger

```yaml
dry_run: false  # Set to true to test without DB changes
debug: false    # Set to true for verbose logging
```

## Data Sources

- **State Candidates**: Federal and state-level offices
  - URL: `https://elections.maryland.gov/elections/2026/Primary_candidates/gen_cand_lists_2026_1_ALL.csv`
  
- **Local Candidates**: County and municipal offices
  - URL: `https://elections.maryland.gov/elections/2026/Primary_candidates/gen_cand_lists_2026_1_by_county_ALL.csv`

## Deduplication Logic

The system uses a multi-tiered matching approach:

1. **Exact Match (100%)**: Name + Office + Party
2. **High Confidence (95%+)**: Auto-accept matches
3. **Review Needed (85-95%)**: Flagged for manual review
4. **New Candidate (<85%)**: Treated as new entry

Matching considers:
- Full name similarity (fuzzy matching)
- Office name and level
- Party affiliation
- District information
- Election year

## Monitoring

### Logs

Logs are stored in `Maryland/logs/` with timestamps. GitHub Actions artifacts preserve logs for 30 days.

### Notifications

On failure, the system:
- Creates a GitHub issue (scheduled runs only)
- Preserves logs as artifacts
- Returns non-zero exit code

### Success Metrics

Track via the `ingest_runs` table:
- Total records processed
- New candidates added
- Existing candidates updated
- Processing time
- Error count

## Development

### Project Structure

```
Maryland/
├── src/
│   ├── config.py              # Configuration
│   ├── models.py              # Data models
│   ├── maryland_fetcher.py   # Download CSVs
│   ├── transformer.py        # Transform data
│   ├── database.py          # Supabase operations
│   ├── deduplication.py    # Matching logic
│   └── main.py             # Orchestration
├── tests/                  # Unit tests
├── logs/                  # Log files
├── requirements.txt      # Dependencies
├── .env.example         # Environment template
└── README.md           # This file
```

### Testing

```bash
# Run tests
pytest tests/

# Test with dry run
DRY_RUN=true python -m src.main

# Test specific component
python -m src.maryland_fetcher  # Test fetching
```

### Adding New Fields

1. Update `models.py` with new field definitions
2. Modify `transformer.py` to map CSV fields
3. Update `database.py` to handle new fields
4. Test with dry run before deploying

## Troubleshooting

### Common Issues

**CSV Download Fails**
- Check Maryland BOE website for URL changes
- Verify network connectivity
- Check for rate limiting

**Deduplication Errors**
- Review confidence thresholds in `config.py`
- Check `candidate_matches` table for patterns
- Adjust fuzzy matching parameters

**Database Connection Issues**
- Verify Supabase credentials
- Check Supabase service status
- Ensure IP is not blocked

### Debug Mode

Enable detailed logging:
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m src.main
```

## License

[Your License]

## Support

For issues or questions, please create an issue in the GitHub repository.