-- Track the last local-date delivery scheduled for each user
-- so the scheduler does not enqueue duplicate daily podcasts.
ALTER TABLE users
ADD COLUMN IF NOT EXISTS last_scheduled_delivery_date DATE;
