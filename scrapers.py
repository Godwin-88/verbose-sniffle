"""
job_hunter/scrapers.py

Scrapers for:
  🇰🇪 Kenyan Government
      • NEAIMS       — neaims.go.ke        (National Employment Authority)
      • GAA          — gaa.go.ke           (Government Advertising Agency)

  🇰🇪 Kenyan Private / NGO
      • BrighterMonday
      • MyJobMag
      • Fuzu          (JSON API)
      • JobWebKenya
      • CareersInKenya
      • NGO/INGO      — ReliefWeb JSON API

  🌐 Global / Social
      • LinkedIn      (public guest endpoint)
      • Reddit        (PRAW — r/KenyaJobs, r/forhire, r/jobbit)

  🌍 Remote / Global Tech
      • RemoteOK      (public JSON API)
      • WeWorkRemotely (RSS feed)
      • RemoteForAfrica (HTML — African remote roles)
      • Himalayas     (public JSON API)

pip install requests beautifulsoup4 praw python-dotenv
Optional: pip install playwright && playwright install chromium
"""

import re, time, random, logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ════════════════════════════════════════════════════════════════════════════
def scrape_all(keywords: List[str], sources: List[str]) -> List[Dict]:
    scrapers = {
        # Kenyan government
        "neaims":         scrape_neaims,
        "gaa":            scrape_gaa,
        # Kenyan private / NGO
        "brightermonday": scrape_brightermonday,
        "myjobmag":       scrape_myjobmag,
        "fuzu":           scrape_fuzu,
        "jobwebkenya":    scrape_jobwebkenya,
        "careersinkenya": scrape_careersinkenya,
        "ngojobskenya":   scrape_ngojobs,
        # Global / social
        "linkedin":         scrape_linkedin_public,
        "reddit":           scrape_reddit,
        # Remote / global tech
        "remoteok":         scrape_remoteok,
        "weworkremotely":   scrape_weworkremotely,
        "remoteforafrica":  scrape_remoteforafrica,
        "himalayas":        scrape_himalayas,
    }
    results = []
    for source in sources:
        fn = scrapers.get(source) or scrapers.get(source.lower().replace(" ", "").replace("-", ""))
        if not fn:
            log.warning(f"No scraper registered for '{source}'")
            continue
        for kw in keywords:
            log.info(f"[{source}] Searching: '{kw}'")
            try:
                jobs = fn(kw)
                for j in jobs:
                    j.setdefault("source", source)
                    j.setdefault("keyword", kw)
                results.extend(jobs)
                _polite_delay()
            except Exception as e:
                log.error(f"[{source}/{kw}] Error: {e}")
    return _deduplicate(results)


def enrich_job_description(job: dict) -> dict:
    """Fetch and parse the full job description from the listing URL."""
    try:
        r    = _get_with_retry(job["url"], headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["nav", "footer", "script", "style", "aside", "header"]):
            tag.decompose()
        selectors = [
            ".job-description", "#job-description", ".description",
            "article", ".content", "main", "div[class*='detail']",
            "div[class*='job']", "section",
        ]
        body = ""
        for sel in selectors:
            el = soup.select_one(sel)
            if el and len(el.get_text()) > 200:
                body = el.get_text(separator="\n", strip=True)
                break
        if not body:
            body = soup.get_text(separator="\n", strip=True)[:3000]
        job["full_description"] = body[:4000]
    except Exception as e:
        log.warning(f"Enrich failed for {job.get('url')}: {e}")
        job["full_description"] = job.get("snippet", "")
    return job


# ════════════════════════════════════════════════════════════════════════════
# 🇰🇪 KENYAN GOVERNMENT BOARDS
# ════════════════════════════════════════════════════════════════════════════

def scrape_neaims(keyword: str) -> List[Dict]:
    """
    National Employment Authority — neaims.go.ke
    The site lists job vacancies submitted by employers via the NEAIMS portal.
    Tries the search endpoint first; falls back to listing page keyword filter.
    """
    jobs = []

    # Attempt 1: search parameter
    urls_to_try = [
        f"https://neaims.go.ke/jobs?search={_enc(keyword)}",
        f"https://neaims.go.ke/vacancies?q={_enc(keyword)}",
        f"https://neaims.go.ke/job-listings?keyword={_enc(keyword)}",
        "https://neaims.go.ke/jobs",          # fallback: grab all, filter below
    ]

    soup = None
    for url in urls_to_try:
        soup = _get_soup(url)
        if soup:
            break

    if not soup:
        log.warning("NEAIMS: could not load any page")
        return jobs

    # Common card selectors on government portals (WordPress / Bootstrap)
    card_selectors = [
        "div.job-listing", "article.job", "div.vacancy", "tr.job-row",
        "div.card", "li.job-item", "div[class*='job']", "table tr",
    ]
    cards = []
    for sel in card_selectors:
        cards = soup.select(sel)
        if cards:
            break

    # If no cards found, try raw <a> links containing keyword
    if not cards:
        all_links = soup.find_all("a", href=True)
        for a in all_links:
            text = a.get_text(strip=True)
            if keyword.lower() in text.lower() and len(text) > 10:
                jobs.append({
                    "title":    text,
                    "url":      _abs("https://neaims.go.ke", a["href"]),
                    "company":  "Government of Kenya (via NEAIMS)",
                    "location": "Kenya",
                    "deadline": "",
                    "snippet":  "",
                    "sector":   "government",
                })
        return jobs

    for card in cards:
        title_el = card.select_one("h2 a, h3 a, h4 a, a.title, td a, .job-title a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if keyword.lower() not in title.lower() and \
           keyword.lower() not in _text(card, "*"):
            continue  # skip unrelated when we loaded the full listing
        jobs.append({
            "title":    title,
            "url":      _abs("https://neaims.go.ke", title_el.get("href", "")),
            "company":  _text(card, ".employer, .company, td:nth-child(2)") or "Government of Kenya",
            "location": _text(card, ".location, td:nth-child(3)") or "Kenya",
            "deadline": _text(card, ".deadline, .closing-date, time, td:nth-child(4)"),
            "snippet":  _text(card, ".description, p"),
            "sector":   "government",
        })
    return jobs


def scrape_gaa(keyword: str) -> List[Dict]:
    """
    Government Advertising Agency — gaa.go.ke/job-adverts
    GAA publishes government job adverts from all ministries/parastatals.
    """
    jobs = []

    pages = [
        f"https://gaa.go.ke/job-adverts?search={_enc(keyword)}",
        f"https://gaa.go.ke/job-adverts?s={_enc(keyword)}",
        "https://gaa.go.ke/job-adverts",        # full listing, filter by keyword
    ]

    soup = None
    used_url = ""
    for url in pages:
        soup = _get_soup(url)
        if soup:
            used_url = url
            break

    if not soup:
        log.warning("GAA: could not load job-adverts page")
        return jobs

    # GAA is a WordPress site — articles or divs with job posts
    card_selectors = [
        "article", "div.job-advert", "div.post", "div.entry",
        "div.card", "li.advert",
    ]
    cards = []
    for sel in card_selectors:
        cards = soup.select(sel)
        if len(cards) > 1:
            break

    kw_lower = keyword.lower()

    for card in cards:
        title_el = card.select_one("h2 a, h3 a, h1 a, .entry-title a, a.post-title")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        card_text = card.get_text().lower()

        # Filter by keyword when we loaded the unfiltered listing
        if "search=" not in used_url and kw_lower not in card_text:
            continue

        href = title_el.get("href", "")
        jobs.append({
            "title":    title,
            "url":      href if href.startswith("http") else _abs("https://gaa.go.ke", href),
            "company":  _text(card, ".organisation, .ministry, .category") or "Government of Kenya (via GAA)",
            "location": _text(card, ".location") or "Kenya",
            "deadline": _text(card, "time, .date, .deadline, .closing"),
            "snippet":  _text(card, ".entry-content p, .excerpt, p")[:400],
            "sector":   "government",
        })

    log.info(f"GAA: found {len(jobs)} jobs for '{keyword}'")
    return jobs


# ════════════════════════════════════════════════════════════════════════════
# 🇰🇪 KENYAN PRIVATE / THIRD SECTOR
# ════════════════════════════════════════════════════════════════════════════

def scrape_brightermonday(keyword: str) -> List[Dict]:
    jobs = []
    for page in range(1, 4):
        url  = f"https://www.brightermonday.co.ke/jobs/?q={_enc(keyword)}&page={page}"
        soup = _get_soup(url)
        if not soup:
            break
        cards = soup.select("div.search-result, article.job-item")
        if not cards:
            break
        for card in cards:
            title_el = card.select_one("h3.title a, a.job-title, h2 a")
            if not title_el:
                continue
            jobs.append({
                "title":    title_el.get_text(strip=True),
                "url":      _abs("https://www.brightermonday.co.ke", title_el["href"]),
                "company":  _text(card, ".company-name, .employer"),
                "location": _text(card, ".location, .job-location"),
                "deadline": _text(card, ".closing-date, time"),
                "snippet":  _text(card, ".job-description, p")[:400],
                "sector":   "private",
            })
    return jobs


def scrape_myjobmag(keyword: str) -> List[Dict]:
    jobs = []
    url  = f"https://www.myjobmag.co.ke/jobs-by-field/?q={_enc(keyword)}"
    soup = _get_soup(url)
    if not soup:
        return jobs
    for card in soup.select("article.job-item, div.job-item, li.job"):
        title_el = card.select_one("h2 a, h3 a, a.job-title")
        if not title_el:
            continue
        jobs.append({
            "title":    title_el.get_text(strip=True),
            "url":      _abs("https://www.myjobmag.co.ke", title_el["href"]),
            "company":  _text(card, ".company, .employer-name"),
            "location": _text(card, ".location"),
            "deadline": _text(card, ".deadline, time"),
            "snippet":  _text(card, ".description, p")[:400],
            "sector":   "private",
        })
    return jobs


def scrape_fuzu(keyword: str) -> List[Dict]:
    """Fuzu has a JSON API — cleaner than HTML scraping."""
    jobs = []
    url  = (
        "https://fuzu.com/api/v2/jobs"
        f"?query={_enc(keyword)}&country=Kenya&per_page=20"
    )
    try:
        r    = _get_with_retry(url, headers=HEADERS, timeout=15)
        data = r.json()
        for item in data.get("jobs", []):
            jobs.append({
                "title":    item.get("title", ""),
                "url":      f"https://fuzu.com/jobs/{item.get('slug', item.get('id', ''))}",
                "company":  item.get("company", {}).get("name", ""),
                "location": item.get("location", "Kenya"),
                "deadline": item.get("deadline", ""),
                "snippet":  item.get("summary", "")[:400],
                "sector":   "private",
            })
    except Exception as e:
        log.error(f"Fuzu API error: {e}")
    return jobs


def scrape_jobwebkenya(keyword: str) -> List[Dict]:
    jobs = []
    url  = f"https://jobwebkenya.com/?s={_enc(keyword)}"
    soup = _get_soup(url)
    if not soup:
        return jobs
    for card in soup.select("article, div.job-post"):
        title_el = card.select_one("h2 a, h3 a, .entry-title a")
        if not title_el:
            continue
        jobs.append({
            "title":    title_el.get_text(strip=True),
            "url":      title_el["href"],
            "company":  _text(card, ".company, .employer"),
            "location": _text(card, ".location"),
            "deadline": _text(card, ".deadline, time"),
            "snippet":  _text(card, ".entry-content p, .description")[:400],
            "sector":   "private",
        })
    return jobs


def scrape_careersinkenya(keyword: str) -> List[Dict]:
    jobs = []
    url  = f"https://careersinkenya.com/?s={_enc(keyword)}"
    soup = _get_soup(url)
    if not soup:
        return jobs
    for card in soup.select("article, div.job-item"):
        title_el = card.select_one("h2 a, h3 a")
        if not title_el:
            continue
        jobs.append({
            "title":    title_el.get_text(strip=True),
            "url":      title_el["href"],
            "company":  _text(card, ".company"),
            "location": _text(card, ".location"),
            "deadline": _text(card, "time, .date"),
            "snippet":  _text(card, "p")[:400],
            "sector":   "private",
        })
    return jobs


def scrape_ngojobs(keyword: str) -> List[Dict]:
    """ReliefWeb JSON API — best for NGO/UN/INGO roles in Kenya."""
    jobs = []
    url  = (
        "https://api.reliefweb.int/v1/jobs"
        f"?appname=jobhunter-ke&query[value]={_enc(keyword)}"
        "&filter[field]=country.name&filter[value]=Kenya"
        "&fields[include][]=title&fields[include][]=body-html"
        "&fields[include][]=date&fields[include][]=source&fields[include][]=url"
        "&limit=20"
    )
    try:
        r    = _get_with_retry(url, timeout=15)
        data = r.json()
        for item in data.get("data", []):
            f = item.get("fields", {})
            body_html = f.get("body-html", "")
            snippet   = BeautifulSoup(body_html, "html.parser").get_text()[:400]
            jobs.append({
                "title":    f.get("title", ""),
                "url":      f.get("url", ""),
                "company":  (f.get("source") or [{}])[0].get("name", "NGO/INGO"),
                "location": "Kenya",
                "deadline": (f.get("date") or {}).get("closing", ""),
                "snippet":  snippet,
                "sector":   "ngo",
            })
    except Exception as e:
        log.error(f"ReliefWeb error: {e}")
    return jobs


# ════════════════════════════════════════════════════════════════════════════
# 🌐 GLOBAL / SOCIAL
# ════════════════════════════════════════════════════════════════════════════

def scrape_linkedin_public(keyword: str) -> List[Dict]:
    """LinkedIn public job search — no login required for basic listings."""
    jobs = []
    url  = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        f"?keywords={_enc(keyword)}&location=Kenya&start=0"
    )
    soup = _get_soup(url)
    if not soup:
        return jobs
    for card in soup.select("li"):
        title_el = card.select_one("h3.base-search-card__title")
        link_el  = card.select_one("a.base-card__full-link")
        if not title_el or not link_el:
            continue
        posted_raw = _text(card, "time").lower()
        # Skip listings posted more than 30 days ago
        if any(x in posted_raw for x in ["month", "months", "year", "years"]):
            continue
        jobs.append({
            "title":    title_el.get_text(strip=True),
            "url":      link_el["href"].split("?")[0],
            "company":  _text(card, "h4.base-search-card__subtitle"),
            "location": _text(card, "span.job-search-card__location"),
            "deadline": f"Posted {posted_raw}" if posted_raw else "",
            "snippet":  "",
            "sector":   "private",
        })
    return jobs


def scrape_reddit(keyword: str) -> List[Dict]:
    """
    Reddit PRAW scraper — r/KenyaJobs, r/forhire, r/jobbit, r/remotework.
    Set REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET in your .env
    Register a free app at: https://www.reddit.com/prefs/apps
    """
    import os, praw
    jobs = []
    try:
        reddit = praw.Reddit(
            client_id     = os.getenv("REDDIT_CLIENT_ID", ""),
            client_secret = os.getenv("REDDIT_CLIENT_SECRET", ""),
            user_agent    = "JobHunterKE/1.0",
        )
        subreddits = ["KenyaJobs", "forhire", "jobbit", "remotework"]
        for sub in subreddits:
            try:
                for post in reddit.subreddit(sub).search(
                    keyword, limit=10, time_filter="month"
                ):
                    jobs.append({
                        "title":    post.title,
                        "url":      f"https://reddit.com{post.permalink}",
                        "company":  f"Reddit · r/{sub}",
                        "location": "Remote / Kenya",
                        "deadline": "",
                        "snippet":  (post.selftext or "")[:400],
                        "sector":   "social",
                    })
            except Exception as e:
                log.warning(f"Reddit r/{sub}: {e}")
    except Exception as e:
        log.error(f"Reddit PRAW init error: {e}")
    return jobs


# ════════════════════════════════════════════════════════════════════════════
# 🌍 REMOTE / GLOBAL TECH BOARDS
# ════════════════════════════════════════════════════════════════════════════

def scrape_remoteok(keyword: str) -> List[Dict]:
    """
    RemoteOK public JSON API — remoteok.com/api
    No auth required. Returns all remote tech listings; filtered client-side by keyword.
    """
    jobs = []
    try:
        r = _get_with_retry(
            "https://remoteok.com/api",
            headers={**HEADERS, "Accept": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        kw_lower = keyword.lower()
        for item in data:
            if not isinstance(item, dict) or not item.get("position"):
                continue
            text = " ".join([
                item.get("position", ""),
                item.get("company", ""),
                " ".join(item.get("tags", [])),
                item.get("description", ""),
            ]).lower()
            if kw_lower not in text:
                continue
            jobs.append({
                "title":    item.get("position", ""),
                "company":  item.get("company", ""),
                "url":      item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id','')}",
                "location": "Remote",
                "deadline": item.get("date", "")[:10] if item.get("date") else "",
                "snippet":  (item.get("description") or "")[:400],
                "sector":   "remote",
            })
    except Exception as e:
        log.error(f"RemoteOK error: {e}")
    return jobs


def scrape_weworkremotely(keyword: str) -> List[Dict]:
    """
    We Work Remotely RSS feeds — programming, devops, design, product, data science.
    No auth required.
    """
    import xml.etree.ElementTree as ET
    jobs = []
    feeds = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
        "https://weworkremotely.com/categories/remote-product-jobs.rss",
        "https://weworkremotely.com/remote-jobs.rss",  # full feed covers all categories
    ]
    kw_lower = keyword.lower()
    for feed_url in feeds:
        try:
            r = requests.get(feed_url, headers=HEADERS, timeout=20, allow_redirects=True)
            r.raise_for_status()
            if not r.content.strip():
                continue
            root = ET.fromstring(r.content)
            for item in root.findall(".//item"):
                title   = (item.findtext("title") or "").strip()
                link    = (item.findtext("link") or "").strip()
                company = (item.findtext("company") or "").strip()
                pub     = (item.findtext("pubDate") or "")[:16]
                desc    = (item.findtext("description") or "")[:400]
                region  = (item.findtext("region") or "Worldwide")
                text    = f"{title} {company} {desc}".lower()
                if kw_lower not in text:
                    continue
                # WWR encodes title as "CompanyName: JobTitle"
                if ":" in title and not company:
                    parts   = title.split(":", 1)
                    company = parts[0].strip()
                    title   = parts[1].strip()
                jobs.append({
                    "title":    title,
                    "company":  company,
                    "url":      link,
                    "location": f"Remote · {region}",
                    "deadline": pub,
                    "snippet":  desc,
                    "sector":   "remote",
                })
            _polite_delay()
        except Exception as e:
            log.warning(f"WeWorkRemotely feed {feed_url}: {e}")
    return jobs


def scrape_remoteforafrica(keyword: str) -> List[Dict]:
    """
    Remote for Africa — remoteforafrica.com (React/MUI site)
    Scrapes the /jobs listing page (no JS needed for initial HTML) and
    filters by keyword across title + visible card text.
    """
    jobs = []
    kw_lower = keyword.lower()
    seen: set = set()

    # The site renders job cards server-side on /jobs — no JS needed for listing
    soup = _get_soup("https://remoteforafrica.com/jobs")
    if not soup:
        return jobs

    # Cards are <a href="/jobs/slug"> inside MUI Box divs
    # Each card's ancestor at ~level 2 contains company, title, location, date
    for a in soup.find_all("a", href=lambda h: h and h.startswith("/jobs/")):
        href = "https://remoteforafrica.com" + a["href"]
        if href in seen:
            continue

        # Walk up two levels to get the full card text
        card = a.parent.parent if a.parent and a.parent.parent else a.parent
        card_text = card.get_text(separator="|", strip=True) if card else a.get_text(strip=True)

        if kw_lower not in card_text.lower():
            continue

        seen.add(href)
        # Card text format: "Company|Title|Location|type|Country|...|Date"
        parts = [p.strip() for p in card_text.split("|") if p.strip()]
        title   = a.get_text(strip=True) or (parts[1] if len(parts) > 1 else "")
        company = parts[0] if parts else "—"
        location = next((p for p in parts if "remote" in p.lower() or any(
            c in p for c in ["Nigeria","Kenya","Ghana","Africa","South Africa","Egypt","Remote"]
        )), "Remote · Africa")
        date = next((p for p in reversed(parts) if re.match(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d", p)), "")

        jobs.append({
            "title":    title,
            "company":  company,
            "url":      href,
            "location": location,
            "deadline": date,
            "snippet":  card_text[:300],
            "sector":   "remote",
        })

    return jobs


def scrape_himalayas(keyword: str) -> List[Dict]:
    """
    Himalayas public jobs API — himalayas.app
    Strong coverage of remote AI/ML, fintech, full-stack, and data engineering roles.
    """
    jobs = []
    try:
        r = _get_with_retry(
            f"https://himalayas.app/jobs/api?q={_enc(keyword)}&limit=50",
            headers={**HEADERS, "Accept": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return jobs
        for item in items:
            if not isinstance(item, dict):
                continue
            location = item.get("locationRestrictions")
            if isinstance(location, list):
                location = ", ".join(location) if location else "Remote (Worldwide)"
            jobs.append({
                "title":    item.get("title", ""),
                "company":  item.get("companyName") or item.get("company", ""),
                "url":      item.get("applicationLink") or item.get("guid", ""),
                "location": location or "Remote (Worldwide)",
                "deadline": _ts_to_date(item.get("pubDate")),
                "snippet":  (item.get("excerpt") or item.get("description") or "")[:400],
                "sector":   "remote",
            })
    except Exception as e:
        log.error(f"Himalayas error: {e}")
    return jobs


# ════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _ts_to_date(ts) -> str:
    """Convert a Unix timestamp (int or str) or ISO date string to YYYY-MM-DD."""
    if not ts:
        return ""
    try:
        if isinstance(ts, (int, float)):
            import datetime
            return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        return str(ts)[:10]
    except Exception:
        return ""


def _get_soup(url: str) -> BeautifulSoup | None:
    try:
        r = _get_with_retry(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        log.warning(f"GET {url} → {e}")
        return None


def _text(tag, selector: str) -> str:
    el = tag.select_one(selector)
    return el.get_text(strip=True) if el else ""


def _abs(base: str, href: str) -> str:
    if not href:
        return base
    if href.startswith("http"):
        return href
    return base.rstrip("/") + "/" + href.lstrip("/")


def _enc(s: str) -> str:
    from urllib.parse import quote_plus
    return quote_plus(s)


def _polite_delay():
    time.sleep(random.uniform(3.0, 6.0))


def _get_with_retry(url, headers=None, timeout=20, retries=3):
    """GET with exponential backoff on 429/503."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers or HEADERS, timeout=timeout)
            if r.status_code == 429:
                wait = (2 ** attempt) * random.uniform(5, 10)
                log.warning(f"429 from {url[:60]} — waiting {wait:.0f}s")
                time.sleep(wait)
                continue
            return r
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt * 2)
    return None


def _deduplicate(jobs: List[Dict]) -> List[Dict]:
    seen, out = set(), []
    for j in jobs:
        key = j.get("url") or j.get("title", "")
        if key and key not in seen:
            seen.add(key)
            out.append(j)
    return out


# ════════════════════════════════════════════════════════════════════════════
# PLAYWRIGHT NOTE — for JS-heavy pages (LinkedIn full descriptions, etc.)
# ════════════════════════════════════════════════════════════════════════════
# Replace _get_soup() calls with this when needed:
#
# from playwright.sync_api import sync_playwright
# def _get_soup_js(url: str) -> BeautifulSoup | None:
#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=True)
#         page    = browser.new_page()
#         page.goto(url, wait_until="networkidle")
#         html    = page.content()
#         browser.close()
#     return BeautifulSoup(html, "html.parser")
