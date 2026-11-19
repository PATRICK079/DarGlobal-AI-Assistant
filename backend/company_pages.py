OFFICIAL_SITES = {
    "DarGlobal": "https://darglobal.co.uk/",
    "Wasalt": "https://wasalt.sa/en",
}

DAR_ABOUT = "https://darglobal.co.uk/about"
DAR_FAQ = "https://darglobal.co.uk/faq"
DAR_RESULTS = "https://data.fca.org.uk/artefacts/NSM/RNS/72dab3cd-9922-4b16-9e31-9f48b1d2a5d2.html"
WASALT_CORPORATE = "https://wasalt.sa/en/corporate"
COMPANY_PROFILE_URLS = {
    "DarGlobal": (DAR_ABOUT, DAR_FAQ, DAR_RESULTS),
    "Wasalt": (WASALT_CORPORATE, OFFICIAL_SITES["Wasalt"]),
}

DAR_CONTACT = "https://darglobal.co.uk/get-in-touch"
DAR_CONTACT_PREVIEW = "https://preprod.darglobal.co.uk/get-in-touch"
DAR_DG1_BROCHURE = "https://cdn.darglobal.co.uk/DG_1_Brochure_mini_Digital_1_b323d310fc.pdf"
WASALT_LICENSE = "https://cdn.wasalt.sa/license/ministryOfTourismPdf.pdf"
WASALT_APP = "https://play.google.com/store/apps/details?hl=en_GB&id=com.wasalt.app"
WASALT_SUPPORT = "https://support.wasalt.com/"

CONTACT_URLS = {
    "DarGlobal": (DAR_CONTACT, DAR_CONTACT_PREVIEW, DAR_DG1_BROCHURE),
    "Wasalt": (WASALT_LICENSE, WASALT_APP, WASALT_SUPPORT),
}
for company, urls in CONTACT_URLS.items():
    COMPANY_PROFILE_URLS[company] += urls

WASALT_CITIES = {
    "riyadh": "Riyadh",
    "jeddah": "Jeddah",
    "dammam": "Dammam",
    "al-khobar": "Al Khobar",
    "makkah": "Makkah",
}
