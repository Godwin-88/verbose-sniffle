"""
job_hunter/ai_engine.py

OpenAI-compatible AI engine — free-tier providers (Groq / OpenRouter / Together / Ollama).
Generates:
  • Jobs       — cover letter + tailored resume insights
  • Scholarships — motivation letter (SOP) + research proposal + resume insights
  • Markdown polisher for all outputs
  • Full assembled application package (.md)

pip install openai python-dotenv
"""

import os, re, json, textwrap, datetime
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


# ════════════════════════════════════════════════════════════════════════════
# PROVIDER — auto-detected from .env
# Priority: Groq → OpenRouter → Together → Ollama
# ════════════════════════════════════════════════════════════════════════════
def _build_client() -> tuple:
    if os.getenv("GROQ_API_KEY"):
        return (
            OpenAI(api_key=os.environ["GROQ_API_KEY"],
                   base_url="https://api.groq.com/openai/v1"),
            os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        )
    if os.getenv("OPENROUTER_API_KEY"):
        return (
            OpenAI(
                api_key=os.environ["OPENROUTER_API_KEY"],
                base_url="https://openrouter.ai/api/v1",
                default_headers={"HTTP-Referer": "jobhunter-ke", "X-Title": "JobHunterKE"},
            ),
            os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"),
        )
    if os.getenv("TOGETHER_API_KEY"):
        return (
            OpenAI(api_key=os.environ["TOGETHER_API_KEY"],
                   base_url="https://api.together.xyz/v1"),
            os.getenv("TOGETHER_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"),
        )
    return (
        OpenAI(api_key="ollama",
               base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434") + "/v1"),
        os.getenv("OLLAMA_MODEL", "llama3.1"),
    )


client, MODEL = _build_client()


def _chat(system: str, user: str,
          max_tokens: int = 2048, temperature: float = 0.7) -> str:
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=max_tokens, temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:json|markdown)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


# ════════════════════════════════════════════════════════════════════════════
# ── MARKDOWN POLISHER ────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def polish_markdown(md: str) -> str:
    """Post-processes AI Markdown output for clean formatting."""
    if not md:
        return ""
    md = _strip_fences(md)
    md = re.sub(r"^[*+] ", "- ", md, flags=re.MULTILINE)       # normalise bullets
    md = re.sub(r"([^\n])\n(#{1,6} )", r"\1\n\n\2", md)        # blank line before heading
    md = re.sub(r"(#{1,6} [^\n]+)\n([^\n#\-\*\d\>])", r"\1\n\n\2", md)  # blank line after heading
    md = re.sub(r"(---+)\n([^\n])", r"\1\n\n\2", md)            # blank line after hr
    md = re.sub(r"\n{3,}", "\n\n", md)                          # max 2 blank lines
    return md.strip() + "\n"


# ════════════════════════════════════════════════════════════════════════════
# ── JOB DOCUMENTS ────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def generate_cover_letter(job: dict, profile: dict) -> str:
    system = textwrap.dedent("""\
        You are a seasoned Kenyan career coach and professional writer.
        Output clean Markdown only. Flowing paragraphs — no bullets inside the letter.
        Avoid clichés. Be specific, confident, human.
    """)
    user = textwrap.dedent(f"""\
        Write a tailored cover letter for this job.

        ## PROFILE
        {json.dumps(profile, indent=2)}

        ## JOB
        Title: {job.get('title')}
        Company: {job.get('company')}
        Location: {job.get('location','Kenya')}
        Deadline: {job.get('deadline','ASAP')}
        Description:
        {(job.get('full_description') or job.get('snippet',''))[:2500]}

        ## FORMAT (output exactly this Markdown structure)
        # {profile.get('name','')}
        {profile.get('email','')} · {profile.get('phone','')} · {profile.get('location','Nairobi, Kenya')}
        {datetime.date.today().strftime('%d %B %Y')}

        ---

        **{job.get('company','')}**

        Dear Hiring Manager,

        [Hook — name the role, show you know the org]

        [2–3 measurable achievements mapped to requirements]

        [Why this company/sector specifically]

        [Confident closing with call to action]

        Yours sincerely,

        **{profile.get('name','')}**
        {(profile.get('experience') or [{}])[0].get('title','')}

        Return ONLY the Markdown. No outer code fences.
    """)
    return polish_markdown(_chat(system, user, max_tokens=1200))


def tailor_resume(job: dict, profile: dict) -> dict:
    system = textwrap.dedent("""\
        You are an ATS optimisation expert and Kenyan CV strategist.
        Return ONLY a single valid JSON object — no prose, no fences.
    """)
    user = textwrap.dedent(f"""\
        Return ONE JSON object:
        {{
          "match_score": <0-100>,
          "summary": "<2-3 sentence tailored summary>",
          "highlighted_skills": ["skill1",...],
          "keywords": ["ats_phrase1",...],
          "bullet_rewrites": {{"<original>": "<rewritten with verb + numbers>"}},
          "markdown": "<full Markdown resume section>"
        }}

        markdown template:
        ## Tailored Resume — {job.get('title')} @ {job.get('company')}
        ### Summary
        [summary]
        ### Key Skills
        [skills inline]
        ### Experience Highlights
        - [5 rewritten bullets]
        ### ATS Keywords
        [keywords]
        *Match: X%*

        ## PROFILE
        {json.dumps(profile, indent=2)}

        ## JOB
        {job.get('title')} @ {job.get('company')}
        {(job.get('full_description') or job.get('snippet',''))[:2500]}

        Rules: max 5 rewrites, past-tense verbs, quantify, return ONLY JSON.
    """)
    raw = _strip_fences(_chat(system, user, max_tokens=2000, temperature=0.3))
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"\{[\s\S]+\}", raw)
        try:
            data = json.loads(m.group()) if m else _fallback_resume(raw)
        except Exception:
            data = _fallback_resume(raw)
    if "markdown" in data:
        data["markdown"] = polish_markdown(str(data["markdown"]))
    return data


def _fallback_resume(raw: str) -> dict:
    return {"match_score": 0, "summary": "Parse error.", "highlighted_skills": [],
            "keywords": [], "bullet_rewrites": {},
            "markdown": f"## Resume Insights\n\n_Parse error_\n\n```\n{raw[:300]}\n```\n"}


# ════════════════════════════════════════════════════════════════════════════
# ── SCHOLARSHIP DOCUMENTS ────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def generate_motivation_letter(scholarship: dict, profile: dict) -> str:
    """
    Generates a full Statement of Purpose / Motivation Letter for a scholarship.
    Returns polished Markdown.
    Structure:
      - Opening: hook + specific programme name
      - Academic background & achievements
      - Professional experience & impact
      - Research interests / future goals (aligned to funder's mandate)
      - Why this specific scholarship / university / country
      - How you will use it back home (development impact)
      - Closing
    """
    level    = scholarship.get("level", "masters")
    funder   = scholarship.get("funder", scholarship.get("company", ""))
    country  = scholarship.get("funder_country", "")
    coverage = scholarship.get("coverage", "")
    mandate  = _funder_mandate(funder, country)

    system = textwrap.dedent("""\
        You are an elite scholarship application coach who has helped 500+ Africans
        win fully-funded scholarships (Chevening, DAAD, Fulbright, MEXT, etc.).
        You write compelling Statements of Purpose that are:
        - Deeply personal yet professionally grounded
        - Explicitly aligned with the funder's mandate and values
        - Specific about how the scholarship connects to the applicant's career plan
        - Honest about Kenya/Africa context without being generic or pitiful
        - 700-900 words, 4-5 paragraphs
        Output clean Markdown only. No bullets in the letter body.
    """)

    user = textwrap.dedent(f"""\
        Write a Statement of Purpose / Motivation Letter for this scholarship application.

        ## SCHOLARSHIP
        Name:         {scholarship.get('title')}
        Funder:       {funder}
        Country:      {country}
        Level:        {level}
        Coverage:     {coverage}
        Field:        {scholarship.get('field', 'applicants field from profile')}
        Funder Mandate/Values: {mandate}
        Description:
        {(scholarship.get('full_description') or scholarship.get('snippet',''))[:2000]}

        ## CANDIDATE PROFILE
        {json.dumps(profile, indent=2)}

        ## REQUIRED MARKDOWN STRUCTURE
        # Statement of Purpose
        ## {scholarship.get('title','')}
        **Applicant:** {profile.get('name','')} · {profile.get('email','')}
        **Date:** {datetime.date.today().strftime('%d %B %Y')}

        ---

        [Opening paragraph — strong hook. Name the exact scholarship. Connect
         your present work to the opportunity. Do NOT start with "I am writing to".]

        [Academic Excellence paragraph — degrees, awards, thesis/research,
         quantified achievements. Connect to the field of study.]

        [Professional Impact paragraph — roles, measurable outcomes, problems
         you worked on in the Kenyan/African context.]

        [Research/Future Goals paragraph — what you will study, at which university
         if known, and why. Align explicitly with the funder's mandate: {mandate}]

        [Development Impact paragraph — specific plan to apply knowledge back in
         Kenya. Be concrete: sector, institution, policy, community.]

        [Closing — why THIS scholarship above others. Acknowledge the funder's
         legacy. Confident, grateful, forward-looking.]

        Output ONLY the Markdown. No outer code fences.
    """)

    raw = _chat(system, user, max_tokens=1500, temperature=0.72)
    return polish_markdown(raw)


def generate_research_proposal(scholarship: dict, profile: dict) -> str:
    """
    Generates a concise research proposal for PhD / research scholarships.
    Returns polished Markdown. (~500 words)
    """
    system = textwrap.dedent("""\
        You are an academic writing expert specialising in African postgraduate research.
        Write a concise, compelling research proposal in clean Markdown.
        Be specific about methodology, relevance to Kenya/Africa, and contribution to knowledge.
    """)
    user = textwrap.dedent(f"""\
        Write a research proposal for this PhD/research scholarship application.

        ## SCHOLARSHIP
        {scholarship.get('title')}
        Funder: {scholarship.get('funder', scholarship.get('company',''))}
        Field: {scholarship.get('field', 'Derive from profile')}
        Description: {(scholarship.get('full_description') or scholarship.get('snippet',''))[:1500]}

        ## CANDIDATE PROFILE
        {json.dumps(profile, indent=2)}

        ## STRUCTURE (output this Markdown exactly)
        ## Research Proposal
        **Title:** [Proposed Research Title]
        **Candidate:** {profile.get('name','')}
        **Date:** {datetime.date.today().strftime('%d %B %Y')}

        ### Background and Problem Statement
        [2 paragraphs — the problem in the Kenyan/African context, why it matters now]

        ### Research Objectives
        - Objective 1
        - Objective 2
        - Objective 3

        ### Methodology
        [1-2 paragraphs — research design, data sources, analytical approach]

        ### Expected Outcomes and Significance
        [1 paragraph — contribution to knowledge + practical impact]

        ### Timeline (indicative)
        | Phase | Activity | Duration |
        |-------|----------|----------|
        | 1 | Literature review | Months 1-3 |
        | 2 | Data collection | Months 4-9 |
        | 3 | Analysis | Months 10-15 |
        | 4 | Writing & submission | Months 16-18 |

        Output ONLY the Markdown. No outer fences.
    """)
    raw = _chat(system, user, max_tokens=1200, temperature=0.6)
    return polish_markdown(raw)


def generate_scholarship_resume_insights(scholarship: dict, profile: dict) -> dict:
    """
    Tailors the CV for a scholarship application — different emphasis from jobs:
    - Academic achievements come first
    - Leadership and community service weighted heavily
    - Research publications / presentations
    - Development impact framing
    Returns same dict structure as tailor_resume() for DB/dashboard compat.
    """
    system = textwrap.dedent("""\
        You are a scholarship application strategist specialising in competitive awards
        (Chevening, DAAD, Fulbright, Commonwealth, MEXT, etc.).
        Return ONLY valid JSON. No prose, no fences.
    """)
    funder  = scholarship.get("funder", scholarship.get("company",""))
    mandate = _funder_mandate(funder, scholarship.get("funder_country",""))

    user = textwrap.dedent(f"""\
        Analyse this candidate's fit for the scholarship and return ONE JSON object:
        {{
          "match_score": <0-100>,
          "summary": "<2-3 sentence academic/professional summary tailored for scholarship>",
          "highlighted_skills": ["skill1", ...],
          "keywords": ["selection_criterion1", ...],
          "bullet_rewrites": {{"<original>": "<rewritten for scholarship emphasis>"}},
          "strengths": ["strength1", "strength2", "strength3"],
          "gaps": ["gap1", "gap2"],
          "markdown": "<full Markdown CV tailoring section>"
        }}

        markdown template:
        ## CV Tailoring — {scholarship.get('title')}
        ### Scholarship Summary
        [summary]
        ### Strongest Qualifications for This Award
        - [bullet1]
        - [bullet2]
        - [bullet3]
        ### Selection Criteria Alignment
        | Criterion | Evidence from Your Profile |
        |-----------|---------------------------|
        | [criterion] | [evidence] |
        ### Suggested CV Bullet Rewrites
        [rewrites]
        ### Gaps to Address in Motivation Letter
        [gaps]
        *Match: X%*

        ## SCHOLARSHIP
        Name:    {scholarship.get('title')}
        Funder:  {funder} ({scholarship.get('funder_country','')})
        Level:   {scholarship.get('level','')}
        Mandate: {mandate}
        Description: {(scholarship.get('full_description') or scholarship.get('snippet',''))[:2000]}

        ## CANDIDATE PROFILE
        {json.dumps(profile, indent=2)}

        Return ONLY JSON. No fences.
    """)
    raw = _strip_fences(_chat(system, user, max_tokens=2000, temperature=0.3))
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"\{[\s\S]+\}", raw)
        try:
            data = json.loads(m.group()) if m else _fallback_resume(raw)
        except Exception:
            data = _fallback_resume(raw)
    if "markdown" in data:
        data["markdown"] = polish_markdown(str(data["markdown"]))
    return data


# ════════════════════════════════════════════════════════════════════════════
# ── FULL DOCUMENT ASSEMBLERS ─────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def assemble_application_doc(job: dict, profile: dict,
                              cover_letter_md: str, resume_data: dict) -> str:
    """Assemble job application package as one Markdown document."""
    today = datetime.date.today().strftime("%d %B %Y")
    return polish_markdown(textwrap.dedent(f"""\
        <!--
          Job Hunter KE — Job Application Package
          Generated : {today}
          Role      : {job.get('title')} @ {job.get('company')}
          Source    : {job.get('source')} | {job.get('url')}
          Match     : {resume_data.get('match_score','?')}%
          Model     : {MODEL}
        -->

        # Application Package — {job.get('title')}

        > **Company:** {job.get('company','—')}
        > **Location:** {job.get('location','Kenya')}
        > **Deadline:** {job.get('deadline','TBC')}
        > **Source:** [{job.get('source','')}]({job.get('url','#')})
        > **Generated:** {today}

        ---

        ## Part 1 — Cover Letter

        {cover_letter_md}

        ---

        ## Part 2 — Resume Tailoring Guide

        {resume_data.get('markdown','_Resume insights not available._')}

        ---

        ## Part 3 — Application Checklist

        - [ ] Read the full job description at the source link above
        - [ ] Update CV with bullet rewrites from Part 2
        - [ ] Add ATS keywords naturally to CV summary and skills sections
        - [ ] Confirm application method (email / portal / physical)
        - [ ] Attachments: CV (PDF), Cover Letter (PDF), Certificates
        - [ ] Submit before: **{job.get('deadline','TBC')}**
        - [ ] Follow up in 7–10 business days if no response

        ---

        *Job Hunter KE · Model: {MODEL} · {today}*
    """))


def assemble_scholarship_doc(scholarship: dict, profile: dict,
                              motivation_md: str,
                              resume_data: dict,
                              research_proposal_md: Optional[str] = None) -> str:
    """
    Assemble a complete scholarship application package as one Markdown document.
    Includes: motivation letter + CV tailoring + research proposal (if PhD) + checklist.
    """
    today    = datetime.date.today().strftime("%d %B %Y")
    funder   = scholarship.get("funder", scholarship.get("company",""))
    level    = scholarship.get("level","")
    is_phd   = "phd" in level.lower() if level else False
    coverage = scholarship.get("coverage","")
    eligible = scholarship.get("eligible_countries","")

    proposal_section = ""
    if is_phd and research_proposal_md:
        proposal_section = textwrap.dedent(f"""\
            ---

            ## Part 3 — Research Proposal

            {research_proposal_md}

        """)

    strengths = resume_data.get("strengths", [])
    gaps      = resume_data.get("gaps", [])
    strengths_md = "\n".join(f"- {s}" for s in strengths) if strengths else "_See CV tailoring section_"
    gaps_md      = "\n".join(f"- {g}" for g in gaps) if gaps else "_None identified_"

    checklist = _scholarship_checklist(scholarship)

    return polish_markdown(textwrap.dedent(f"""\
        <!--
          Job Hunter KE — Scholarship Application Package
          Generated  : {today}
          Scholarship: {scholarship.get('title')}
          Funder     : {funder} ({scholarship.get('funder_country','')})
          Level      : {level}
          Funding    : {scholarship.get('funding_type','unknown')}
          Match      : {resume_data.get('match_score','?')}%
          Model      : {MODEL}
        -->

        # Scholarship Application Package

        > **Scholarship:** {scholarship.get('title','—')}
        > **Funder:** {funder}
        > **Country:** {scholarship.get('funder_country','—')}
        > **Level:** {level}
        > **Funding:** {scholarship.get('funding_type','unknown').replace('_',' ').title()}
        > **Coverage:** {coverage or '—'}
        > **Eligible Countries:** {eligible or '—'}
        > **Deadline:** {scholarship.get('deadline','TBC')}
        > **Source:** [{scholarship.get('source','')}]({scholarship.get('url','#')})
        > **Match Score:** {resume_data.get('match_score','?')}%
        > **Generated:** {today}

        ---

        ## Part 1 — Statement of Purpose / Motivation Letter

        {motivation_md}

        ---

        ## Part 2 — CV Tailoring Guide

        {resume_data.get('markdown','_CV insights not available._')}

        ### Key Strengths for This Award
        {strengths_md}

        ### Gaps to Address
        {gaps_md}

        {proposal_section}---

        ## Part {4 if is_phd and research_proposal_md else 3} — Application Checklist

        {checklist}

        ---

        *Job Hunter KE · Model: {MODEL} · {today}*
    """))


def _scholarship_checklist(scholarship: dict) -> str:
    """Generate a scholarship-specific checklist."""
    level    = (scholarship.get("level") or "").lower()
    country  = scholarship.get("funder_country","")
    deadline = scholarship.get("deadline","TBC")
    url      = scholarship.get("url","#")
    funder   = scholarship.get("funder", scholarship.get("company",""))

    base = textwrap.dedent(f"""\
        - [ ] Read full scholarship details at [official page]({url})
        - [ ] Confirm you meet ALL eligibility criteria (nationality, age, academic level)
        - [ ] Request official transcripts from your university (allow 2–4 weeks)
        - [ ] Request 2–3 reference letters from academic/professional referees
        - [ ] Update CV to emphasise academic achievements and community leadership
        - [ ] Prepare certified copies of degree certificates
        - [ ] Obtain English language test score (IELTS/TOEFL) if required
        - [ ] Write and polish motivation letter (Part 1 above)
    """)

    if "phd" in level:
        base += "- [ ] Identify and contact potential supervisors at target universities\n"
        base += "- [ ] Finalise research proposal (Part 3 above)\n"
        base += "- [ ] Get research proposal reviewed by current supervisor\n"

    if country in ("Japan", "South Korea", "China"):
        base += f"- [ ] Apply via the {country} Embassy in Nairobi (Embassy route)\n"
        base += "- [ ] Prepare passport-sized photographs as required\n"
        base += "- [ ] Check if medical examination is required\n"

    if country in ("UK", "USA", "Australia", "Canada"):
        base += "- [ ] Prepare for interview (many require Skype/Teams interview)\n"
        base += "- [ ] Research 2–3 potential universities/supervisors\n"

    base += f"- [ ] Submit application before **{deadline}**\n"
    base += "- [ ] Save confirmation email / submission receipt\n"
    base += "- [ ] Follow up with the scholarship office 2 weeks after deadline\n"

    return base


# ════════════════════════════════════════════════════════════════════════════
# ── FUNDER MANDATE LOOKUP ────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def _funder_mandate(funder: str, country: str) -> str:
    """Returns the mandate/values string to inject into prompts."""
    f = funder.lower()
    mandates = {
        "chevening":        "future global leaders with diplomatic engagement, networking, influencing change",
        "commonwealth":     "development impact in Commonwealth countries, academic excellence",
        "daad":             "academic excellence, research, Germany as a hub of science and innovation",
        "fulbright":        "mutual understanding between USA and the world, academic excellence, leadership",
        "mext":             "Japan's international education cooperation, academic and technical excellence",
        "australia awards": "sustainable development, leadership in the Indo-Pacific and Africa",
        "vlir-uos":         "development-relevant research, North-South collaboration, social impact",
        "swedish institute": "global professionals, sustainability, democratic values, Sweden's foreign policy",
        "eiffel":           "academic excellence, France's scientific and economic influence",
        "chevening":        "UK foreign policy, leadership, global influence, networking",
        "aga khan":         "pluralism, civil society, development in the Global South",
        "mastercard":       "economically disadvantaged African youth, leadership, community transformation",
        "rotary":           "peace, conflict resolution, international understanding",
        "ford foundation":  "social justice, equity, human rights, community leadership",
        "heinrich böll":    "ecology, democracy, human rights, feminist perspectives",
        "open society":     "open society values, democracy, anti-corruption, human rights",
    }
    for key, mandate in mandates.items():
        if key in f:
            return mandate
    # Fallback by country
    country_mandates = {
        "Germany":     "academic excellence, research innovation, development cooperation",
        "Japan":       "technical excellence, Japan-Africa cooperation, cultural exchange",
        "Australia":   "sustainable development, leadership, regional stability",
        "Canada":      "multilateralism, development, diversity and inclusion",
        "Netherlands": "water management, agriculture, professional capacity development",
        "Sweden":      "sustainability, gender equality, democratic governance",
        "France":      "academic excellence, Francophonie, scientific research",
        "Belgium":     "development-relevant research, North-South partnership",
        "Turkey":      "cultural diplomacy, development, South-South cooperation",
        "China":       "Belt and Road, South-South cooperation, technical development",
        "South Korea": "economic development, Korean Wave, technical education",
    }
    return country_mandates.get(country, "academic excellence, leadership, development impact")


# ════════════════════════════════════════════════════════════════════════════
# ── ENRICHER ─────────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def enrich_description(record: dict) -> dict:
    """Fetch and parse full description from URL for any record type."""
    import requests
    from bs4 import BeautifulSoup
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r    = requests.get(record["url"], headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["nav","footer","script","style","aside","header"]):
            tag.decompose()
        selectors = [".job-description","#job-description",".description","article",
                     ".content","main","div[class*='detail']","div[class*='job']","section"]
        body = ""
        for sel in selectors:
            el = soup.select_one(sel)
            if el and len(el.get_text()) > 200:
                body = el.get_text(separator="\n", strip=True)
                break
        if not body:
            body = soup.get_text(separator="\n", strip=True)[:3000]
        record["full_description"] = body[:4000]
    except Exception:
        record["full_description"] = record.get("snippet","")
    return record


# Alias kept for backwards compat with scrapers.py
enrich_job_description = enrich_description


# ════════════════════════════════════════════════════════════════════════════
# ── FULL PIPELINES ───────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def generate_application_package(job: dict, profile: dict) -> dict:
    """
    Full job pipeline: enrich → cover letter → resume → assemble.
    Returns: {cover_letter_md, tailored_resume, full_doc_md, match_score}
    """
    job      = enrich_description(job)
    cover_md = generate_cover_letter(job, profile)
    resume   = tailor_resume(job, profile)
    full_doc = assemble_application_doc(job, profile, cover_md, resume)
    return {
        "cover_letter_md": cover_md,
        "tailored_resume": resume,
        "full_doc_md":     full_doc,
        "match_score":     resume.get("match_score", 0),
    }


def generate_scholarship_package(scholarship: dict, profile: dict) -> dict:
    """
    Full scholarship pipeline:
      enrich → motivation letter → resume insights
             → research proposal (PhD only) → assemble.

    Returns:
    {
      motivation_letter:   str  (Markdown)
      research_proposal:   str  (Markdown, PhD only)
      tailored_resume:     dict (includes .markdown)
      full_doc_md:         str  (complete application package Markdown)
      match_score:         int
    }
    """
    scholarship = enrich_description(scholarship)

    motivation  = generate_motivation_letter(scholarship, profile)
    resume      = generate_scholarship_resume_insights(scholarship, profile)

    level = (scholarship.get("level") or "").lower()
    proposal = None
    if "phd" in level or "research" in level:
        proposal = generate_research_proposal(scholarship, profile)

    full_doc = assemble_scholarship_doc(
        scholarship, profile, motivation, resume, proposal
    )

    return {
        "motivation_letter":  motivation,
        "research_proposal":  proposal or "",
        "tailored_resume":    resume,
        "full_doc_md":        full_doc,
        "match_score":        resume.get("match_score", 0),
    }
