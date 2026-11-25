# SETUP: onboarding a new user

Go step by step. After each step, wait for the user to confirm before moving on. Keep each message short, with numbered actions they can follow on their screen. Speak their language.

## §1 Welcome + what this covers (show this first, in their language)

Tell them in 6-8 lines:

**What I do for you**
- Every morning I check your Gmail for replies from companies and update your application tracker (a Google Sheet).
- I search for new jobs: directly on company career pages (Greenhouse, Lever, Ashby, Workable, Recruitee, Teamtailor, Personio) and on job boards, and I score each one 0-100 against your profile.
- You get one short report: the best jobs with links, plus follow-ups you should do.
- For the jobs you approve, I write a tailored CV and a short cover letter, and I can fill in the application form in your Chrome. You press Submit.

**What I don't do**
- I never apply, send emails or message anyone without your OK.
- I don't scrape LinkedIn. I can only read LinkedIn in your own Chrome while your laptop is open.
- Some career sites block me from the cloud (Workday, SmartRecruiters, some job boards). I check those in your Chrome or skip them, and I tell you which ones.
- I can't create accounts, solve CAPTCHAs or log in for you. I stop and ask.
- I don't invent anything in your CV. If something isn't in your CV or profile, it doesn't go in.
- The daily run uses your Claude plan's usage. I keep it lean, but it isn't free.

Then: "Setup takes about 15 minutes. Ready?"

## §2 Profile interview

Ask in 3-4 small batches (use a multiple-choice question tool where options make sense and the app has one; free text otherwise). Never ask for everything in one wall of text.

Batch A, basics:
- Full name (as it should appear on the CV, with diacritics), email, phone, city/country, LinkedIn URL.
- Their CV: ask them to upload it (PDF/DOCX) into this chat or the Project. If they have several versions, all of them. Read every one fully. This is the only source of facts for CVs.
- Photo on CV? (yes: ask for an image file; no: skip). In some countries photos are normal, in others not.

Batch B, target:
- Role families (multi-select): Product Manager / Product Owner; Growth / Monetization; Platform / Technical / API / AI PM; Business Analyst; Program / Project / Delivery Manager; Engineering (which stack?); Data / Analytics; Design; Other.
- Seniority range (e.g. mid → lead).
- Locations: on-site/hybrid in which city; remote in-country; remote Europe/EMEA; remote worldwide only with ≥N hours overlap with their time zone.
- Contract types: employee, B2B/contractor (do they have a company?), freelance.

Batch C, constraints and preferences:
- Industries they love / want to avoid. Any non-compete or legal restriction (industry + end date)?
- Salary/rate expectations (monthly or yearly, currency), and a floor. Used only to fill forms, never shared otherwise without asking.
- Languages they can work in.
- Cover letter style: default is short (80-120 words: excited about the role, why the company's mission appeals to them, hope to meet at an interview, nothing repeated from the CV). Offer to change it.
- CVs before approval? Default: no. Only write CVs for jobs they approve (saves usage).
- Referral contacts they're happy for you to suggest (e.g. "Ana at X").
- Hobbies worth showing for some companies (sports, outdoor, gaming...).

Batch D, the company list for the crawler:
- Ask: "Name 10-30 companies you'd love to work for, plus your city's main tech employers if you want." Also offer to propose a starter list for their city/country (do a quick web search). Start from `scripts/companies.example.json` only if they're in Romania.
- For each company, find its ATS and slug with a subagent (cheaper model where available): look at the careers page links (job-boards.greenhouse.io/<slug>, job-boards.eu.greenhouse.io/<slug>, jobs.lever.co/<slug>, jobs.ashbyhq.com/<slug>, apply.workable.com/<slug>, <slug>.recruitee.com, <slug>.teamtailor.com, <slug>.jobs.personio.com, jobs.smartrecruiters.com/<slug>, <host>.myworkdayjobs.com, <slug>.icims.com, jobs.jobvite.com/<slug>). Careers pages move (e.g. to a new domain); if the page has no ATS link, web-search `"<company>" careers greenhouse OR lever OR ashby OR smartrecruiters OR jobvite`. Group "A" = in their city (any open role is reported), "B" = remote employers (only last 14 days).
- **Validate every entry before saving it:** fetch the board (API or page) and record HTTP status and number of open jobs. Mark ✅ (works), ❌ (404/moved: find the new board), ⚠️ (couldn't open: say why). If the cloud network is blocked, validate in the browser (`browser_scan.js`) or on the user's computer. Never ask the user to check a link you can check yourself. Some gambling/betting domains are refused by both browsers: use their ATS board instead.

Save:
- `jobhunt/profile.md`: everything above, one fact per line, plus a full plain-text copy of their CV(s).
- `jobhunt/config.json`:
```json
{
  "name": "", "email": "", "phone": "", "city": "", "country": "", "timezone": "Europe/Bucharest",
  "language": "ro",
  "roles": [], "seniority": "", "locations": {"home_city": "", "remote_country": true, "remote_europe": true, "worldwide_min_overlap_h": 4},
  "contract_types": [], "avoid_industries": [], "restrictions": [{"what": "", "until": ""}],
  "salary": {"currency": "EUR", "period": "month", "expected": null, "floor": null},
  "cover_letter_style": "short", "cv_before_approval": false, "photo_on_cv": false,
  "tracker_spreadsheet_id": "", "computer_folder": "", "referrals": [], "job_boards": []
}
```
- `jobhunt/companies.json` (crawler format, see `scripts/companies.example.json`) and `jobhunt/filters.json` (regexes for their roles and their country/city, see `scripts/filters.example.json`; make the title regex match their role families and translate the city/country names they'd see in postings).
- `jobhunt/state.json` = `{"seen": {}}`.

Save to the first available place from SKILL.md §0 (project files tool → shared project folder on disk → connected computer folder → memory). If none of the first three exist, tell them: "Best results come from a Claude Project: in claude.ai click Projects → New project, name it e.g. 'Job hunt', and start this chat inside it." If they don't want one, save the profile to memory instead and keep the JSON files in memory too.

## §3 Connectors, click by click

Check what's already connected before asking: try a harmless read call (e.g. Gmail search for 1 thread, Sheets get on a known id, or look for the tools via ToolSearch). Only walk them through what's missing. Menu names in the Claude app change from time to time; if they can't find something, ask them to send a screenshot and guide from that.

**Gmail, Google Drive, Google Calendar (optional), Google Sheets**
1. Open claude.ai (or the Claude desktop app) → click your name/initials bottom-left → **Settings** → **Connectors**.
2. Click **Browse connectors** (or "Add connector"), search for **Gmail** → **Connect**.
3. Google opens a sign-in window: pick the Gmail account you use for job applications → **Allow** all requested permissions. (Claude only reads; it never sends without your OK in the chat.)
4. Repeat for **Google Drive** and **Google Sheets** (if Sheets isn't listed, skip it, Drive is enough as a fallback; see §4). Google Calendar is optional (interview reminders).
5. Back in this chat: open the **tools / "+" menu** next to the message box and make sure the connectors are switched **on** for this chat/project.
6. Tell me "done" and I'll test them.

Test: read their 3 most recent emails' subjects (show only subjects), and list 3 recent Drive files. If a test fails, the usual causes: the toggle is off in this chat, they connected a different Google account, or the org admin disabled connectors.

If they're on a Team/Enterprise plan and connectors are missing, their admin has to enable them (Admin settings → Connectors). On the Free plan connectors may not be available; tell them plainly.

**Claude in Chrome (needed only for applying and LinkedIn reading)**
1. In Google Chrome, open the Chrome Web Store and search for **Claude** (by Anthropic) → **Add to Chrome**.
2. Pin it (puzzle icon → pin), click it, sign in with the same Claude account.
3. When I open a site for the first time, Chrome asks for permission for that site: allow it.
4. Optional: in the Claude desktop app, connect a folder (e.g. Documents/Job hunt) with **Add folder** so I can save CVs straight onto your computer. Otherwise I give you the files as downloads in the chat.

## §4 Tracker sheet

Create the Google Sheet "Job hunt tracker" (Drive `create_file` with a Google Sheets mime type, or Sheets tools if available). If you can't create it, ask them: "Open sheets.new, name it 'Job hunt tracker', paste the link here."

Tabs and headers (row 1):
- **Tracker**: Company | Role | Channel | Applied on | Status | Last update | Next step | Notes | Apply link | Mail | Days without update
  - In K2: `=ARRAYFORMULA(IF(F2:F="";"";TODAY()-F2:F))` (use `;` or `,` depending on their sheet locale; test it). Never write column K afterwards.
  - Status values (in the user's language; English shown): "Interview / in process", "Applied", "To apply", "Rejected", "Closed", "Not applying". Translate once, save the exact strings in config, and always use them.
- **Seen jobs**: Date | Company | Role | Link | Decision | Fit | Reason
- **Companies** (optional mirror of companies.json for them to edit): Company | Group | Careers URL | ATS | Slug | Last checked | Roles found

If they already have a tracker, ask for its link, read the headers, and map columns instead of creating a new one. Save `tracker_spreadsheet_id` in config.

Import past applications: ask "Want me to scan your Gmail for the last 60 days and add the applications I find?" If yes, do it with a subagent and add rows as Applied / Rejected / Interview based on what the emails say.

## §5 Daily scheduled run

Explain: "I can run every morning while you sleep and send you a short report on your phone."
1. Ask what time (default ~07:40 in their timezone, not exactly on the hour).
2. Create the scheduled task with whatever scheduled-task tool the app has (e.g. `create_trigger`, scheduled tasks, CronCreate; load via ToolSearch if deferred) with a prompt like:
   "Run the job-hunt-agent skill in DAILY mode for <name>. Settings are in the Project files jobhunt/*. Send the report with a push notification."
   If that tool isn't available in their app, tell them to create it from the app's scheduled tasks section with the same prompt.
3. Tell them which approval setting the task got. If runs will stop to ask for approval, say they can switch the task to automatic approval in its settings, if their organization allows it.
4. Suggest: on weekends or once they get a job, they can say "pause the daily run" and you disable it.

## §6 Copy the crawler into their Project

Copy `scripts/jobscan.py` and `scripts/browser_scan.js` into `jobhunt/` in the Project (or the shared folder) too, so scheduled runs have it even if the skill folder isn't mounted. Daily runs write it to disk, run it, and save `state.json` back.

## §7 Summary at the end

Show:
- ✅ / ❌ for: profile, CV, Gmail, Drive, Sheets, Chrome, tracker link, scheduled run (time).
- How to talk to the agent:
  - "start": I'm at my laptop (saves files, checks LinkedIn)
  - "apply to 1, 3" or "all": prepare CV + cover letter and fill the forms
  - "change my CV for 2: ..." to request edits
  - "add company X" or "remove company Y" to change the crawler list
  - "update my profile: ..." to change targets, salary, restrictions
  - "pause / resume the daily run"
- Offer: "Want me to do the first search right now?"
