#!/usr/bin/env python3
"""Generate email validation report."""

import sys
import os
import json
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import EmailDatabase
from config import get_logger

logger = get_logger(__name__)


def generate_html_report(stats: dict, invalid_emails: list) -> str:
    """Generate HTML report of email validation status.
    
    Args:
        stats: Validation statistics
        invalid_emails: List of invalid email records
        
    Returns:
        HTML report as string
    """
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Email Validation Report - {datetime.now().strftime('%Y-%m-%d')}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #333;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #555;
                margin-top: 30px;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 20px 0;
            }}
            .stat-card {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
            }}
            .stat-card.valid {{
                background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
            }}
            .stat-card.invalid {{
                background: linear-gradient(135deg, #f44336 0%, #da190b 100%);
            }}
            .stat-card.warning {{
                background: linear-gradient(135deg, #ff9800 0%, #fb8c00 100%);
            }}
            .stat-value {{
                font-size: 2em;
                font-weight: bold;
                margin: 10px 0;
            }}
            .stat-label {{
                font-size: 0.9em;
                opacity: 0.9;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th {{
                background-color: #4CAF50;
                color: white;
                padding: 12px;
                text-align: left;
            }}
            td {{
                padding: 10px;
                border-bottom: 1px solid #ddd;
            }}
            tr:hover {{
                background-color: #f5f5f5;
            }}
            .badge {{
                display: inline-block;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 0.85em;
                font-weight: bold;
            }}
            .badge.disposable {{
                background-color: #ff9800;
                color: white;
            }}
            .badge.syntax {{
                background-color: #f44336;
                color: white;
            }}
            .badge.dns {{
                background-color: #9c27b0;
                color: white;
            }}
            .badge.role {{
                background-color: #2196f3;
                color: white;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📧 Email Validation Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <h2>📊 Overall Statistics</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Candidates with Email</div>
                    <div class="stat-value">{stats.get('total_candidates_with_email', 0)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Validation Coverage</div>
                    <div class="stat-value">{stats.get('validation_coverage', 0)}%</div>
                </div>
                <div class="stat-card valid">
                    <div class="stat-label">Valid Emails</div>
                    <div class="stat-value">{stats.get('valid_emails', 0)}</div>
                </div>
                <div class="stat-card invalid">
                    <div class="stat-label">Invalid Emails</div>
                    <div class="stat-value">{stats.get('invalid_emails', 0)}</div>
                </div>
                <div class="stat-card warning">
                    <div class="stat-label">Disposable Emails</div>
                    <div class="stat-value">{stats.get('disposable_emails', 0)}</div>
                </div>
                <div class="stat-card warning">
                    <div class="stat-label">Role Accounts</div>
                    <div class="stat-value">{stats.get('role_accounts', 0)}</div>
                </div>
            </div>
            
            <h2>❌ Invalid Emails (Top {len(invalid_emails)})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Candidate</th>
                        <th>Email</th>
                        <th>State</th>
                        <th>Office</th>
                        <th>Issue</th>
                        <th>Last Checked</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for record in invalid_emails:
        candidate = record.get('candidates', {})
        issue = record.get('validation_error', 'Unknown')
        
        # Create badge for issue type
        badge_class = 'syntax'
        if 'disposable' in issue.lower():
            badge_class = 'disposable'
        elif 'dns' in issue.lower() or 'domain' in issue.lower():
            badge_class = 'dns'
        elif 'role' in issue.lower():
            badge_class = 'role'
        
        last_checked = record.get('last_validated_at', '')
        if last_checked:
            last_checked = datetime.fromisoformat(last_checked.replace('Z', '+00:00')).strftime('%Y-%m-%d')
        
        html += f"""
                    <tr>
                        <td>{candidate.get('full_name', 'Unknown')}</td>
                        <td>{record.get('email_address', '')}</td>
                        <td>{candidate.get('source_state', 'N/A')}</td>
                        <td>{candidate.get('office_name', 'N/A')}</td>
                        <td><span class="badge {badge_class}">{issue}</span></td>
                        <td>{last_checked}</td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
            
            <h2>📈 Validation Health</h2>
            <p>
    """
    
    # Calculate health metrics
    total = stats.get('total_candidates_with_email', 0)
    valid = stats.get('valid_emails', 0)
    if total > 0:
        valid_rate = (valid / total) * 100
        if valid_rate >= 90:
            health = "🟢 Excellent"
        elif valid_rate >= 80:
            health = "🟡 Good"
        elif valid_rate >= 70:
            health = "🟠 Fair"
        else:
            health = "🔴 Needs Attention"
        
        html += f"""
            <strong>Email Quality Score: {health}</strong><br>
            Valid email rate: {valid_rate:.1f}%<br>
            """
    
    html += """
            </p>
            
            <h2>💡 Recommendations</h2>
            <ul>
    """
    
    # Add recommendations based on stats
    if stats.get('validation_coverage', 0) < 100:
        html += f"<li>Complete validation for remaining {100 - stats.get('validation_coverage', 0)}% of emails</li>"
    
    if stats.get('disposable_emails', 0) > 10:
        html += f"<li>Review and replace {stats.get('disposable_emails', 0)} disposable email addresses</li>"
    
    if stats.get('invalid_emails', 0) > total * 0.2:
        html += "<li>High invalid email rate - consider manual review of data sources</li>"
    
    html += """
            </ul>
        </div>
    </body>
    </html>
    """
    
    return html


def main():
    """Generate and save email validation report."""
    print("=" * 60)
    print("EMAIL VALIDATION REPORT GENERATOR")
    print("=" * 60)
    
    try:
        # Initialize database
        print("\nConnecting to database...")
        db = EmailDatabase()
        
        # Get statistics
        print("Gathering validation statistics...")
        stats = db.get_validation_statistics()
        
        # Get invalid emails
        print("Fetching invalid email details...")
        invalid_emails = db.get_invalid_emails_report(limit=50)
        
        # Generate report
        print("Generating report...")
        
        # Console output
        print("\n" + "=" * 60)
        print("VALIDATION STATISTICS")
        print("=" * 60)
        for key, value in stats.items():
            print(f"{key}: {value}")
        
        print(f"\nTop {len(invalid_emails)} invalid emails identified")
        
        # Generate HTML report
        output_file = input("\nSave HTML report to (press Enter for report.html): ").strip()
        if not output_file:
            output_file = "email_validation_report.html"
        
        html_report = generate_html_report(stats, invalid_emails)
        
        with open(output_file, 'w') as f:
            f.write(html_report)
        
        print(f"\n✅ Report saved to {output_file}")
        
        # Also save JSON data
        json_file = output_file.replace('.html', '.json')
        with open(json_file, 'w') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'statistics': stats,
                'invalid_emails_sample': invalid_emails
            }, f, indent=2, default=str)
        
        print(f"📊 JSON data saved to {json_file}")
        
    except Exception as e:
        print(f"\n❌ Error generating report: {e}")
        logger.error(f"Report generation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()