// browser_scan.js — the browser fallback for jobscan.py.
// Use it when jobscan.py exits with NETWORK_BLOCKED (e.g. a cloud container whose network blocks the ATS APIs)
// and it can't be run on the user's computer either.
//
// How to use (from the javascript tool of the built-in browser or Claude in Chrome):
//   1. Open a page whose CSP allows fetch to other domains. Tested OK: https://jobs.lever.co/<any-slug>
//      (even the 404 page works) and https://jobs.jobvite.com/<slug>/jobs.
//   2. Run: <the contents of this file> + `await jobhuntScan(COMPANIES, TITLE_REGEX)`
//      COMPANIES = the array from companies.json, TITLE_REGEX = the title_include string from filters.json.
//   3. The result is {jobs:[...], needsPage:[...], errors:[...]}. Save `jobs` to raw.json and run:
//      python3 jobscan.py --companies companies.json --raw-in raw.json --filters filters.json ...
//   4. For each item in `needsPage` (ATS without CORS: greenhouse_eu, workable, workday, teamtailor, personio,
//      icims, jobvite), navigate to item.page and run `await jobhuntPage(item, TITLE_REGEX)` on that page
//      (same-origin fetch); append the returned jobs to raw.json.
// It only returns jobs whose title matches TITLE_REGEX, without descriptions, to keep the output small.

const _CORS = {
  greenhouse: c => [`https://boards-api.greenhouse.io/v1/boards/${c.slug}/jobs`,
    d => (d.jobs || []).map(j => ({title: j.title, location: (j.location || {}).name || "", url: j.absolute_url,
      posted: j.first_published || j.updated_at}))],
  lever: c => [`https://api.lever.co/v0/postings/${c.slug}?mode=json`,
    d => (d || []).map(j => ({title: j.text, location: ((j.categories || {}).allLocations || [(j.categories || {}).location || ""]).join(", "),
      url: j.hostedUrl, posted: j.createdAt ? new Date(j.createdAt).toISOString() : null,
      remote: (j.workplaceType || "").toLowerCase() === "remote" || null}))],
  ashby: c => [`https://api.ashbyhq.com/posting-api/job-board/${c.slug}`,
    d => (d.jobs || []).filter(j => j.isListed !== false).map(j => ({title: j.title,
      location: [j.location, ...(j.secondaryLocations || []).map(s => s.location)].filter(Boolean).join(", "),
      url: j.jobUrl, posted: j.publishedAt, remote: j.isRemote ?? null}))],
  smartrecruiters: c => [`https://api.smartrecruiters.com/v1/companies/${c.slug}/postings?limit=100${c.country ? "&country=" + c.country : ""}`,
    d => (d.content || []).map(j => ({title: j.name, location: [(j.location || {}).city, (j.location || {}).country].filter(Boolean).join(", "),
      url: `https://jobs.smartrecruiters.com/${c.slug}/${j.id}`, posted: j.releasedDate, remote: (j.location || {}).remote ?? null}))],
};

const _PAGE = {
  greenhouse_eu: c => `https://job-boards.eu.greenhouse.io/${c.slug}`,
  workable: c => `https://apply.workable.com/${c.slug}/`,
  workday: c => `https://${c.host}/${c.site}`,
  teamtailor: c => `https://${c.slug}.teamtailor.com/jobs`,
  personio: c => `https://${c.slug}.jobs.personio.com/`,
  icims: c => `https://${c.host || c.slug + ".icims.com"}/jobs/search?pr=0&in_iframe=1`,
  jobvite: c => `https://jobs.jobvite.com/${c.slug}/jobs`,
};

async function jobhuntScan(companies, titleRe) {
  const re = new RegExp(titleRe, "i"), jobs = [], needsPage = [], errors = [];
  await Promise.all(companies.map(async c => {
    const spec = _CORS[c.ats];
    if (!spec) { if (_PAGE[c.ats]) needsPage.push({...c, page: _PAGE[c.ats](c)}); else errors.push(`${c.name}: unsupported ATS ${c.ats}`); return; }
    const [url, map] = spec(c);
    try {
      const r = await fetch(url);
      if (!r.ok) { errors.push(`${c.name}: HTTP ${r.status}`); return; }
      for (const j of map(await r.json())) if (re.test(j.title || "")) jobs.push({company: c.name, ats: c.ats, ...j});
    } catch (e) { errors.push(`${c.name}: ${e.message}`); }
  }));
  return {jobs, needsPage, errors};
}

// Run on the company's own page (same origin), after navigating to item.page.
async function jobhuntPage(c, titleRe) {
  const re = new RegExp(titleRe, "i"), out = [];
  const keep = j => { if (re.test(j.title || "")) out.push({company: c.name, ats: c.ats, ...j}); };
  const txt = el => (el ? el.textContent : "").replace(/\s+/g, " ").trim();
  if (c.ats === "workable") {
    const d = await (await fetch(`/api/v1/widget/accounts/${c.slug}`)).json();
    (d.jobs || []).forEach(j => keep({title: j.title, location: [j.city, j.country].filter(Boolean).join(", "),
      url: j.url || j.shortlink, posted: j.published_on || j.created_at, remote: j.telecommuting ?? null}));
  } else if (c.ats === "workday") {
    for (const term of c.search || ["product", "business analyst", "program manager"]) {
      const r = await fetch(`/wday/cxs/${c.tenant}/${c.site}/jobs`, {method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({appliedFacets: {}, limit: 20, offset: 0, searchText: term})});
      ((await r.json()).jobPostings || []).forEach(j => keep({title: j.title, location: j.locationsText || "",
        url: `https://${c.host}/${c.site}${j.externalPath}`, posted: j.postedOn}));
    }
  } else if (c.ats === "personio") {
    const x = new DOMParser().parseFromString(await (await fetch("/xml")).text(), "text/xml");
    x.querySelectorAll("position").forEach(p => keep({title: txt(p.querySelector("name")), location: txt(p.querySelector("office")),
      url: `https://${location.host}/job/${txt(p.querySelector("id"))}`, posted: txt(p.querySelector("createdAt"))}));
  } else if (c.ats === "teamtailor") {
    const x = new DOMParser().parseFromString(await (await fetch("/jobs.rss")).text(), "text/xml");
    x.querySelectorAll("item").forEach(i => keep({title: txt(i.querySelector("title")), location: "",
      url: txt(i.querySelector("link")), posted: txt(i.querySelector("pubDate"))}));
  } else {
    // greenhouse_eu, icims, jobvite: read the job links from the current page
    const pat = {greenhouse_eu: /\/jobs\/\d+/, icims: /\/jobs\/\d+\/[^/]+\/job/, jobvite: /\/job\/[A-Za-z0-9]+$/}[c.ats];
    const doc = c.ats === "icims" && document.querySelector("#icims_content_iframe")
      ? document.querySelector("#icims_content_iframe").contentDocument : document;
    doc.querySelectorAll("a").forEach(a => {
      const href = (a.getAttribute("href") || "").split("?")[0];
      if (!pat.test(href)) return;
      const row = a.closest("tr, div.row, .job-post, li") || a;
      const loc = row.querySelector(".jv-job-list-location, .location, [class*=location]")
        || [...row.querySelectorAll("span")].find(s => /Job Locations?/.test(txt(s.previousElementSibling)));
      keep({title: txt(a.querySelector("h3, p, .title") || a), location: txt(loc), url: new URL(href, location.href).href, posted: null});
    });
  }
  return out;
}
