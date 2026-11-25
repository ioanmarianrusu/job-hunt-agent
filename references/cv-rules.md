# CV and cover letter rules

## CV (PDF, 1-2 pages)
- Facts only from the user's CV(s) and `profile.md`. Never invent employers, titles, dates, numbers, tools or skills. If the job wants something the user doesn't have, don't add it: mention the gap to the user instead.
- Tailor: summary (3-4 lines, aimed at this job), order of sections, which bullets come first, keywords from the posting that are true for the user.
- Name exactly as in the profile (keep diacritics). Photo top-right (cropped round) only if `photo_on_cv` is true and the posting doesn't ask for no photo.
- Language = the posting's language.
- Clean typography, no em dashes, no tables that break ATS parsing, selectable text. With reportlab, escape "&" as "&amp;".
- Gaps/sabbaticals: present them exactly as the user worded them in the profile.
- Load the `pdf` skill (or `docx` if they want Word) before building.
- File names: `<First>_<Last>_CV_<Company>.pdf`.

## Cover letter (PDF)
- Default style "short": 80-120 words. Only: excitement about the role; what the company's mission is (concretely, named) and why it appeals; hope to meet at an interview. Every sentence must make sense on its own. Nothing repeated from the CV.
- If `cover_letter_style` in config says otherwise, follow it.
- File name: `<First>_<Last>_Cover_Letter_<Company>.pdf`.
- Save `job_description.txt` (the posting text) next to them.
