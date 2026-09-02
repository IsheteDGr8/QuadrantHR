-- Migration: Add azure_object_id column to user_profiles table
-- Run this once against the live SQLite database

ALTER TABLE user_profiles ADD COLUMN azure_object_id VARCHAR(100);
CREATE INDEX IF NOT EXISTS ix_user_profiles_azure_object_id ON user_profiles (azure_object_id);
