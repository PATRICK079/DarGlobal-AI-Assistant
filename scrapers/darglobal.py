import re
import sys

import httpx

from backend.company_pages import (
    DAR_ABOUT, DAR_CONTACT, DAR_CONTACT_PREVIEW, DAR_DG1_BROCHURE, DAR_FAQ, DAR_RESULTS,
)
from scrapers.company_helpers import EMAIL, PHONE, collect_contacts, page_text, profile_record, whatsapp_links

URLS = ("https://darglobal.co.uk/the-astera", "https://darglobal.co.uk/dg1")
FILING = "https://www.investegate.co.uk/announcement/rns/dar-global--dar/full-year-results-/9468098"


def project(fetch, url):
    page = fetch(url)
    for element in page.select("header, footer, nav, script, style, form, noscript"):
        element.decompose()
    body = page.find("main") or page.body
    heading = body.find("h1") if body else None
    title = heading or page.title
    content = " ".join(body.stripped_strings) if body else ""
    if not title or len(content) < 150:
        raise ValueError(f"No project content found at {url}")
    return {"url": url, "source": "DarGlobal", "title": title.get_text(" ", strip=True),
            "content": content[:9000]}


def filing(fetch):
    page = fetch(FILING)
    projects = ("the astera", "trump tower jeddah", "trump tower, jeddah", "marea by missoni")
    paragraphs = []
    for node in page.find_all(string=True):
        text = " ".join(node.split())
        if not 100 <= len(text) <= 1800 or not any(name in text.lower() for name in projects):
            continue
        if node.find_parent("p") and node.find_parent(class_="fr-view-element"):
            paragraphs.append(text)
    if not paragraphs:
        raise ValueError("No project information found in the Dar Global PLC filing.")
    return {
        "url": FILING, "source": "DarGlobal", "title": "Dar Global PLC Full Year 2025 Results",
        "content": "\n".join(dict.fromkeys(paragraphs))[:9000],
    }


def scrape(fetch):
    records = []
    for url in URLS:
        try:
            records.append(project(fetch, url))
        except (httpx.HTTPError, ValueError) as error:
            print(f"DarGlobal page unavailable: {error}", file=sys.stderr)
    if len(records) < len(URLS):
        records.append(filing(fetch))
    return records


def dar_results(page):
    review = []
    for paragraph in page.select("p"):
        text = paragraph.get_text(" ", strip=True)
        if text.casefold().rstrip(":") == "financials summary":
            break
        if text and not paragraph.find_parent("table"):
            review.append(text)

    about_heading = page.find(string=lambda text: text and text.strip().casefold() == "about dar global")
    if not about_heading or not about_heading.find_parent("p"):
        raise ValueError(f"No company description found at {DAR_RESULTS}")
    overview = []
    for paragraph in about_heading.find_parent("p").find_next_siblings("p"):
        text = paragraph.get_text(" ", strip=True)
        if text.startswith("- Ends -"):
            break
        if text:
            overview.append(text)
    return [*overview, *review]


def dar_contact(page):
    heading = None
    for node in page.select("h3, p, a[href]"):
        text = node.get_text(" ", strip=True)
        if node.name == "h3":
            heading = text
        elif heading:
            for phone in re.findall(PHONE, text):
                yield f"{heading} phone: {phone}"
            for email in re.findall(EMAIL, text, re.I):
                yield f"{heading} email: {email}"
    yield from whatsapp_links(page)


def dg1_brochure(text):
    normalized = " ".join(text.split())
    for phone in re.findall(rf"please call\s+({PHONE})", normalized, re.I):
        yield f"DG1 brochure enquiry phone: {phone}"


def scrape_profiles(fetch, *, rendered_fetch=None):
    records = []
    for url, title, extract, fetch_page in (
        (DAR_ABOUT, "DarGlobal About", page_text, rendered_fetch or fetch),
        (DAR_FAQ, "DarGlobal frequently asked questions", page_text, rendered_fetch or fetch),
        (DAR_RESULTS, "Dar Global PLC company overview and business results", dar_results, fetch),
    ):
        try:
            page = fetch_page(url)
            if url in (DAR_ABOUT, DAR_FAQ):
                if "incapsula incident id" in page.get_text(" ", strip=True).casefold():
                    raise ValueError("DarGlobal returned an Incapsula block page")
                if not page.select_one("h1, h2"):
                    raise ValueError("The response did not contain the company page")
            records.append(profile_record(url, "DarGlobal", title, extract(page)))
        except (httpx.HTTPError, ValueError) as error:
            print(f"DarGlobal company source unavailable at {url}: {error}", file=sys.stderr)
    return records


def scrape_contacts(fetch_rendered, fetch_pdf):
    sources = (
        (DAR_CONTACT, "DarGlobal office and department contacts", fetch_rendered, dar_contact),
        (DAR_CONTACT_PREVIEW, "DarGlobal contacts from its preview site", fetch_rendered, dar_contact),
        (DAR_DG1_BROCHURE, "DarGlobal DG1 enquiry phone", fetch_pdf, dg1_brochure),
    )
    return collect_contacts("DarGlobal", sources)
