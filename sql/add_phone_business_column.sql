-- Add phone_business column to candidate_contact_info table
-- This supports states like North Carolina that provide business phone numbers

ALTER TABLE candidate_contact_info
ADD COLUMN IF NOT EXISTS phone_business TEXT;

COMMENT ON COLUMN candidate_contact_info.phone_business IS 'Business phone number (provided by some states like NC)';
