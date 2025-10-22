"""Transform North Carolina candidate data to normalized schema."""

import re
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models import NormalizedCandidate, OfficeLevel
from .config import SOURCE_STATE, SOURCE_NAME, ELECTION_YEAR, setup_logging

logger = setup_logging(__name__)


class NorthCarolinaTransformer:
    """Transforms NC BOE data to normalized candidate schema."""

    def __init__(self):
        self.state = SOURCE_STATE
        self.source = SOURCE_NAME
        self.election_year = ELECTION_YEAR

    def determine_office_level(self, contest_name: str, county: str) -> OfficeLevel:
        """
        Determine office level from contest name.

        Args:
            contest_name: Contest name (e.g., "US SENATE", "NC HOUSE OF REPRESENTATIVES")
            county: County name

        Returns:
            OfficeLevel enum value
        """
        if not contest_name:
            return OfficeLevel.LOCAL

        contest_upper = contest_name.upper()

        # Federal offices
        if any(x in contest_upper for x in ['US SENATE', 'US HOUSE', 'PRESIDENT', 'U.S. SENATE', 'U.S. HOUSE']):
            return OfficeLevel.FEDERAL

        # State offices
        if any(x in contest_upper for x in [
            'NC SENATE', 'NC HOUSE', 'GOVERNOR', 'LIEUTENANT GOVERNOR',
            'ATTORNEY GENERAL', 'STATE SENATE', 'STATE HOUSE',
            'SECRETARY OF STATE', 'STATE TREASURER', 'STATE AUDITOR',
            'COMMISSIONER OF AGRICULTURE', 'COMMISSIONER OF INSURANCE',
            'COMMISSIONER OF LABOR', 'SUPERINTENDENT OF PUBLIC INSTRUCTION'
        ]):
            return OfficeLevel.STATE

        # Judicial offices
        if any(x in contest_upper for x in ['JUDGE', 'JUSTICE', 'COURT', 'DISTRICT ATTORNEY']):
            return OfficeLevel.JUDICIAL

        # Everything else is local
        return OfficeLevel.LOCAL

    def extract_district_number(self, contest_name: str) -> Optional[str]:
        """
        Extract district number from contest name.

        Args:
            contest_name: Contest name

        Returns:
            District number as string, or None
        """
        if not contest_name:
            return None

        # Look for patterns like "DISTRICT 5", "DISTRICT 05", "5TH DISTRICT"
        patterns = [
            r'DISTRICT\s+(\d+)',
            r'(\d+)(?:ST|ND|RD|TH)\s+DISTRICT',
            r'DIST\s+(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, contest_name.upper())
            if match:
                return match.group(1).lstrip('0') or '0'  # Remove leading zeros

        return None

    def parse_name(self, row: Dict[str, Any]) -> tuple[str, Optional[str], Optional[str]]:
        """
        Parse name fields into full_name, first_name, last_name.

        Args:
            row: Raw candidate row

        Returns:
            Tuple of (full_name, first_name, last_name)
        """
        first = str(row.get('first_name', '') or '').strip()
        middle = str(row.get('middle_name', '') or '').strip()
        last = str(row.get('last_name', '') or '').strip()
        suffix = str(row.get('name_suffix_lbl', '') or '').strip()

        # Build full name
        name_parts = [first, middle, last]
        if suffix:
            name_parts.append(suffix)

        full_name = ' '.join(filter(None, name_parts))

        return full_name, first, last

    def normalize_party(self, party: str) -> Optional[str]:
        """
        Normalize party affiliation.

        Args:
            party: Raw party string

        Returns:
            Normalized party name
        """
        if not party or pd.isna(party):
            return None

        party = str(party).strip().upper()

        # Common party mappings
        party_map = {
            'DEM': 'Democratic',
            'REP': 'Republican',
            'LIB': 'Libertarian',
            'GRE': 'Green',
            'UNA': 'Unaffiliated',
            'UNAFFILIATED': 'Unaffiliated',
            'DEMOCRATIC': 'Democratic',
            'REPUBLICAN': 'Republican',
            'LIBERTARIAN': 'Libertarian',
            'GREEN': 'Green',
        }

        return party_map.get(party, party.title())

    def transform_candidate(self, row: Dict[str, Any], row_idx: int) -> Optional[Dict[str, Any]]:
        """
        Transform a single NC candidate row to normalized format.

        Args:
            row: Raw candidate data from CSV
            row_idx: Row index for tracking

        Returns:
            Dictionary with candidate and contact info, or None if invalid
        """
        try:
            # Parse name
            full_name, first_name, last_name = self.parse_name(row)

            if not full_name:
                logger.warning(f"Row {row_idx}: Missing name, skipping")
                return None

            # Get office info
            contest_name = str(row.get('contest_name', '') or '').strip()
            county = str(row.get('county_name', '') or '').strip()

            if not contest_name:
                logger.warning(f"Row {row_idx}: Missing contest name for {full_name}, skipping")
                return None

            # Determine office level and district
            office_level = self.determine_office_level(contest_name, county)
            district_number = self.extract_district_number(contest_name)

            # Parse party
            party_candidate = str(row.get('party_candidate', '') or '').strip()
            party = self.normalize_party(party_candidate)

            # External ID: use combination of name + contest + election_dt for uniqueness
            election_dt = str(row.get('election_dt', '') or '').strip()
            external_id = f"{full_name}_{contest_name}_{election_dt}".replace(' ', '_')

            # Create normalized candidate
            candidate = NormalizedCandidate(
                full_name=full_name,
                first_name=first_name if first_name else None,
                last_name=last_name if last_name else None,
                party=party,
                office_level=office_level,
                office_name=contest_name,
                state=self.state,
                district_number=district_number,
                ocd_division_id=None,  # TODO: Map NC districts to OCD IDs
                election_year=self.election_year,
                gender=None,  # NC doesn't provide gender
                jurisdiction=county if county else None,
                committee_name=None,  # NC doesn't provide committee info in this file
                website=None,  # NC doesn't provide website in this file
                email=str(row.get('email', '') or '').strip() or None,
                status='active',  # NC doesn't provide explicit status
                is_withdrawn=False,
                external_id_type='nc_candidate_id',
                external_id_value=external_id,
                source=self.source,
                source_row_id=str(row_idx),
                raw_ref=dict(row)  # Store raw data for reference
            )

            # Build contact info
            contact_info = {
                'phone_primary': str(row.get('phone', '') or '').strip() or None,
                'phone_secondary': str(row.get('office_phone', '') or '').strip() or None,
                'phone_business': str(row.get('business_phone', '') or '').strip() or None,
                'mailing_address_street': str(row.get('street_address', '') or '').strip() or None,
                'mailing_address_city': str(row.get('city', '') or '').strip() or None,
                'mailing_address_state': str(row.get('state', '') or '').strip() or None,
                'mailing_address_zip': str(row.get('zip_code', '') or '').strip() or None,
            }

            # Build filing info
            filing_info = {
                'filing_date': row.get('candidacy_dt'),
                'election_date': row.get('election_dt'),
                'is_unexpired': row.get('is_unexpired'),
                'has_primary': row.get('has_primary'),
                'is_partisan': row.get('is_partisan'),
                'term': row.get('term'),
            }

            return {
                'candidate': candidate.model_dump(),
                'contact_info': contact_info,
                'filing_info': filing_info
            }

        except Exception as e:
            logger.error(f"Error transforming row {row_idx}: {e}", exc_info=True)
            return None

    def transform_batch(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Transform a batch of NC candidates.

        Args:
            df: DataFrame with raw NC candidate data

        Returns:
            List of transformed candidate dictionaries
        """
        logger.info(f"Transforming {len(df)} NC candidates...")

        transformed = []
        for idx, row in df.iterrows():
            result = self.transform_candidate(row.to_dict(), idx)
            if result:
                transformed.append(result)

        logger.info(f"Successfully transformed {len(transformed)}/{len(df)} candidates")

        return transformed


def transform_nc_data(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Main function to transform NC candidate data.

    Args:
        df: Raw NC candidate DataFrame

    Returns:
        List of transformed candidates
    """
    transformer = NorthCarolinaTransformer()
    return transformer.transform_batch(df)
