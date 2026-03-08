from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from ..models import Resume, InterviewSession
from ..extensions import db
from ..resume.reporting import build_report_filename, generate_resume_report_pdf
import os
import json
from datetime import datetime, timedelta
from collections import defaultdict

dashboard_bp = Blueprint('dashboard', __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
REPORT_FOLDER = os.path.join(BASE_DIR, 'uploads', 'reports')
os.makedirs(REPORT_FOLDER, exist_ok=True)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    # Get user's resume analyses
    resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.created_at.desc()).limit(5).all()
    
    # Get user's interview sessions
    interviews = InterviewSession.query.filter_by(user_id=current_user.id).order_by(InterviewSession.created_at.desc()).limit(5).all()
    
    # Calculate statistics
    total_resumes = Resume.query.filter_by(user_id=current_user.id).count()
    total_interviews = InterviewSession.query.filter_by(user_id=current_user.id).count()
    
    # Calculate average ATS score
    avg_ats_score = db.session.query(db.func.avg(Resume.ats_score)).filter_by(user_id=current_user.id).scalar() or 0
    
    # Get recent activity (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_resumes = Resume.query.filter(
        Resume.user_id == current_user.id,
        Resume.created_at >= week_ago
    ).count()
    recent_interviews = InterviewSession.query.filter(
        InterviewSession.user_id == current_user.id,
        InterviewSession.created_at >= week_ago
    ).count()
    
    user_data = {
        'name': current_user.name,
        'email': current_user.email,
        'role': current_user.role or 'candidate',
        'total_analyses': total_resumes,
        'total_interviews': total_interviews,
        'avg_ats_score': round(avg_ats_score, 1),
        'recent_resumes': recent_resumes,
        'recent_interviews': recent_interviews
    }
    
    return render_template('dashboard.html', 
                         user=user_data, 
                         resumes=resumes, 
                         interviews=interviews)


@dashboard_bp.route('/profile')
@login_required
def profile():
    # Get user statistics
    total_resumes = Resume.query.filter_by(user_id=current_user.id).count()
    total_interviews = InterviewSession.query.filter_by(user_id=current_user.id).count()
    avg_ats_score = db.session.query(db.func.avg(Resume.ats_score)).filter_by(user_id=current_user.id).scalar() or 0
    
    # Get member since date
    member_since = current_user.created_at.strftime('%B %Y') if current_user.created_at else 'Recently'
    
    profile_data = {
        'name': current_user.name,
        'email': current_user.email,
        'role': current_user.role or 'Job Seeker',
        'member_since': member_since,
        'total_analyses': total_resumes,
        'total_interviews': total_interviews,
        'avg_ats_score': round(avg_ats_score, 1)
    }
    
    return render_template('profile.html', profile=profile_data)


@dashboard_bp.route('/history')
@login_required
def history():
    # Get all user's resume analyses
    resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.created_at.desc()).all()
    
    # Get all user's interview sessions
    interviews = InterviewSession.query.filter_by(user_id=current_user.id).order_by(InterviewSession.created_at.desc()).all()
    
    # Prepare resume data with parsed analysis
    resume_data = []
    for resume in resumes:
        try:
            analysis_dict = json.loads(resume.analysis) if resume.analysis else {}
        except:
            analysis_dict = {}
        
        resume_data.append({
            'id': resume.id,
            'filename': resume.filename,
            'role': resume.role_target,
            'score': resume.ats_score,
            'date': resume.created_at.strftime('%B %d, %Y'),
            'analysis': analysis_dict
        })
    
    # Prepare interview data
    interview_data = []
    for interview in interviews:
        interview_data.append({
            'id': interview.id,
            'role': interview.role,
            'status': interview.status,
            'score': interview.overall_score or 0,
            'date': interview.created_at.strftime('%B %d, %Y')
        })
    
    return render_template('history.html', resumes=resume_data, interviews=interview_data)


@dashboard_bp.route('/history/resume/<int:resume_id>')
@login_required
def view_resume_report(resume_id):
    # Get the resume record
    resume = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first()
    
    if not resume:
        flash('Resume analysis not found', 'error')
        return redirect(url_for('dashboard.history'))
    
    try:
        analysis = json.loads(resume.analysis) if resume.analysis else {}
    except Exception:
        analysis = {}

    if not analysis:
        flash('Analysis report not found for this resume', 'error')
        return redirect(url_for('dashboard.history'))

    # Ensure all required fields are present
    candidate_name = analysis.get('candidate_name') or current_user.name or 'Candidate'
    analysis['candidate_name'] = candidate_name
    
    return render_template('resume_report.html', analysis=analysis)


@dashboard_bp.route('/history/resume/<int:resume_id>/download')
@login_required
def download_resume_history(resume_id):
    # Get the resume record
    resume = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first()
    
    if not resume:
        flash('Resume analysis not found', 'error')
        return redirect(url_for('dashboard.history'))
    
    try:
        analysis = json.loads(resume.analysis) if resume.analysis else {}
    except Exception:
        analysis = {}

    if not analysis:
        flash('Analysis report not found for this resume', 'error')
        return redirect(url_for('dashboard.history'))

    role = analysis.get('job_role') or (resume.role_target or 'role').replace(' ', '-').lower()
    role_label = analysis.get('role_label') or (resume.role_target or role.replace('-', ' ').title())

    candidate_name = analysis.get('candidate_name') or current_user.name or 'Candidate'
    analysis['candidate_name'] = candidate_name
    analysis['role_label'] = role_label
    analysis['report_title'] = analysis.get('report_title') or f"{candidate_name} - {role_label}"

    base_report_name = build_report_filename(candidate_name, role)
    report_name = f"resume-analysis-{resume.id}-{base_report_name}"
    report_path = os.path.join(REPORT_FOLDER, report_name)

    generate_resume_report_pdf(report_path, analysis)

    return send_file(
        report_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=report_name
    )
