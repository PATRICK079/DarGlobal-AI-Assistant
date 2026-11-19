create schema if not exists extensions;
create extension if not exists vector with schema extensions;

create table if not exists public.documents (
    url text not null,
    chunk_index integer not null check (chunk_index >= 0),
    source text not null check (source in ('DarGlobal', 'Wasalt')),
    title text not null,
    content text not null,
    embedding extensions.vector(384) not null,
    scraped_at timestamptz not null default now(),
    primary key (url, chunk_index)
);

alter table public.documents enable row level security;
revoke all on public.documents from anon, authenticated, public;

create or replace function public.match_property_documents(query_embedding extensions.vector(384))
returns table (url text, source text, title text, content text, scraped_at timestamptz)
language sql stable
set search_path = public, extensions
as $$
    select d.url, d.source, d.title, d.content, d.scraped_at
    from public.documents as d
    where d.embedding <=> query_embedding <= 0.55
    order by d.embedding <=> query_embedding
    limit 6;
$$;

revoke all on function public.match_property_documents(extensions.vector) from anon, authenticated, public;

-- Retain the source photo once per indexed page.
alter table public.documents add column if not exists image_url text;
alter table public.documents add column if not exists listing_metadata jsonb;

-- The fallback fields preserve apartment listings from the original scraper.
create or replace view public.property_listings
with (security_invoker = true) as
select distinct on (substring(url from '-([0-9]+)$'))
       substring(url from '-([0-9]+)$') as id,
       url, source, title, image_url, scraped_at,
       case when listing_metadata ? 'property_type' then listing_metadata->>'property_type' else 'apartment' end as property_type,
       split_part(url, '/', 6) as transaction_type,
       coalesce(listing_metadata->>'location', substring(content from 'Apartment for sale in ([^.]+)')) as location,
       coalesce(
           (listing_metadata->>'price')::bigint,
           replace(substring(content from 'Advertised asking price: SAR ([0-9][0-9,]{0,14})[.]'), ',', '')::bigint
       ) as price,
       'SAR'::text as currency,
       substring(title from '(?i)([0-9]{1,2}) bedrooms?')::integer as bedrooms,
       coalesce(listing_metadata->>'category', 'residential') as category,
       listing_metadata->>'rental_period' as rental_period,
       listing_metadata->'details' as details
from public.documents
where source = 'Wasalt' and chunk_index = 0
  and url ~ '^https://wasalt[.]sa/en/property/(sale|rent)/[^/]+-[0-9]+$'
  and (listing_metadata is not null or url like 'https://wasalt.sa/en/property/sale/%')
order by substring(url from '-([0-9]+)$'), scraped_at desc, url;

revoke all on public.property_listings from anon, authenticated, public;
