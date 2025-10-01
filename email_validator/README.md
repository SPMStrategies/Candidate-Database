# Email Validation System

A comprehensive email validation system for the candidate database that validates all email addresses using both free checks and Hunter.io API.

## Features

- **Multi-layer validation**:
  - Syntax validation (RFC 5322 compliant)
  - DNS/MX record verification
  - Disposable email detection
  - Role account detection (info@, admin@, etc.)
  - Typo detection with suggestions
  - Hunter.io API validation for deliverability

- **Automated validation**:
  - Validates new emails after each state data import
  - 60-day revalidation cycle for all emails
  - GitHub Actions integration

- **Comprehensive reporting**:
  - HTML and JSON reports
  - Validation statistics dashboard
  - Invalid email tracking

## Setup

### 1. Install Dependencies

```bash
cd email_validator
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Add to your `.env` file:
```
HUNTER_API_KEY=your_hunter_io_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

### 3. Create Database Schema

Run the SQL script to create the validation tables:
```bash
# Apply the schema to your Supabase database
psql $DATABASE_URL < ../sql/email_validation_schema.sql
```

## Usage

### Test the System

```bash
# Test all components
python test_system.py
```

### Validate Emails

```bash
# Validate all emails in database
cd scripts
python validate_all.py

# Validate only new/unvalidated emails
python validate_new.py

# Revalidate emails due for 60-day check
python revalidate_due.py

# Generate validation report
python generate_report.py
```

### Check Hunter.io Credits

```bash
python -c "from hunter_client import test_hunter_connection; test_hunter_connection()"
```

## Validation Process

1. **Syntax Check**: Validates email format against RFC standards
2. **Typo Detection**: Checks for common domain typos (gmial.com → gmail.com)
3. **DNS Verification**: Confirms domain exists and has MX records
4. **Disposable Check**: Compares against 50,000+ known disposable domains
5. **Role Account Check**: Identifies generic emails (info@, support@, etc.)
6. **Hunter.io Validation**: Verifies deliverability and mailbox existence

## Email Status Classifications

- **Valid**: Passed all checks, safe to send
- **Invalid**: Failed validation, do not send
  - Invalid syntax
  - Domain doesn't exist
  - No mail server
  - Disposable email
  - Hunter.io marked as undeliverable
- **Role Account**: Generic email (still valid but flagged)
- **Unknown**: Could not determine status

## Automated Workflows

### Post-Import Validation
- Triggers after Maryland/Delaware data updates
- Validates any new emails added to database
- Runs within 5 minutes of import

### 60-Day Revalidation
- Runs daily at 4 AM ET
- Checks for emails due for revalidation
- Updates validation status and next check date

## Statistics and Reporting

The system tracks:
- Total candidates with emails
- Validation coverage percentage
- Valid vs invalid email counts
- Disposable and role account counts
- Hunter.io credit usage

Reports are generated in HTML and JSON formats with:
- Overall statistics
- Invalid email details
- Validation health score
- Recommendations for improvement

## API Credit Management

Hunter.io credits are used efficiently:
1. Free checks are performed first
2. Only emails passing free checks use Hunter.io
3. Results are cached for 60 days
4. Batch processing to optimize API calls

## Database Schema

### Tables

**email_validations**
- Stores validation results for each email
- Tracks validation history and next check date
- Links to candidate records

**email_validation_runs**
- Logs each validation run
- Tracks statistics and credit usage
- Audit trail for validation activities

### Views

**email_validation_status**
- Current validation status for all candidate emails
- Joins candidates with validation results
- Easy querying for reports

## Troubleshooting

### Hunter.io Connection Issues
```bash
# Test API key
python hunter_client.py
```

### Database Connection Issues
```bash
# Test database connection
python database.py
```

### DNS Resolution Issues
- Ensure dnspython is installed
- Check network connectivity
- Verify DNS server accessibility

## Monitoring

The system creates GitHub issues automatically when:
- Invalid email rate exceeds 30%
- Validation jobs fail
- Hunter.io credits are low

## Best Practices

1. **Regular Validation**: Let the 60-day cycle run automatically
2. **Manual Review**: Check emails marked as invalid for false positives
3. **Credit Monitoring**: Watch Hunter.io credit usage
4. **Data Quality**: Fix typos and invalid emails at the source
5. **Sender Reputation**: Never send to invalid emails

## Support

For issues or questions:
1. Check the test script: `python test_system.py`
2. Review logs in GitHub Actions
3. Check validation reports for patterns
4. Monitor Hunter.io credit balance