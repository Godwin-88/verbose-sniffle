"""
job_hunter/scholarship_scrapers.py

Comprehensive scholarship scraper covering:

  🇬🇧  UK          — Chevening, Commonwealth, British Council
  🇺🇸  USA         — Fulbright, Hubert Humphrey, State Dept portals
  🇩🇪  Germany     — DAAD, Heinrich Böll, Konrad Adenauer, Friedrich Ebert
  🇫🇷  France      — Campus France, Eiffel Excellence
  🇳🇱  Netherlands — Nuffic/OKP, Orange Knowledge, Holland Scholarship
  🇸🇪  Sweden      — SI (Swedish Institute), SIDA
  🇳🇴  Norway      — Norpart, Norwegian Government
  🇩🇰  Denmark     — Danish Government Scholarships
  🇨🇭  Switzerland — Swiss Government Excellence (ESKAS)
  🇧🇪  Belgium     — VLIR-UOS, WBI
  🇦🇹  Austria     — OeAD
  🇫🇮  Finland     — CIMO/UniHelsinki
  🇯🇵  Japan       — MEXT, JICA, Rotary, ADB/Japan
  🇦🇺  Australia   — Australia Awards, Endeavour
  🇨🇦  Canada      — Vanier, Trudeau, IDRC, Mastercard Foundation
  🇨🇳  China       — CSC (Chinese Government), Confucius Institute
  🇰🇷  South Korea — GKS (KGSP), KOICA
  🇷🇺  Russia      — Rossotrudnichestvo
  🇮🇳  India       — ICCR
  🇹🇷  Turkey      — Türkiye Burslari
  🌍  Africa-wide  — AU, AfDB, MasterCard Foundation
  🌐  Global       — Aga Khan, Ford Foundation, Rotary, Open Society,
                     DAAD scholarshipdb, Scholarship-positions,
                     Opportunitiescircle, OFN, Scholars4Dev

  Aggregators (catch everything else):
      • scholarshipdb.net
      • scholars4dev.com
      • opportunitiesforafricans.com
      • opportunitiescircle.com
      • afterschoolafrica.com
      • scholarshippositions.com

pip install requests beautifulsoup4 feedparser python-dotenv lxml
"""

import re, time, random, logging, json
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

try:
    import feedparser          # for RSS feeds
except ImportError:
    feedparser = None

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# Canonical funding types
FULLY_FUNDED   = "fully_funded"
PARTIAL        = "partially_funded"
UNKNOWN        = "unknown"


# ════════════════════════════════════════════════════════════════════════════
# MASTER REGISTRY — maps source_key → (scraper_fn, country, region)
# ════════════════════════════════════════════════════════════════════════════
SCHOLARSHIP_SOURCES = {
    # ── UK ──────────────────────────────────────────────────────────────────
    "chevening":            ("UK",          "europe",     "fully_funded"),
    "commonwealth":         ("UK",          "europe",     "fully_funded"),
    "british_council":      ("UK",          "europe",     "mixed"),
    # ── USA ─────────────────────────────────────────────────────────────────
    "fulbright":            ("USA",         "americas",   "fully_funded"),
    "hubert_humphrey":      ("USA",         "americas",   "fully_funded"),
    "aminef":               ("USA",         "americas",   "fully_funded"),
    # ── Germany ─────────────────────────────────────────────────────────────
    "daad":                 ("Germany",     "europe",     "fully_funded"),
    "heinrich_boell":       ("Germany",     "europe",     "fully_funded"),
    "konrad_adenauer":      ("Germany",     "europe",     "fully_funded"),
    "friedrich_ebert":      ("Germany",     "europe",     "fully_funded"),
    # ── France ──────────────────────────────────────────────────────────────
    "campus_france":        ("France",      "europe",     "mixed"),
    "eiffel":               ("France",      "europe",     "fully_funded"),
    # ── Netherlands ─────────────────────────────────────────────────────────
    "nuffic_okp":           ("Netherlands", "europe",     "fully_funded"),
    "orange_knowledge":     ("Netherlands", "europe",     "fully_funded"),
    # ── Sweden ──────────────────────────────────────────────────────────────
    "swedish_institute":    ("Sweden",      "europe",     "fully_funded"),
    # ── Norway ──────────────────────────────────────────────────────────────
    "norway_gov":           ("Norway",      "europe",     "mixed"),
    # ── Switzerland ─────────────────────────────────────────────────────────
    "swiss_eskas":          ("Switzerland", "europe",     "fully_funded"),
    # ── Belgium ─────────────────────────────────────────────────────────────
    "vlir_uos":             ("Belgium",     "europe",     "fully_funded"),
    # ── Austria ─────────────────────────────────────────────────────────────
    "oead":                 ("Austria",     "europe",     "mixed"),
    # ── Japan ───────────────────────────────────────────────────────────────
    "mext":                 ("Japan",       "asia",       "fully_funded"),
    "jica":                 ("Japan",       "asia",       "fully_funded"),
    # ── Australia ───────────────────────────────────────────────────────────
    "australia_awards":     ("Australia",   "oceania",    "fully_funded"),
    # ── Canada ──────────────────────────────────────────────────────────────
    "vanier":               ("Canada",      "americas",   "fully_funded"),
    "idrc":                 ("Canada",      "americas",   "fully_funded"),
    "mastercard_scholars":  ("Canada",      "africa",     "fully_funded"),
    # ── China ───────────────────────────────────────────────────────────────
    "csc_china":            ("China",       "asia",       "fully_funded"),
    # ── South Korea ─────────────────────────────────────────────────────────
    "gks_korea":            ("South Korea", "asia",       "fully_funded"),
    # ── Turkey ──────────────────────────────────────────────────────────────
    "turkiye_burslari":     ("Turkey",      "europe",     "fully_funded"),
    # ── Africa / Global ─────────────────────────────────────────────────────
    "aga_khan":             ("Global",      "global",     "fully_funded"),
    "ford_foundation":      ("USA",         "global",     "fully_funded"),
    "open_society":         ("Global",      "global",     "mixed"),
    "rotary_peace":         ("Global",      "global",     "fully_funded"),
    "african_union":        ("Africa",      "africa",     "mixed"),
    # ── Aggregators ─────────────────────────────────────────────────────────
    "scholarshipdb":        ("Global",      "global",     "mixed"),
    "scholars4dev":         ("Global",      "global",     "mixed"),
    "opportunitiesforafricans": ("Africa",  "africa",     "mixed"),
    "opportunitiescircle":  ("Global",      "global",     "mixed"),
    "afterschoolafrica":    ("Africa",      "africa",     "mixed"),
    "scholarshippositions": ("Global",      "global",     "mixed"),
    "opportunitiesworld":   ("Global",      "global",     "mixed"),
}


# ════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ════════════════════════════════════════════════════════════════════════════
def scrape_scholarships(
    keywords: List[str],
    sources: Optional[List[str]] = None,
    region_filter: Optional[str] = None,         # "europe","asia","americas","africa","global"
    funding_filter: Optional[str] = None,        # "fully_funded","partially_funded"
) -> List[Dict]:
    """
    Main entry point. Returns a deduplicated list of scholarship dicts.
    If sources=None, ALL registered sources are scraped.
    """
    if sources is None:
        sources = list(SCHOLARSHIP_SOURCES.keys())

    # Apply region filter
    if region_filter:
        sources = [s for s in sources
                   if SCHOLARSHIP_SOURCES.get(s, ("", region_filter, ""))[1] == region_filter]

    scraper_map = _build_scraper_map()
    results = []

    for src in sources:
        fn = scraper_map.get(src)
        if not fn:
            log.warning(f"[scholarships] No scraper for '{src}'")
            continue
        meta = SCHOLARSHIP_SOURCES.get(src, ("Unknown", "global", "mixed"))
        log.info(f"[scholarships/{src}] Scraping ({meta[0]})...")
        try:
            items = fn(keywords)
            for item in items:
                item.setdefault("record_type",    "scholarship")
                item.setdefault("source",         src)
                item.setdefault("funder_country", meta[0])
                item.setdefault("region",         meta[1])
                item.setdefault("funding_type",   meta[2])
                item.setdefault("sector",         "scholarship")
                _infer_funding_type(item)   # refine from text
            results.extend(items)
            _polite_delay()
        except Exception as e:
            log.error(f"[scholarships/{src}] {e}")

    results = _deduplicate(results)

    # Apply funding filter after scraping
    if funding_filter:
        results = [r for r in results if r.get("funding_type") == funding_filter]

    log.info(f"[scholarships] Total unique: {len(results)}")
    return results


def _build_scraper_map() -> Dict:
    """Maps source key → scraper function."""
    return {
        # UK
        "chevening":            scrape_chevening,
        "commonwealth":         scrape_commonwealth,
        "british_council":      scrape_british_council,
        # USA
        "fulbright":            scrape_fulbright,
        "hubert_humphrey":      scrape_hubert_humphrey,
        "aminef":               scrape_aminef,
        # Germany
        "daad":                 scrape_daad,
        "heinrich_boell":       scrape_heinrich_boell,
        "konrad_adenauer":      scrape_konrad_adenauer,
        "friedrich_ebert":      scrape_friedrich_ebert,
        # France
        "campus_france":        scrape_campus_france,
        "eiffel":               scrape_eiffel,
        # Netherlands
        "nuffic_okp":           scrape_nuffic_okp,
        "orange_knowledge":     scrape_orange_knowledge,
        # Sweden
        "swedish_institute":    scrape_swedish_institute,
        # Norway
        "norway_gov":           scrape_norway_gov,
        # Switzerland
        "swiss_eskas":          scrape_swiss_eskas,
        # Belgium
        "vlir_uos":             scrape_vlir_uos,
        # Austria
        "oead":                 scrape_oead,
        # Japan
        "mext":                 scrape_mext,
        "jica":                 scrape_jica,
        # Australia
        "australia_awards":     scrape_australia_awards,
        # Canada
        "vanier":               scrape_vanier,
        "idrc":                 scrape_idrc,
        "mastercard_scholars":  scrape_mastercard_scholars,
        # China
        "csc_china":            scrape_csc_china,
        # South Korea
        "gks_korea":            scrape_gks_korea,
        # Turkey
        "turkiye_burslari":     scrape_turkiye_burslari,
        # Africa / Global
        "aga_khan":             scrape_aga_khan,
        "ford_foundation":      scrape_ford_foundation,
        "open_society":         scrape_open_society,
        "rotary_peace":         scrape_rotary_peace,
        "african_union":        scrape_african_union,
        # Aggregators
        "scholarshipdb":        scrape_scholarshipdb,
        "scholars4dev":         scrape_scholars4dev,
        "opportunitiesforafricans": scrape_opportunities_for_africans,
        "opportunitiescircle":  scrape_opportunities_circle,
        "afterschoolafrica":    scrape_afterschoolafrica,
        "scholarshippositions": scrape_scholarship_positions,
        "opportunitiesworld":   scrape_opportunities_world,
    }


# ════════════════════════════════════════════════════════════════════════════
# SCHOLARSHIP DICT TEMPLATE
# ════════════════════════════════════════════════════════════════════════════
def _s(title="", url="", funder="", funder_country="", level="",
       field="", deadline="", snippet="", funding_type=UNKNOWN,
       coverage="", eligible_countries="", source="") -> Dict:
    """Build a canonical scholarship dict."""
    return {
        "record_type":        "scholarship",
        "title":              title,
        "url":                url,
        "company":            funder,           # reuse 'company' for funder name (DB compat)
        "funder":             funder,
        "funder_country":     funder_country,
        "level":              level,            # masters / phd / undergraduate / short_course
        "field":              field,
        "deadline":           deadline,
        "snippet":            snippet[:500],
        "funding_type":       funding_type,
        "coverage":           coverage,         # what is covered: tuition, living, flights
        "eligible_countries": eligible_countries,
        "location":           funder_country,
        "source":             source,
        "sector":             "scholarship",
    }


# ════════════════════════════════════════════════════════════════════════════
# ─── UK ──────────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_chevening(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://www.chevening.org/scholarships/")
    if not soup:
        return items
    for card in soup.select("article, .scholarship-card, div.card"):
        t = card.select_one("h2 a, h3 a, a.title")
        if not t:
            continue
        items.append(_s(
            title    = t.get_text(strip=True),
            url      = _abs("https://www.chevening.org", t.get("href","")),
            funder   = "Chevening / FCDO",
            funder_country = "UK",
            level    = "masters",
            funding_type   = FULLY_FUNDED,
            coverage = "Full tuition, living allowance, flights, visa",
            snippet  = _text(card, "p, .description")[:400],
            deadline = _text(card, "time, .deadline"),
            eligible_countries = "Most countries incl. Kenya",
            source   = "chevening",
        ))
    # Fallback: if no cards, add the known main programme
    if not items:
        items.append(_s(
            title    = "Chevening Scholarships",
            url      = "https://www.chevening.org/scholarships/",
            funder   = "Chevening / FCDO",
            funder_country = "UK",
            level    = "masters",
            funding_type   = FULLY_FUNDED,
            coverage = "Full tuition, living allowance, return flights, visa",
            snippet  = "UK government scholarship for future global leaders. 1-year Masters at UK university.",
            deadline = "November (annual)",
            eligible_countries = "100+ countries including Kenya",
            source   = "chevening",
        ))
    return items


def scrape_commonwealth(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://cscuk.fcdo.gov.uk/apply/scholarships-for-developing-countries/")
    if not soup:
        return [_s(
            title   = "Commonwealth Scholarships",
            url     = "https://cscuk.fcdo.gov.uk/apply/scholarships-for-developing-countries/",
            funder  = "Commonwealth Scholarship Commission",
            funder_country = "UK",
            level   = "masters,phd",
            funding_type   = FULLY_FUNDED,
            coverage = "Tuition, living allowance, return airfare, thesis grant",
            snippet  = "Commonwealth Scholarships for citizens of developing Commonwealth countries.",
            deadline = "October–December (annual)",
            eligible_countries = "Kenya and all developing Commonwealth countries",
            source  = "commonwealth",
        )]
    for card in soup.select("article, div.scholarship, div.card, li.scholarship"):
        t = card.select_one("h2 a, h3 a, a")
        if not t:
            continue
        items.append(_s(
            title  = t.get_text(strip=True),
            url    = _abs("https://cscuk.fcdo.gov.uk", t.get("href","")),
            funder = "Commonwealth Scholarship Commission",
            funder_country = "UK",
            funding_type   = FULLY_FUNDED,
            snippet = _text(card, "p"),
            deadline = _text(card, "time, .deadline"),
            source = "commonwealth",
        ))
    return items or [_s(
        title="Commonwealth Scholarships",
        url="https://cscuk.fcdo.gov.uk/apply/scholarships-for-developing-countries/",
        funder="Commonwealth Scholarship Commission",
        funder_country="UK", level="masters,phd",
        funding_type=FULLY_FUNDED, source="commonwealth",
        coverage="Full award", eligible_countries="Kenya + Commonwealth",
    )]


def scrape_british_council(keywords: List[str]) -> List[Dict]:
    items = []
    kw = keywords[0] if keywords else "scholarship"
    soup = _get_soup(f"https://www.britishcouncil.org/study-work-abroad/in-uk/scholarship-finder?q={quote_plus(kw)}")
    if soup:
        for card in soup.select("div.scholarship-card, article, li.result"):
            t = card.select_one("h2 a, h3 a, a.title")
            if not t:
                continue
            items.append(_s(
                title  = t.get_text(strip=True),
                url    = _abs("https://www.britishcouncil.org", t.get("href","")),
                funder = "British Council",
                funder_country = "UK",
                snippet = _text(card, "p"),
                source  = "british_council",
            ))
    return items


# ════════════════════════════════════════════════════════════════════════════
# ─── USA ─────────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_fulbright(keywords: List[str]) -> List[Dict]:
    items = []
    # Fulbright Foreign Student Program
    pages = [
        "https://foreign.fulbrightonline.org/about/foreign-fulbright",
        "https://www.iie.org/programs/fulbright",
    ]
    for url in pages:
        soup = _get_soup(url)
        if soup:
            for card in soup.select("div.card, article, div.program"):
                t = card.select_one("h2 a, h3 a, a.title, h2, h3")
                if not t:
                    continue
                items.append(_s(
                    title    = t.get_text(strip=True),
                    url      = _abs(url, t.get("href", url)),
                    funder   = "Fulbright Program / US Department of State",
                    funder_country = "USA",
                    level    = "masters,phd",
                    funding_type   = FULLY_FUNDED,
                    coverage = "Tuition, living stipend, health insurance, round-trip travel",
                    snippet  = _text(card, "p")[:400],
                    deadline = _text(card, "time, .deadline"),
                    eligible_countries = "Kenya and most countries",
                    source   = "fulbright",
                ))
            if items:
                break
    if not items:
        items.append(_s(
            title    = "Fulbright Foreign Student Program",
            url      = "https://foreign.fulbrightonline.org/",
            funder   = "Fulbright / US Dept of State",
            funder_country = "USA",
            level    = "masters,phd",
            funding_type   = FULLY_FUNDED,
            coverage = "Full tuition, living stipend, health insurance, travel",
            snippet  = "US Government's premier international scholarship. Study at US universities.",
            deadline = "Varies by country — Kenya: ~Oct",
            eligible_countries = "Kenya",
            source   = "fulbright",
        ))
    return items


def scrape_hubert_humphrey(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "Hubert H. Humphrey Fellowship Program",
        url      = "https://www.humphreyfellowship.org/",
        funder   = "US Department of State / IIE",
        funder_country = "USA",
        level    = "professional_development",
        funding_type   = FULLY_FUNDED,
        coverage = "Program costs, living allowance, travel, professional development",
        snippet  = (
            "10-month non-degree fellowship for experienced professionals from designated countries. "
            "Focus on public service, development and leadership."
        ),
        deadline = "Varies by country (~July)",
        eligible_countries = "Kenya",
        source   = "hubert_humphrey",
    )]


def scrape_aminef(keywords: List[str]) -> List[Dict]:
    """American Indonesian Exchange Foundation — also covers broader Fulbright regional."""
    items = []
    soup = _get_soup("https://www.aminef.or.id/grants-for-indonesians/fulbright-programs/")
    # Minimal fallback — this is more useful as a known source stub
    return [_s(
        title    = "Fulbright — AMINEF Regional Programs",
        url      = "https://www.aminef.or.id/",
        funder   = "AMINEF / US Dept of State",
        funder_country = "USA",
        funding_type   = FULLY_FUNDED,
        source   = "aminef",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── GERMANY ─────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_daad(keywords: List[str]) -> List[Dict]:
    items = []
    kw = keywords[0] if keywords else ""
    # DAAD scholarship database API-like endpoint
    url = f"https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?status=&origin=&subjectGrps=&daad=&q={quote_plus(kw)}&page=1&back=1"
    soup = _get_soup(url)
    if soup:
        for card in soup.select("li.c-funding-teaser, div.scholarship-item, article"):
            t = card.select_one("h2 a, h3 a, a.title, h2, h3")
            if not t:
                continue
            items.append(_s(
                title    = t.get_text(strip=True),
                url      = _abs("https://www2.daad.de", t.get("href", "")),
                funder   = "DAAD",
                funder_country = "Germany",
                funding_type   = FULLY_FUNDED,
                coverage = "Tuition (in many cases), monthly stipend, travel subsidy, health insurance",
                snippet  = _text(card, "p, .description")[:400],
                deadline = _text(card, "time, .deadline"),
                eligible_countries = "Kenya + sub-Saharan Africa",
                source   = "daad",
            ))
    if not items:
        # Known flagship programmes
        for prog in [
            ("DAAD Development-Related Postgraduate Courses (EPOS)",
             "https://www.daad.de/en/study-and-research-in-germany/scholarships/development-related-postgraduate-courses/",
             "masters", "All developing countries incl. Kenya"),
            ("DAAD Scholarships for Development — Research Grants",
             "https://www.daad.de/en/study-and-research-in-germany/scholarships/",
             "phd,masters", "Africa"),
            ("DAAD Helmut Schmidt Programme",
             "https://www.daad.de/en/study-and-research-in-germany/scholarships/helmut-schmidt-programme/",
             "masters", "Developing countries"),
        ]:
            items.append(_s(
                title=prog[0], url=prog[1], funder="DAAD",
                funder_country="Germany", level=prog[2],
                funding_type=FULLY_FUNDED,
                coverage="Monthly stipend, travel, tuition, health insurance",
                eligible_countries=prog[3], source="daad",
            ))
    return items


def scrape_heinrich_boell(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://www.boell.de/en/scholarships")
    if soup:
        for card in soup.select("article, div.scholarship, div.teaser"):
            t = card.select_one("h2 a, h3 a, a")
            if t and len(t.get_text(strip=True)) > 10:
                items.append(_s(
                    title    = t.get_text(strip=True),
                    url      = _abs("https://www.boell.de", t.get("href","")),
                    funder   = "Heinrich Böll Foundation",
                    funder_country = "Germany",
                    funding_type   = FULLY_FUNDED,
                    source   = "heinrich_boell",
                    snippet  = _text(card, "p"),
                ))
    return items or [_s(
        title="Heinrich Böll Foundation Scholarships",
        url="https://www.boell.de/en/scholarships",
        funder="Heinrich Böll Foundation", funder_country="Germany",
        funding_type=FULLY_FUNDED, level="masters,phd",
        snippet="Scholarships for socially engaged students with emphasis on ecology, democracy and human rights.",
        source="heinrich_boell",
    )]


def scrape_konrad_adenauer(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "Konrad-Adenauer-Stiftung (KAS) Scholarships",
        url      = "https://www.kas.de/en/web/begabtenfoerderung-und-kultur/scholarships",
        funder   = "Konrad-Adenauer-Stiftung",
        funder_country = "Germany",
        level    = "masters,phd",
        funding_type   = FULLY_FUNDED,
        coverage = "Monthly stipend, study grant, social contribution",
        snippet  = "KAS scholarships for international students with excellent academic records and social engagement.",
        source   = "konrad_adenauer",
    )]


def scrape_friedrich_ebert(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "Friedrich Ebert Foundation Scholarships",
        url      = "https://www.fes.de/en/scholarships",
        funder   = "Friedrich-Ebert-Stiftung",
        funder_country = "Germany",
        level    = "masters,phd",
        funding_type   = FULLY_FUNDED,
        snippet  = "Scholarships for students demonstrating academic excellence and social/political commitment.",
        source   = "friedrich_ebert",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── FRANCE ──────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_campus_france(keywords: List[str]) -> List[Dict]:
    items = []
    kw = keywords[0] if keywords else "scholarship"
    url = f"https://www.campusfrance.org/en/the-french-government-scholarships-mge"
    soup = _get_soup(url)
    items.append(_s(
        title    = "French Government Scholarships (MGE) — Campus France",
        url      = url,
        funder   = "French Ministry for Europe and Foreign Affairs",
        funder_country = "France",
        level    = "masters,phd,short_course",
        funding_type   = FULLY_FUNDED,
        coverage = "Tuition waiver, monthly stipend, health coverage, visa fees",
        snippet  = "French government scholarships awarded through Campus France for international students.",
        deadline = "Varies by programme",
        eligible_countries = "Kenya and most African countries",
        source   = "campus_france",
    ))
    return items


def scrape_eiffel(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "Eiffel Excellence Scholarship Programme",
        url      = "https://www.campusfrance.org/en/eiffel-scholarship-program-of-excellence",
        funder   = "Campus France / French Ministry",
        funder_country = "France",
        level    = "masters,phd",
        funding_type   = FULLY_FUNDED,
        coverage = "Monthly allowance, travel, cultural activities, health insurance",
        snippet  = "Eiffel Excellence: attracts top foreign students to French grandes écoles and universities.",
        deadline = "January (annual)",
        eligible_countries = "Priority: emerging economies incl. Kenya",
        source   = "eiffel",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── NETHERLANDS ─────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_nuffic_okp(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://www.nuffic.nl/en/subjects/scholarships-and-grants")
    if soup:
        for card in soup.select("article, div.card, li.scholarship"):
            t = card.select_one("h2 a, h3 a, a")
            if t and len(t.get_text(strip=True)) > 8:
                items.append(_s(
                    title    = t.get_text(strip=True),
                    url      = _abs("https://www.nuffic.nl", t.get("href","")),
                    funder   = "Nuffic / Netherlands Government",
                    funder_country = "Netherlands",
                    funding_type   = FULLY_FUNDED,
                    snippet  = _text(card, "p"),
                    source   = "nuffic_okp",
                ))
    return items or [_s(
        title="Orange Knowledge Programme (OKP)",
        url="https://www.nuffic.nl/en/subjects/orange-knowledge-programme",
        funder="Nuffic / Netherlands Ministry of Foreign Affairs",
        funder_country="Netherlands", level="masters,short_course",
        funding_type=FULLY_FUNDED,
        coverage="Tuition, living allowance, travel, visa",
        snippet="OKP supports professionals from developing countries for short courses and Masters.",
        eligible_countries="Kenya (priority country)",
        source="nuffic_okp",
    )]


def scrape_orange_knowledge(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "Orange Knowledge Programme — Short Courses & Masters",
        url      = "https://www.nuffic.nl/en/subjects/orange-knowledge-programme",
        funder   = "Nuffic",
        funder_country = "Netherlands",
        level    = "masters,short_course",
        funding_type   = FULLY_FUNDED,
        coverage = "Full tuition, accommodation, travel, insurance",
        snippet  = "OKP for professionals from Kenya and other ODA countries. Strong focus on capacity development.",
        eligible_countries = "Kenya (priority)",
        source   = "orange_knowledge",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── SWEDEN ──────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_swedish_institute(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://si.se/en/apply/scholarships/")
    if soup:
        for card in soup.select("article, div.card, div.scholarship"):
            t = card.select_one("h2 a, h3 a, a.title, h2, h3")
            if t and len(t.get_text(strip=True)) > 8:
                items.append(_s(
                    title    = t.get_text(strip=True),
                    url      = _abs("https://si.se", t.get("href","")),
                    funder   = "Swedish Institute",
                    funder_country = "Sweden",
                    funding_type   = FULLY_FUNDED,
                    coverage = "Living costs, travel, tuition covered by Swedish free university system",
                    snippet  = _text(card, "p"),
                    source   = "swedish_institute",
                ))
    return items or [_s(
        title="Swedish Institute Scholarships for Global Professionals (SISGP)",
        url="https://si.se/en/apply/scholarships/swedish-institute-scholarships-for-global-professionals/",
        funder="Swedish Institute",
        funder_country="Sweden", level="masters",
        funding_type=FULLY_FUNDED,
        coverage="Living expenses, travel grants, tuition (free at Swedish universities)",
        snippet="SISGP for professionals from select countries. Kenya is an eligible country.",
        eligible_countries="Kenya + selected countries",
        source="swedish_institute",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── NORWAY ──────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_norway_gov(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "Norwegian Government Quota Scheme / Norpart",
        url      = "https://diku.no/en/programmes/norpart/",
        funder   = "Norwegian Agency for International Cooperation (Diku)",
        funder_country = "Norway",
        level    = "masters,phd",
        funding_type   = FULLY_FUNDED,
        coverage = "Full scholarship including living costs",
        snippet  = "Norpart promotes international cooperation in higher education between Norway and selected partner countries.",
        eligible_countries = "Eastern Africa including Kenya",
        source   = "norway_gov",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── SWITZERLAND ─────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_swiss_eskas(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://www.sbfi.admin.ch/sbfi/en/home/education/scholarships-and-grants/swiss-government-excellence-scholarships.html")
    if not soup:
        soup = _get_soup("https://eskas.ch/en/")
    return [_s(
        title    = "Swiss Government Excellence Scholarships (ESKAS)",
        url      = "https://www.sbfi.admin.ch/sbfi/en/home/education/scholarships-and-grants/swiss-government-excellence-scholarships.html",
        funder   = "ESKAS — Swiss Federal Commission for Scholarships",
        funder_country = "Switzerland",
        level    = "masters,phd,postdoc,research",
        funding_type   = FULLY_FUNDED,
        coverage = "Monthly stipend, tuition waiver, health insurance, airfare",
        snippet  = "Swiss Government Excellence Scholarships for foreign scholars and artists to pursue research or studies at Swiss universities.",
        deadline = "Varies by country (apply via Swiss Embassy)",
        eligible_countries = "Kenya — apply via Swiss Embassy in Nairobi",
        source   = "swiss_eskas",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── BELGIUM ─────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_vlir_uos(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://www.vliruos.be/en/scholarships/6")
    if soup:
        for card in soup.select("article, div.scholarship, li.programme"):
            t = card.select_one("h2 a, h3 a, a")
            if t and len(t.get_text(strip=True)) > 8:
                items.append(_s(
                    title    = t.get_text(strip=True),
                    url      = _abs("https://www.vliruos.be", t.get("href","")),
                    funder   = "VLIR-UOS",
                    funder_country = "Belgium",
                    funding_type   = FULLY_FUNDED,
                    snippet  = _text(card, "p"),
                    deadline = _text(card, "time, .deadline"),
                    eligible_countries = "Kenya + sub-Saharan Africa",
                    source   = "vlir_uos",
                ))
    return items or [_s(
        title="VLIR-UOS Scholarships for Developing Countries",
        url="https://www.vliruos.be/en/scholarships/6",
        funder="VLIR-UOS", funder_country="Belgium",
        level="masters,phd,short_course",
        funding_type=FULLY_FUNDED,
        coverage="Full scholarship: tuition, accommodation, travel, living allowance",
        snippet="Belgium scholarships for students from developing countries at Flemish universities.",
        eligible_countries="Kenya (priority country)",
        source="vlir_uos",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── AUSTRIA ─────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_oead(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "OeAD Scholarships — Austrian Agency for Education and Internationalisation",
        url      = "https://oead.at/en/to-austria/grants-scholarships/",
        funder   = "OeAD",
        funder_country = "Austria",
        level    = "masters,phd,research",
        funding_type   = FULLY_FUNDED,
        coverage = "Monthly grant, travel subsidy, one-time settling-in allowance",
        snippet  = "OeAD manages various Austrian government and EU scholarships for international researchers and students.",
        eligible_countries = "Africa including Kenya",
        source   = "oead",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── JAPAN ───────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_mext(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://www.mext.go.jp/en/policy/education/highered/title02/detail02/sdetail02/1373895.htm")
    programmes = [
        ("MEXT Research Scholarship (University Recommendation)",
         "https://www.mext.go.jp/en/policy/education/highered/title02/detail02/sdetail02/1373895.htm",
         "phd,masters,research"),
        ("MEXT Undergraduate Scholarship",
         "https://www.mext.go.jp/en/policy/education/highered/title02/detail02/sdetail02/1374003.htm",
         "undergraduate"),
        ("MEXT Teacher Training Scholarship",
         "https://www.mext.go.jp/en/policy/education/highered/title02/detail02/sdetail02/1374001.htm",
         "professional_development"),
    ]
    for name, url, level in programmes:
        items.append(_s(
            title    = name,
            url      = url,
            funder   = "MEXT (Japanese Ministry of Education)",
            funder_country = "Japan",
            level    = level,
            funding_type   = FULLY_FUNDED,
            coverage = "Tuition, monthly stipend ¥117,000–¥145,000, return airfare, accommodation",
            snippet  = f"Japanese Government (MEXT) scholarship. {name}. Apply via Japanese Embassy Nairobi.",
            deadline = "April–June (Embassy recommendation)",
            eligible_countries = "Kenya — apply via Japanese Embassy in Nairobi",
            source   = "mext",
        ))
    return items


def scrape_jica(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "JICA Long-term Training Programme",
        url      = "https://www.jica.go.jp/english/our_work/types_of_assistance/tech/training/long.html",
        funder   = "JICA (Japan International Cooperation Agency)",
        funder_country = "Japan",
        level    = "masters,professional_development",
        funding_type   = FULLY_FUNDED,
        coverage = "Travel, accommodation, living allowance, tuition, health insurance",
        snippet  = "JICA training and scholarship programmes for professionals from developing countries including Kenya.",
        eligible_countries = "Kenya",
        source   = "jica",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── AUSTRALIA ───────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_australia_awards(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://www.australiaawards.gov.au/scholarships")
    if soup:
        for card in soup.select("article, div.card, div.scholarship"):
            t = card.select_one("h2 a, h3 a, a")
            if t and len(t.get_text(strip=True)) > 8:
                items.append(_s(
                    title    = t.get_text(strip=True),
                    url      = _abs("https://www.australiaawards.gov.au", t.get("href","")),
                    funder   = "Australian Government — DFAT",
                    funder_country = "Australia",
                    funding_type   = FULLY_FUNDED,
                    snippet  = _text(card, "p"),
                    source   = "australia_awards",
                ))
    return items or [_s(
        title    = "Australia Awards Scholarships",
        url      = "https://www.australiaawards.gov.au/",
        funder   = "Australian Government (DFAT)",
        funder_country = "Australia",
        level    = "masters,phd",
        funding_type   = FULLY_FUNDED,
        coverage = "Full tuition, return airfare, establishment allowance, living stipend, health cover",
        snippet  = "Australia Awards: long-term development scholarships for emerging leaders from the Indo-Pacific and Africa.",
        deadline = "August (annual, varies by country)",
        eligible_countries = "Kenya — administered by Australian High Commission Nairobi",
        source   = "australia_awards",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── CANADA ──────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_vanier(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "Vanier Canada Graduate Scholarships",
        url      = "https://vanier.gc.ca/en/home-accueil.html",
        funder   = "Government of Canada",
        funder_country = "Canada",
        level    = "phd",
        funding_type   = FULLY_FUNDED,
        coverage = "CAD $50,000/year for 3 years",
        snippet  = "Vanier CGS for doctoral students who demonstrate leadership skills and high academic achievement.",
        eligible_countries = "All nationalities (apply through Canadian universities)",
        source   = "vanier",
    )]


def scrape_idrc(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://idrc.ca/en/funding")
    if soup:
        for card in soup.select("article, div.card, li"):
            t = card.select_one("h2 a, h3 a, a")
            if t and "award" in t.get_text().lower() or "scholar" in t.get_text().lower():
                items.append(_s(
                    title  = t.get_text(strip=True),
                    url    = _abs("https://idrc.ca", t.get("href","")),
                    funder = "IDRC Canada",
                    funder_country = "Canada",
                    funding_type   = FULLY_FUNDED,
                    snippet = _text(card, "p"),
                    source  = "idrc",
                ))
    return items or [_s(
        title="IDRC Research Awards",
        url="https://idrc.ca/en/funding/idrc-research-awards",
        funder="International Development Research Centre (IDRC)",
        funder_country="Canada", level="masters,phd",
        funding_type=FULLY_FUNDED,
        snippet="IDRC Research Awards for students pursuing development research affecting the Global South.",
        eligible_countries="Kenya and Global South countries",
        source="idrc",
    )]


def scrape_mastercard_scholars(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://mastercardfdn.org/all/scholars/becoming-a-scholar/scholarship-institutions/")
    if soup:
        for card in soup.select("article, div.partner, div.card"):
            t = card.select_one("h2 a, h3 a, a")
            if t and len(t.get_text(strip=True)) > 8:
                items.append(_s(
                    title    = "Mastercard Foundation Scholars — " + t.get_text(strip=True),
                    url      = _abs("https://mastercardfdn.org", t.get("href","")),
                    funder   = "Mastercard Foundation",
                    funder_country = "Canada/Global",
                    funding_type   = FULLY_FUNDED,
                    snippet  = _text(card, "p"),
                    source   = "mastercard_scholars",
                ))
    return items or [_s(
        title    = "Mastercard Foundation Scholars Program",
        url      = "https://mastercardfdn.org/all/scholars/",
        funder   = "Mastercard Foundation",
        funder_country = "Canada/Global",
        level    = "undergraduate,masters",
        funding_type   = FULLY_FUNDED,
        coverage = "Full tuition, room and board, travel, and leadership development",
        snippet  = "Scholarships for academically talented young Africans who are economically disadvantaged.",
        eligible_countries = "Kenya and all African countries",
        source   = "mastercard_scholars",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── CHINA ───────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_csc_china(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://www.csc.edu.cn/studyinchina/scholarshipdetailen.aspx")
    programmes = [
        ("Chinese Government Scholarship — Type A (Full)",
         "https://www.csc.edu.cn/studyinchina/scholarshipdetailen.aspx",
         "undergraduate,masters,phd", FULLY_FUNDED,
         "Tuition, accommodation, living allowance, health insurance, return airfare"),
        ("Chinese Government Scholarship — Belt & Road",
         "https://www.csc.edu.cn/studyinchina/",
         "masters,phd", FULLY_FUNDED,
         "Full scholarship for Belt & Road countries"),
        ("Confucius Institute Scholarship",
         "https://www.chinesescholarshipcouncil.com/confucius-institute-scholarship.html",
         "language,masters", FULLY_FUNDED,
         "Tuition, accommodation, living allowance"),
    ]
    for name, url, level, ft, cov in programmes:
        items.append(_s(
            title    = name,
            url      = url,
            funder   = "Chinese Scholarship Council (CSC)",
            funder_country = "China",
            level    = level,
            funding_type   = ft,
            coverage = cov,
            snippet  = f"{name} for international students to study at Chinese universities.",
            deadline = "February–April (annual)",
            eligible_countries = "Kenya",
            source   = "csc_china",
        ))
    return items


# ════════════════════════════════════════════════════════════════════════════
# ─── SOUTH KOREA ─────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_gks_korea(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "Global Korea Scholarship (GKS / KGSP)",
        url      = "https://www.studyinkorea.go.kr/en/sub/gks/allnew_invitation.do",
        funder   = "National Institute for International Education (NIIED)",
        funder_country = "South Korea",
        level    = "undergraduate,masters,phd",
        funding_type   = FULLY_FUNDED,
        coverage = "Tuition, airfare, living allowance, language training, medical insurance",
        snippet  = "GKS scholarship for international students to study at Korean universities. Apply via Korean Embassy.",
        deadline = "February–March (Embassy route)",
        eligible_countries = "Kenya — apply via Korean Embassy in Nairobi",
        source   = "gks_korea",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── TURKEY ──────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_turkiye_burslari(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://turkiyeburslari.gov.tr/en")
    if soup:
        for card in soup.select("div.scholarship, article, div.program-card"):
            t = card.select_one("h2 a, h3 a, a")
            if t and len(t.get_text(strip=True)) > 8:
                items.append(_s(
                    title    = t.get_text(strip=True),
                    url      = _abs("https://turkiyeburslari.gov.tr", t.get("href","")),
                    funder   = "Türkiye Bursları (Turkish Government)",
                    funder_country = "Turkey",
                    funding_type   = FULLY_FUNDED,
                    snippet  = _text(card, "p"),
                    source   = "turkiye_burslari",
                ))
    return items or [_s(
        title    = "Türkiye Scholarships — Turkish Government Scholarship",
        url      = "https://turkiyeburslari.gov.tr/en",
        funder   = "Republic of Turkey — Presidency for Turks Abroad",
        funder_country = "Turkey",
        level    = "undergraduate,masters,phd,research",
        funding_type   = FULLY_FUNDED,
        coverage = "Monthly stipend, accommodation, one-time travel, health insurance",
        snippet  = "Full scholarship for all levels of study at Turkish universities. Includes Turkish language course.",
        deadline = "February–March (annual)",
        eligible_countries = "Kenya and all African countries",
        source   = "turkiye_burslari",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── AFRICA / GLOBAL ─────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_aga_khan(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://www.akdn.org/our-work/agency/aga-khan-foundation/education/international-scholarship-programme")
    return [_s(
        title    = "Aga Khan Foundation International Scholarship Programme",
        url      = "https://www.akdn.org/our-work/agency/aga-khan-foundation/education/international-scholarship-programme",
        funder   = "Aga Khan Foundation",
        funder_country = "Global",
        level    = "masters",
        funding_type   = FULLY_FUNDED,
        coverage = "50% grant + 50% loan (loan forgiven under conditions); tuition, living costs",
        snippet  = "AKF scholarships for postgraduate studies for students from developing countries who have no other means of funding.",
        deadline = "March–May (annual, varies by country)",
        eligible_countries = "Kenya",
        source   = "aga_khan",
    )]


def scrape_ford_foundation(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "Ford Foundation International Fellowships Program (IFP)",
        url      = "https://www.fordfoundation.org/work/our-grants/scholarships-and-fellowships/",
        funder   = "Ford Foundation",
        funder_country = "USA",
        level    = "masters,phd",
        funding_type   = FULLY_FUNDED,
        coverage = "Full tuition, living allowance, travel, research funds",
        snippet  = "Ford Foundation supports social justice leaders. IFP targets individuals from excluded groups.",
        eligible_countries = "Kenya and select African countries",
        source   = "ford_foundation",
    )]


def scrape_open_society(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://www.opensocietyfoundations.org/grants/open-society-fellowship")
    return [_s(
        title    = "Open Society Foundations — Scholarships & Fellowships",
        url      = "https://www.opensocietyfoundations.org/grants",
        funder   = "Open Society Foundations",
        funder_country = "Global",
        level    = "phd,fellowship,research",
        funding_type   = FULLY_FUNDED,
        snippet  = "OSF supports scholars and practitioners advancing human rights and open societies.",
        eligible_countries = "Kenya and Global",
        source   = "open_society",
    )]


def scrape_rotary_peace(keywords: List[str]) -> List[Dict]:
    return [_s(
        title    = "Rotary Peace Fellowships",
        url      = "https://www.rotary.org/en/our-programs/peace-fellowships",
        funder   = "Rotary Foundation",
        funder_country = "Global",
        level    = "masters,professional_development",
        funding_type   = FULLY_FUNDED,
        coverage = "Full tuition, room/board, round-trip travel, internship expenses",
        snippet  = "Rotary Peace Fellowships for peace and conflict resolution professionals. 1-2 year Masters or 3-month certificate.",
        deadline = "May 31 (annual)",
        eligible_countries = "All countries incl. Kenya",
        source   = "rotary_peace",
    )]


def scrape_african_union(keywords: List[str]) -> List[Dict]:
    items = []
    soup = _get_soup("https://au.int/en/scholarships")
    if soup:
        for card in soup.select("article, div.scholarship, div.card"):
            t = card.select_one("h2 a, h3 a, a")
            if t and len(t.get_text(strip=True)) > 8:
                items.append(_s(
                    title    = t.get_text(strip=True),
                    url      = _abs("https://au.int", t.get("href","")),
                    funder   = "African Union",
                    funder_country = "Africa",
                    funding_type   = UNKNOWN,
                    snippet  = _text(card, "p"),
                    source   = "african_union",
                ))
    return items or [_s(
        title    = "African Union Scholarships",
        url      = "https://au.int/en/scholarships",
        funder   = "African Union Commission",
        funder_country = "Africa",
        level    = "masters,phd",
        snippet  = "AU scholarship programmes for intra-African mobility and development.",
        eligible_countries = "All AU member states including Kenya",
        source   = "african_union",
    )]


# ════════════════════════════════════════════════════════════════════════════
# ─── AGGREGATORS (catch-all scrapers) ────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def scrape_scholarshipdb(keywords: List[str]) -> List[Dict]:
    """scholarshipdb.net — large aggregator with search."""
    items = []
    for kw in keywords[:2]:   # limit to 2 keywords to avoid rate limits
        url  = f"https://scholarshipdb.net/scholarships?q={quote_plus(kw)}&country=Kenya"
        soup = _get_soup(url)
        if not soup:
            continue
        for card in soup.select("div.list-group-item, article, div.scholarship"):
            t = card.select_one("h2 a, h3 a, h4 a, a.title, a")
            if not t or len(t.get_text(strip=True)) < 8:
                continue
            href = t.get("href","")
            items.append(_s(
                title    = t.get_text(strip=True),
                url      = _abs("https://scholarshipdb.net", href),
                funder   = _text(card, ".university, .host, .provider"),
                funder_country = _text(card, ".country"),
                deadline = _text(card, ".deadline, time"),
                snippet  = _text(card, "p, .description")[:400],
                source   = "scholarshipdb",
            ))
        _polite_delay()
    return items


def scrape_scholars4dev(keywords: List[str]) -> List[Dict]:
    """scholars4dev.com — well-curated Africa-focused aggregator."""
    items = []
    for kw in keywords[:2]:
        url  = f"https://www.scholars4dev.com/?s={quote_plus(kw)}"
        soup = _get_soup(url)
        if not soup:
            continue
        for card in soup.select("article, div.post"):
            t = card.select_one("h2 a, h3 a, .entry-title a")
            if not t:
                continue
            text = card.get_text().lower()
            funding = FULLY_FUNDED if "fully funded" in text else (PARTIAL if "partial" in text else UNKNOWN)
            items.append(_s(
                title    = t.get_text(strip=True),
                url      = t.get("href",""),
                funder   = _text(card, ".cat-links a, .category"),
                deadline = _text(card, "time, .date"),
                snippet  = _text(card, ".entry-summary, p")[:400],
                funding_type = funding,
                source   = "scholars4dev",
            ))
        _polite_delay()
    return items


def scrape_opportunities_for_africans(keywords: List[str]) -> List[Dict]:
    """opportunitiesforafricans.com — African-focused scholarship listings."""
    items = []
    for kw in keywords[:2]:
        url  = f"https://opportunitiesforafricans.com/?s={quote_plus(kw)}"
        soup = _get_soup(url)
        if not soup:
            # Try RSS feed
            if feedparser:
                feed = feedparser.parse("https://opportunitiesforafricans.com/feed/")
                for entry in feed.entries[:15]:
                    title = entry.get("title","")
                    if kw.lower() in title.lower() or "scholarship" in title.lower():
                        items.append(_s(
                            title    = title,
                            url      = entry.get("link",""),
                            snippet  = re.sub(r'<[^>]+>', '', entry.get("summary",""))[:400],
                            funder_country = "Global",
                            source   = "opportunitiesforafricans",
                        ))
            continue
        for card in soup.select("article, div.post"):
            t = card.select_one("h2 a, h3 a, .entry-title a")
            if not t:
                continue
            items.append(_s(
                title    = t.get_text(strip=True),
                url      = t.get("href",""),
                snippet  = _text(card, ".entry-summary, p")[:400],
                deadline = _text(card, "time"),
                source   = "opportunitiesforafricans",
            ))
        _polite_delay()
    return items


def scrape_opportunities_circle(keywords: List[str]) -> List[Dict]:
    """opportunitiescircle.com"""
    items = []
    for kw in keywords[:2]:
        url  = f"https://opportunitiescircle.com/?s={quote_plus(kw)}+scholarship"
        soup = _get_soup(url)
        if not soup:
            continue
        for card in soup.select("article, div.post"):
            t = card.select_one("h2 a, h3 a, .entry-title a")
            if not t:
                continue
            items.append(_s(
                title    = t.get_text(strip=True),
                url      = t.get("href",""),
                snippet  = _text(card, "p, .entry-summary")[:400],
                source   = "opportunitiescircle",
            ))
        _polite_delay()
    return items


def scrape_afterschoolafrica(keywords: List[str]) -> List[Dict]:
    """afterschoolafrica.com — African opportunities aggregator."""
    items = []
    urls = [
        "https://afterschoolafrica.com/category/scholarships/",
        f"https://afterschoolafrica.com/?s={quote_plus('fully funded scholarship africa')}",
    ]
    for url in urls[:1]:
        soup = _get_soup(url)
        if not soup:
            continue
        for card in soup.select("article, div.post"):
            t = card.select_one("h2 a, h3 a, .entry-title a")
            if not t:
                continue
            text = card.get_text().lower()
            if not any(kw.lower() in text or "scholarship" in text for kw in keywords):
                continue
            items.append(_s(
                title    = t.get_text(strip=True),
                url      = t.get("href",""),
                snippet  = _text(card, ".entry-summary, p")[:400],
                deadline = _text(card, "time"),
                source   = "afterschoolafrica",
            ))
        _polite_delay()
    return items


def scrape_scholarship_positions(keywords: List[str]) -> List[Dict]:
    """scholarshippositions.com — large global aggregator."""
    items = []
    for kw in keywords[:2]:
        url  = f"https://scholarship-positions.com/?s={quote_plus(kw)}"
        soup = _get_soup(url)
        if not soup:
            continue
        for card in soup.select("article, div.post, div.entry"):
            t = card.select_one("h2 a, h3 a, .entry-title a")
            if not t:
                continue
            text = card.get_text().lower()
            ft = FULLY_FUNDED if "fully funded" in text else (PARTIAL if "partial" in text else UNKNOWN)
            items.append(_s(
                title    = t.get_text(strip=True),
                url      = t.get("href",""),
                snippet  = _text(card, ".entry-summary, p")[:400],
                funding_type = ft,
                deadline = _text(card, "time"),
                source   = "scholarshippositions",
            ))
        _polite_delay()
    return items


def scrape_opportunities_world(keywords: List[str]) -> List[Dict]:
    """opportunitiesworld.net / similar aggregators via RSS."""
    items = []
    rss_feeds = [
        "https://www.opportunitiesworld.net/feed/",
        "https://www.scholars4dev.com/feed/",
        "https://opportunitiesforafricans.com/feed/",
    ]
    if not feedparser:
        return items
    for feed_url in rss_feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                title = entry.get("title","")
                if not any(kw.lower() in title.lower() for kw in keywords) and \
                   "scholarship" not in title.lower() and "fellowship" not in title.lower():
                    continue
                text = re.sub(r'<[^>]+>', '', entry.get("summary","")).lower()
                ft = FULLY_FUNDED if "fully funded" in text else (PARTIAL if "partial" in text else UNKNOWN)
                items.append(_s(
                    title    = title,
                    url      = entry.get("link",""),
                    snippet  = re.sub(r'<[^>]+>', '', entry.get("summary",""))[:400],
                    funding_type = ft,
                    source   = "opportunitiesworld",
                ))
        except Exception as e:
            log.warning(f"RSS feed {feed_url}: {e}")
    return items


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════
def _get_soup(url: str, retries: int = 2) -> Optional[BeautifulSoup]:
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            log.warning(f"GET {url} [{attempt+1}/{retries}] → {e}")
            time.sleep(2)
    return None


def _text(tag, selector: str) -> str:
    el = tag.select_one(selector) if hasattr(tag, 'select_one') else None
    return el.get_text(strip=True) if el else ""


def _abs(base: str, href: str) -> str:
    if not href:
        return base
    if href.startswith("http"):
        return href
    return urljoin(base, href)


def _polite_delay():
    time.sleep(random.uniform(1.5, 3.5))


def _deduplicate(items: List[Dict]) -> List[Dict]:
    seen, out = set(), []
    for item in items:
        key = item.get("url") or item.get("title","")
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _infer_funding_type(item: Dict) -> None:
    """Refine funding_type from title + snippet text if currently UNKNOWN."""
    if item.get("funding_type") not in (UNKNOWN, None):
        return
    text = (item.get("title","") + " " + item.get("snippet","")).lower()
    if any(p in text for p in ["fully funded","full scholarship","full award","fully-funded","all expenses"]):
        item["funding_type"] = FULLY_FUNDED
    elif any(p in text for p in ["partial","part-funded","co-funded","50%","tuition only"]):
        item["funding_type"] = PARTIAL
