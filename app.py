import streamlit as st
import pandas as pd
from serpapi import GoogleSearch
import requests
from bs4 import BeautifulSoup
import re
import time
import json
from urllib.parse import urljoin, urlparse
from io import BytesIO

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Sales Intelligence Tool",
    layout="wide"
)

st.title("🚀 Sales Intelligence Tool")
st.caption(
    "Find real importers, distributors, wholesalers and retailers"
)

# =========================================================
# SESSION STATE
# =========================================================

if "customs_df" not in st.session_state:
    st.session_state.customs_df = None


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("⚙️ System Settings")

serpapi_key = st.sidebar.text_input(
    "SerpApi API Key",
    type="password"
)

max_pages_per_company = st.sidebar.slider(
    "Website pages to scan",
    1,
    5,
    3
)

request_timeout = st.sidebar.slider(
    "Website timeout (seconds)",
    3,
    15,
    7
)


# =========================================================
# BLOCKED DOMAINS
# =========================================================

BLOCKED_DOMAINS = {
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "wikipedia.org",
    "europages.com",
    "yellowpages.com",
    "yellowpages.vn",
    "kompass.com",
    "globalsources.com",
    "alibaba.com",
    "made-in-china.com",
    "tradekey.com",
    "revenuebase.ai",
    "crunchbase.com",
    "zoominfo.com",
    "apollo.io",
    "glassdoor.com",
    "indeed.com",
    "amazon.com",
    "ebay.com"
}

BLOCKED_EMAIL_PREFIX = {
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "privacy",
    "legal",
    "abuse",
    "webmaster"
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/125 Safari/537.36"
)

session = requests.Session()

session.headers.update({
    "User-Agent": USER_AGENT
})


# =========================================================
# URL / DOMAIN
# =========================================================

def normalize_domain(url):

    try:

        if not url.startswith("http"):
            url = "https://" + url

        parsed = urlparse(url)

        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except:

        return ""


def is_blocked_domain(domain):

    domain = domain.lower()

    for blocked in BLOCKED_DOMAINS:

        if (
            domain == blocked
            or domain.endswith("." + blocked)
        ):
            return True

    return False


# =========================================================
# COMPANY NAME NORMALIZATION
# =========================================================

def normalize_company_name(name):

    if not name:
        return ""

    name = name.lower()

    suffixes = [
        " gmbh",
        " ltd",
        " limited",
        " inc",
        " incorporated",
        " llc",
        " sarl",
        " bv",
        " nv",
        " ag",
        " kg",
        " co",
        " company",
        " corp",
        " corporation"
    ]

    for suffix in suffixes:

        if name.endswith(suffix):
            name = name[:-len(suffix)]

    name = re.sub(
        r"[^a-z0-9äöüßà-ÿ\s]",
        " ",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip()

    return name


# =========================================================
# EMAIL EXTRACTION
# =========================================================

def extract_emails(text):

    if not text:
        return []

    emails = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text
    )

    clean = []

    for email in emails:

        email = email.lower().strip()

        prefix = email.split("@")[0]

        if prefix in BLOCKED_EMAIL_PREFIX:
            continue

        if email not in clean:
            clean.append(email)

    return clean


# =========================================================
# JSON-LD COMPANY EXTRACTION
# =========================================================

def extract_jsonld_company(soup):

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):

        try:

            data = json.loads(
                script.string or script.get_text()
            )

            items = []

            if isinstance(data, dict):

                if "@graph" in data:
                    items = data["@graph"]
                else:
                    items = [data]

            elif isinstance(data, list):

                items = data

            for item in items:

                if not isinstance(item, dict):
                    continue

                item_type = item.get(
                    "@type",
                    ""
                )

                if isinstance(
                    item_type,
                    list
                ):
                    item_type = " ".join(
                        item_type
                    )

                item_type = str(
                    item_type
                ).lower()

                if any(
                    x in item_type
                    for x in [
                        "organization",
                        "corporation",
                        "localbusiness",
                        "store",
                        "retailer"
                    ]
                ):

                    name = item.get(
                        "name"
                    )

                    if name and len(
                        name.strip()
                    ) > 2:

                        return name.strip()

        except:

            continue

    return ""


# =========================================================
# COMPANY NAME EXTRACTION
# =========================================================

def extract_company_name(
    soup,
    url,
    google_title=""
):

    # 1. JSON-LD
    name = extract_jsonld_company(
        soup
    )

    if name:
        return name

    # 2. OG Site Name
    og = soup.find(
        "meta",
        attrs={
            "property": "og:site_name"
        }
    )

    if og and og.get("content"):

        return og["content"].strip()

    # 3. Application Name
    app = soup.find(
        "meta",
        attrs={
            "name": "application-name"
        }
    )

    if app and app.get("content"):

        return app["content"].strip()

    # 4. Website title
    title = ""

    if soup.title and soup.title.string:

        title = soup.title.string.strip()

    if title:

        parts = re.split(
            r"\s+[|–—-]\s+",
            title
        )

        candidate = parts[0].strip()

        generic_words = [
            "importer",
            "distributor",
            "wholesale",
            "wholesaler",
            "supplier",
            "coconut water",
            "products",
            "home",
            "homepage"
        ]

        if (
            len(candidate) > 2
            and not all(
                word in candidate.lower()
                for word in generic_words
            )
        ):

            return candidate

    # 5. Domain fallback
    domain = normalize_domain(url)

    return (
        domain
        .split(".")[0]
        .replace("-", " ")
        .title()
    )


# =========================================================
# FETCH WEBSITE
# =========================================================

def fetch_page(
    url,
    timeout=7
):

    try:

        response = session.get(
            url,
            timeout=timeout,
            allow_redirects=True
        )

        if response.status_code >= 400:
            return None, ""

        content_type = response.headers.get(
            "content-type",
            ""
        ).lower()

        if "text/html" not in content_type:
            return None, ""

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        return soup, response.url

    except:

        return None, ""


# =========================================================
# FIND CONTACT PAGES
# =========================================================

def find_contact_pages(
    base_url,
    soup
):

    candidates = []

    keywords = [
        "contact",
        "contact-us",
        "kontakt",
        "impressum",
        "about",
        "about-us",
        "company",
        "unternehmen",
        "kontaktieren"
    ]

    for a in soup.find_all(
        "a",
        href=True
    ):

        text = (
            a.get_text(
                " ",
                strip=True
            ).lower()
        )

        href = a.get(
            "href",
            ""
        ).lower()

        combined = (
            text + " " + href
        )

        if any(
            k in combined
            for k in keywords
        ):

            url = urljoin(
                base_url,
                a["href"]
            )

            if url not in candidates:
                candidates.append(url)

    # Common paths
    for path in [
        "/contact",
        "/contact-us",
        "/kontakt",
        "/impressum",
        "/about",
        "/about-us"
    ]:

        url = urljoin(
            base_url,
            path
        )

        if url not in candidates:
            candidates.append(url)

    return candidates[:5]


# =========================================================
# WEBSITE DATA EXTRACTION
# =========================================================

def extract_website_data(
    url,
    timeout=7,
    max_pages=3
):

    result = {
        "company_name": "",
        "email": "",
        "contact_page": "",
        "final_url": url,
        "website_evidence": "",
        "website_text": ""
    }

    soup, final_url = fetch_page(
        url,
        timeout
    )

    if soup is None:
        return result

    result["final_url"] = final_url

    # -----------------------------------------------------
    # COMPANY NAME
    # -----------------------------------------------------

    result["company_name"] = extract_company_name(
        soup,
        final_url
    )

    # -----------------------------------------------------
    # EMAIL
    # -----------------------------------------------------

    emails = []

    # mailto links
    for a in soup.find_all(
        "a",
        href=True
    ):

        href = a["href"]

        if href.lower().startswith(
            "mailto:"
        ):

            email = (
                href[7:]
                .split("?")[0]
                .strip()
            )

            if email:
                emails.append(email)

    # Homepage text
    page_text = soup.get_text(
        " ",
        strip=True
    )

    emails.extend(
        extract_emails(page_text)
    )

    # -----------------------------------------------------
    # CONTACT PAGES
    # -----------------------------------------------------

    contact_pages = find_contact_pages(
        final_url,
        soup
    )

    scanned = 1

    for contact_url in contact_pages:

        if scanned >= max_pages:
            break

        try:

            contact_soup, contact_final = fetch_page(
                contact_url,
                timeout
            )

            scanned += 1

            if contact_soup is None:
                continue

            contact_text = contact_soup.get_text(
                " ",
                strip=True
            )

            emails.extend(
                extract_emails(
                    contact_text
                )
            )

            for a in contact_soup.find_all(
                "a",
                href=True
            ):

                href = a["href"]

                if href.lower().startswith(
                    "mailto:"
                ):

                    email = (
                        href[7:]
                        .split("?")[0]
                        .strip()
                    )

                    if email:
                        emails.append(
                            email
                        )

            if (
                emails
                and not result["contact_page"]
            ):

                result["contact_page"] = (
                    contact_final
                )

        except:

            continue

    # -----------------------------------------------------
    # CLEAN EMAIL
    # -----------------------------------------------------

    clean_emails = []

    for email in emails:

        email = email.lower().strip()

        if not re.match(
            r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            email
        ):
            continue

        prefix = email.split("@")[0]

        if prefix in BLOCKED_EMAIL_PREFIX:
            continue

        if email not in clean_emails:
            clean_emails.append(email)

    if clean_emails:

        result["email"] = (
            clean_emails[0]
        )

    # -----------------------------------------------------
    # WEBSITE TEXT
    # -----------------------------------------------------

    result["website_text"] = page_text[
        :20000
    ]

    # -----------------------------------------------------
    # BUSINESS EVIDENCE
    # -----------------------------------------------------

    evidence_words = []

    text_lower = page_text.lower()

    for word in [
        "importer",
        "import",
        "distributor",
        "distribution",
        "wholesale",
        "wholesaler",
        "retailer",
        "retail",
        "supermarket",
        "beverages",
        "foodservice"
    ]:

        if word in text_lower:
            evidence_words.append(
                word
            )

    result["website_evidence"] = ", ".join(
        sorted(
            set(evidence_words)
        )
    )

    return result


# =========================================================
# COMPANY TYPE
# =========================================================

def classify_company_type(text):

    text = text.lower()

    scores = {
        "Nhà nhập khẩu": 0,
        "Nhà phân phối": 0,
        "Nhà bán buôn": 0,
        "Retailer": 0,
        "HoReCa": 0
    }

    importer_words = [
        "importer",
        "import",
        "importing",
        "imports"
    ]

    distributor_words = [
        "distributor",
        "distribution",
        "distributing"
    ]

    wholesale_words = [
        "wholesale",
        "wholesaler",
        "cash & carry",
        "cash and carry"
    ]

    retailer_words = [
        "retailer",
        "retail",
        "supermarket",
        "grocery",
        "stores",
        "store"
    ]

    horeca_words = [
        "hotel",
        "restaurant",
        "cafe",
        "foodservice",
        "horeca"
    ]

    for word in importer_words:

        if word in text:
            scores[
                "Nhà nhập khẩu"
            ] += 3

    for word in distributor_words:

        if word in text:
            scores[
                "Nhà phân phối"
            ] += 3

    for word in wholesale_words:

        if word in text:
            scores[
                "Nhà bán buôn"
            ] += 3

    for word in retailer_words:

        if word in text:
            scores[
                "Retailer"
            ] += 2

    for word in horeca_words:

        if word in text:
            scores[
                "HoReCa"
            ] += 2

    best_type = max(
        scores,
        key=scores.get
    )

    if scores[best_type] == 0:
        return "Chưa xác định"

    return best_type


# =========================================================
# LEAD SCORE
# =========================================================

def calculate_lead_score(
    title,
    snippet,
    keyword,
    website_text,
    email,
    company_name,
    company_type
):

    score = 0

    evidence = []

    combined = (
        title
        + " "
        + snippet
        + " "
        + website_text
    ).lower()

    keyword_lower = keyword.lower()

    # Product relevance
    if keyword_lower in combined:

        score += 20

        evidence.append(
            "Product match"
        )

    # Importer
    if any(
        x in combined
        for x in [
            "importer",
            "import",
            "importing"
        ]
    ):

        score += 20

        evidence.append(
            "Importer evidence"
        )

    # Distributor
    if any(
        x in combined
        for x in [
            "distributor",
            "distribution"
        ]
    ):

        score += 15

        evidence.append(
            "Distributor evidence"
        )

    # Wholesale
    if any(
        x in combined
        for x in [
            "wholesale",
            "wholesaler"
        ]
    ):

        score += 10

        evidence.append(
            "Wholesale evidence"
        )

    # Retail
    if any(
        x in combined
        for x in [
            "retailer",
            "supermarket",
            "grocery",
            "retail"
        ]
    ):

        score += 10

        evidence.append(
            "Retail evidence"
        )

    # Real company
    if company_name:

        score += 10

        evidence.append(
            "Company identified"
        )

    # Email
    if email:

        score += 15

        evidence.append(
            "Email found"
        )

    # Customer type
    if company_type != "Chưa xác định":

        score += 5

    score = min(
        score,
        100
    )

    if score >= 75:

        confidence = "CAO"

    elif score >= 50:

        confidence = "TRUNG BÌNH"

    else:

        confidence = "THẤP"

    return (
        score,
        confidence,
        ", ".join(evidence)
    )


# =========================================================
# QUERY GENERATOR
# =========================================================

def generate_queries(
    keywords,
    country,
    target_roles
):

    queries = []

    role_map = {

        "Nhà nhập khẩu": [
            "importer",
            "import company"
        ],

        "Nhà phân phối": [
            "distributor",
            "distribution"
        ],

        "Nhà bán buôn": [
            "wholesale",
            "wholesaler"
        ],

        "HoReCa / Retailer": [
            "retailer",
            "supermarket",
            "foodservice"
        ]
    }

    for keyword in keywords[:3]:

        for role in target_roles:

            for role_keyword in role_map.get(
                role,
                ["importer"]
            ):

                queries.append(
                    f'"{keyword}" '
                    f'"{role_keyword}" '
                    f'"{country}"'
                )

    # Germany local language
    if country.lower() == "germany":

        local_roles = [
            "Importeur",
            "Distributor",
            "Großhandel",
            "Händler"
        ]

        for keyword in keywords[:2]:

            for role in local_roles:

                queries.append(
                    f'"{keyword}" '
                    f'"{role}" '
                    f'Deutschland'
                )

    # Spain local language
    if country.lower() == "spain":

        local_roles = [
            "importador",
            "distribuidor",
            "mayorista",
            "retailer"
        ]

        for keyword in keywords[:2]:

            for role in local_roles:

                queries.append(
                    f'"{keyword}" '
                    f'"{role}" '
                    f'España'
                )

    # Korea local language
    if country.lower() in [
        "korea",
        "south korea"
    ]:

        local_roles = [
            "수입업체",
            "유통업체",
            "도매",
            "수입"
        ]

        for keyword in keywords[:2]:

            for role in local_roles:

                queries.append(
                    f'"{keyword}" '
                    f'"{role}"'
                )

    return list(
        dict.fromkeys(queries)
    )


# =========================================================
# GOOGLE SEARCH
# =========================================================

def google_search(
    query,
    api_key
):

    try:

        params = {
            "q": query,
            "engine": "google",
            "num": 10,
            "api_key": api_key
        }

        search = GoogleSearch(
            params
        )

        return search.get_dict().get(
            "organic_results",
            []
        )

    except:

        return []


# =========================================================
# CUSTOMS MATCH
# =========================================================

def customs_match(
    company_name,
    domain,
    customs_df
):

    if customs_df is None:
        return False

    if customs_df.empty:
        return False

    normalized_company = normalize_company_name(
        company_name
    )

    normalized_domain = normalize_domain(
        domain
    )

    for _, row in customs_df.iterrows():

        row_text = " ".join(
            str(v)
            for v in row.values
        ).lower()

        normalized_row = normalize_company_name(
            row_text
        )

        if (
            normalized_company
            and normalized_company in normalized_row
        ):

            return True

        if (
            normalized_domain
            and normalized_domain in row_text
        ):

            return True

    return False


# =========================================================
# TABS
# =========================================================

tab_search, tab_customs = st.tabs([
    "🔎 Find Sales Leads",
    "📦 Customs Data"
])


# =========================================================
# TAB 1
# =========================================================

with tab_search:

    st.subheader(
        "🎯 Find Importers / Distributors / Retailers"
    )

    col1, col2, col3 = st.columns(
        [2, 1, 1]
    )

    with col1:

        raw_product = st.text_area(
            "Products / Keywords",
            "coconut water\norganic coconut water\ncoconut beverage",
            height=120
        )

    with col2:

        country = st.text_input(
            "Target country",
            "Germany"
        ).strip()

        num_target = st.slider(
            "Target leads",
            5,
            100,
            30
        )

    with col3:

        target_roles = st.multiselect(
            "Target customer type",
            [
                "Nhà nhập khẩu",
                "Nhà phân phối",
                "Nhà bán buôn",
                "HoReCa / Retailer"
            ],
            default=[
                "Nhà nhập khẩu",
                "Nhà phân phối",
                "HoReCa / Retailer"
            ]
        )

    btn_start = st.button(
        "🚀 START LEAD GENERATION",
        type="primary"
    )

    if btn_start:

        if not serpapi_key:

            st.error(
                "⚠️ Please enter your SerpApi API key."
            )

        else:

            keywords = [
                k.strip()
                for k in raw_product
                .replace("\n", ",")
                .split(",")
                if k.strip()
            ]

            if not keywords:

                st.error(
                    "Please enter at least one product keyword."
                )

                st.stop()

            queries = generate_queries(
                keywords,
                country,
                target_roles
            )

            st.info(
                f"🔍 Generated {len(queries)} search queries."
            )

            all_leads = []

            progress = st.progress(0)

            status = st.empty()

            # -------------------------------------------------
            # SEARCH
            # -------------------------------------------------

            for idx, query in enumerate(
                queries
            ):

                status.text(
                    f"🔎 Searching "
                    f"{idx + 1}/{len(queries)}: "
                    f"{query}"
                )

                results = google_search(
                    query,
                    serpapi_key
                )

                for item in results:

                    link = item.get(
                        "link",
                        ""
                    )

                    title = item.get(
                        "title",
                        ""
                    )

                    snippet = item.get(
                        "snippet",
                        ""
                    )

                    if not link:
                        continue

                    domain = normalize_domain(
                        link
                    )

                    # -----------------------------------------
                    # BLOCK DIRECTORIES / SOCIAL
                    # -----------------------------------------

                    if is_blocked_domain(
                        domain
                    ):
                        continue

                    if not domain:
                        continue

                    # -----------------------------------------
                    # VISIT WEBSITE
                    # -----------------------------------------

                    website_data = extract_website_data(
                        link,
                        timeout=request_timeout,
                        max_pages=max_pages_per_company
                    )

                    company_name = website_data[
                        "company_name"
                    ]

                    email = website_data[
                        "email"
                    ]

                    final_url = website_data[
                        "final_url"
                    ]

                    website_text = website_data[
                        "website_text"
                    ]

                    company_type = classify_company_type(
                        title
                        + " "
                        + snippet
                        + " "
                        + website_text
                    )

                    score, confidence, evidence = (
                        calculate_lead_score(
                            title,
                            snippet,
                            keywords[0],
                            website_text,
                            email,
                            company_name,
                            company_type
                        )
                    )

                    # -----------------------------------------
                    # CUSTOMS
                    # -----------------------------------------

                    verified_customs = customs_match(
                        company_name,
                        domain,
                        st.session_state.customs_df
                    )

                    if verified_customs:

                        score = min(
                            score + 20,
                            100
                        )

                        confidence = (
                            "CAO - CUSTOMS VERIFIED"
                        )

                        evidence += (
                            ", Customs match"
                        )

                    # -----------------------------------------
                    # SAVE
                    # -----------------------------------------

                    all_leads.append({

                        "Company":
                            company_name,

                        "Country":
                            country,

                        "Customer Type":
                            company_type,

                        "Email":
                            email,

                        "Website":
                            final_url,

                        "Contact Page":
                            website_data[
                                "contact_page"
                            ],

                        "Domain":
                            domain,

                        "Lead Score":
                            score,

                        "Confidence":
                            confidence,

                        "Customs Verified":
                            "YES"
                            if verified_customs
                            else "NO",

                        "Evidence":
                            evidence,

                        "Google Title":
                            title,

                        "Google Snippet":
                            snippet

                    })

                progress.progress(
                    (idx + 1) / len(queries)
                )

                time.sleep(0.3)

            status.text(
                "✅ Lead generation completed."
            )

            # =================================================
            # CLEAN DATA
            # =================================================

            if all_leads:

                df = pd.DataFrame(
                    all_leads
                )

                # Remove empty companies
                df = df[
                    df["Company"].notna()
                    & (
                        df["Company"]
                        .astype(str)
                        .str.len()
                        > 2
                    )
                ]

                # Normalize domain
                df["Domain"] = (
                    df["Domain"]
                    .fillna("")
                    .str.lower()
                )

                # Sort by score first
                df = df.sort_values(
                    "Lead Score",
                    ascending=False
                )

                # Remove duplicate companies/domains
                df = df.drop_duplicates(
                    subset=["Domain"],
                    keep="first"
                )

                # Limit results
                df = df.head(
                    num_target
                )

                # =================================================
                # METRICS
                # =================================================

                m1, m2, m3, m4 = st.columns(4)

                m1.metric(
                    "Raw Results",
                    len(all_leads)
                )

                m2.metric(
                    "Unique Companies",
                    len(df)
                )

                m3.metric(
                    "Email Found",
                    len(
                        df[
                            df["Email"]
                            .astype(str)
                            .str.len()
                            > 3
                        ]
                    )
                )

                m4.metric(
                    "Customs Verified",
                    len(
                        df[
                            df[
                                "Customs Verified"
                            ] == "YES"
                        ]
                    )
                )

                # =================================================
                # DISPLAY
                # =================================================

                st.subheader(
                    "🎯 Qualified Sales Leads"
                )

                display_cols = [
                    "Company",
                    "Country",
                    "Customer Type",
                    "Email",
                    "Website",
                    "Contact Page",
                    "Lead Score",
                    "Confidence",
                    "Customs Verified",
                    "Evidence"
                ]

                st.dataframe(
                    df[
                        display_cols
                    ],
                    use_container_width=True,
                    column_config={

                        "Website":
                            st.column_config.LinkColumn(
                                "Website"
                            ),

                        "Contact Page":
                            st.column_config.LinkColumn(
                                "Contact"
                            ),

                        "Email":
                            st.column_config.TextColumn(
                                "Email"
                            ),

                        "Lead Score":
                            st.column_config.ProgressColumn(
                                "Lead Score",
                                min_value=0,
                                max_value=100
                            )

                    },
                    hide_index=True
                )

                # =================================================
                # EXCEL EXPORT
                # =================================================

                output = BytesIO()

                with pd.ExcelWriter(
                    output,
                    engine="openpyxl"
                ) as writer:

                    # ---------------------------------------------
                    # SHEET 1 - SALES LEADS
                    # ---------------------------------------------

                    export_cols = [
                        "Company",
                        "Country",
                        "Customer Type",
                        "Email",
                        "Website",
                        "Contact Page",
                        "Domain",
                        "Lead Score",
                        "Confidence",
                        "Customs Verified",
                        "Evidence"
                    ]

                    df[
                        export_cols
                    ].to_excel(
                        writer,
                        index=False,
                        sheet_name="Sales Leads"
                    )

                    # ---------------------------------------------
                    # SHEET 2 - SEARCH EVIDENCE
                    # ---------------------------------------------

                    df[
                        [
                            "Company",
                            "Google Title",
                            "Google Snippet",
                            "Website",
                            "Domain"
                        ]
                    ].to_excel(
                        writer,
                        index=False,
                        sheet_name="Search Evidence"
                    )

                    # ---------------------------------------------
                    # SHEET 3 - CUSTOMS VERIFIED
                    # ---------------------------------------------

                    customs_verified_df = df[
                        df[
                            "Customs Verified"
                        ] == "YES"
                    ]

                    if not customs_verified_df.empty:

                        customs_verified_df[
                            export_cols
                        ].to_excel(
                            writer,
                            index=False,
                            sheet_name="Customs Verified"
                        )

                output.seek(0)

                st.download_button(
                    "📥 Download Sales Leads (.xlsx)",
                    data=output.getvalue(),
                    file_name=(
                        f"Sales_Leads_"
                        f"{country.replace(' ', '_')}.xlsx"
                    ),
                    mime=(
                        "application/"
                        "vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    )
                )

                st.success(
                    "✅ Excel file ready."
                )

            else:

                st.warning(
                    "Không tìm thấy lead phù hợp."
                )


# =========================================================
# TAB 2 - CUSTOMS DATA
# =========================================================

with tab_customs:

    st.subheader(
        "📦 Customs / Shipment Data"
    )

    st.write(
        "Upload dữ liệu shipment để xác minh importer thực tế."
    )

    uploaded_file = st.file_uploader(
        "Upload Excel / CSV",
        type=[
            "xlsx",
            "csv"
        ]
    )

    if uploaded_file:

        try:

            if uploaded_file.name.lower().endswith(
                ".csv"
            ):

                customs_df = pd.read_csv(
                    uploaded_file,
                    encoding="utf-8-sig"
                )

            else:

                customs_df = pd.read_excel(
                    uploaded_file
                )

            st.session_state.customs_df = (
                customs_df
            )

            st.success(
                f"✅ Loaded "
                f"{len(customs_df)} shipment records."
            )

            st.dataframe(
                customs_df.head(20),
                use_container_width=True
            )

            st.info(
                "Các lead tìm được ở Tab 1 sẽ được "
                "đối chiếu với dữ liệu này theo "
                "Company Name / Domain."
            )

        except Exception as e:

            st.error(
                f"File error: {e}"
            )
