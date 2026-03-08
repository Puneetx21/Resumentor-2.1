from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
import os
import pdfplumber
import re
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from flask_login import current_user
from ResumAi.keywords import TECH_ROLE_KEYWORDS  # Our keywords DB
from ResumAi.models import User, Resume
from ResumAi.extensions import db
from .reporting import build_report_filename, generate_resume_report_pdf
from .scoring import score_resume

resume_bp = Blueprint('resume', __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'resumes')
REPORT_FOLDER = os.path.join(BASE_DIR, 'uploads', 'reports')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text(filepath):
    """Extract text from PDF"""
    try:
        with pdfplumber.open(filepath) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception:
        return ""


def extract_candidate_name(text, fallback_filename='candidate', fallback_user='candidate'):
    """Try to infer candidate name from first lines of resume text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:8]:
        compact = re.sub(r'\s+', ' ', line)
        if re.search(r'(@|http|www\.|linkedin|github|phone|email|resume|curriculum)', compact, re.I):
            continue
        if 2 <= len(compact.split()) <= 4 and re.fullmatch(r"[A-Za-z][A-Za-z\s.'-]{2,60}", compact):
            return compact.title()

    if fallback_user and fallback_user != 'user':
        return str(fallback_user).strip().title()

    base_name = os.path.splitext(os.path.basename(fallback_filename))[0]
    cleaned = re.sub(r'[_\-.]+', ' ', base_name)
    return cleaned.title() if cleaned else 'Candidate'


def build_section_recommendations(text):
    lowered = text.lower()
    section_checks = {
        'Professional Summary': ['summary', 'objective', 'profile'],
        'Skills': ['skills', 'technical skills', 'tech stack'],
        'Experience': ['experience', 'employment', 'work history'],
        'Projects': ['projects', 'project experience'],
        'Education': ['education', 'academic'],
        'Certifications': ['certification', 'certifications', 'certified'],
    }

    recommendations = []
    for section_name, aliases in section_checks.items():
        present = any(alias in lowered for alias in aliases)
        if present:
            recommendations.append({
                'section': section_name,
                'status': 'good',
                'message': f"{section_name} section is present.",
            })
        else:
            recommendations.append({
                'section': section_name,
                'status': 'improve',
                'message': f"Add a dedicated {section_name} section with concise, ATS-friendly bullets.",
            })
    return recommendations


def classify_score(score):
    if score >= 80:
        return 'Excellent', 'Your resume is strongly ATS-optimized for this role.'
    if score >= 65:
        return 'Good', 'Your resume is reasonably ATS-optimized and can be improved further.'
    if score >= 50:
        return 'Fair', 'Your resume needs optimization in keywords, structure, and impact statements.'
    return 'Needs Major Improvement', 'Your resume may be filtered early by ATS without targeted updates.'


def detect_experience_level(text):
    lowered = text.lower()
    if re.search(r'(8\+|9\+|10\+|senior|lead|principal|architect)', lowered):
        return 'Senior (8+ YoE)'
    if re.search(r'(4\+|5\+|6\+|7\+|mid-level|mid level)', lowered):
        return 'Mid-Level (4-7 YoE)'
    return 'Junior (0-3 YoE)'


def normalize_metric(raw_value, raw_cap):
    if raw_cap <= 0:
        return 0.0
    return round((raw_value / raw_cap) * 100.0, 1)


@resume_bp.route('/resume')
def analyzer():
    return render_template('resume_analyzer.html')


@resume_bp.route('/resume/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('resume.analyzer'))

    file = request.files['file']
    job_role = request.form.get('job_role', '').replace(' ', '-').lower()

    if file.filename == '' or not allowed_file(file.filename):
        flash('Please select a valid PDF file', 'error')
        return redirect(url_for('resume.analyzer'))

    # Save file
    filename = secure_filename(file.filename)
    user_identifier = current_user.id if current_user.is_authenticated else 'guest'
    filepath = os.path.join(UPLOAD_FOLDER, f"{user_identifier}_{filename}")
    file.save(filepath)

    # Real analysis in logic mode (API mode is scaffolded but disabled).
    text = extract_text(filepath)
    if not text.strip():
        flash('Could not read text from this PDF. Please upload a text-based PDF.', 'error')
        return redirect(url_for('resume.analyzer'))

    scoring_mode = 'logic'
    ats_result = score_resume(text=text, job_role=job_role, mode=scoring_mode)

    matched_keywords = ats_result.matched_keywords
    missing_keywords = ats_result.missing_keywords
    ats_score = ats_result.score
    role_label = job_role.replace('-', ' ').title()

    user_name = 'Guest'
    if current_user.is_authenticated:
        user_name = current_user.name

    candidate_name = extract_candidate_name(text, fallback_filename=filename, fallback_user=user_name)
    section_recommendations = build_section_recommendations(text)

    readiness_level = 'Needs Work'
    if ats_score >= 80:
        readiness_level = 'Strong'
    elif ats_score >= 65:
        readiness_level = 'Moderate'

    score_label, score_explanation = classify_score(ats_score)
    experience_level = detect_experience_level(text)

    total_keywords = len(TECH_ROLE_KEYWORDS.get(job_role, []))
    keyword_coverage = round((len(matched_keywords) / max(1, total_keywords)) * 100.0, 1)

    breakdown = ats_result.score_breakdown
    length_score = 90.0 if 300 <= len(re.findall(r'\w+', text)) <= 1200 else 65.0
    formatting_score = normalize_metric(breakdown.get('format_readability', 0), 15)
    action_verbs_score = normalize_metric(breakdown.get('experience_impact', 0), 25)
    technical_depth_score = normalize_metric(breakdown.get('keyword_relevance', 0), 45)
    consistency_score = round((formatting_score + normalize_metric(breakdown.get('resume_structure', 0), 25)) / 2, 1)
    sections_present = sum(1 for item in section_recommendations if item.get('status') == 'good')

    detailed_metrics = [
        {'label': 'Experience', 'value': experience_level, 'icon': 'fas fa-briefcase', 'type': 'text'},
        {'label': 'Keywords', 'value': keyword_coverage, 'icon': 'fas fa-key', 'type': 'percent'},
        {'label': 'Completeness', 'value': round((sections_present / 6) * 100.0, 1), 'icon': 'fas fa-check-circle', 'type': 'percent'},
        {'label': 'Technical Depth', 'value': technical_depth_score, 'icon': 'fas fa-microchip', 'type': 'score'},
        {'label': 'Action Verbs', 'value': action_verbs_score, 'icon': 'fas fa-bolt', 'type': 'score'},
        {'label': 'Consistency', 'value': consistency_score, 'icon': 'fas fa-balance-scale', 'type': 'score'},
    ]

    # Split keywords into required (core) vs nice-to-have (secondary)
    all_role_keywords = TECH_ROLE_KEYWORDS.get(job_role, [])
    core_kw_set = set(k.lower() for k in all_role_keywords[:6])
    required_matched = [k for k in matched_keywords if k.lower() in core_kw_set]
    nice_to_have_matched = [k for k in matched_keywords if k.lower() not in core_kw_set]
    required_missing = [k.replace(' (critical)', '') for k in missing_keywords if '(critical)' in k]
    nice_to_have_missing = [k for k in missing_keywords if '(critical)' not in k]

    recommended_additions = []
    if keyword_coverage < 70:
        recommended_additions.append('Add 4-6 role-specific skills from the target job description.')
    if sections_present < 5:
        recommended_additions.append('Add missing core sections to improve ATS parsing completeness.')
    if action_verbs_score < 70:
        recommended_additions.append('Rewrite bullets with stronger action verbs and measurable outcomes.')
    if len(recommended_additions) == 0:
        recommended_additions.append('Tailor the top summary to the specific role and company tech stack.')

    analysis = {
        'candidate_name': candidate_name,
        'filename': filename,
        'ats_score': ats_score,
        'job_role': job_role,
        'role_label': role_label,
        'report_title': f"{candidate_name} - {role_label}",
        'readiness_level': readiness_level,
        'score_label': score_label,
        'score_explanation': score_explanation,
        'experience_level': experience_level,
        'keyword_coverage': keyword_coverage,
        'text_length': len(text),
        'matched_keywords': matched_keywords,
        'missing_keywords': missing_keywords,
        'required_matched': required_matched,
        'required_missing': required_missing,
        'nice_to_have_matched': nice_to_have_matched,
        'nice_to_have_missing': nice_to_have_missing,
        'strong_points': ats_result.strengths,
        'weak_points': ats_result.weaknesses,
        'suggestions': ats_result.suggestions,
        'recommended_additions': recommended_additions,
        'detailed_metrics': detailed_metrics,
        'sections_present': sections_present,
        'section_recommendations': section_recommendations,
        'score_breakdown': breakdown,
        'scoring_mode': ats_result.engine,
        'keyword_total': total_keywords,
        'length_score': length_score,
        'formatting_score': formatting_score,
        'action_verbs_score': action_verbs_score,
        'layout_feedback': (
            f"Target ATS score for role-fit resumes: {85 if ats_score < 85 else 90}% | "
            "Use clear section headings, concise bullets, and ATS-friendly formatting."
        )
    }

    session['last_analysis'] = analysis
    
    # Save to database if user is authenticated
    if current_user.is_authenticated:
        try:
            resume_record = Resume(
                user_id=current_user.id,
                filename=filename,
                file_path=filepath,
                ats_score=ats_score,
                analysis=json.dumps(analysis),
                role_target=role_label,
                created_at=datetime.utcnow()
            )
            db.session.add(resume_record)
            db.session.commit()
            flash(f'Analysis complete! ATS Score: {ats_score}% (Saved to your history)', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Analysis complete! ATS Score: {ats_score}% (History save failed)', 'warning')
    else:
        flash(f'Analysis complete! ATS Score: {ats_score}% (Guest mode - not saved)', 'info')
    
    return redirect(url_for('resume.report'))


@resume_bp.route('/resume/report')
def report():
    analysis = session.get('last_analysis', {})
    if not analysis:
        flash('No analysis found. Please analyze a resume first.', 'warning')
        return redirect(url_for('resume.analyzer'))
    return render_template('resume_report.html', analysis=analysis)


@resume_bp.route('/resume/report/download')
def download_report():
    analysis = session.get('last_analysis', {})
    if not analysis:
        flash('No analysis found. Please analyze a resume first.', 'warning')
        return redirect(url_for('resume.analyzer'))

    username = 'Guest'
    if current_user.is_authenticated:
        username = current_user.name

    role = analysis.get('job_role', 'role')
    role_label = analysis.get('role_label', role.replace('-', ' ').title())
    analysis.setdefault('candidate_name', username.title() if isinstance(username, str) else 'Candidate')
    analysis.setdefault('role_label', role_label)
    analysis.setdefault('report_title', f"{analysis.get('candidate_name', 'Candidate')} - {role_label}")

    candidate_for_file = analysis.get('candidate_name') or username
    report_name = build_report_filename(candidate_for_file, role)
    report_path = os.path.join(REPORT_FOLDER, report_name)

    generate_resume_report_pdf(report_path, analysis)

    return send_file(
        report_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=report_name,
    )
