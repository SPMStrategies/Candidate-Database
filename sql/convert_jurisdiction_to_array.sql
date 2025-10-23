-- Convert jurisdiction column from TEXT to TEXT[] array type
-- This allows storing multiple counties/jurisdictions for candidates who run in multiple areas

-- Step 1: Drop dependent view (will be recreated after)
DROP VIEW IF EXISTS candidates_full CASCADE;

-- Step 2: Convert existing data to array format
-- Single values become single-element arrays, NULL stays NULL
ALTER TABLE candidates
ALTER COLUMN jurisdiction TYPE TEXT[]
USING CASE
  WHEN jurisdiction IS NULL OR jurisdiction = '' THEN NULL
  ELSE ARRAY[jurisdiction]
END;

-- Add comment explaining the field
COMMENT ON COLUMN candidates.jurisdiction IS 'Array of jurisdictions/counties where candidate is running. Can contain specific county names or ["Statewide"] for statewide races.';

-- Step 3: Recreate the view (if you have the view definition, add it here)
-- Example (you'll need to replace this with your actual view definition):
-- CREATE VIEW candidates_full AS
-- SELECT * FROM candidates;
