-- ADR-0009: FastAPI connects as this restricted role (subject to RLS), never the service-role key.
-- Rotate the password via the Supabase dashboard before using in any real environment.
create role sensei_restricted with login password 'CHANGE_ME_IN_DASHBOARD' noinherit;

grant usage on schema public to sensei_restricted;
grant select, insert, delete on chunks to sensei_restricted;
