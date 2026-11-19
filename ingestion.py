import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from scrapers import darglobal, wasalt

AGENT = "DarGlobalAssignmentBot"


@lru_cache(maxsize=4)
def robots(origin):
    response = httpx.get(origin + "/robots.txt", headers={"User-Agent": AGENT}, timeout=20)
    policy = RobotFileParser()
    if response.status_code == 404:
        policy.parse([])
    else:
        response.raise_for_status()
        policy.parse(response.text.splitlines())
    return policy


def wait_for_crawl_policy(url):
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    policy = robots(origin)
    if not policy.can_fetch(AGENT, url):
        raise ValueError(f"robots.txt disallows {url}")
    rate = policy.request_rate(AGENT)
    time.sleep(max(1, policy.crawl_delay(AGENT) or 0, rate.seconds / rate.requests if rate and rate.requests else 0))


def fetch(url):
    wait_for_crawl_policy(url)
    response = httpx.get(url, headers={"User-Agent": AGENT}, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def fetch_pdf(url):
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as error:
        raise ValueError("Install requirements-ingestion.txt to read contact PDFs") from error

    wait_for_crawl_policy(url)
    response = httpx.get(url, headers={"User-Agent": AGENT}, timeout=30)
    response.raise_for_status()
    try:
        return "\n".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
    except PdfReadError as error:
        raise ValueError(f"Could not read PDF at {url}") from error


def fetch_rendered(url):
    chrome = next(
        (path for path in (
            os.getenv("CHROME_BINARY"), shutil.which("google-chrome"), shutil.which("chromium"),
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ) if path and Path(path).is_file()),
        None,
    )
    if not chrome:
        return fetch(url)
    wait_for_crawl_policy(url)
    try:
        with TemporaryDirectory(prefix="darglobal-chrome-") as profile:
            result = subprocess.run(
                [chrome, "--headless", "--no-first-run", "--dump-dom",
                 "--timeout=15000", f"--user-data-dir={profile}", url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=True,
            )
    except (OSError, subprocess.SubprocessError):
        raise ValueError(f"Headless Chrome could not render {url}") from None
    return BeautifulSoup(result.stdout, "html.parser")


def store(records):
    from backend.database import connect, embedding_model

    model = embedding_model()
    with connect() as connection:
        for record in records:
            words = record["content"].split()
            chunks = [" ".join(words[start:start + 180]) for start in range(0, len(words), 160)
                      if start == 0 or start + 20 < len(words)]
            embeddings = model.passage_embed([f"{record['title']}\n{chunk}" for chunk in chunks])
            rows = [
                (
                    record["url"], index, record["source"], record["title"], chunk,
                    str(vector.tolist()), record.get("image_url") if index == 0 else None,
                    Jsonb(record["listing_metadata"]) if index == 0 and "listing_metadata" in record else None,
                )
                for index, (chunk, vector) in enumerate(zip(chunks, embeddings, strict=True))
            ]
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute("delete from public.documents where url = %s and chunk_index > 0", (record["url"],))
                cursor.executemany(
                    """insert into public.documents
                       (url, chunk_index, source, title, content, embedding, image_url, listing_metadata)
                       values (%s, %s, %s, %s, %s, %s::extensions.vector, %s, %s)
                       on conflict (url, chunk_index) do update
                       set source = excluded.source, title = excluded.title, content = excluded.content,
                           embedding = excluded.embedding, image_url = excluded.image_url, scraped_at = now(),
                           listing_metadata = coalesce(documents.listing_metadata || excluded.listing_metadata,
                                                       excluded.listing_metadata)""",
                    rows,
                )
            print(f"Stored {len(chunks)} chunks from {record['url']}")


def enrich_wasalt():
    from backend.database import connect

    with connect() as connection:
        urls = connection.execute("select url from public.property_listings order by id").fetchall()
    failed = False
    for row in urls:
        url = row["url"]
        try:
            details = wasalt.listing_details(fetch(url), url)
        except (httpx.HTTPError, ValueError) as error:
            print(f"wasalt: {url}: {error}", file=sys.stderr)
            failed = True
            continue
        with connect() as connection:
            connection.execute(
                """update public.documents
                   set listing_metadata = jsonb_set(coalesce(listing_metadata, '{}'::jsonb), '{details}', %s)
                   where url = %s and chunk_index = 0 and source = 'Wasalt'""",
                (Jsonb(details), url),
            )
        print(f"Checked Wasalt details at {url}", flush=True)
    return int(failed)


def main():
    parser = argparse.ArgumentParser(description="Collect public property data and index it in Supabase.")
    parser.add_argument("--source", choices=("all", "darglobal", "wasalt"), default="all")
    parser.add_argument("--wasalt-limit", type=int, choices=range(1, 26), default=10, metavar="1–25",
                        help="maximum Wasalt listings per city, category, and transaction")
    parser.add_argument("--dry-run", action="store_true", help="Print collected records without writing to the database.")
    parser.add_argument("--wasalt-details", action="store_true", help="Refresh specifications for indexed Wasalt listings.")
    parser.add_argument("--companies-only", action="store_true", help="Collect company profiles and public contacts only.")
    args = parser.parse_args()
    load_dotenv()
    if args.wasalt_details:
        if args.dry_run or args.source == "darglobal" or args.companies_only:
            parser.error("--wasalt-details updates the indexed Wasalt listings")
        return enrich_wasalt()
    records = []
    failed = False
    scrapers = {
        "darglobal": (
            lambda: darglobal.scrape_profiles(fetch, rendered_fetch=fetch_rendered),
            lambda: darglobal.scrape_contacts(fetch_rendered, fetch_pdf),
            lambda: darglobal.scrape(fetch),
        ),
        "wasalt": (
            lambda: wasalt.scrape_profiles(fetch),
            lambda: wasalt.scrape_contacts(fetch, fetch_pdf),
            lambda: wasalt.scrape(fetch, args.wasalt_limit),
        ),
    }
    for source, (profiles, contacts, properties) in scrapers.items():
        if args.source not in ("all", source):
            continue
        tasks = [profiles, contacts]
        if not args.companies_only:
            tasks.append(properties)
        for task in tasks:
            try:
                collected = task()
                if not collected:
                    raise ValueError("No records matched the public page markup.")
                records.extend(collected)
            except (httpx.HTTPError, ValueError) as error:
                failed = True
                if isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 403:
                    print(f"{source}: HTTP 403 Forbidden at {error.request.url}. "
                          "Check with the site for an approved way to access the data.", file=sys.stderr)
                else:
                    print(f"{source}: {error}", file=sys.stderr)

    if args.dry_run:
        print(json.dumps(records, ensure_ascii=False, indent=2))
    elif records:
        store(records)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
