# Delaware Candidate Data Ingestion

## Data Sources

Delaware provides candidate lists in three HTML pages:
1. **School Board Candidates**: https://elections.delaware.gov/candidates/candidatelist/sb_fcddt_2026.shtml
2. **Primary Election Candidates**: https://elections.delaware.gov/candidates/candidatelist/prim_fcddt_2026.shtml
3. **General Election Candidates**: https://elections.delaware.gov/candidates/candidatelist/genl_fcddt_2026.shtml

## Data Collection Methods

### Option 1: Browser Automation (Recommended)
Due to Cloudflare protection on Delaware's election website, we need to use browser automation:
- Use Selenium or Playwright to navigate the pages
- Wait for JavaScript to render the content
- Extract the candidate data from the rendered HTML

### Option 2: Manual Download
- Manually download the HTML files periodically
- Place them in the `data/` directory
- Process the static HTML files

### Option 3: API Investigation
- Check if Delaware provides an API or data export
- Contact Delaware Division of Elections for data access

## Data Structure

Delaware candidate data typically includes:
- Candidate Name
- Office Sought
- District/Jurisdiction (if applicable)
- Filing Status
- Contact Information (limited)

Note: Delaware does not track party affiliation for many offices.

## Directory Structure

```
Delaware/
├── src/
│   ├── __init__.py
│   ├── config.py          # Configuration settings
│   ├── fetcher.py         # Data fetching logic
│   ├── transformer.py     # Transform to standard format
│   ├── database.py        # Database operations
│   └── main.py           # Main workflow
├── data/                  # Local data cache
├── logs/                  # Process logs
└── requirements.txt       # Dependencies
```