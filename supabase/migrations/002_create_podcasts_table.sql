-- Create podcasts table
CREATE TABLE podcasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    topic VARCHAR(255),
    script TEXT,
    audio_url TEXT,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    duration_seconds INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX idx_podcasts_user_id ON podcasts(user_id);
CREATE INDEX idx_podcasts_status ON podcasts(status);
CREATE INDEX idx_podcasts_created_at ON podcasts(created_at DESC);

-- Enable Row Level Security
ALTER TABLE podcasts ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Users can view their own podcasts" ON podcasts
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own podcasts" ON podcasts
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own podcasts" ON podcasts
    FOR UPDATE USING (auth.uid() = user_id);

-- Grant permissions
GRANT SELECT ON podcasts TO anon;
GRANT ALL PRIVILEGES ON podcasts TO authenticated;