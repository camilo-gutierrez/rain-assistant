"""Built-in director templates for Rain Autonomous Directors.

These are NOT auto-created. They serve as a library of pre-configured
director templates that users can install and customize.

Team templates group multiple directors into reusable project setups.
"""

# ---------------------------------------------------------------------------
# Team templates — pre-configured groups of directors for common project types
# ---------------------------------------------------------------------------

TEAM_TEMPLATES = [
    {
        "id": "job_hunter",
        "name": "Job Hunter",
        "emoji": "🎯",
        "description": (
            "Automated job application pipeline: scouts openings, verifies companies, "
            "prepares tailored application drafts, and generates daily progress reports."
        ),
        "color": "#F9E2AF",
        "directors": ["job_scout", "job_researcher", "job_applicant", "job_reporter"],
    },
    {
        "id": "empty",
        "name": "Empty Project",
        "emoji": "📂",
        "description": "Start with an empty project and add directors manually.",
        "color": "#6C7086",
        "directors": [],
    },
]


# ---------------------------------------------------------------------------
# Individual director templates
# ---------------------------------------------------------------------------

DIRECTOR_TEMPLATES = [
    # ------ Job Hunter team directors (team_only — not installable individually) ------
    {
        "id": "job_scout",
        "team_only": True,
        "name": "Job Scout",
        "emoji": "🔍",
        "description": (
            "Searches job boards daily for positions matching your CV. "
            "Delegates company verification and application preparation to the team."
        ),
        "role_prompt": (
            "You are the Job Scout — the lead director of the Job Hunter team. "
            "Your mission is to find job opportunities that match the user's profile "
            "and orchestrate the entire application pipeline.\n\n"
            "## Your Workflow\n\n"
            "### Step 1 — Check Setup\n"
            "Check your persistent context for these keys:\n"
            "- `cv_summary`: the user's profile/skills summary\n"
            "- `target_roles`: JSON list of target job titles/keywords\n"
            "- `target_locations`: JSON list of preferred locations\n"
            "- `blacklist`: JSON list of company names to permanently skip\n"
            "- `search_sources`: JSON list of job board URLs to check\n"
            "- `active_leads`: JSON list of leads currently in pipeline\n"
            "- `daily_limit`: max new leads per run (default 10)\n\n"
            "If `cv_summary` or `target_roles` are empty, save a notification to the inbox "
            "asking the user to configure them via set_context, and STOP.\n\n"
            "### Step 2 — Process Previous Results\n"
            "Before searching for new jobs, check the inbox for recent verification "
            "results from the Job Researcher:\n"
            "- For companies with verdict PASS: delegate an application task to `job_applicant` "
            "with input_data: company_name, job_title, job_url, job_description, requirements, "
            "company_info (from the researcher's report)\n"
            "- For companies with verdict FAIL: update `active_leads` to mark as 'rejected', "
            "consider adding the company to `blacklist`\n"
            "- For CAUTION verdicts: include in your report for the user to decide\n\n"
            "### Step 3 — Search for New Jobs\n"
            "Use browser tools to search job boards:\n"
            "- Navigate to job sites (LinkedIn Jobs, Indeed, Glassdoor, or URLs in `search_sources`)\n"
            "- Search for each role in `target_roles` combined with `target_locations`\n"
            "- Extract: job title, company name, location, posting URL, key requirements\n"
            "- Only collect jobs posted in the last 7 days\n\n"
            "### Step 4 — Filter Results\n"
            "- Check `blacklist` — skip any matching company\n"
            "- Check `active_leads` — skip jobs already in the pipeline\n"
            "- Match against `cv_summary` — keep jobs where the user meets >=60%% of requirements\n"
            "- Limit to `daily_limit` new leads per run (default 10)\n\n"
            "### Step 5 — Delegate Verification\n"
            "For each NEW matching job, delegate a task to `job_researcher` with input_data:\n"
            "{ company_name, job_title, job_url, job_description, requirements }\n"
            "Add each job to `active_leads` with status 'verifying'.\n\n"
            "### Step 6 — Update Context & Report\n"
            "- Update `active_leads` with current pipeline state\n"
            "- Increment `jobs_found_total`\n"
            "- Save a summary report to inbox (type 'report') with:\n"
            "  - New jobs found today\n"
            "  - Leads sent for verification\n"
            "  - Applications delegated from previous verifications\n"
            "  - CAUTION companies pending user decision\n"
            "  - Current blacklist size\n\n"
            "## Blacklist Management\n"
            "The `blacklist` context key is a JSON list: [\"Company A\", \"scam-corp.com\"]\n"
            "Add companies when: Researcher flags them, user rejects them, or they are scams.\n"
            "The user can also add companies manually via set_context.\n\n"
            "## Edge Cases\n"
            "- No matching jobs found: report it, suggest broadening search terms\n"
            "- Browser fails on a job board: try alternative sources, note the failure\n"
            "- Too many results: prioritize by match quality with cv_summary\n"
            "- First run ever: explain the setup process in the inbox report\n\n"
            "## Phase Awareness\n"
            "Phase 1 (current): All applications go to inbox as drafts for user review.\n"
            "Phase 2 (future): Applicant will send emails directly after user trusts quality.\n"
            "Phase 3 (future): Browser automation for job portal form submissions."
        ),
        "schedule": "0 7 * * *",
        "tools_allowed": ["*"],
        "plugins_allowed": ["*"],
        "permission_level": "green",
        "can_delegate": True,
        "required_context": [
            {
                "key": "cv_summary",
                "label": "CV / Profile Summary",
                "label_es": "Resumen del CV / Perfil",
                "type": "textarea",
                "hint": "Your skills, experience, and professional summary",
                "hint_es": "Tus habilidades, experiencia y resumen profesional",
                "required": True,
                "default": "",
                "options": [],
                "group": "profile",
                "allow_file_attach": True,
            },
            {
                "key": "target_roles",
                "label": "Target Job Titles",
                "label_es": "Puestos Objetivo",
                "type": "tags",
                "hint": "e.g. Frontend Developer, React Engineer",
                "hint_es": "Ej: Desarrollador Frontend, Ingeniero React",
                "required": True,
                "default": "",
                "options": [],
                "group": "search",
            },
            {
                "key": "target_locations",
                "label": "Preferred Locations",
                "label_es": "Ubicaciones Preferidas",
                "type": "tags",
                "hint": "e.g. Remote, Madrid, Barcelona",
                "hint_es": "Ej: Remoto, Madrid, Barcelona",
                "required": False,
                "default": "",
                "options": [],
                "group": "search",
            },
            {
                "key": "blacklist",
                "label": "Blacklisted Companies",
                "label_es": "Empresas Bloqueadas",
                "type": "tags",
                "hint": "Companies to never apply to",
                "hint_es": "Empresas a las que nunca aplicar",
                "required": False,
                "default": "",
                "options": [],
                "group": "filters",
            },
            {
                "key": "search_sources",
                "label": "Job Board URLs",
                "label_es": "URLs de Portales de Empleo",
                "type": "tags",
                "hint": "e.g. linkedin.com/jobs, indeed.com",
                "hint_es": "Ej: linkedin.com/jobs, indeed.com",
                "required": False,
                "default": "",
                "options": [],
                "group": "search",
            },
            {
                "key": "daily_limit",
                "label": "Max Leads per Run",
                "label_es": "Leads Maximo por Ejecucion",
                "type": "number",
                "hint": "Maximum new leads per execution (default: 10)",
                "hint_es": "Maximo de leads nuevos por ejecucion (por defecto: 10)",
                "required": False,
                "default": "10",
                "options": [],
                "group": "filters",
            },
            # --- Runtime / auto-managed fields ---
            {
                "key": "active_leads",
                "label": "Active Leads Pipeline",
                "label_es": "Pipeline de Leads Activos",
                "type": "textarea",
                "hint": "Auto-managed: current job leads in pipeline (JSON)",
                "hint_es": "Auto-gestionado: leads actuales en el pipeline (JSON)",
                "required": False,
                "default": "[]",
                "options": [],
                "group": "runtime",
                "read_only": True,
                "auto_managed": True,
            },
            {
                "key": "pipeline_status",
                "label": "Pipeline Status",
                "label_es": "Estado del Pipeline",
                "type": "select",
                "hint": "Current status of the job search pipeline",
                "hint_es": "Estado actual del pipeline de busqueda",
                "required": False,
                "default": "awaiting_configuration",
                "options": ["awaiting_configuration", "active", "paused", "completed"],
                "group": "runtime",
                "read_only": True,
                "auto_managed": True,
            },
            {
                "key": "last_run_status",
                "label": "Last Run Status",
                "label_es": "Estado de Ultima Ejecucion",
                "type": "select",
                "hint": "Result of the most recent execution",
                "hint_es": "Resultado de la ejecucion mas reciente",
                "required": False,
                "default": "",
                "options": ["success", "failed", "partial", "no_results", "setup_required"],
                "group": "runtime",
                "read_only": True,
                "auto_managed": True,
            },
            {
                "key": "runs_completed",
                "label": "Runs Completed",
                "label_es": "Ejecuciones Completadas",
                "type": "number",
                "hint": "Auto-managed: total completed runs",
                "hint_es": "Auto-gestionado: ejecuciones completadas",
                "required": False,
                "default": "0",
                "options": [],
                "group": "runtime",
                "read_only": True,
                "auto_managed": True,
            },
            {
                "key": "run_status",
                "label": "Run Status",
                "label_es": "Estado de Ejecucion",
                "type": "select",
                "hint": "Current execution state",
                "hint_es": "Estado de ejecucion actual",
                "required": False,
                "default": "",
                "options": ["idle", "running", "setup_required", "error"],
                "group": "runtime",
                "read_only": True,
                "auto_managed": True,
            },
        ],
    },
    {
        "id": "job_researcher",
        "team_only": True,
        "name": "Job Researcher",
        "emoji": "🔬",
        "description": (
            "Verifies companies from job leads: checks legitimacy, reviews reputation, "
            "and flags blacklisted or suspicious employers."
        ),
        "role_prompt": (
            "You are the Job Researcher — the verification specialist of the Job Hunter team. "
            "Your mission is to verify that companies from job leads are legitimate and worth applying to.\n\n"
            "## Your Workflow\n\n"
            "You are ONLY triggered by delegated tasks from the Job Scout. "
            "Each task contains a job lead to verify.\n\n"
            "### Step 1 — Read Task Data\n"
            "Extract from the delegated task's input_data:\n"
            "- company_name, job_title, job_url, job_description, requirements\n\n"
            "### Step 2 — Check Cache\n"
            "Check your `verified_companies` context (JSON object: {company: {verdict, date, notes}}).\n"
            "If this company was already verified recently (within 30 days), return the cached result "
            "without re-researching.\n\n"
            "### Step 3 — Research the Company\n"
            "Use browser tools to investigate:\n"
            "- Company website: does it exist? Is it professional?\n"
            "- LinkedIn company page: size, industry, employee count\n"
            "- Glassdoor / review sites: ratings, employee reviews, red flags\n"
            "- News: any recent scandals, lawsuits, or fraud reports?\n"
            "- The job listing itself: is it still active? Does it look legitimate?\n\n"
            "### Step 4 — Determine Verdict\n\n"
            "**PASS** — Company is legitimate, has good or neutral reputation:\n"
            "- Verifiable web presence and LinkedIn page\n"
            "- Reasonable reviews (3+ stars on Glassdoor)\n"
            "- Clear product/service and business model\n\n"
            "**FAIL** — Do not apply. Automatic fail criteria:\n"
            "- No verifiable web presence at all\n"
            "- Multiple reports of being a scam or fraudulent employer\n"
            "- Job posting asks for payment from the applicant\n"
            "- Company appears on the user's blacklist\n"
            "- Job URL is broken or listing has been removed\n\n"
            "**CAUTION** — Let user decide. Flag when:\n"
            "- Very few reviews or mixed sentiment\n"
            "- Company founded less than 1 year ago\n"
            "- Job description is vague or looks copied\n"
            "- Salary seems unrealistically high for the role\n"
            "- Cannot find enough information to confidently verify\n\n"
            "### Step 5 — Save Results\n"
            "1. Update `verified_companies` context with the verdict and date\n"
            "2. Increment `total_verified`\n"
            "3. Save a verification report to inbox:\n"
            "   - content_type: 'analysis'\n"
            "   - Title: \"Verification: [Company Name] — [PASS/FAIL/CAUTION]\"\n"
            "   - Content: company website, size, rating summary, red flags, verdict reasoning\n"
            "   - Priority: 3 (FAIL), 4 (CAUTION), 5 (PASS)\n\n"
            "## Edge Cases\n"
            "- Cannot find any info: verdict CAUTION, note lack of data\n"
            "- Company already verified with PASS recently: return cached result\n"
            "- Multiple job listings from same company: verify once, cache for all\n\n"
            "## Phase Awareness\n"
            "Your verification data feeds into the application pipeline. "
            "In all phases, your role remains the same: thorough, honest verification."
        ),
        "schedule": None,
        "tools_allowed": ["*"],
        "plugins_allowed": ["*"],
        "permission_level": "green",
        "can_delegate": False,
        "required_context": [
            {
                "key": "verified_companies",
                "label": "Verified Companies Cache",
                "label_es": "Cache de Empresas Verificadas",
                "type": "textarea",
                "hint": "Auto-managed: JSON cache of verified companies",
                "hint_es": "Auto-gestionado: cache JSON de empresas verificadas",
                "required": False,
                "default": "{}",
                "options": [],
                "group": "runtime",
                "read_only": True,
                "auto_managed": True,
            },
            {
                "key": "total_verified",
                "label": "Total Verified",
                "label_es": "Total Verificadas",
                "type": "number",
                "hint": "Auto-managed: total companies verified",
                "hint_es": "Auto-gestionado: empresas verificadas en total",
                "required": False,
                "default": "0",
                "options": [],
                "group": "runtime",
                "read_only": True,
                "auto_managed": True,
            },
        ],
    },
    {
        "id": "job_applicant",
        "team_only": True,
        "name": "Job Applicant",
        "emoji": "📝",
        "description": (
            "Prepares tailored application drafts: adapts CV and writes cover letters "
            "for each verified job. Saves drafts to inbox for user approval."
        ),
        "role_prompt": (
            "You are the Job Applicant — the application specialist of the Job Hunter team. "
            "Your mission is to prepare high-quality, tailored job applications.\n\n"
            "## Your Workflow\n\n"
            "You are triggered by delegated tasks from the Job Scout, "
            "each containing a verified job lead.\n\n"
            "### Step 1 — Read Task Data\n"
            "Extract from the delegated task's input_data:\n"
            "- company_name, job_title, job_url, job_description, requirements, company_info\n\n"
            "### Step 2 — Check CV Base\n"
            "Check your `cv_base` context key for the user's base CV in markdown.\n"
            "If empty, save a notification to inbox asking the user to provide their CV "
            "via set_context (key: cv_base), and STOP.\n"
            "Also check `cover_letter_template` — if empty, use a standard professional template.\n\n"
            "### Step 3 — Check for Duplicates\n"
            "Check `applications_prepared` (JSON list) — if this exact company+role "
            "combination already exists, skip it and note in the report.\n\n"
            "### Step 4 — Tailor the CV\n"
            "Starting from `cv_base`:\n"
            "- Reorder sections to highlight the most relevant experience for this role\n"
            "- Adjust the professional summary to match the job description\n"
            "- Emphasize skills and achievements that match requirements\n"
            "- NEVER fabricate experience, skills, or qualifications\n"
            "- Output as clean, professional markdown\n\n"
            "### Step 5 — Write Cover Letter\n"
            "Using `cover_letter_template` as structure:\n"
            "- Personalize for the company (use company_info from Researcher)\n"
            "- Address specific requirements from the job description\n"
            "- Show genuine interest in the company's mission/product\n"
            "- Keep it concise: 3-4 paragraphs maximum\n"
            "- Professional but personable tone\n"
            "- Match tone to company culture (startup vs corporate)\n\n"
            "### Step 6 — Prepare Email Draft\n"
            "Compose the application email:\n"
            "- Subject: \"Application for [Role] — [User Name]\"\n"
            "- Body: brief professional intro + mention attached CV and cover letter\n"
            "- Include the contact email if found in the job listing\n\n"
            "### Step 7 — Save as DRAFT to Inbox\n"
            "Save with content_type 'draft' and priority 2 (high — user should review promptly).\n"
            "Title: \"Application Draft: [Job Title] at [Company]\"\n"
            "Content format:\n\n"
            "## Application: [Job Title] at [Company]\n"
            "**Job URL**: [url]\n"
            "**Company**: [brief company info]\n"
            "**Match Score**: [your assessment of fit]\n"
            "**Prepared**: [date]\n\n"
            "### Email Draft\n"
            "**To**: [email if known]\n"
            "**Subject**: [subject line]\n"
            "[email body]\n\n"
            "### Cover Letter\n"
            "[full tailored cover letter]\n\n"
            "### Tailored CV\n"
            "[full adapted CV in markdown]\n\n"
            "### Step 8 — Update Context\n"
            "- Add to `applications_prepared`: {company, role, date, status: 'draft'}\n"
            "- Increment `total_applications`\n\n"
            "## Quality Standards\n"
            "- NEVER fabricate skills, experience, or qualifications\n"
            "- NEVER use generic filler — every sentence must be specific to this role/company\n"
            "- Proofread carefully for grammar and spelling\n"
            "- All content in the user's preferred language\n\n"
            "## Edge Cases\n"
            "- cv_base is empty: save notification, do not produce incomplete application\n"
            "- Job description too vague: produce best-effort draft with notes for user\n"
            "- Duplicate application: skip and note it\n\n"
            "## Phase Awareness\n"
            "Phase 1 (current): ALL applications are saved as DRAFTS in the inbox. "
            "The user reviews and sends manually. NEVER send emails automatically.\n"
            "Phase 2 (future): You will send application emails directly.\n"
            "Phase 3 (future): You will fill application forms on job portals via browser."
        ),
        "schedule": None,
        "tools_allowed": ["*"],
        "plugins_allowed": ["*"],
        "permission_level": "green",
        "can_delegate": False,
        "required_context": [
            {
                "key": "cv_base",
                "label": "Base CV (Markdown)",
                "label_es": "CV Base (Markdown)",
                "type": "textarea",
                "hint": "Your full CV in markdown format — this will be tailored for each application",
                "hint_es": "Tu CV completo en formato markdown — se adaptara para cada aplicacion",
                "required": True,
                "default": "",
                "options": [],
                "group": "profile",
                "allow_file_attach": True,
            },
            {
                "key": "cover_letter_template",
                "label": "Cover Letter Template",
                "label_es": "Plantilla de Carta de Presentacion",
                "type": "textarea",
                "hint": "Optional template for cover letters (leave empty for default)",
                "hint_es": "Plantilla opcional para cartas de presentacion (dejar vacio para usar la predeterminada)",
                "required": False,
                "default": "",
                "options": [],
                "group": "profile",
                "allow_file_attach": True,
            },
            # --- Runtime / auto-managed fields ---
            {
                "key": "applications_prepared",
                "label": "Prepared Applications",
                "label_es": "Aplicaciones Preparadas",
                "type": "textarea",
                "hint": "Auto-managed: JSON list of prepared applications",
                "hint_es": "Auto-gestionado: lista JSON de aplicaciones preparadas",
                "required": False,
                "default": "[]",
                "options": [],
                "group": "runtime",
                "read_only": True,
                "auto_managed": True,
            },
            {
                "key": "total_applications",
                "label": "Total Applications",
                "label_es": "Total de Aplicaciones",
                "type": "number",
                "hint": "Auto-managed: total applications prepared",
                "hint_es": "Auto-gestionado: aplicaciones preparadas en total",
                "required": False,
                "default": "0",
                "options": [],
                "group": "runtime",
                "read_only": True,
                "auto_managed": True,
            },
        ],
    },
    {
        "id": "job_reporter",
        "team_only": True,
        "name": "Job Reporter",
        "emoji": "📊",
        "description": (
            "Creates daily evening reports of the job hunting pipeline: "
            "new leads, verifications, applications prepared, and overall progress."
        ),
        "role_prompt": (
            "You are the Job Reporter — the analytics director of the Job Hunter team. "
            "Your mission is to produce clear, actionable daily reports on the job hunting pipeline.\n\n"
            "## Your Workflow\n\n"
            "You run every evening on schedule. You do NOT receive delegated tasks.\n\n"
            "### Step 1 — Gather Data\n"
            "Check recent inbox items from the other Job Hunter directors:\n"
            "- From job_scout: new leads found, pipeline updates\n"
            "- From job_researcher: company verification results (PASS/FAIL/CAUTION)\n"
            "- From job_applicant: application drafts prepared\n\n"
            "### Step 2 — Compile Daily Report\n"
            "Structure the report with these sections:\n\n"
            "**Pipeline Overview**\n"
            "- Total active leads in pipeline\n"
            "- New leads found today\n"
            "- Companies verified today (pass/fail/caution breakdown)\n"
            "- Applications prepared today\n"
            "- Applications pending user review in inbox\n\n"
            "**Today's Highlights**\n"
            "- Top 3 new opportunities (by match quality)\n"
            "- Notable company verification findings\n"
            "- Application drafts ready for review (quick summary of each)\n\n"
            "**Action Items for User**\n"
            "- Application drafts awaiting review/approval\n"
            "- CAUTION companies needing user decision\n"
            "- Missing profile info (cv_summary, target_roles not configured)\n"
            "- Stale leads (in pipeline >7 days with no progress)\n\n"
            "**Weekly Stats** (include on Sundays or Mondays)\n"
            "- Week-over-week comparison\n"
            "- Total applications this week vs last week\n"
            "- Suggestions for improving search parameters\n\n"
            "### Step 3 — Update Context\n"
            "- Set `last_report_date` to today\n"
            "- Increment `reports_generated`\n\n"
            "### Step 4 — Save Report\n"
            "Save to inbox with:\n"
            "- content_type: 'report'\n"
            "- Title: \"Job Hunt Report — [date]\"\n"
            "- Priority: 4 (informational)\n\n"
            "## Report Quality\n"
            "- Use actual numbers, not vague summaries\n"
            "- Be actionable: clearly state what the user needs to do\n"
            "- Be concise: scannable in under 2 minutes\n"
            "- If no activity today: still produce a brief report noting zero activity\n"
            "- If first run ever: produce an onboarding report explaining the pipeline setup\n\n"
            "## Phase Awareness\n"
            "In later phases, also report on sent applications, response rates, "
            "and interview scheduling. For now, focus on the draft preparation pipeline."
        ),
        "schedule": "0 19 * * *",
        "tools_allowed": ["*"],
        "plugins_allowed": ["*"],
        "permission_level": "green",
        "can_delegate": False,
        "required_context": [
            {
                "key": "last_report_date",
                "label": "Last Report Date",
                "label_es": "Fecha del Ultimo Reporte",
                "type": "text",
                "hint": "Auto-managed: date of last generated report",
                "hint_es": "Auto-gestionado: fecha del ultimo reporte generado",
                "required": False,
                "default": "",
                "options": [],
                "group": "runtime",
                "read_only": True,
                "auto_managed": True,
            },
            {
                "key": "reports_generated",
                "label": "Reports Generated",
                "label_es": "Reportes Generados",
                "type": "number",
                "hint": "Auto-managed: total reports generated",
                "hint_es": "Auto-gestionado: reportes generados en total",
                "required": False,
                "default": "0",
                "options": [],
                "group": "runtime",
                "read_only": True,
                "auto_managed": True,
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_team_template(template_id: str) -> dict | None:
    """Get a team template by ID."""
    for t in TEAM_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def get_director_template(director_id: str) -> dict | None:
    """Get a single director template by ID."""
    for t in DIRECTOR_TEMPLATES:
        if t["id"] == director_id:
            return t
    return None
