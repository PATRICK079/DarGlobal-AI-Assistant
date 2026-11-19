import os
from functools import lru_cache

import psycopg
from fastembed import TextEmbedding
from psycopg.rows import dict_row

if __package__:
    from .company_pages import COMPANY_PROFILE_URLS
else:
    from company_pages import COMPANY_PROFILE_URLS

PROFILE_URLS = [url for urls in COMPANY_PROFILE_URLS.values() for url in urls]


@lru_cache(maxsize=1)
def embedding_model():
    return TextEmbedding("BAAI/bge-small-en-v1.5", threads=2)


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=8, row_factory=dict_row)


def search(question):
    embedding = next(embedding_model().query_embed(question)).tolist()
    with connect() as connection:
        return connection.execute(
            """select * from public.match_property_documents(%s::extensions.vector)
               where url <> all(%s)""",
            (str(embedding), PROFILE_URLS),
        ).fetchall()


def company_profiles(companies):
    urls = [url for company in companies for url in COMPANY_PROFILE_URLS[company]]
    with connect() as connection:
        return connection.execute(
            """select url, source, title, content, scraped_at from public.documents
               where url = any(%s) order by source, url, chunk_index""",
            (urls,),
        ).fetchall()


def search_listings(*, location, property_type, transaction_type, max_price, strict_max,
                    min_bedrooms, bedrooms, category=None, rental_period=None, price_order=None, page=1):
    location_pattern = None
    if location:
        location_pattern = "%" + location.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    params = {
        "location": location_pattern,
        "type": property_type,
        "transaction": transaction_type,
        "category": category,
        "rental_period": rental_period,
        "max_price": max_price,
        "strict_max": strict_max,
        "min_bedrooms": min_bedrooms,
        "bedrooms": bedrooms,
        "highest": price_order == "highest",
        "ranked": price_order in ("highest", "lowest"),
        "limit": 1 if price_order in ("highest", "lowest") else 12,
        "offset": (page - 1) * 12,
    }
    with connect() as connection:
        rows = connection.execute(
            """select id, url, source, title, image_url, location, price, currency,
                      bedrooms, rental_period, property_type, details, count(*) over () as total
               from public.property_listings
               where (%(location)s::text is null or location ilike %(location)s)
                 and (%(type)s::text is null or property_type = %(type)s)
                 and (%(transaction)s::text is null or transaction_type = %(transaction)s)
                 and (%(category)s::text is null or category = %(category)s)
                 and (%(rental_period)s::text is null or rental_period = %(rental_period)s)
                 and (%(max_price)s::bigint is null or
                      (case when %(strict_max)s::boolean then price < %(max_price)s else price <= %(max_price)s end))
                 and (%(min_bedrooms)s::int is null or bedrooms >= %(min_bedrooms)s)
                 and (%(bedrooms)s::int is null or bedrooms = %(bedrooms)s)
                 and (not %(ranked)s or price is not null)
               order by case when %(highest)s then price end desc nulls last,
                        case when %(ranked)s or %(transaction)s = 'sale' then price end asc nulls last, id
               limit %(limit)s offset %(offset)s""",
            params,
        ).fetchall()
    total = rows[0]["total"] if rows else 0
    for row in rows:
        row.pop("total")
    return rows, total


def compare_listing(listing_id):
    """Return an indexed property and its closest-priced comparable, if any."""
    with connect() as connection:
        return connection.execute(
            """select listing.*, to_jsonb(peer) as comparable
               from public.property_listings as listing
               left join lateral (
                   select candidate.title, candidate.price, candidate.location, candidate.details
                   from public.property_listings as candidate
                   where candidate.id <> listing.id
                     and candidate.property_type = listing.property_type
                     and candidate.category = listing.category
                     and candidate.transaction_type = listing.transaction_type
                     and candidate.rental_period is not distinct from listing.rental_period
                     and candidate.currency = listing.currency
                     and (listing.bedrooms is null or candidate.bedrooms = listing.bedrooms)
                     and lower(trim(regexp_replace(candidate.location, '^.*,', ''))) =
                         lower(trim(regexp_replace(listing.location, '^.*,', '')))
                     and candidate.price > 0
                   order by abs(candidate.price - listing.price), candidate.id
                   limit 1
               ) as peer on true
               where listing.id = %s""",
            (listing_id,),
        ).fetchone()
