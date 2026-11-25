# DAILY run, START, APPLY

Load `jobhunt/config.json`, `jobhunt/profile.md` first. Respect every constraint in them (they override this file). Today's date comes from the environment. A scheduled run is unattended: don't ask questions, make reasonable choices and say what you assumed.

## Phase 0: Gmail → tracker sync

1. Read the Tracker tab (whole range). The user may sort the sheet: always locate rows by company + role, never by remembered row numbers. Read columns "Next step"/"Notes": the user sometimes leaves instructions for you there. Act on them.
2. One sonnet subagent searches Gmail (read-only):
   `newer_than:2d (application OR applying OR interview OR candidate OR "next step" OR unfortunately OR regret OR "moving forward" OR offer OR recruiter OR greenhouse OR teamtailor OR workable OR ashby OR lever OR icims OR jobvite OR successfactors OR workday OR recruitee OR bamboohr OR personio) -category:promotions` plus `in:sent newer_than:2d`, adding the local-language words for application/interview (e.g. RO: candidatura, interviu). Ignore newsletters and job alerts. It returns per relevant thread: company | role | date | type (rejection / real interview step from a person / application confirmation / viewed / other) | 1-line summary (interview time in the user's timezone) | thread link.
3. Update the tracker yourself:
   - existing row: Status (rejection → Rejected; real interview step → Interview), Last update = email date, Next step, append to Notes, Mail = `=HYPERLINK("<link>";"mail")` (separator per locale).
   - "application viewed" only touches Last update and Notes.
   - confirmation for a company not in the sheet: append a row as Applied.
   - Automated mails (validation codes, consent forms, "we received your application") never make a row "Interview".
   - Batch the writes; on a quota error wait 60 s and retry. Read back the changed rows.
4. "Tracker today": what changed, interviews in the next 7 days, follow-ups due (Applied with 7+ days without update). If nothing changed, one line.

## Phase 1: search and score

Give every subagent: the list of "company | role" already in the tracker and the seen-jobs URLs, so they skip them; the user's role families, locations, seniority, constraints; and the profile summary for scoring.

1. **Crawler (cheap, no AI):** write `jobscan.py`, `companies.json`, `filters.json`, `state.json` from the Project to a work dir, write `tracker_pairs.txt` ("Company | Role" per line) and `seen_links.txt`, then run
   `python3 jobscan.py --companies companies.json --filters filters.json --tracker tracker_pairs.txt --seen seen_links.txt --state state.json --out out`
   `pip install requests` if needed. If it exits with code 3 (`NETWORK_BLOCKED`), follow "Running the crawler when the network is blocked" in SKILL.md: run it on the user's computer, or collect the jobs in the browser with `browser_scan.js` and rerun with `--raw-in raw.json`. Companies on an ATS the script can't read, or whose site the browser refuses, get checked through their ATS board or job boards, never handed to the user. Afterwards save `state.json` back where the setup lives.
   Supported ATS: greenhouse, greenhouse_eu, lever, ashby, workable, smartrecruiters, recruitee, personio, teamtailor, workday, icims (`slug` = the subdomain before `.icims.com`, or `host`), jobvite (`slug` from `jobs.jobvite.com/<slug>/jobs`; Jobvite gives no posting date).
   A sonnet subagent scores every item in `out/candidates.json` from the description already downloaded.
2. **Job boards (1 sonnet subagent):** boards in `config.job_boards` (good defaults for EU tech/product: euremotejobs.com, builtin.com (country page), remoterocketship.com, workinproduct.eu, productjobsanywhere.com, plus 3-4 web searches for "<role> <city>" and "<role> remote <country>" in the last week). For each candidate it must open the company's own careers page/ATS and confirm the job is listed and open. Unverified → max fit 60 and never recommended.
3. Fit score 0-100: role family match, seniority, the user's strong domains vs. gaps, location eligibility, language requirements, constraints. 1-line reason in the user's language.
4. Once a week (Mondays), widen: sweep all companies in the list via their careers pages, plus extra boards. If a daily run finds fewer than 3 candidates, widen too.

## Report

- ≥ 70: recommended, ranked. 60-69: "stretch", link + 1 line, no CV. Max 3 "notable exclusions".
- If `cv_before_approval` is true, write CV + cover letter for ≥ 70 now (rules in `cv-rules.md`); otherwise don't.
- Append recommended + stretch to the Tracker in ONE append: Status "To apply", Last update today, Next step "Waiting for your approval", Notes "Agent <date>: fit <n>/100: <why>", Apply link. Append every evaluated job to Seen jobs in one append. Read back.
- Message format (user's language):
  1. Tracker today
  2. Home city today: what the crawler found there (or how many companies were checked)
  3. `# | Company: Role | location/type | fit | why | link`, then stretch, then exclusions
  4. Stats (applications in the last 14 days, responses), what you widened, 1-3 concrete actions (follow-ups, referral angles from `config.referrals`), "URGENT" for jobs closing soon or posted < 24 h ago
  5. Closing line: "When you're at your laptop write 'start'. Then tell me 'apply to 1, 3' (or 'all') and I'll prepare everything."
- Send with the app's message tool; on scheduled runs also a push notification if a push tool exists (first sentence = headline). If nothing qualifies, say so in 2-3 lines and how you'll widen tomorrow.

## START (user is at the laptop)

1. If CVs exist and a computer folder is connected (`config.computer_folder`), write them there (one subfolder per job: `<date>_<Company>_<Role>`). Otherwise send them as downloads.
2. If Claude in Chrome is available: a sonnet subagent reads (read-only, never clicks Apply/Save/Message) their LinkedIn job tracker https://www.linkedin.com/jobs-tracker/ (Saved, In progress, Applied; scroll and wait ~2 s per page), plus a quick LinkedIn Jobs search (past 24 h) for their role families × locations, plus the careers pages that were blocked from the cloud. Saved jobs not yet evaluated → score them. Applied ones not in the tracker → add as Applied. "Clicked apply" → ask the user if they finished. Note 1st-degree connections shown as poster/hiring team.
3. Ask which jobs to apply to.

## APPLY (only after "apply to …" for specific jobs)

1. Write the tailored CV + cover letter (`cv-rules.md`) if not done; show them briefly; accept edit requests.
2. In Claude in Chrome open the application page, fill it from the profile (contact details, LinkedIn, work authorization as stated by the user, salary from config; if unclear, ask). Upload the CV and cover letter yourself.
3. Logins, account creation, CAPTCHAs: stop for that job and ask. Questions you can't answer truthfully from the profile: draft an answer and ask.
4. Leave the final Submit to the user unless they explicitly tell you to submit. After they confirm: tracker → Applied, Applied on + Last update = today, Next step "Waiting for reply", Notes: what was submitted (salary etc.); Seen jobs → "applied".
5. Summary: applied / blocked (why) / next steps.
