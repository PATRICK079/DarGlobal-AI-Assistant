# DarGlobal Property Assistant

A Next.js chat UI for public DarGlobal developments and Wasalt listings. FastAPI looks up relevant passages in Supabase pgvector and asks OpenRouter’s free model router to answer using those passages. The assistant can provide a direct listing link when requested.

## Property search

Ask “Show me apartments in Riyadh under SAR 800,000” to see structured Wasalt
results. Ask “List properties” to choose residential or commercial and then rent
or buy. If you already know, ask “Show commercial properties for rent in Riyadh.”
Catalogue search uses SQL filters for category, location, property type,
transaction, price in SAR, and bedroom count. Rental cards show the advertised
billing period, and rental price comparisons use the selected period. Cards link to the
original listings and show a photo only when it was associated with that listing
on the source page. Asking prices reflect the scrape date.

Development and amenity questions still use vector search. DarGlobal project
pages and filings provide development information. Wasalt ingestion collects
listings for sale and rent from Riyadh, Jeddah, Dammam, Al Khobar, and Makkah. The residential search pages
also show other types, so ingestion includes only clearly residential listing
types from those pages. Ingestion reads the first page of each catalogue. The `--wasalt-limit` cap
applies per city, category, and transaction.

For an existing Supabase setup, rerun `schema.sql` to update the listing view
and add listing metadata. Existing Wasalt apartment records remain searchable.
Rerun `python ingestion.py --source wasalt` to populate the expanded catalogue.

The chat answers company questions from scraped DarGlobal company pages and
its published regulatory filing, plus Wasalt's corporate page and FAQ. The
scraper skips sources it cannot access and reports them on stderr.
Run `python ingestion.py --companies-only` to refresh company profiles and
public contact details. Add `--dry-run` to preview the records without writing
to Supabase. Contacts retain their source URL. A phone number is recorded as
WhatsApp only when the source publishes a direct WhatsApp link.
Ingestion uses local headless Chrome or Chromium for DarGlobal's About and FAQ
pages when available. Set `CHROME_BINARY` to a custom executable path if needed.

## Set up data

1. Create a Supabase project and run [schema.sql](schema.sql) in its SQL editor. Use the PostgreSQL connection string from the Supabase Connect dialog. The session pooler is an option if your network requires IPv4.
2. Copy `.env.example` to `.env` and set `DATABASE_URL` and `OPENROUTER_API_KEY`.
3. Run the ingestion commands from this repository's root.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-ingestion.txt
python ingestion.py --dry-run
python ingestion.py --source wasalt --wasalt-limit 1
python ingestion.py --source wasalt --wasalt-details
python ingestion.py
```

The scraper checks robots.txt. If a source denies access or fails, ingestion reports the failure, processes records from the other source, and exits with status 1. Dry-run JSON is printed to stdout and source errors go to stderr. Wasalt records come from public English search cards. If DarGlobal’s project pages are unavailable, the scraper uses Dar Global PLC’s public regulatory filing carried by Investegate. A rerun replaces the chunks for each fetched URL, while older records remain until removed. Asking prices and availability reflect the collection date. The shared embedding model is BAAI/bge-small-en-v1.5 with 384 dimensions.

## Run the Docker containers

```sh
docker build -t darglobal-backend ./backend
docker build -t darglobal-frontend ./frontend
docker network create darglobal
docker run --rm -d --name darglobal-backend --network darglobal --env-file .env -e PORT=8000 -e BIND_HOST=0.0.0.0 darglobal-backend
docker run --rm -d --name darglobal-frontend --network darglobal -e BACKEND_URL=http://darglobal-backend:8000 -p 3000:3000 darglobal-frontend
```

Open http://localhost:3000. Create the Docker network once and reuse it for later runs. Stop both containers with `docker stop darglobal-frontend darglobal-backend`.

## Deploy on Railway

Create both services in the same Railway project and environment, using this repository as the source for each.

| Service | Root Directory | Variables |
| --- | --- | --- |
| Backend | `/backend` | `DATABASE_URL`, `OPENROUTER_API_KEY`, optional `OPENAI_API_KEY`, `PORT=8000`, `BIND_HOST=::` |
| Frontend | `/frontend` | `BACKEND_URL=http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8000`, `PORT=3000` |

Use the exact backend service name in the frontend variable reference. Railway detects the Dockerfile in each service's root. Set the backend health check path to `/health` and generate a public HTTPS domain for the frontend.

- [Railway Dockerfile builds](https://docs.railway.com/builds/dockerfiles)
- [Railway service domains](https://docs.railway.com/networking/domains/working-with-domains)
## LLM providers and failover

OpenRouter’s `openrouter/free` is the primary provider. Set `OPENROUTER_API_KEY`
for local development and on the Railway backend. Leave `OPENAI_API_KEY` blank
to use OpenRouter alone.

To enable the fallback, set `OPENAI_API_KEY` on the backend. It sends the same
prompts and property context to OpenAI’s `gpt-4.1-mini` when OpenRouter hits a rate
limit, times out, returns a server error, or fails to return a usable completion.
The backend logs when it switches providers. OpenAI API usage is billable.
Both model names are set in `backend/rag.py`.

- [OpenRouter Free Models Router](https://openrouter.ai/openrouter/free)
- [OpenAI GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)

Before submitting the frontend URL, open it in a private window and confirm that both sample questions return grounded answers and that an explicit listing-link request produces a clickable link.
