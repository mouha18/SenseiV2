create extension if not exists vector;

create table if not exists chunks (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  session_id text not null,
  document_id text not null,
  content text not null,
  embedding vector(1536) not null,
  page_number integer,
  book_title text,
  chunk_index integer not null,
  is_scope_anchor boolean not null default false,
  created_at timestamptz not null default now()
);
