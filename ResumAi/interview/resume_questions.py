"""
Pure-Python resume parser and question generator for mock interviews.
No external API required — uses regex and keyword matching to extract
skills, projects, experience from resume text and generate targeted questions.
"""

import re
from typing import List, Dict

from ResumAi.keywords import TECH_ROLE_KEYWORDS


# ── Section extraction helpers ──────────────────────────────────────────

_SECTION_HEADERS = [
    'summary', 'objective', 'profile', 'about',
    'skills', 'technical skills', 'tech stack', 'technologies', 'tools',
    'experience', 'work experience', 'employment', 'work history', 'professional experience',
    'projects', 'project experience', 'personal projects', 'academic projects',
    'education', 'academic', 'qualifications',
    'certifications', 'certificates', 'achievements', 'awards',
]

_SECTION_PATTERN = re.compile(
    r'^[\s]*(' + '|'.join(re.escape(h) for h in _SECTION_HEADERS) + r')[\s]*[:\-–—]?\s*$',
    re.IGNORECASE | re.MULTILINE,
)


def _split_sections(text: str) -> Dict[str, str]:
    """Split resume text into named sections based on common headings."""
    matches = list(_SECTION_PATTERN.finditer(text))
    sections: Dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        # Merge similar section names
        canonical = _canonical_section(name)
        if canonical in sections:
            sections[canonical] += '\n' + content
        else:
            sections[canonical] = content
    return sections


def _canonical_section(name: str) -> str:
    name = name.lower().strip()
    if name in ('summary', 'objective', 'profile', 'about'):
        return 'summary'
    if name in ('skills', 'technical skills', 'tech stack', 'technologies', 'tools'):
        return 'skills'
    if name in ('experience', 'work experience', 'employment', 'work history', 'professional experience'):
        return 'experience'
    if name in ('projects', 'project experience', 'personal projects', 'academic projects'):
        return 'projects'
    if name in ('education', 'academic', 'qualifications'):
        return 'education'
    if name in ('certifications', 'certificates'):
        return 'certifications'
    if name in ('achievements', 'awards'):
        return 'achievements'
    return name


# ── Entity extraction ───────────────────────────────────────────────────

# Common tech skills/tools to look for beyond role keywords
_COMMON_TECH = [
    'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust', 'ruby', 'php', 'swift', 'kotlin',
    'react', 'angular', 'vue', 'nextjs', 'node.js', 'express', 'django', 'flask', 'fastapi', 'spring', 'springboot',
    'mongodb', 'postgresql', 'mysql', 'redis', 'elasticsearch', 'sqlite', 'firebase',
    'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'terraform', 'jenkins', 'github actions', 'ci/cd',
    'git', 'linux', 'rest api', 'graphql', 'websockets', 'microservices',
    'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy', 'opencv',
    'html', 'css', 'tailwind', 'bootstrap', 'sass', 'webpack',
    'sql', 'nosql', 'orm', 'jwt', 'oauth', 'api',
    'agile', 'scrum', 'jira', 'confluence',
    'machine learning', 'deep learning', 'nlp', 'computer vision', 'data analysis',
]


def extract_skills(text: str, role_slug: str = '') -> List[str]:
    """Extract skills mentioned in the resume text."""
    lowered = text.lower()
    found = []

    # Check role-specific keywords first
    role_kw = TECH_ROLE_KEYWORDS.get(role_slug, [])
    for kw in role_kw:
        if re.search(r'\b' + re.escape(kw.lower()) + r'\b', lowered):
            found.append(kw)

    # Check common tech stack
    for tech in _COMMON_TECH:
        if tech.lower() not in [f.lower() for f in found]:
            if re.search(r'\b' + re.escape(tech.lower()) + r'\b', lowered):
                found.append(tech)

    return found


def extract_projects(text: str) -> List[Dict[str, str]]:
    """Extract project names and descriptions from resume text."""
    sections = _split_sections(text)
    projects_text = sections.get('projects', '')
    if not projects_text:
        return []

    projects = []
    lines = projects_text.split('\n')
    current_project = None
    current_desc_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect project title lines: typically short, may have pipes/dashes for tech
        # Heuristic: line that starts with a capital letter, is under 120 chars, and
        # doesn't start with a bullet
        is_bullet = stripped.startswith(('•', '-', '–', '▪', '●', '*', '○'))

        if not is_bullet and len(stripped) < 120 and stripped[0:1].isupper():
            # Save previous project
            if current_project:
                projects.append({
                    'name': current_project,
                    'description': ' '.join(current_desc_lines),
                })
            current_project = stripped
            current_desc_lines = []
        else:
            # Bullet point or continuation — add to description
            clean = re.sub(r'^[•\-–▪●*○]\s*', '', stripped)
            if clean:
                current_desc_lines.append(clean)

    # Don't forget the last project
    if current_project:
        projects.append({
            'name': current_project,
            'description': ' '.join(current_desc_lines),
        })

    return projects[:6]  # Cap at 6 projects


def extract_experience(text: str) -> List[Dict[str, str]]:
    """Extract work experience entries (company, role, highlights)."""
    sections = _split_sections(text)
    exp_text = sections.get('experience', '')
    if not exp_text:
        return []

    entries = []
    lines = exp_text.split('\n')
    current_entry = None
    current_highlights = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        is_bullet = stripped.startswith(('•', '-', '–', '▪', '●', '*', '○'))

        # Detect role/company lines: non-bullet, may contain date patterns
        has_date = bool(re.search(r'(20\d{2}|present|current|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', stripped, re.I))

        if not is_bullet and (has_date or (len(stripped) < 120 and stripped[0:1].isupper() and '|' in stripped)):
            if current_entry:
                entries.append({
                    'title': current_entry,
                    'highlights': ' '.join(current_highlights),
                })
            current_entry = stripped
            current_highlights = []
        elif not is_bullet and not current_entry and len(stripped) < 100 and stripped[0:1].isupper():
            current_entry = stripped
            current_highlights = []
        else:
            clean = re.sub(r'^[•\-–▪●*○]\s*', '', stripped)
            if clean:
                current_highlights.append(clean)

    if current_entry:
        entries.append({
            'title': current_entry,
            'highlights': ' '.join(current_highlights),
        })

    return entries[:5]


# ── Question generation templates ───────────────────────────────────────

_SKILL_QUESTION_TEMPLATES = [
    'Your resume mentions {skill}. Describe a challenging problem you solved using it and the tradeoffs involved.',
    'You listed {skill} as a skill. How do you stay updated with its ecosystem and best practices?',
    'Walk me through a real scenario where your experience with {skill} directly impacted project outcomes.',
    'If a teammate struggled with {skill}, how would you help them get up to speed quickly?',
    'What is the most complex feature you built using {skill}, and what architecture decisions did you make?',
    'Describe how you would evaluate whether {skill} is the right choice for a new project requirement.',
    'What testing and debugging strategies do you use specifically when working with {skill}?',
    'How has your understanding of {skill} evolved over time? What did you learn the hard way?',
]

_PROJECT_QUESTION_TEMPLATES = [
    'Tell me about your project "{project}". What was the problem it solved and what was your specific role?',
    'In your project "{project}", what was the most difficult technical challenge you faced and how did you resolve it?',
    'If you had to rebuild "{project}" from scratch today, what would you do differently and why?',
    'What technologies did you use in "{project}" and how did you decide on that tech stack?',
    'How did you ensure code quality and testing in your project "{project}"?',
    'Describe the deployment and maintenance approach for "{project}". How did you handle production issues?',
]

_EXPERIENCE_QUESTION_TEMPLATES = [
    'You worked as described in "{role}". What was your most impactful achievement in that position?',
    'During your time at "{role}", what was the biggest technical challenge your team faced?',
    'How did your experience at "{role}" prepare you for the role you are interviewing for today?',
    'Describe a situation at "{role}" where you had to learn a new technology quickly to deliver results.',
]

_SKILL_COMBO_TEMPLATES = [
    'Your resume shows experience with both {skill1} and {skill2}. How do these technologies complement each other in your workflow?',
    'Compare your experience with {skill1} versus {skill2}. In what situations would you choose one over the other?',
]


def generate_resume_questions(text: str, role_slug: str) -> List[Dict[str, str]]:
    """
    Parse resume text and generate personalized interview questions.
    Returns a list of dicts with 'question_text' and 'difficulty' keys.
    Pure Python — no API calls.
    """
    skills = extract_skills(text, role_slug)
    projects = extract_projects(text)
    experience = extract_experience(text)

    questions: List[Dict[str, str]] = []

    # ── Skill-based questions (pick up to 3) ──
    skill_templates_used = 0
    for i, skill in enumerate(skills[:6]):
        if skill_templates_used >= 3:
            break
        template = _SKILL_QUESTION_TEMPLATES[i % len(_SKILL_QUESTION_TEMPLATES)]
        questions.append({
            'question_text': template.format(skill=skill),
            'difficulty': 'medium',
        })
        skill_templates_used += 1

    # ── Skill combo question (pick 1 if enough skills) ──
    if len(skills) >= 2:
        template = _SKILL_COMBO_TEMPLATES[0]
        questions.append({
            'question_text': template.format(skill1=skills[0], skill2=skills[1]),
            'difficulty': 'medium',
        })

    # ── Project-based questions (pick up to 2) ──
    project_templates_used = 0
    for i, proj in enumerate(projects[:3]):
        if project_templates_used >= 2:
            break
        template = _PROJECT_QUESTION_TEMPLATES[i % len(_PROJECT_QUESTION_TEMPLATES)]
        proj_name = proj['name']
        # Clean up project name: take first 80 chars, strip trailing tech/dates
        if len(proj_name) > 80:
            proj_name = proj_name[:80].rsplit(' ', 1)[0]
        questions.append({
            'question_text': template.format(project=proj_name),
            'difficulty': 'medium',
        })
        project_templates_used += 1

    # ── Experience-based questions (pick up to 2) ──
    exp_templates_used = 0
    for i, exp in enumerate(experience[:3]):
        if exp_templates_used >= 2:
            break
        template = _EXPERIENCE_QUESTION_TEMPLATES[i % len(_EXPERIENCE_QUESTION_TEMPLATES)]
        role_name = exp['title']
        if len(role_name) > 80:
            role_name = role_name[:80].rsplit(' ', 1)[0]
        questions.append({
            'question_text': template.format(role=role_name),
            'difficulty': 'medium',
        })
        exp_templates_used += 1

    # Cap at 8 resume-based questions
    return questions[:8]


def parse_resume_for_interview(text: str, role_slug: str) -> Dict:
    """
    Full resume parse returning structured data + generated questions.
    """
    skills = extract_skills(text, role_slug)
    projects = extract_projects(text)
    experience = extract_experience(text)
    questions = generate_resume_questions(text, role_slug)

    return {
        'skills_found': skills,
        'projects_found': [p['name'] for p in projects],
        'experience_found': [e['title'] for e in experience],
        'resume_questions': questions,
        'total_resume_questions': len(questions),
    }
