"""Database operations for North Carolina candidates."""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

# Add parent directory to path to import shared modules
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import from Maryland implementation (will be moved to shared later)
from Maryland.src.database import SupabaseClient as BaseSupabaseClient
from Maryland.src.models import UpdateStatistics

from .config import SOURCE_STATE, SOURCE_NAME, DRY_RUN

logger = logging.getLogger(__name__)


class NorthCarolinaSupabaseClient(BaseSupabaseClient):
    """North Carolina-specific database operations."""

    def __init__(self):
        """Initialize North Carolina database client."""
        super().__init__()
        self.source_state = SOURCE_STATE

    def insert_candidate(self, candidate_data: Dict[str, Any]) -> Optional[UUID]:
        """
        Insert a new North Carolina candidate.

        Args:
            candidate_data: Candidate data dictionary

        Returns:
            UUID of created candidate or None
        """
        # Add source_state to candidate data
        candidate_data['candidate']['source_state'] = SOURCE_STATE

        # Use parent class insert method
        return super().insert_candidate(candidate_data)

    def get_nc_candidates(self) -> List[Dict[str, Any]]:
        """
        Get all candidates from North Carolina.

        Returns:
            List of North Carolina candidates
        """
        if DRY_RUN:
            logger.info("DRY RUN: Would fetch North Carolina candidates")
            return []

        try:
            # Get candidates where North Carolina is the source
            result = self.client.table('candidates').select('*').eq(
                'source_state', SOURCE_STATE
            ).execute()

            logger.info(f"Found {len(result.data)} North Carolina candidates")
            return result.data

        except Exception as e:
            logger.error(f"Error fetching North Carolina candidates: {e}")
            return []

    def get_existing_nc_candidates(self, election_year: int) -> List[Any]:
        """
        Get existing North Carolina candidates for deduplication.
        Only checks within North Carolina candidates (no cross-state).

        Args:
            election_year: Election year to filter by

        Returns:
            List of existing North Carolina candidates
        """
        logger.info(f"Fetching existing North Carolina candidates for year {election_year}")

        if DRY_RUN:
            logger.info("DRY RUN: Would fetch existing North Carolina candidates")
            return []

        try:
            # Only get North Carolina candidates for deduplication
            result = self.client.table('candidates').select(
                "*, candidate_identifiers(authority, id_value)"
            ).eq('election_year', election_year).eq('source_state', SOURCE_STATE).execute()

            # Convert to DatabaseCandidate objects (reusing Maryland's model)
            from Maryland.src.models import DatabaseCandidate

            candidates = []
            for row in result.data:
                # Extract external IDs
                external_ids = []
                if 'candidate_identifiers' in row:
                    for id_row in row['candidate_identifiers']:
                        external_ids.append({
                            'authority': id_row['authority'],
                            'value': id_row['id_value']
                        })

                candidate = DatabaseCandidate(
                    id=row['id'],
                    full_name=row['full_name'],
                    first_name=row.get('first_name'),
                    last_name=row.get('last_name'),
                    party=row.get('party'),
                    office_level=row.get('office_level'),
                    office_name=row.get('office_name'),
                    district_id=row.get('district_id'),
                    ocd_division_id=row.get('ocd_division_id'),
                    election_year=row.get('election_year'),
                    status=row.get('status'),
                    is_withdrawn=row.get('is_withdrawn', False),
                    external_ids=external_ids
                )
                candidates.append(candidate)

            logger.info(f"Found {len(candidates)} existing North Carolina candidates")
            return candidates

        except Exception as e:
            logger.error(f"Error fetching existing North Carolina candidates: {e}")
            return []
