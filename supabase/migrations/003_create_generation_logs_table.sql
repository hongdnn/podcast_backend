-- Create generation_logs table
CREATE TABLE generation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    podcast_id UUID NOT NULL REFERENCES podcasts(id),
    step VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_generation_logs_podcast_id ON generation_logs(podcast_id);
CREATE INDEX idx_generation_logs_created_at ON generation_logs(created_at DESC);

-- Enable Row Level Security
ALTER TABLE generation_logs ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Users can view logs for their own podcasts" ON generation_logs
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM podcasts 
            WHERE podcasts.id = generation_logs.podcast_id 
            AND podcasts.user_id = auth.uid()
        )
    );

CREATE POLICY "Service can insert generation logs" ON generation_logs
    FOR INSERT WITH CHECK (true);

-- Grant permissions
GRANT SELECT ON generation_logs TO anon;
GRANT ALL PRIVILEGES ON generation_logs TO authenticated;