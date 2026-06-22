-- ADR-0005/0009: private bucket for raw uploaded PDFs. Accessed via a narrow
-- Storage credential (SUPABASE_STORAGE_KEY), not the DB service-role key.
-- 5MB cap mirrors the per-file upload limit (ADR-0005); RLS-scoping
-- storage.objects is deferred per ADR-0009, not MVP.
insert into storage.buckets (id, name, public, file_size_limit)
values ('raw-pdfs', 'raw-pdfs', false, 5242880)
on conflict (id) do nothing;
