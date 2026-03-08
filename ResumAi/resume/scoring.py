import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from ResumAi.keywords import TECH_ROLE_KEYWORDS


@dataclass
class ATSResult:
    score: int
    matched_keywords: List[str]
    missing_keywords: List[str]
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]
    score_breakdown: Dict[str, int]
    engine: str


def _tokenize_words(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9\+\.#-]+", text.lower())


def _contains_keyword(text: str, keyword: str) -> bool:
    escaped = re.escape(keyword.lower())
    return bool(re.search(rf"\b{escaped}\b", text))


def _safe_score(value: float, cap: int = 95) -> int:
    return max(0, min(int(round(value)), cap))


def _logic_score(text: str, job_role: str) -> ATSResult:
    lowered = text.lower()
    keywords = TECH_ROLE_KEYWORDS.get(job_role, [])

    if not keywords:
        return ATSResult(
            score=55,
            matched_keywords=[],
            missing_keywords=[],
            strengths=["Resume parsed successfully"],
            weaknesses=["No keyword bank found for selected role"],
            suggestions=["Use a supported role for role-specific ATS scoring"],
            score_breakdown={
                "keyword_relevance": 20,
                "resume_structure": 20,
                "experience_impact": 15,
                "format_readability": 0,
            },
            engine="logic",
        )

    matched_keywords: List[str] = []
    missing_keywords: List[str] = []

    core_keywords = keywords[:6]
    secondary_keywords = keywords[6:]

    for keyword in core_keywords:
        if _contains_keyword(lowered, keyword):
            matched_keywords.append(keyword)
        else:
            missing_keywords.append(f"{keyword} (critical)")

    for keyword in secondary_keywords:
        if _contains_keyword(lowered, keyword):
            matched_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)

    keyword_ratio = (len(matched_keywords) / max(1, len(keywords)))
    keyword_score = min(45, keyword_ratio * 45)

    # Resume structure coverage.
    sections = ["summary", "skills", "experience", "projects", "education"]
    found_sections = sum(1 for section in sections if section in lowered)
    structure_score = (found_sections / len(sections)) * 25

    # Experience quality via metrics and action verbs.
    has_metrics = bool(re.search(r"(\d+%|\$\d+|\d+x|\d+\+)", lowered))
    has_action_verbs = bool(
        re.search(
            r"(built|improved|designed|developed|implemented|optimized|reduced|increased|delivered)",
            lowered,
        )
    )
    experience_score = 10
    if has_metrics:
        experience_score += 8
    if has_action_verbs:
        experience_score += 7

    # Formatting/readability heuristics.
    word_count = len(_tokenize_words(lowered))
    has_contact = bool(re.search(r"(@|linkedin|github|\+\d{2,}|\d{10})", lowered))
    readable_length = 300 <= word_count <= 1200
    formatting_score = 5
    if has_contact:
        formatting_score += 5
    if readable_length:
        formatting_score += 5

    total_score = _safe_score(keyword_score + structure_score + experience_score + formatting_score)

    strengths: List[str] = []
    weaknesses: List[str] = []
    suggestions: List[str] = []

    if keyword_ratio >= 0.6:
        strengths.append(f"Strong role relevance: {len(matched_keywords)}/{len(keywords)} target keywords found")
    else:
        weaknesses.append(f"Low role relevance: only {len(matched_keywords)}/{len(keywords)} target keywords found")
        suggestions.append("Add role-specific skills and tools in Skills and Projects sections")

    if has_metrics:
        strengths.append("Quantifiable achievements are present")
    else:
        weaknesses.append("Achievements are not quantified")
        suggestions.append("Add measurable impact like percentages, cost/time reduction, or scale")

    if found_sections >= 4:
        strengths.append("Resume has good section coverage")
    else:
        weaknesses.append("Resume structure is incomplete for ATS scanning")
        suggestions.append("Include clear headings: Summary, Skills, Experience, Projects, Education")

    if not readable_length:
        suggestions.append("Keep resume focused to 1 page equivalent content for ATS readability")

    if not has_contact:
        suggestions.append("Add clear contact details, LinkedIn, and GitHub")

    if not suggestions:
        suggestions.append("Tailor top bullets with job-description language for the selected role")

    return ATSResult(
        score=total_score,
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        strengths=strengths,
        weaknesses=weaknesses,
        suggestions=suggestions,
        score_breakdown={
            "keyword_relevance": _safe_score(keyword_score, cap=45),
            "resume_structure": _safe_score(structure_score, cap=25),
            "experience_impact": _safe_score(experience_score, cap=25),
            "format_readability": _safe_score(formatting_score, cap=15),
        },
        engine="logic",
    )


def _api_score_stub(text: str, job_role: str, api_provider: str = "openai") -> ATSResult:
    """API scoring placeholder for future paid key usage.

    This intentionally returns a placeholder result and is not wired as active mode.
    """
    return ATSResult(
        score=0,
        matched_keywords=[],
        missing_keywords=[],
        strengths=[f"{api_provider} scoring is configured as scaffold"],
        weaknesses=["API scoring currently disabled"],
        suggestions=["Enable API mode after adding paid key in environment variables"],
        score_breakdown={
            "keyword_relevance": 0,
            "resume_structure": 0,
            "experience_impact": 0,
            "format_readability": 0,
        },
        engine="api-disabled",
    )


def score_resume(text: str, job_role: str, mode: str = "logic") -> ATSResult:
    """Compute ATS score with either logic mode or (future) API mode.

    Modes:
    - logic: active pure-python ATS engine (default)
    - api: future paid API engine (currently disabled scaffold)
    """
    if mode == "api":
        # API path is intentionally disabled for now.
        # return _api_score_live(text, job_role)
        return _api_score_stub(text, job_role, api_provider="openai")
    return _logic_score(text, job_role)
