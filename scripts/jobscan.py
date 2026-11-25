#!/usr/bin/env python3
"""jobscan: colecteaza joburi direct din ATS-urile firmelor (fara AI), filtreaza si deduplica.

Utilizare:
  python3 jobscan.py --companies companies.json [--tracker tracker_pairs.txt] [--seen seen_links.txt]
                     [--days 14] [--out out/] [--state state.json]

Iesire (in --out):
  candidates.json   joburile care trec filtrele (cu descriere scurta, daca ATS-ul o da)
  candidates.md     tabel compact pentru raport
  sources.json      status per firma (ok / eroare / numar joburi)
"""
import argparse, concurrent.futures as cf, datetime as dt, html, json, os, re, sys, time
import xml.etree.ElementTree as ET
import requests

UA = {"User-Agent": "Mozilla/5.0 (jobscan; personal job search)", "Accept": "application/json, text/html;q=0.9, */*;q=0.8"}
TIMEOUT = 25
NOW = dt.datetime.now(dt.timezone.utc)

# ---------- filtre ----------
TITLE_INCLUDE = re.compile(r"""(
    product\s+(manager|owner|lead|director|management|operations|ops|leader)|
    head\s+of\s+product|chief\s+product|\bcpo\b|vp,?\s+product|director,?\s+(of\s+)?product|
    \bproduct\s+owner\b|\bpo\b|\bapm\b|\bgpm\b|group\s+product|
    growth\s+(manager|lead|pm|product)|monetization\s+(manager|lead)|
    business\s+analyst|program(me)?\s+manager|project\s+manager|delivery\s+manager|
    (founder|entrepreneur)\s+in\s+residence|product\s+ops|franchise
)""", re.I | re.X)
TITLE_EXCLUDE = re.compile(r"product\s+marketing|product\s+design|designer|creative|professional\s+services|"
                           r"substation|transmission|salesforce|construction|engineer|developer|scientist|counsel|accountant|"
                           r"\bsales\b|account\s+exec|recruit|copywriter|support\s+specialist|"
                           r"project\s+manager\s*,?\s*(construction|civil|mep)|clinical", re.I)

# Defaults (Romania / Cluj). Override per user with --filters filters.json:
# {"title_include": "...regex...", "title_exclude": "...", "home_country": "romania|bucharest|...", "home_city": "cluj"}
RO = re.compile(r"romania|rom[aâ]nia|cluj|bucharest|bucure[sș]ti|iasi|ia[sș]i|timi[sș]oara|brasov|bra[sș]ov|sibiu|oradea|craiova", re.I)
CLUJ = re.compile(r"cluj", re.I)


def apply_filters(path):
    global TITLE_INCLUDE, TITLE_EXCLUDE, RO, CLUJ
    f = json.load(open(path, encoding="utf-8"))
    if f.get("title_include"): TITLE_INCLUDE = re.compile(f["title_include"], re.I)
    if f.get("title_exclude"): TITLE_EXCLUDE = re.compile(f["title_exclude"], re.I)
    if f.get("home_country"): RO = re.compile(f["home_country"], re.I)
    if f.get("home_city"): CLUJ = re.compile(f["home_city"], re.I)
EUROPE = re.compile(r"europe|\beu\b|emea|european|cet|eet|worldwide|anywhere|global", re.I)
REMOTE = re.compile(r"remote|work from home|home[- ]based|distributed|anywhere", re.I)


def strip_html(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def parse_date(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):  # ms epoch (Lever)
        return dt.datetime.fromtimestamp(v / 1000, dt.timezone.utc)
    s = str(v).strip()
    m = re.match(r"Posted\s+(Today|Yesterday|(\d+)\+?\s+Days?\s+Ago)", s, re.I)  # Workday
    if m:
        days = 0 if m.group(1).lower() == "today" else 1 if m.group(1).lower() == "yesterday" else int(m.group(2))
        return NOW - dt.timedelta(days=days)
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            d = dt.datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
        except Exception:
            pass
    return None


def job(company, title, location, url, posted=None, remote=None, desc="", ats=""):
    return {"company": company, "title": (title or "").strip(), "location": (location or "").strip(),
            "url": url, "posted": posted.date().isoformat() if posted else None,
            "remote": remote, "desc": strip_html(desc)[:4000], "ats": ats}


# ---------- fetchers per ATS ----------
def get(url, **kw):
    for attempt in range(3):  # retry scurt pe 429 (Workable limiteaza agresiv)
        r = requests.get(url, headers=UA, timeout=TIMEOUT, **kw)
        if r.status_code == 429 and attempt < 2:
            time.sleep(6 * (attempt + 1))
            continue
        r.raise_for_status()
        return r


def f_greenhouse(c, eu=False):
    host = "boards-api.eu.greenhouse.io" if eu else "boards-api.greenhouse.io"
    data = get(f"https://{host}/v1/boards/{c['slug']}/jobs?content=true").json()
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        offices = ", ".join(o.get("name", "") for o in j.get("offices", []) if o.get("name"))
        posted = parse_date(j.get("first_published") or j.get("updated_at"))
        out.append(job(c["name"], j.get("title"), f"{loc} | {offices}" if offices else loc,
                       j.get("absolute_url"), posted, None, html.unescape(j.get("content", "")), "greenhouse"))
    return out


def f_lever(c):
    data = get(f"https://api.lever.co/v0/postings/{c['slug']}?mode=json").json()
    out = []
    for j in data:
        cat = j.get("categories") or {}
        locs = cat.get("allLocations") or [cat.get("location", "")]
        loc = ", ".join(x for x in locs if x)
        if j.get("country"):
            loc += f" ({j['country']})"
        wt = (j.get("workplaceType") or "").lower()
        out.append(job(c["name"], j.get("text"), loc, j.get("hostedUrl"), parse_date(j.get("createdAt")),
                       wt == "remote" if wt else None, j.get("descriptionPlain") or j.get("description", ""), "lever"))
    return out


def f_ashby(c):
    data = get(f"https://api.ashbyhq.com/posting-api/job-board/{c['slug']}?includeCompensation=false").json()
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations", []) or []]
        addr = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
        loc = ", ".join(x for x in locs if x) + (f" ({addr})" if addr else "")
        wt = (j.get("workplaceType") or "").lower()
        remote = j.get("isRemote") if j.get("isRemote") is not None else (wt == "remote" if wt else None)
        out.append(job(c["name"], j.get("title"), loc, j.get("jobUrl"), parse_date(j.get("publishedAt")),
                       remote, j.get("descriptionPlain") or j.get("descriptionHtml", ""), "ashby"))
    return out


def f_workable(c):
    data = get(f"https://apply.workable.com/api/v1/widget/accounts/{c['slug']}?details=true").json()
    out = []
    for j in data.get("jobs", []):
        locs = j.get("locations") or [{"city": j.get("city"), "country": j.get("country")}]
        loc = "; ".join(", ".join(x for x in (l.get("city"), l.get("region"), l.get("country")) if x) for l in locs)
        out.append(job(c["name"], j.get("title"), loc, j.get("url") or j.get("application_url"),
                       parse_date(j.get("published_on") or j.get("created_at")), j.get("telecommuting"),
                       j.get("description", ""), "workable"))
    return out


def f_smartrecruiters(c):
    q = f"&country={c['country']}" if c.get("country") else ""
    data = get(f"https://api.smartrecruiters.com/v1/companies/{c['slug']}/postings?limit=100{q}").json()
    out = []
    for j in data.get("content", []):
        l = j.get("location") or {}
        loc = ", ".join(x for x in (l.get("city"), l.get("country")) if x)
        out.append(job(c["name"], j.get("name"), loc, f"https://jobs.smartrecruiters.com/{c['slug']}/{j.get('id')}",
                       parse_date(j.get("releasedDate")), l.get("remote"), "", "smartrecruiters"))
    return out


def f_recruitee(c):
    data = get(f"https://{c['slug']}.recruitee.com/api/offers/").json()
    out = []
    for j in data.get("offers", []):
        loc = ", ".join(x for x in (j.get("city"), j.get("country")) if x) or j.get("location", "")
        out.append(job(c["name"], j.get("title"), loc, j.get("careers_url"), parse_date(j.get("published_at")),
                       j.get("remote"), j.get("description", ""), "recruitee"))
    return out


def f_personio(c):
    root = ET.fromstring(get(f"https://{c['slug']}.jobs.personio.com/xml").content)
    out = []
    for p in root.findall("position"):
        t = lambda k: (p.findtext(k) or "").strip()
        desc = " ".join((d.findtext("value") or "") for d in p.findall("jobDescriptions/jobDescription"))
        out.append(job(c["name"], t("name"), t("office"), f"https://{c['slug']}.jobs.personio.com/job/{t('id')}",
                       parse_date(t("createdAt")), None, desc, "personio"))
    return out


def f_teamtailor(c):
    # Teamtailor are RSS public pe /jobs.rss
    root = ET.fromstring(get(f"https://{c['slug']}.teamtailor.com/jobs.rss").content)
    out = []
    for it in root.iter("item"):
        t = lambda k: (it.findtext(k) or "").strip()
        locs = [e.text or "" for e in it.iter() if e.tag.endswith("location") or e.tag.endswith("city")]
        rs = [e.text or "" for e in it.iter() if e.tag.endswith("remoteStatus")]
        out.append(job(c["name"], t("title"), ", ".join(x for x in locs if x), t("link"), parse_date(t("pubDate")),
                       (rs[0].lower() in ("fully", "hybrid")) if rs else None, t("description"), "teamtailor"))
    return out


def f_workday(c):
    url = f"https://{c['host']}/wday/cxs/{c['tenant']}/{c['site']}/jobs"
    out, seen = [], set()
    for term in c.get("search", ["product", "business analyst", "program manager"]):
        r = requests.post(url, json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": term},
                          headers={**UA, "Content-Type": "application/json"}, timeout=TIMEOUT)
        r.raise_for_status()
        for j in r.json().get("jobPostings", []):
            path = j.get("externalPath", "")
            if path in seen:
                continue
            seen.add(path)
            out.append(job(c["name"], j.get("title"), j.get("locationsText", ""),
                           f"https://{c['host']}/{c['site']}{path}", parse_date(j.get("postedOn")), None, "", "workday"))
    return out


def _icims_date(chunk):
    """iCIMS scrie data in formatul localei firmei (DD/MM sau MM/DD) plus un text relativ ("2 months ago").
    Alegem varianta care nu e in viitor si se potriveste cel mai bine cu textul relativ."""
    d = re.search(r"\((\d{1,2})/(\d{1,2})/(\d{4})", chunk)
    if not d:
        return None
    a, b, y = int(d.group(1)), int(d.group(2)), int(d.group(3))
    cands = []
    for mo, da in ((a, b), (b, a)):
        try:
            c = dt.datetime(y, mo, da, tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if c <= NOW + dt.timedelta(days=1):
            cands.append(c)
    if not cands:
        return None
    rel = re.search(r"(\d+|an?|one)\s+(day|week|month|year)s?\s+ago", chunk, re.I)
    if rel:
        n = 1 if rel.group(1).lower() in ("a", "an", "one") else int(rel.group(1))
        days = n * {"day": 1, "week": 7, "month": 30, "year": 365}[rel.group(2).lower()]
        target = NOW - dt.timedelta(days=days)
        return min(cands, key=lambda c: abs((c - target).total_seconds()))
    return max(cands)


def _icims_rows(page_html, base):
    """Parseaza o pagina de listare iCIMS (in_iframe=1). Fiecare job e un <div class="row">."""
    out = []
    for chunk in re.split(r'<div class="row"', page_html)[1:]:
        m = re.search(r'href="(?:https?://[^/"]+)?(/jobs/(\d+)/[^"?]+/job)', chunk)
        if not m:
            continue
        t = re.search(r"<h3[^>]*>(.*?)</h3>", chunk, re.S)
        loc = re.search(r"Job Locations?</span>\s*<span[^>]*>(.*?)</span>", chunk, re.S)
        posted = _icims_date(chunk)
        desc = re.search(r'class="col-xs-12 description"[^>]*>(.*?)</div>', chunk, re.S)
        out.append((strip_html(t.group(1)) if t else "", strip_html(loc.group(1)) if loc else "",
                    f"https://{base}{m.group(1)}", posted, desc.group(1) if desc else ""))
    return out


def f_icims(c):
    # host implicit: <slug>.icims.com (ex. careers-arobs.icims.com). in_iframe=1 da lista direct, fara JS.
    base = c.get("host") or f"{c['slug']}.icims.com"
    out, seen = [], set()
    for pr in range(0, 30):  # paginare: pr=0,1,2... pana nu mai vin joburi noi
        rows = _icims_rows(get(f"https://{base}/jobs/search?pr={pr}&in_iframe=1&schemaId=&o=").text, base)
        new = [r for r in rows if r[2] not in seen]
        if not new:
            break
        for title, loc, url, posted, desc in new:
            seen.add(url)
            out.append(job(c["name"], title, loc, url, posted, None, desc, "icims"))
    return out


def _jobvite_rows(page_html, slug):
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", page_html, re.S):
        a = re.search(r'<a href="(/%s/job/[A-Za-z0-9]+)"[^>]*>(.*?)</a>' % re.escape(slug), tr, re.S)
        if not a:
            continue
        loc = re.search(r'class="jv-job-list-location"[^>]*>(.*?)</td>', tr, re.S)
        out.append((strip_html(a.group(2)), re.sub(r"\s*,\s*", ", ", strip_html(loc.group(1)) if loc else "").replace("\n", " "),
                    f"https://jobs.jobvite.com{a.group(1)}"))
    return out


def f_jobvite(c):
    # Pagina publica jobs.jobvite.com/<slug>/jobs listeaza toate joburile in HTML static (fara data publicarii).
    page = get(f"https://jobs.jobvite.com/{c['slug']}/jobs").text
    return [job(c["name"], t, l, u, None, None, "", "jobvite") for t, l, u in _jobvite_rows(page, c["slug"])]


FETCHERS = {"greenhouse": f_greenhouse, "greenhouse_eu": lambda c: f_greenhouse(c, eu=True), "lever": f_lever,
            "ashby": f_ashby, "workable": f_workable, "smartrecruiters": f_smartrecruiters, "recruitee": f_recruitee,
            "personio": f_personio, "teamtailor": f_teamtailor, "workday": f_workday,
            "icims": f_icims, "jobvite": f_jobvite}


# ---------- clasificare ----------
def classify_location(j, group):
    text = f"{j['location']} {j['title']}"
    desc = j["desc"][:2500]
    is_remote = j["remote"] is True or bool(REMOTE.search(text))
    # agregatorii (ex. Jobgether) dubleaza anuntul pe tari; descrierea spune unde e de fapt rolul
    m = re.search(r"based in ([A-Z][A-Za-z ]{2,30}?)[.,;]", desc)
    if m and not (RO.search(m.group(1)) or EUROPE.search(m.group(1))):
        return None
    if CLUJ.search(text):
        return "Cluj"
    if RO.search(text):
        return "Romania remote" if is_remote else "Romania (alt oras)"
    if is_remote and EUROPE.search(text):
        return "Remote EU/EMEA"
    # locatia numeste explicit tari/orase (fara RO si fara Europa/EMEA) -> nu e pentru Romania
    loc_only = re.sub(REMOTE, "", j["location"]).strip(" ,|;-()")
    if loc_only:
        return "Remote (alta tara?)" if is_remote else None
    if is_remote and RO.search(desc):
        return "Remote (RO in descriere)"
    if is_remote and EUROPE.search(desc):
        return "Remote (EU in descriere)"
    if is_remote:
        return "Remote (neclar)"
    if is_remote:
        return "Remote (alta tara?)"
    return None  # on-site in alta tara


LOC_OK = {"Cluj", "Romania remote", "Romania (alt oras)", "Remote EU/EMEA", "Remote (RO in descriere)",
          "Remote (EU in descriere)", "Remote (neclar)"}


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def load_lines(path):
    if not path or not os.path.exists(path):
        return []
    return [l.strip() for l in open(path, encoding="utf-8") if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--companies", required=True)
    ap.add_argument("--tracker", help="fisier 'Companie | Rol' pe linie")
    ap.add_argument("--seen", help="fisier cu URL-uri deja vazute, unul pe linie")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--out", default="out")
    ap.add_argument("--state", default="state.json", help="ID-uri vazute in rulari anterioare")
    ap.add_argument("--all", action="store_true", help="ignora dedup (pentru test)")
    ap.add_argument("--filters", help="JSON cu regex-uri proprii (title_include, title_exclude, home_country, home_city)")
    ap.add_argument("--raw-in", help="JSON cu joburi deja colectate (ex. din browser cu browser_scan.js); "
                                     "se sare peste descarcare, se aplica doar filtrele si dedup")
    ap.add_argument("--raw-out", help="salveaza toate joburile descarcate (inainte de filtre) in acest fisier")
    a = ap.parse_args()
    if a.filters:
        apply_filters(a.filters)
    os.makedirs(a.out, exist_ok=True)

    companies = json.load(open(a.companies, encoding="utf-8"))
    tracker = [tuple(norm(x) for x in l.split("|", 1)) for l in load_lines(a.tracker) if "|" in l]
    seen_urls = {u.rstrip("/").lower() for u in load_lines(a.seen)}
    state = json.load(open(a.state)) if os.path.exists(a.state) else {"seen": {}}
    # memoria de dedup: tot ce a fost raportat in rulari anterioare + lista de joburi vazute din sheet
    for u in seen_urls:
        state["seen"].setdefault(u, "seen-list")
    seen_urls |= set(state["seen"])

    sources, all_jobs = {}, []

    def run(c):
        f = FETCHERS.get(c["ats"])
        if not f:
            return c, None, "ATS nesuportat"
        t0 = time.time()
        print(f"-> {c['name']}", file=sys.stderr, flush=True)
        try:
            return c, f(c), f"ok ({time.time() - t0:.1f}s)"
        except Exception as e:
            return c, None, f"eroare: {type(e).__name__}: {str(e)[:120]}"

    if a.raw_in:
        raw = json.load(open(a.raw_in, encoding="utf-8"))
        groups = {c["name"]: c.get("group", "") for c in companies}
        by_co = {}
        for r in raw:
            j = job(r.get("company", ""), r.get("title"), r.get("location"), r.get("url"),
                    parse_date(r.get("posted")), r.get("remote"), r.get("desc", ""), r.get("ats", "browser"))
            by_co.setdefault(j["company"], []).append(j)
        results = [({"name": n, "ats": "browser", "group": groups.get(n, "")}, js, "ok (raw-in)")
                   for n, js in by_co.items()]
        fast, slow = [], []
    else:
        results = None
    fast = [] if a.raw_in else [c for c in companies if c["ats"] != "workable"]
    slow = [] if a.raw_in else [c for c in companies if c["ats"] == "workable"]  # secvential, cu pauza (rate limit)

    def run_slow(cs):
        for c in cs:
            yield run(c)
            time.sleep(3)

    if results is None:
        with cf.ThreadPoolExecutor(max_workers=12) as ex:
            results = list(ex.map(run, fast))
        results += list(run_slow(slow))
        # Retea blocata (ex. container cloud cu allowlist): aproape toate sursele pica cu erori de conexiune/proxy.
        net_err = [s for _, _, s in results if re.search(r"ProxyError|ConnectionError|ConnectTimeout|NameResolution|403 Client Error: Forbidden for url: https://(boards-api|api\.lever|api\.ashby)", s)]
        if results and len(net_err) >= 0.8 * len(results):
            print(json.dumps({"error": "NETWORK_BLOCKED", "failed": len(net_err), "total": len(results),
                              "hint": "Ruleaza jobscan.py pe calculatorul utilizatorului sau colecteaza joburile in browser "
                                      "cu browser_scan.js si apoi: jobscan.py --raw-in raw.json"}), file=sys.stdout)
            sys.exit(3)
    if a.raw_out:
        json.dump([dict(j, group=c.get("group", "")) for c, js, _ in results for j in (js or [])],
                  open(a.raw_out, "w", encoding="utf-8"), ensure_ascii=False)
    if True:
        for c, jobs, status in results:
            sources[c["name"]] = {"ats": c["ats"], "status": status, "jobs_total": len(jobs or [])}
            for j in jobs or []:
                j["group"] = c.get("group", "")
                all_jobs.append(j)

    cands, stats = [], {"total": len(all_jobs), "title": 0, "loc": 0, "date": 0, "dup": 0}
    cutoff = NOW - dt.timedelta(days=a.days)
    for j in all_jobs:
        if not TITLE_INCLUDE.search(j["title"]) or TITLE_EXCLUDE.search(j["title"]):
            continue
        stats["title"] += 1
        j["loc_class"] = classify_location(j, j["group"])
        if j["loc_class"] not in LOC_OK:
            continue
        stats["loc"] += 1
        p = parse_date(j["posted"]) if j["posted"] else None
        if p and p < cutoff and j["group"] != "A":  # firmele din Cluj: orice rol deschis conteaza
            continue
        stats["date"] += 1
        url_key = (j["url"] or "").rstrip("/").lower()
        nc, nt = norm(j["company"]), norm(j["title"])
        dup = url_key in seen_urls or any(
            (tc and (tc in nc or nc in tc)) and (tt and (tt[:40] in nt or nt[:40] in tt)) for tc, tt in tracker)
        j["already_known"] = dup
        stats["sources_ok"] = sum(1 for s in sources.values() if s["status"].startswith("ok"))
        if dup and not a.all:
            stats["dup"] += 1
            continue
        cands.append(j)

    for j in cands:
        state["seen"].setdefault((j["url"] or "").rstrip("/").lower(), NOW.date().isoformat())
    json.dump(state, open(a.state, "w"), indent=1)

    order = {"Cluj": 0, "Romania remote": 1, "Romania (alt oras)": 2, "Remote EU/EMEA": 3,
             "Remote (RO in descriere)": 3, "Remote (EU in descriere)": 4, "Remote (neclar)": 5}
    cands.sort(key=lambda j: (order.get(j["loc_class"], 9), -(parse_date(j["posted"]) or cutoff).timestamp()))
    json.dump(cands, open(os.path.join(a.out, "candidates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(sources, open(os.path.join(a.out, "sources.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    with open(os.path.join(a.out, "candidates.md"), "w", encoding="utf-8") as f:
        f.write("| # | Companie | Rol | Locatie | Clasa | Postat | Link |\n|---|---|---|---|---|---|---|\n")
        for i, j in enumerate(cands, 1):
            f.write(f"| {i} | {j['company']} | {j['title']} | {j['location'][:50]} | {j['loc_class']} | "
                    f"{j['posted'] or '?'} | {j['url']} |\n")

    stats["candidates"] = len(cands)
    print(json.dumps({"stats": stats, "sources": sources}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
