import re
import sys
from urllib.parse import parse_qs, urlsplit

import httpx

PHONE = r"\+\d(?:[ \t().-]*\d){7,14}(?!\d)"
EMAIL = r"[a-z][\w.+-]*@[a-z\d.-]+\.[a-z]{2,}"


def whatsapp_links(page):
    for link in page.select("a[href]"):
        url = urlsplit(link["href"].strip())
        if url.scheme not in ("", "https", "http"):
            continue
        if url.hostname == "wa.me":
            number = url.path.strip("/")
        elif url.hostname in ("api.whatsapp.com", "web.whatsapp.com") and url.path == "/send":
            number = parse_qs(url.query).get("phone", [""])[0].lstrip("+")
        else:
            continue
        if re.fullmatch(r"[1-9][0-9]{7,14}", number):
            yield f"Official WhatsApp number: +{number}"


def page_text(page):
    for element in page.select("header, footer, nav, script, style, form, noscript"):
        element.decompose()
    body = page.find("main") or page.body
    return list(dict.fromkeys(
        node.get_text(" ", strip=True)
        for node in body.select("h1, h2, h3, p, li")
        if node.get_text(" ", strip=True)
    )) if body else []


def profile_record(url, source, title, paragraphs):
    content = "\n".join(paragraphs)
    if len(content) < 150:
        raise ValueError(f"No company profile content found at {url}")
    return {"url": url, "source": source, "title": title, "content": content}


def collect_contacts(company, sources):
    records = []
    for url, title, load, extract in sources:
        try:
            contacts = list(dict.fromkeys(extract(load(url))))
            if not contacts:
                raise ValueError("No public contact details found")
            records.append({"url": url, "source": company, "title": title, "content": "\n".join(contacts)})
        except (httpx.HTTPError, ValueError) as error:
            print(f"{company} contact source unavailable at {url}: {error}", file=sys.stderr)
    return records
