-- Extensões necessárias
create extension if not exists "pgcrypto";   -- gen_random_uuid()
create extension if not exists "citext";     -- e-mail case-insensitive
create extension if not exists "pg_trgm";    -- busca por nome/razão social

create schema if not exists mei_email;
