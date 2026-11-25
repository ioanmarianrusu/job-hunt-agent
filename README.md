# Job Hunt Agent (Claude skill)

A job-search assistant for Claude. You set it up once (about 15 minutes) and then:

- every morning it reads your Gmail for replies from companies and updates your application tracker (a Google Sheet);
- it looks for new jobs directly on company career pages (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday, Teamtailor, Personio, Recruitee, iCIMS, Jobvite) and on job boards, and scores each one 0-100 against your profile;
- you get one short report with the best jobs and the follow-ups to do;
- for the jobs you approve, it writes a tailored CV and a short cover letter and can fill in the application form in Chrome. You press Submit.

It never applies, sends an email or messages anyone without your OK, and never invents anything in your CV.

## Install

1. Download this repository as a zip: **Code → Download ZIP**.
2. In [claude.ai](https://claude.ai): **Settings → Capabilities → Skills → Upload skill**, and pick the zip. (On a Team/Enterprise plan your admin may need to enable skills.)
3. Recommended: create a Claude **Project** (e.g. "Job hunt") and start the chat inside it, so your profile and tracker settings are kept between chats.
4. Write: **"I want to start my job search"** (or in your own language, e.g. „vreau să încep căutarea de job"). The setup interview starts.

You'll need the Gmail, Google Drive and Google Sheets connectors; the setup walks you through connecting them. Claude in Chrome is only needed for filling in applications and reading LinkedIn.

## What's inside

| Path | What it is |
|---|---|
| `SKILL.md` | The skill's instructions (modes: SETUP, DAILY, START, APPLY) |
| `references/setup.md` | The onboarding interview, connectors, tracker template, daily schedule |
| `references/daily-run.md` | The daily run: Gmail → tracker, search & scoring, report, applying |
| `references/cv-rules.md` | Rules for tailored CVs and cover letters |
| `scripts/jobscan.py` | Crawler for company ATS boards (no AI, cheap). `python3 jobscan.py --help` |
| `scripts/browser_scan.js` | Browser fallback when the network blocks the ATS APIs (e.g. in a cloud sandbox) |
| `scripts/companies.example.json`, `filters.example.json` | Starter company list and filters (Romania / Cluj); setup builds your own |

## Notes

- The daily run uses your Claude plan's usage. It's kept lean, but it isn't free.
- Some career sites block automated access; the agent then checks them in your browser or covers them through job boards, and tells you which ones.
- Feedback and fixes are welcome: open an issue.
