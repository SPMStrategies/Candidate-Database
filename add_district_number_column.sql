-- Add district_number column to candidates table
ALTER TABLE public.candidates 
ADD COLUMN IF NOT EXISTS district_number character varying;

-- Add comment for documentation
COMMENT ON COLUMN public.candidates.district_number IS 'District number extracted from office/contest information (e.g., "1", "2A", "47")';

-- Optional: Create an index for faster queries by district
CREATE INDEX IF NOT EXISTS idx_candidates_district_number 
ON public.candidates(district_number);

-- Optional: Create a composite index for office + district queries
CREATE INDEX IF NOT EXISTS idx_candidates_office_district 
ON public.candidates(office_name, district_number);