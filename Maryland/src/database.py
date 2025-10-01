"""Database operations for Maryland candidate system."""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
import math
from datetime import date, datetime
from enum import Enum as _Enum

# We'll handle numpy-like scalars via duck-typing (check for .item()) to avoid hard dependency
from supabase import create_client, Client
from .models import (
    IngestRun,
    NormalizedCandidate,
    DatabaseCandidate,
    CandidateSource,
    UpdateStatistics
)
from .config import SUPABASE_URL, SUPABASE_KEY, DRY_RUN, SOURCE_NAME, setup_logging, LOG_DIR

logger = setup_logging(__name__)


class SupabaseClient:
    """Client for Supabase database operations."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.ingest_run_id: Optional[UUID] = None
    
    def create_ingest_run(self, total_raw: int) -> UUID:
        """
        Create a new ingest run record.
        
        Args:
            total_raw: Total number of raw records to process
            
        Returns:
            UUID of the created ingest run
        """
        logger.info("Creating ingest run")
        
        if DRY_RUN:
            self.ingest_run_id = uuid4()
            logger.info(f"DRY RUN: Would create ingest run with ID {self.ingest_run_id}")
            return self.ingest_run_id
        
        ingest_run = IngestRun(
            source=SOURCE_NAME,
            run_key=f"maryland_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            endpoint_or_file="Maryland BOE CSVs",
            row_count_raw=total_raw,
            actor="github_action",
            notes=f"Automated update for {datetime.now().date()}"
        )
        
        # Convert to dict and handle datetime serialization
        ingest_data = ingest_run.dict(exclude={'id'})
        # Convert datetime to ISO string for JSON serialization
        if 'started_at' in ingest_data and ingest_data['started_at']:
            ingest_data['started_at'] = ingest_data['started_at'].isoformat()
        if 'finished_at' in ingest_data and ingest_data['finished_at']:
            ingest_data['finished_at'] = ingest_data['finished_at'].isoformat()
        
        result = self.client.table('ingest_runs').insert(ingest_data).execute()
        
        self.ingest_run_id = UUID(result.data[0]['id'])
        logger.info(f"Created ingest run: {self.ingest_run_id}")
        
        return self.ingest_run_id
    
    def stage_candidates(self, candidates: List[Dict[str, Any]]) -> int:
        """
        Stage normalized candidates for processing.
        
        Args:
            candidates: List of normalized candidate dictionaries
            
        Returns:
            Number of candidates staged
        """
        logger.info(f"Staging {len(candidates)} candidates")
        
        if DRY_RUN:
            logger.info(f"DRY RUN: Would stage {len(candidates)} candidates")
            return len(candidates)
        
        # Helper: sanitize values to JSON-serializable primitives for PostgREST
        def _sanitize_value(v):
            # None stays None
            if v is None:
                return None

            # basic Python types
            if isinstance(v, (str, bool, int)):
                return v

            # floats - handle NaN/inf
            if isinstance(v, float):
                if math.isnan(v) or math.isinf(v):
                    return None
                return float(v)

            # datetime/date -> ISO
            if isinstance(v, (datetime, date)):
                return v.isoformat()

            # UUID -> str
            if isinstance(v, UUID):
                return str(v)

            # Enums -> their value
            if isinstance(v, _Enum):
                return v.value

            # numpy-like scalars: try .item() if available (duck-typing)
            if hasattr(v, "item") and callable(getattr(v, "item")):
                try:
                    return v.item()
                except Exception:
                    return None

            # Lists/tuples -> sanitize each element
            if isinstance(v, (list, tuple)):
                return [_sanitize_value(x) for x in v]

            # Dicts -> sanitize values
            if isinstance(v, dict):
                return {str(k): _sanitize_value(val) for k, val in v.items()}

            # Fallback: try to stringify
            try:
                return str(v)
            except Exception:
                return None

        # Prepare data for staging table
        staged_data = []
        for idx, candidate_data in enumerate(candidates):
            candidate = candidate_data['candidate']
            
            staged = {
                'ingest_run_id': str(self.ingest_run_id),
                'source': SOURCE_NAME,
                'source_row_id': str(idx),
                'full_name': candidate['full_name'],
                'first_name': candidate.get('first_name'),
                'last_name': candidate.get('last_name'),
                'party': candidate.get('party'),
                'office_level': candidate['office_level'],
                'office_name': candidate['office_name'],
                'state': candidate['state'],
                'district_number': candidate.get('district_number'),
                'ocd_division_id': candidate.get('ocd_division_id'),
                'election_year': candidate['election_year'],
                'external_id_type': 'maryland_row_id',
                'external_id_value': str(idx),
                'raw_ref': candidate.get('raw_ref', {})
            }
            staged_data.append(staged)
        
        # Insert in batches
        batch_size = 100
        total_staged = 0
        
        for i in range(0, len(staged_data), batch_size):
            batch = staged_data[i:i+batch_size]
            # Sanitize batch to ensure all values are JSON-serializable
            sanitized_batch = []
            for record in batch:
                sanitized_record = {k: _sanitize_value(v) for k, v in record.items()}
                sanitized_batch.append(sanitized_record)
            # Validate each sanitized record can be JSON-encoded before sending to PostgREST
            import json
            for ridx, srec in enumerate(sanitized_batch):
                try:
                    # ensure_ascii False to catch unicode issues as well
                    json.dumps(srec, ensure_ascii=False)
                except Exception as ve:
                    logger.error(f"Record {ridx} in batch {i//batch_size + 1} is not JSON-serializable: {ve}")
                    try:
                        debug_file = LOG_DIR / f"staging_record_error_{uuid4().hex}.json"
                        debug_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(debug_file, 'w', encoding='utf-8') as fh:
                            fh.write('/* sanitization error: ' + str(ve) + ' */\n')
                            json.dump(srec, fh, ensure_ascii=False, indent=2)
                        logger.error(f"Wrote failing sanitized record to {debug_file}")
                    except Exception as ex2:
                        logger.error(f"Failed to write failing record debug file: {ex2}")
                    # raise a clear error so CI stops and we can inspect the file
                    raise ValueError(f"Sanitized record not serializable: {ve}")

            try:
                result = self.client.table('normalized_candidates_stage').insert(sanitized_batch).execute()
                total_staged += len(result.data)
                logger.info(f"Staged batch {i//batch_size + 1}: {len(batch)} candidates")
            except Exception as e:
                # Log error and write sanitized batch to a debug file for inspection
                logger.error(f"Error staging batch {i//batch_size + 1}: {e}")
                try:
                    debug_file = LOG_DIR / f"staging_debug_{uuid4().hex}.json"
                    debug_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(debug_file, 'w', encoding='utf-8') as fh:
                        json.dump(sanitized_batch, fh, ensure_ascii=False, indent=2)
                    logger.error(f"Wrote sanitized batch to {debug_file}")
                except Exception as ex2:
                    logger.error(f"Failed to write staging debug file: {ex2}")
                raise
        
        logger.info(f"Total candidates staged: {total_staged}")
        return total_staged
    
    def get_existing_candidates(self, election_year: int) -> List[DatabaseCandidate]:
        """
        Get existing candidates from database for matching.
        
        Args:
            election_year: Election year to filter by
            
        Returns:
            List of existing candidates
        """
        logger.info(f"Fetching existing candidates for year {election_year}")
        
        if DRY_RUN:
            logger.info("DRY RUN: Would fetch existing candidates")
            return []
        
        # Get candidates. Different versions of the Supabase/PostgREST client expose
        # an `or_` helper; if it's not available, pass the `or` param to execute().
        # Build a fresh select query base (don't reuse builders since many
        # postgrest client request builders are mutable and calling filters
        # on the same object can accumulate unexpected state). We attempt
        # to use the client-side `or_()` helper if present; otherwise we
        # run two separate queries and merge results.
        base_select = "*, candidate_identifiers(authority, id_value)"

        # For now, just get candidates for the specific election year
        # Skip the null check which is causing issues with the Supabase client
        result = self.client.table('candidates').select(base_select).eq('election_year', election_year).execute()
        
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
        
        logger.info(f"Found {len(candidates)} existing candidates")
        return candidates
    
    def insert_candidate(self, candidate_data: Dict[str, Any]) -> Optional[UUID]:
        """
        Insert a new candidate with related data.
        
        Args:
            candidate_data: Dictionary with candidate and related data
            
        Returns:
            UUID of created candidate or None if dry run
        """
        if DRY_RUN:
            logger.info(f"DRY RUN: Would insert candidate {candidate_data['candidate']['full_name']}")
            return None
        
        candidate = candidate_data['candidate']
        
        # Insert main candidate record
        candidate_record = {
            'full_name': candidate['full_name'],
            'first_name': candidate.get('first_name'),
            'last_name': candidate.get('last_name'),
            'party': candidate.get('party'),
            'office_level': candidate['office_level'],
            'office_name': candidate['office_name'],
            'ocd_division_id': candidate.get('ocd_division_id'),
            'district_number': candidate.get('district_number'),
            'election_year': candidate['election_year'],
            'gender': candidate.get('gender'),
            'jurisdiction': candidate.get('jurisdiction'),
            'committee_name': candidate.get('committee_name'),
            'website': candidate.get('website'),
            'contact_email': candidate.get('email'),
            'status': candidate.get('status', 'active'),
            'is_withdrawn': candidate.get('is_withdrawn', False)
        }
        
        result = self.client.table('candidates').insert(candidate_record).execute()
        candidate_id = UUID(result.data[0]['id'])
        
        # Insert contact info
        contact_info = candidate_data.get('contact_info', {})
        if any(contact_info.values()):
            contact_record = {
                'candidate_id': str(candidate_id),
                **{k: v for k, v in contact_info.items() if v is not None}
            }
            self.client.table('candidate_contact_info').insert(contact_record).execute()
        
        # Insert social media
        for social in candidate_data.get('social_media', []):
            social_record = {
                'candidate_id': str(candidate_id),
                'platform': social['platform'],
                'handle_or_url': social['handle_or_url']
            }
            self.client.table('candidate_social_media').insert(social_record).execute()
        
        # Insert filing info
        filing_info = candidate_data.get('filing_info', {})
        if any(filing_info.values()):
            filing_record = {
                'candidate_id': str(candidate_id)
            }
            for k, v in filing_info.items():
                if v is not None:
                    # Convert datetime to ISO string if needed
                    if k == 'filing_date' and hasattr(v, 'isoformat'):
                        filing_record[k] = v.isoformat()
                    else:
                        filing_record[k] = v
            self.client.table('candidate_filing_info').insert(filing_record).execute()
        
        # Track source
        source_record = {
            'candidate_id': str(candidate_id),
            'source': SOURCE_NAME,
            'external_id_type': 'maryland_import',
            'external_id_value': f"{datetime.now().date()}"
        }
        self.client.table('candidate_sources').insert(source_record).execute()
        
        logger.info(f"Inserted candidate: {candidate['full_name']} ({candidate_id})")
        return candidate_id
    
    def update_candidate(self, candidate_id: UUID, updates: Dict[str, Any]) -> bool:
        """
        Update existing candidate.
        
        Args:
            candidate_id: ID of candidate to update
            updates: Dictionary of fields to update
            
        Returns:
            True if successful
        """
        if DRY_RUN:
            logger.info(f"DRY RUN: Would update candidate {candidate_id}")
            return True
        
        # Update main candidate record - only include fields that exist in the database
        valid_candidate_fields = {
            'full_name', 'first_name', 'last_name', 'party', 'office_level',
            'office_name', 'ocd_division_id', 'district_number', 'election_year', 
            'gender', 'jurisdiction', 'committee_name', 'website', 'contact_email',
            'status', 'is_withdrawn', 'district_id'
        }
        
        candidate_updates = {
            k: v for k, v in updates['candidate'].items()
            if k in valid_candidate_fields
        }
        
        if candidate_updates:
            self.client.table('candidates').update(
                candidate_updates
            ).eq('id', str(candidate_id)).execute()
        
        # Update or insert contact info
        contact_info = updates.get('contact_info', {})
        if any(contact_info.values()):
            # Check if contact info exists
            existing = self.client.table('candidate_contact_info').select('id').eq(
                'candidate_id', str(candidate_id)
            ).execute()
            
            contact_record = {
                'candidate_id': str(candidate_id),
                **{k: v for k, v in contact_info.items() if v is not None}
            }
            
            if existing.data:
                # Update existing
                self.client.table('candidate_contact_info').update(
                    contact_record
                ).eq('candidate_id', str(candidate_id)).execute()
            else:
                # Insert new
                self.client.table('candidate_contact_info').insert(contact_record).execute()
        
        # Update source last seen
        self.client.table('candidate_sources').update({
            'last_seen': datetime.now().isoformat()
        }).eq('candidate_id', str(candidate_id)).eq('source', SOURCE_NAME).execute()
        
        logger.info(f"Updated candidate: {candidate_id}")
        return True
    
    def record_match(self, stage_id: int, candidate_id: UUID, confidence: float, note: str) -> None:
        """
        Record a candidate match.
        
        Args:
            stage_id: ID from staging table
            candidate_id: Matched candidate ID
            confidence: Match confidence score
            note: Match note
        """
        if DRY_RUN:
            logger.info(f"DRY RUN: Would record match {stage_id} -> {candidate_id} ({confidence:.1f}%)")
            return
        
        match_record = {
            'stage_id': stage_id,
            'candidate_id': str(candidate_id),
            'authority': 'name_office',
            'confidence': confidence,
            'decided_by': 'auto' if confidence >= 95 else 'manual',
            'note': note
        }
        
        self.client.table('candidate_matches').insert(match_record).execute()
    
    def finalize_ingest_run(self, stats: UpdateStatistics) -> None:
        """
        Finalize the ingest run with statistics.
        
        Args:
            stats: Update statistics
        """
        if DRY_RUN:
            logger.info(f"DRY RUN: Would finalize ingest run with stats: {stats.dict()}")
            return
        
        updates = {
            'finished_at': datetime.now().isoformat(),
            'row_count_stage': stats.total_staged,
            'new_candidates': stats.new_candidates,
            'updated_candidates': stats.updated_candidates,
            'notes': f"Processed {stats.total_raw_records} records in {stats.processing_time_seconds:.1f}s"
        }
        
        self.client.table('ingest_runs').update(updates).eq(
            'id', str(self.ingest_run_id)
        ).execute()
        
        logger.info(f"Finalized ingest run {self.ingest_run_id}")
    
    def get_districts(self) -> List[Dict[str, Any]]:
        """
        Get all districts from database.
        
        Returns:
            List of district records
        """
        if DRY_RUN:
            return []
        
        result = self.client.table('districts').select('*').execute()
        return result.data
    
    def create_district(self, ocd_id: str, district_type: str, 
                       district_number: Optional[str] = None,
                       name: Optional[str] = None) -> UUID:
        """
        Create a new district.
        
        Args:
            ocd_id: OCD division ID
            district_type: Type of district
            district_number: District number
            name: District name
            
        Returns:
            UUID of created district
        """
        if DRY_RUN:
            return uuid4()
        
        district_record = {
            'ocd_id': ocd_id,
            'district_type': district_type,
            'district_number': district_number,
            'name': name,
            'state': 'MD'
        }
        
        result = self.client.table('districts').insert(district_record).execute()
        return UUID(result.data[0]['id'])