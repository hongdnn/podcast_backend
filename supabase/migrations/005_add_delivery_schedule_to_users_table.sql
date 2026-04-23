-- Add user delivery scheduling preferences.
ALTER TABLE users
ADD COLUMN IF NOT EXISTS daily_delivery_time TEXT,
ADD COLUMN IF NOT EXISTS timezone TEXT;
