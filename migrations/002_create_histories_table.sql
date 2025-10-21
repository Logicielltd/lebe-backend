-- Migration: Create histories table
-- Description: Creates the histories table for transaction tracking
-- Date: 2025-10-21

BEGIN;

CREATE TABLE IF NOT EXISTS histories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR NOT NULL,
    intent VARCHAR NOT NULL,
    transaction_type VARCHAR NOT NULL,
    amount FLOAT NULL,
    currency VARCHAR DEFAULT 'GHS',
    recipient VARCHAR NULL,
    phone_number VARCHAR NULL,
    data_plan VARCHAR NULL,
    category VARCHAR NULL,
    status VARCHAR DEFAULT 'completed',
    description TEXT NULL,
    transaction_metadata JSON NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on user_id for faster queries
CREATE INDEX IF NOT EXISTS idx_histories_user_id ON histories(user_id);

COMMIT;
