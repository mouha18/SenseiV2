alter table chunks enable row level security;

create policy "Users can read own chunks"
  on chunks for select
  using (user_id = current_setting('app.current_user_id', true));

create policy "Users can insert own chunks"
  on chunks for insert
  with check (user_id = current_setting('app.current_user_id', true));

create policy "Users can delete own chunks"
  on chunks for delete
  using (user_id = current_setting('app.current_user_id', true));
