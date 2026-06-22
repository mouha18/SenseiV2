create index on chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index idx_chunks_session on chunks (session_id);
create index idx_chunks_user on chunks (user_id);
