#!/usr/bin/env python3
"""
Check if North Carolina 2026 candidate data is available.
Sends SMS notification via Twilio with results every time it runs.
"""

import os
import sys
import requests
from datetime import datetime
from twilio.rest import Client


def check_nc_2026_availability():
    """
    Check if NC 2026 candidate data is available.

    Returns:
        tuple: (is_available: bool, file_size: int or None, message: str)
    """
    url = "https://s3.amazonaws.com/dl.ncsbe.gov/Elections/2026/Candidate%20Filing/Candidate_Listing_2026.csv"

    try:
        # Send HEAD request to check without downloading
        response = requests.head(url, timeout=10)

        if response.status_code == 200:
            file_size = int(response.headers.get('Content-Length', 0))

            # Check if file has meaningful content (at least 1KB)
            if file_size > 1000:
                return True, file_size, f"✅ NC 2026 data AVAILABLE! File size: {file_size:,} bytes"
            else:
                return False, file_size, f"⚠️ NC 2026 file exists but appears empty ({file_size} bytes)"

        elif response.status_code == 404:
            return False, None, "⏳ NC 2026 data not yet available (404)"

        else:
            return False, None, f"⚠️ Unexpected status code: {response.status_code}"

    except requests.exceptions.RequestException as e:
        return False, None, f"❌ Error checking URL: {e}"


def send_sms_notification(message):
    """
    Send SMS notification via Twilio.

    Args:
        message: Message to send

    Returns:
        bool: True if successful, False otherwise
    """
    # Get Twilio credentials from environment
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_phone = os.getenv('TWILIO_PHONE_FROM')
    to_phone = os.getenv('TWILIO_PHONE_TO')

    if not all([account_sid, auth_token, from_phone, to_phone]):
        print("ERROR: Missing Twilio credentials in environment variables")
        print("Required: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_FROM, TWILIO_PHONE_TO")
        return False

    try:
        client = Client(account_sid, auth_token)

        sms = client.messages.create(
            body=message,
            from_=from_phone,
            to=to_phone
        )

        print(f"✅ SMS sent successfully! SID: {sms.sid}")
        return True

    except Exception as e:
        print(f"❌ Failed to send SMS: {e}")
        return False


def create_github_issue():
    """
    Create a GitHub issue when data becomes available (only called once).

    Returns:
        bool: True if successful, False otherwise
    """
    github_token = os.getenv('GITHUB_TOKEN')
    repo = os.getenv('GITHUB_REPOSITORY', 'SPMStrategies/Candidate-Database')

    if not github_token:
        print("⚠️  No GITHUB_TOKEN found, skipping issue creation")
        return False

    try:
        url = f"https://api.github.com/repos/{repo}/issues"
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

        data = {
            'title': '🚨 NC 2026 Candidate Data Now Available',
            'body': f"""## North Carolina 2026 Data Detected

The NC State Board of Elections has released 2026 candidate filing data!

**Details:**
- **Detected**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
- **URL**: https://s3.amazonaws.com/dl.ncsbe.gov/Elections/2026/Candidate%20Filing/Candidate_Listing_2026.csv
- **Status**: Available

## Action Required

Update the North Carolina configuration to use 2026 data:

1. Update `NorthCarolina/src/config.py`:
   ```python
   ELECTION_YEAR = 2026  # Change from 2025
   ```

2. Update `.github/workflows/north-carolina-update.yml`:
   ```yaml
   NC_ELECTION_YEAR: 2026  # Change from 2025
   ```

3. Delete 2025 data from database:
   ```sql
   DELETE FROM candidates WHERE source_state = 'NC' AND election_year = 2025;
   ```

4. Trigger workflow to import 2026 data

**This issue was automatically created by the data availability checker.**
""",
            'labels': ['data-availability', 'north-carolina', 'automated']
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 201:
            issue_number = response.json()['number']
            print(f"✅ Created GitHub issue #{issue_number}")
            return True
        else:
            print(f"❌ Failed to create issue: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error creating GitHub issue: {e}")
        return False


def main():
    """Main execution."""
    print("=" * 60)
    print("NC 2026 Data Availability Checker")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Check if data is available
    is_available, file_size, message = check_nc_2026_availability()

    print(f"\n{message}")

    # Prepare SMS message with status
    if is_available:
        sms_message = f"🚨 NC 2026 DATA AVAILABLE! Size: {file_size:,} bytes. Action required - check GitHub issue."
        print("\n🎉 NC 2026 DATA AVAILABLE!")
    else:
        date_str = datetime.now().strftime('%m/%d')
        sms_message = f"NC 2026 Check ({date_str}): Not yet available. Will check again in 2 days."
        print("\n⏳ NC 2026 data not yet available.")

    # Always send SMS with results
    sms_sent = send_sms_notification(sms_message)

    # If data is available, also create GitHub issue (one-time)
    if is_available:
        issue_created = create_github_issue()

        if sms_sent and issue_created:
            print("\n✅ All notifications sent successfully")
            sys.exit(0)
        elif sms_sent:
            print("\n⚠️  SMS sent but issue creation failed")
            sys.exit(1)
        else:
            print("\n❌ Notifications failed")
            sys.exit(1)
    else:
        if sms_sent:
            print("\n✅ Status SMS sent")
            sys.exit(0)
        else:
            print("\n❌ Failed to send SMS")
            sys.exit(1)


if __name__ == "__main__":
    main()
