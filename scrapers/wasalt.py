import re
import sys
from urllib.parse import urljoin, urlparse

import httpx

from backend.company_pages import (
    OFFICIAL_SITES, WASALT_APP, WASALT_CITIES, WASALT_CORPORATE, WASALT_LICENSE, WASALT_SUPPORT,
)
from scrapers.company_helpers import EMAIL, PHONE, collect_contacts, page_text, profile_record, whatsapp_links

ORIGIN = "https://wasalt.sa"
PAGES = {
    ("residential", "sale"): "properties-for-sale-in",
    ("residential", "rent"): "properties-for-rent-in",
    ("commercial", "sale"): "commercial-properties-for-sale-in",
    ("commercial", "rent"): "commercial-properties-for-rent-in",
}
RESIDENTIAL_TYPE = re.compile(r"^(?:(?:semi-)?furnished )?(apartment|villa|house|duplex|studio|floor)\b", re.I)
COMMERCIAL_TYPE = re.compile(r"^(office(?: space)?|warehouse|showroom|shop|retail(?: space)?|commercial (?:land|building))\b", re.I)
PRICE = re.compile(r"^(\d{1,3}(?:,\d{3})+|\d{1,15})\s+(?:(monthly|yearly)\s+)?(.+)$", re.I)


def listing_details(page, url):
    details = {}
    for cell in page.select('li[class*="propInfodetailscell"]'):
        label = cell.select_one('[class*="propInfodetailcaption"]')
        figure = cell.select_one('[class*="propInfodetailfigure"]')
        if not label or not figure:
            continue
        area_type = label.get_text(" ", strip=True).casefold()
        value = re.fullmatch(r"([0-9,]+(?:\.[0-9]+)?)\s*SQM", figure.get_text(" ", strip=True), re.I)
        if value and area_type in ("built-up area", "land area", "plot area"):
            area = float(value[1].replace(",", ""))
            if area > 0 and (area_type == "built-up area" or "area_sqm" not in details):
                details.update(area_sqm=area, area_type=area_type)
    features = {}
    for cell in page.select('[class*="infoSectionInnerContainer"]'):
        label = cell.select_one('[class*="infoLable"]')
        value = cell.select_one('[class*="style_name"]')
        if label and value:
            name = label.get_text(" ", strip=True)
            text = value.get_text(" ", strip=True)
            if name in ("Age", "Facade") and text:
                features[name] = text
    if features:
        details["features"] = features
    property_id = url.rsplit("-", 1)[-1]
    images = {}
    for image in page.select("img[src]"):
        source = image["src"]
        parsed = urlparse(source)
        if parsed.scheme == "https" and parsed.netloc == "imagedelivery.net":
            match = re.search(rf"/properties/{property_id}/images/([^/]+)", parsed.path)
            if match:
                images.setdefault(match[1], source)
    if images:
        details["images"] = list(images.values())[:8]
    return details


def scrape(fetch, limit):
    records = {}
    for slug, city in WASALT_CITIES.items():
        for (category, transaction), prefix in PAGES.items():
            path = f"{prefix}-{slug}"
            try:
                listings = scrape_page(fetch, path, category, transaction, limit, city=city)
            except (httpx.HTTPError, ValueError) as error:
                print(f"Wasalt catalogue unavailable at {ORIGIN}/en/{path}: {error}", file=sys.stderr)
                continue
            for listing in listings:
                records.setdefault(listing["url"], listing)
    return list(records.values())


def scrape_page(fetch, path, category, transaction, limit, *, city):
    page = fetch(f"{ORIGIN}/en/{path}")
    selector = f'a[href*="/property/{transaction}/"]'
    records = {}
    for link in page.select(selector):
        url = urljoin(ORIGIN, link["href"]).split("?")[0].split("#")[0]
        if not re.fullmatch(rf"https://wasalt[.]sa/en/property/{transaction}/[^/]+-[0-9]+", url) or url in records:
            continue
        title = " ".join(link.stripped_strings)
        price = PRICE.fullmatch(title)
        if not price or (transaction == "rent" and not price[2]) or (transaction == "sale" and price[2]):
            continue
        amount, rental_period, description = price.groups()
        type_match = (RESIDENTIAL_TYPE if category == "residential" else COMMERCIAL_TYPE).match(description)
        if category == "residential" and not type_match:
            continue
        if category == "commercial" and RESIDENTIAL_TYPE.match(description):
            continue
        property_type = type_match[1].lower() if type_match else None
        property_type = {"office space": "office", "retail space": "retail"}.get(property_type, property_type)
        location = ""
        for parent in list(link.parents)[:4]:
            if len({item["href"] for item in parent.select(selector)}) > 1:
                break
            heading = parent.find("h6")
            if heading:
                location = heading.get_text(" ", strip=True)
                break
        property_id = url.rsplit("-", 1)[-1]
        image_url = None
        card = link.find_parent("article")
        if card and property_id.isdecimal():
            for image in card.select("img[src]"):
                image_src = urlparse(image["src"])
                if (image_src.scheme == "https" and image_src.netloc == "imagedelivery.net"
                        and f"/properties/{property_id}/images/" in image_src.path):
                    image_url = image["src"]
                    break
        city_names = ("Al Khobar", "Khobar") if city == "Al Khobar" else (city,)
        if not any(re.search(rf"\b{re.escape(name)}\b", location, re.I) for name in city_names):
            location = f"{location}, {city}" if location else city
        rental_period = rental_period.lower() if rental_period else None
        period_text = f" {rental_period}" if rental_period else ""
        price_label = "Advertised rent" if transaction == "rent" else "Advertised asking price"
        records[url] = {
            "url": url, "source": "Wasalt", "title": description, "image_url": image_url,
            "listing_metadata": {
                "category": category,
                "property_type": property_type,
                "location": location,
                "city": city,
                "price": int(amount.replace(",", "")),
                "rental_period": rental_period,
            },
            "content": f"{description}. {category.title()} property for {transaction} in {location}. "
                       f"{price_label}: SAR {amount}{period_text}.",
        }
        if len(records) >= limit:
            break
    return list(records.values())


def wasalt_app(page):
    text = page.get_text(" ", strip=True)
    support = text.partition("App support")[2].partition("Similar apps")[0]
    developer = support.partition("About the developer")[2]
    for phone in re.findall(PHONE, developer):
        yield f"Google Play developer phone: {phone}"
    for email in re.findall(EMAIL, support, re.I):
        yield f"Google Play app support email: {email}"


def wasalt_license(text):
    for phone in re.findall(PHONE, text):
        yield f"Riyadh office phone (tourism licence): {phone}"
    for email in re.findall(EMAIL, text, re.I):
        yield f"Email listed on the Wasalt tourism licence: {email}"


def wasalt_support(page):
    if "wasalt support" in page.get_text(" ", strip=True).casefold():
        yield "Wasalt provides an official online support form at this source."
        yield from whatsapp_links(page)


def scrape_profiles(fetch):
    corporate = page_text(fetch(WASALT_CORPORATE))
    home = fetch(OFFICIAL_SITES["Wasalt"])
    faq = [
        item.get_text(" ", strip=True)
        for item in home.select('li[class*="faqItem"]')
        if item.select_one('[class*="faqAnswer"]')
    ]
    return [
        profile_record(WASALT_CORPORATE, "Wasalt", "Wasalt company and products", corporate),
        profile_record(OFFICIAL_SITES["Wasalt"], "Wasalt", "Wasalt services and frequently asked questions", faq),
    ]


def scrape_contacts(fetch, fetch_pdf):
    sources = (
        (WASALT_LICENSE, "Wasalt tourism licence contacts", fetch_pdf, wasalt_license),
        (WASALT_APP, "Wasalt app contacts on Google Play", fetch, wasalt_app),
        (WASALT_SUPPORT, "Wasalt support form and channels", fetch, wasalt_support),
    )
    return collect_contacts("Wasalt", sources)
