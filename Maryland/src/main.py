"""Main orchestration for Maryland candidate update system."""

import sys
import time
from datetime import datetime
from typing import Dict, Any
from maryland_fetcher import fetch_maryland_candidates
from transformer import transform_maryland_data
from database import SupabaseClient
from deduplication import deduplicate_candidates
from models import UpdateStatistics
from config import (
    DRY_RUN, 
    ELECTION_YEAR,
    HIGH_CONFIDENCE_THRESHOLD,
    setup_logging
)

logger = setup_logging(__name__)


def run_maryland_update() -> UpdateStatistics:
    """
    Run the complete Maryland candidate update process.
    
    Returns:
        Update statistics
    """
    start_time = time.time()
    stats = UpdateStatistics(
        total_raw_records=0,
        total_staged=0,
        new_candidates=0,
        updated_candidates=0,
        skipped_duplicates=0,
        errors=0,
        processing_time_seconds=0,
        dry_run=DRY_RUN
    )
    
    logger.info("=" * 60)
    logger.info("Starting Maryland Candidate Update")
    logger.info(f"Time: {datetime.now()}")
    logger.info(f"DRY RUN: {DRY_RUN}")
    logger.info("=" * 60)
    
    try:
        # Step 1: Fetch data from Maryland BOE
        logger.info("\n📥 STEP 1: Fetching Maryland data...")
        raw_df = fetch_maryland_candidates()
        stats.total_raw_records = len(raw_df)
        logger.info(f"✅ Fetched {stats.total_raw_records} raw candidate records")
        
        if stats.total_raw_records == 0:
            logger.warning("No candidates found in Maryland data")
            return stats
        
        # Step 2: Transform data to normalized format
        logger.info("\n🔄 STEP 2: Transforming data...")
        transformed_candidates = transform_maryland_data(raw_df)
        logger.info(f"✅ Transformed {len(transformed_candidates)} candidates")
        
        # Step 3: Initialize database client
        logger.info("\n🗄️ STEP 3: Initializing database connection...")
        db = SupabaseClient()
        
        # Step 4: Create ingest run
        logger.info("\n📝 STEP 4: Creating ingest run...")
        ingest_run_id = db.create_ingest_run(stats.total_raw_records)
        logger.info(f"✅ Created ingest run: {ingest_run_id}")
        
        # Step 5: Stage candidates
        logger.info("\n📋 STEP 5: Staging candidates...")
        stats.total_staged = db.stage_candidates(transformed_candidates)
        logger.info(f"✅ Staged {stats.total_staged} candidates")
        
        # Step 6: Get existing candidates for deduplication
        logger.info("\n🔍 STEP 6: Fetching existing candidates...")
        existing_candidates = db.get_existing_candidates(ELECTION_YEAR)
        logger.info(f"✅ Found {len(existing_candidates)} existing candidates")
        
        # Step 7: Deduplicate candidates
        logger.info("\n🔗 STEP 7: Running deduplication...")
        categorized = deduplicate_candidates(transformed_candidates, existing_candidates)
        
        logger.info(f"Deduplication results:")
        logger.info(f"  - New candidates: {len(categorized['new'])}")
        logger.info(f"  - Updates: {len(categorized['update'])}")
        logger.info(f"  - Need review: {len(categorized['review'])}")
        
        # Step 8: Process new candidates
        logger.info("\n➕ STEP 8: Processing new candidates...")
        for candidate_data in categorized['new']:
            try:
                candidate_id = db.insert_candidate(candidate_data)
                if candidate_id:
                    stats.new_candidates += 1
            except Exception as e:
                logger.error(f"Error inserting candidate {candidate_data['candidate']['full_name']}: {e}")
                stats.errors += 1
        
        logger.info(f"✅ Inserted {stats.new_candidates} new candidates")
        
        # Step 9: Process updates
        logger.info("\n📝 STEP 9: Processing updates...")
        for candidate_data in categorized['update']:
            try:
                match_info = candidate_data['match_info']
                success = db.update_candidate(match_info['candidate_id'], candidate_data)
                if success:
                    stats.updated_candidates += 1
                    
                    # Record match in database
                    db.record_match(
                        stage_id=0,  # Would need to get from staging table
                        candidate_id=match_info['candidate_id'],
                        confidence=match_info['confidence'],
                        note=f"Auto-matched by {match_info['method']}"
                    )
            except Exception as e:
                logger.error(f"Error updating candidate: {e}")
                stats.errors += 1
        
        logger.info(f"✅ Updated {stats.updated_candidates} existing candidates")
        
        # Step 10: Handle review items
        if categorized['review']:
            logger.info(f"\n⚠️ STEP 10: {len(categorized['review'])} candidates need manual review")
            logger.info("Review candidates:")
            for candidate_data in categorized['review'][:10]:  # Show first 10
                match_info = candidate_data.get('match_info', {})
                logger.info(f"  - {candidate_data['candidate']['full_name']} "
                          f"~= {match_info.get('existing_name')} "
                          f"({match_info.get('confidence', 0):.1f}%)")
        
        # Calculate processing time
        stats.processing_time_seconds = time.time() - start_time
        
        # Step 11: Finalize ingest run
        logger.info("\n✅ STEP 11: Finalizing ingest run...")
        db.finalize_ingest_run(stats)
        
        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("UPDATE COMPLETE")
        logger.info(f"Total raw records: {stats.total_raw_records}")
        logger.info(f"Total staged: {stats.total_staged}")
        logger.info(f"New candidates: {stats.new_candidates}")
        logger.info(f"Updated candidates: {stats.updated_candidates}")
        logger.info(f"Errors: {stats.errors}")
        logger.info(f"Processing time: {stats.processing_time_seconds:.2f} seconds")
        
        if DRY_RUN:
            logger.info("\n⚠️ DRY RUN - No actual database changes were made")
        
        logger.info("=" * 60)
        
        return stats
        
    except Exception as e:
        logger.error(f"Fatal error in update process: {e}", exc_info=True)
        stats.errors += 1
        stats.processing_time_seconds = time.time() - start_time
        
        # Try to finalize ingest run with error status
        try:
            if 'db' in locals():
                db.finalize_ingest_run(stats)
        except:
            pass
        
        raise


def main():
    """Main entry point."""
    try:
        stats = run_maryland_update()
        
        # Exit with appropriate code
        if stats.errors > 0:
            logger.warning(f"Update completed with {stats.errors} errors")
            sys.exit(1)
        else:
            logger.info("Update completed successfully")
            sys.exit(0)
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ Update cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Update failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()