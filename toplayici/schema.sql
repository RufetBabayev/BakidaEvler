-- BakıdaEvlər.az: Supabase cədvəlləri.
-- Supabase panelində: SQL Editor -> New query -> bunu yapışdırın -> Run.

create table if not exists elanlar (
  menba            text        not null,           -- məsələn 'bina.az'
  elan_id          text        not null,
  link             text,
  qiymet           numeric,
  valyuta          text,
  kateqoriya       text,
  otaq_sayi        int,
  sahe_m2          numeric,
  rayon            text,
  metro            text,
  satici_tipi      text,                            -- 'mülkiyyətçi' / 'vasitəçi'
  satici_adi       text,
  telefon          text,
  telefon_elan_sayi int,
  makler_netice    text,                            -- 'ev sahibi' / 'makler' / 'şübhəli makler'
  yenilenme_tarixi timestamptz,
  ilk_gorulme      timestamptz not null default now(),
  data             jsonb       not null,            -- elanın tam qeydi (təsvir, şəkillər və s.)
  primary key (menba, elan_id)
);

create index if not exists elanlar_ilk_gorulme_idx on elanlar (ilk_gorulme desc);
create index if not exists elanlar_telefon_idx on elanlar (telefon);

create table if not exists toplayici_veziyyet (
  menba        text primary key,
  son_max_id   bigint,
  gozleyen     jsonb not null default '[]'::jsonb,
  yenilendi    timestamptz not null default now()
);

-- Bu cədvəllərə yalnız toplayıcı (service_role açarı ilə) yazır.
-- RLS açıq qalır, heç bir siyasət (policy) yoxdur: anonim açar heç nə oxuya bilməz.
-- Tətbiq mərhələsində (4) oxumaq üçün ayrıca siyasət əlavə edəcəyik.
alter table elanlar enable row level security;
alter table toplayici_veziyyet enable row level security;

-- Layihə "yeni cədvəllərə API girişi avtomatik ver" seçimi olmadan yaradılıbsa, toplayıcı üçün icazə lazımdır:
grant all on table elanlar, toplayici_veziyyet to service_role;

-- Mərhələ 4: tətbiq yalnız GİRİŞ EDƏN istifadəçi ilə oxuya bilər (yazmaq yox).
-- Qeydiyyat Supabase-də söndürülür, istifadəçini sahibi özü əlavə edir.
grant select on table elanlar to authenticated;
drop policy if exists "oxumaq: giriş edən" on elanlar;
create policy "oxumaq: giriş edən" on elanlar for select to authenticated using (true);

-- Mərhələ 5: çoxlu sayt. Satıcı açarı (telefon və ya sayt hesabı) makler aşkarlamaq üçündür.
alter table elanlar add column if not exists satici_acari text;
create index if not exists elanlar_satici_acari_idx on elanlar (satici_acari);

-- Mərhələ 6: bildiriş tokenləri. Hər istifadəçi yalnız öz telefonunun tokenini yaza/oxuya bilər; toplayıcı (service_role) hamısını oxuyur.
create table if not exists push_tokenlar (
  token     text primary key,
  user_id   uuid not null default auth.uid(),
  yenilendi timestamptz not null default now()
);
alter table push_tokenlar enable row level security;
grant select, insert, update, delete on table push_tokenlar to authenticated;
grant all on table push_tokenlar to service_role;
drop policy if exists "token: oz" on push_tokenlar;
create policy "token: oz" on push_tokenlar for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
