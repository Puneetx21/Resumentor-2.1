from flask import Blueprint, render_template, session, request, jsonify, url_for, redirect, flash, send_file
from flask_login import current_user
import time
import json
import os
from datetime import datetime
from statistics import mean

from ResumAi.models import Resume, InterviewSession, InterviewQuestion, InterviewResponse
from ResumAi.extensions import db
from ResumAi.keywords import TECH_ROLE_KEYWORDS
from ResumAi.resume.reporting import generate_interview_report_pdf

interview_bp = Blueprint('interview', __name__)


ROUND_LABELS = {
    'intro': 'Introduction Round',
    'technical': 'Technical Round',
    'pressure': 'Pressure Handling Round',
}


INTRO_QUESTIONS = [
    'Introduce yourself in 60-90 seconds and highlight your strongest professional achievements.',
    'Walk me through your most relevant project and your exact ownership in it.',
    'Why are you targeting this role now, and what value will you bring in the first 90 days?',
    'How do your strengths and areas for improvement shape your day-to-day work?',
    'How do teammates usually describe your collaboration and communication style?',
]


PRESSURE_QUESTIONS = [
    'A production issue happens five minutes before a release. How do you handle it?',
    'Two critical tasks have the same deadline and limited resources. How do you prioritize?',
    'Your manager disagrees with your technical approach in a high-pressure meeting. How do you respond?',
]


TECHNICAL_PROMPTS = [
    'Explain how you have used {keyword} in a real project, including one tradeoff you handled.',
    'If you had to design a production-ready component around {keyword}, what architecture would you choose and why?',
    'What are common mistakes teams make with {keyword}, and how do you avoid them?',
    'How do you test and debug systems that rely on {keyword}?',
    'Describe one performance optimization you implemented involving {keyword}.',
    'What security or reliability considerations matter most when using {keyword}?',
    'How do you decide when to use {keyword} versus an alternative?',
    'Give a practical example where {keyword} improved user or business outcomes.',
    'How would you mentor a junior engineer to become effective with {keyword}?',
    'What metrics would you track to evaluate success when using {keyword}?',
    'Describe a difficult bug related to {keyword} and how you resolved it.',
    'What scaling challenges can appear with {keyword}, and how would you mitigate them?',
]


@interview_bp.route('/interview')
def interview():
    return render_template('interview.html')


@interview_bp.route('/interview/report')
def interview_report():
    interview_state = session.get('interview', {})
    if not interview_state or interview_state.get('status') != 'completed':
        flash('Complete an interview session first to view the report.', 'warning')
        return redirect(url_for('interview.interview'))

    report = interview_state.get('report') or _build_report_from_answers(
        interview_state.get('answers', []),
        interview_state.get('role', 'web-developer'),
        interview_state.get('resume_context', {}),
        elapsed_seconds=_compute_elapsed(interview_state),
    )
    return render_template('report_interview.html', report=report)


@interview_bp.route('/interview/report/<int:session_id>')
def view_interview_report(session_id):
    if not current_user.is_authenticated:
        flash('Please login to access saved interview reports.', 'warning')
        return redirect(url_for('auth.login'))

    db_session = InterviewSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if not db_session:
        flash('Interview report not found.', 'error')
        return redirect(url_for('dashboard.history'))

    responses = InterviewResponse.query.filter_by(session_id=session_id).order_by(InterviewResponse.created_at.asc()).all()
    answer_rows = [
        {
            'question': item.question_text,
            'category': item.category,
            'answer': item.answer_text or '',
            'answer_mode': item.answer_mode,
            'score': float(item.logic_score or 0),
            'feedback': item.feedback or '',
        }
        for item in responses
    ]

    role_slug = _slugify_role(db_session.role)
    report = _build_report_from_answers(
        answer_rows,
        role_slug,
        resume_context={},
        elapsed_seconds=0,
    )
    report['generated_at'] = db_session.created_at.strftime('%Y-%m-%d %H:%M') if db_session.created_at else datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    report['session_status'] = db_session.status

    return render_template('report_interview.html', report=report)


@interview_bp.route('/interview/report/download')
def download_interview_report():
    interview_state = session.get('interview', {})
    if not interview_state or interview_state.get('status') != 'completed':
        flash('No completed interview found. Complete an interview session first.', 'warning')
        return redirect(url_for('interview.interview'))

    report = interview_state.get('report', {})
    if not report:
        flash('Unable to generate report.', 'error')
        return redirect(url_for('interview.interview_report'))

    candidate_name = current_user.name if current_user.is_authenticated else 'Candidate'
    role = report.get('role', 'Tech Role')
    
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    REPORT_FOLDER = os.path.join(BASE_DIR, 'uploads', 'reports')
    os.makedirs(REPORT_FOLDER, exist_ok=True)

    report_filename = f"interview-{candidate_name.replace(' ', '_')}-{role.replace(' ', '_')}.pdf"
    report_path = os.path.join(REPORT_FOLDER, report_filename)

    generate_interview_report_pdf(report_path, report, candidate_name)

    return send_file(
        report_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=report_filename,
    )


@interview_bp.route('/interview/report/<int:session_id>/download')
@interview_bp.route('/history/interview/<int:session_id>/download')
def download_interview_history(session_id):
    if not current_user.is_authenticated:
        flash('Please login to download interview reports.', 'warning')
        return redirect(url_for('auth.login'))

    db_session = InterviewSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if not db_session:
        flash('Interview report not found.', 'error')
        return redirect(url_for('dashboard.history'))

    responses = InterviewResponse.query.filter_by(session_id=session_id).order_by(InterviewResponse.created_at.asc()).all()
    answer_rows = [
        {
            'question': item.question_text,
            'category': item.category,
            'answer': item.answer_text or '',
            'answer_mode': item.answer_mode,
            'score': float(item.logic_score or 0),
            'feedback': item.feedback or '',
        }
        for item in responses
    ]

    role_slug = _slugify_role(db_session.role)
    report = _build_report_from_answers(
        answer_rows,
        role_slug,
        resume_context={},
        elapsed_seconds=0,
    )
    report['generated_at'] = db_session.created_at.strftime('%Y-%m-%d %H:%M') if db_session.created_at else datetime.utcnow().strftime('%Y-%m-%d %H:%M')

    candidate_name = current_user.name if current_user.is_authenticated else 'Candidate'
    role = db_session.role

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    REPORT_FOLDER = os.path.join(BASE_DIR, 'uploads', 'reports')
    os.makedirs(REPORT_FOLDER, exist_ok=True)

    report_filename = f"interview-{session_id}-{candidate_name.replace(' ', '_')}-{role.replace(' ', '_')}.pdf"
    report_path = os.path.join(REPORT_FOLDER, report_filename)

    generate_interview_report_pdf(report_path, report, candidate_name)

    return send_file(
        report_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=report_filename,
    )


@interview_bp.route('/api/interview/start', methods=['POST'])
def start_interview():
    payload = request.get_json(silent=True) or {}
    role_slug = payload.get('job_role', 'web-developer')

    _seed_question_bank_for_role(role_slug)

    questions = InterviewQuestion.query.filter_by(
        role_slug=role_slug,
        is_active=True,
    ).order_by(InterviewQuestion.order_index.asc()).all()

    if len(questions) < 15:
        return jsonify({'error': 'Not enough questions available for this role. Please try again.'}), 400

    resume_context = _get_resume_context(role_slug)

    db_session_id = None
    if current_user.is_authenticated:
        try:
            interview_session = InterviewSession(
                user_id=current_user.id,
                role=role_slug.replace('-', ' ').title(),
                status='active',
                created_at=datetime.utcnow(),
            )
            db.session.add(interview_session)
            db.session.commit()
            db_session_id = interview_session.id
        except Exception:
            db.session.rollback()

    first_question = _serialize_question(questions[0], index=1, total=len(questions))

    session['interview'] = {
        'role': role_slug,
        'question_ids': [item.id for item in questions],
        'current_index': 0,
        'answers': [],
        'status': 'active',
        'start_time': time.time(),
        'end_time': None,
        'db_session_id': db_session_id,
        'resume_context': resume_context,
    }

    return jsonify({
        'ok': True,
        'question': first_question,
        'total_questions': len(questions),
        'resume_context_used': bool(resume_context.get('has_analysis')),
    })


@interview_bp.route('/api/interview/current', methods=['GET'])
def current_question():
    interview_state = session.get('interview', {})
    if interview_state.get('status') != 'active':
        return jsonify({'error': 'No active interview session found.'}), 400

    question_data = _get_current_question(interview_state)
    if not question_data:
        return jsonify({'complete': True})

    return jsonify({'ok': True, 'question': question_data})


@interview_bp.route('/api/interview/answer', methods=['POST'])
def submit_answer():
    interview_state = session.get('interview', {})
    if interview_state.get('status') != 'active':
        return jsonify({'error': 'No active interview session found.'}), 400

    payload = request.get_json(silent=True) or {}
    answer_text = (payload.get('answer') or '').strip()
    answer_mode = (payload.get('answer_mode') or 'text').strip().lower()
    response_seconds = int(payload.get('response_seconds') or 0)

    if answer_mode not in {'text', 'oral'}:
        answer_mode = 'text'

    if not answer_text:
        return jsonify({'error': 'Please provide an answer before moving to the next question.'}), 400

    question_ids = interview_state.get('question_ids', [])
    current_index = interview_state.get('current_index', 0)
    if current_index >= len(question_ids):
        _complete_interview(interview_state)
        session['interview'] = interview_state
        return jsonify({'complete': True, 'redirect_url': url_for('interview.interview_report')})

    question_obj = InterviewQuestion.query.get(question_ids[current_index])
    if not question_obj:
        return jsonify({'error': 'Current question not found.'}), 404

    role_slug = interview_state.get('role', 'web-developer')
    score, feedback = _score_answer(
        answer_text=answer_text,
        category=question_obj.category,
        role_slug=role_slug,
    )

    answer_row = {
        'question': question_obj.question_text,
        'category': question_obj.category,
        'answer': answer_text,
        'answer_mode': answer_mode,
        'score': score,
        'feedback': feedback,
    }
    interview_state.setdefault('answers', []).append(answer_row)

    db_session_id = interview_state.get('db_session_id')
    if db_session_id:
        try:
            db_answer = InterviewResponse(
                session_id=db_session_id,
                question_id=question_obj.id,
                question_text=question_obj.question_text,
                category=question_obj.category,
                answer_mode=answer_mode,
                answer_text=answer_text,
                response_seconds=response_seconds,
                logic_score=score,
                feedback=feedback,
                created_at=datetime.utcnow(),
            )
            db.session.add(db_answer)
            db.session.commit()
        except Exception:
            db.session.rollback()

    interview_state['current_index'] = current_index + 1

    if interview_state['current_index'] >= len(question_ids):
        _complete_interview(interview_state)
        session['interview'] = interview_state
        return jsonify({
            'complete': True,
            'report': interview_state.get('report', {}),
            'redirect_url': url_for('interview.interview_report'),
        })

    session['interview'] = interview_state
    next_q = _get_current_question(interview_state)
    return jsonify({
        'ok': True,
        'question': next_q,
        'last_score': score,
        'last_feedback': feedback,
    })


@interview_bp.route('/api/interview/end', methods=['POST'])
def end_interview():
    interview_state = session.get('interview', {})
    if not interview_state:
        return jsonify({'error': 'No interview session found.'}), 400

    _complete_interview(interview_state)
    session['interview'] = interview_state

    return jsonify({
        'ok': True,
        'report': interview_state.get('report', {}),
        'redirect_url': url_for('interview.interview_report'),
    })


def _serialize_question(question_obj, index: int, total: int):
    return {
        'id': question_obj.id,
        'text': question_obj.question_text,
        'category': question_obj.category,
        'round_label': ROUND_LABELS.get(question_obj.category, question_obj.category.title()),
        'index': index,
        'total': total,
    }


def _get_current_question(interview_state):
    question_ids = interview_state.get('question_ids', [])
    current_index = interview_state.get('current_index', 0)
    if current_index >= len(question_ids):
        return None

    question_obj = InterviewQuestion.query.get(question_ids[current_index])
    if not question_obj:
        return None

    return _serialize_question(question_obj, index=current_index + 1, total=len(question_ids))


def _slugify_role(role_name: str):
    return (role_name or '').strip().lower().replace(' ', '-')


def _seed_question_bank_for_role(role_slug: str):
    existing_count = InterviewQuestion.query.filter_by(role_slug=role_slug, is_active=True).count()
    if existing_count >= 15:
        return

    role_keywords = TECH_ROLE_KEYWORDS.get(role_slug, TECH_ROLE_KEYWORDS.get('web-developer', []))
    technical_questions = []

    for idx, keyword in enumerate(role_keywords[:10]):
        template = TECHNICAL_PROMPTS[idx % len(TECHNICAL_PROMPTS)]
        technical_questions.append(template.format(keyword=keyword))

    technical_questions.extend([
        'Explain your approach to writing maintainable and readable code under deadlines.',
        'How do you troubleshoot production bugs when logs are incomplete?',
        'How do you balance feature delivery and technical debt reduction?',
    ])

    technical_questions = technical_questions[:12]

    ordered_questions = []
    for item in INTRO_QUESTIONS[:5]:
        ordered_questions.append({'category': 'intro', 'question_text': item, 'difficulty': 'easy'})

    for item in technical_questions:
        ordered_questions.append({'category': 'technical', 'question_text': item, 'difficulty': 'medium'})

    for item in PRESSURE_QUESTIONS:
        ordered_questions.append({'category': 'pressure', 'question_text': item, 'difficulty': 'hard'})

    if existing_count > 0:
        InterviewQuestion.query.filter_by(role_slug=role_slug).delete()
        db.session.commit()

    for order_index, row in enumerate(ordered_questions, start=1):
        db.session.add(InterviewQuestion(
            role_slug=role_slug,
            category=row['category'],
            question_text=row['question_text'],
            difficulty=row['difficulty'],
            order_index=order_index,
            is_active=True,
            created_at=datetime.utcnow(),
        ))

    db.session.commit()


def _get_resume_context(role_slug: str):
    context = {
        'has_analysis': False,
        'ats_score': 0,
        'missing_keywords': [],
        'weak_points': [],
    }

    if not current_user.is_authenticated:
        return context

    role_title = role_slug.replace('-', ' ').title()
    resume = Resume.query.filter_by(user_id=current_user.id, role_target=role_title).order_by(Resume.created_at.desc()).first()
    if not resume:
        return context

    try:
        analysis = json.loads(resume.analysis) if resume.analysis else {}
    except Exception:
        analysis = {}

    if not analysis:
        return context

    context['has_analysis'] = True
    context['ats_score'] = analysis.get('ats_score', resume.ats_score or 0)
    context['missing_keywords'] = analysis.get('missing_keywords', [])[:6]
    context['weak_points'] = analysis.get('weak_points', [])[:4]
    return context


def _score_answer(answer_text: str, category: str, role_slug: str):
    text = answer_text.lower()
    words = [token for token in text.split() if token.strip()]
    word_count = len(words)

    base_score = min(45, word_count * 1.5)

    structure_bonus = 0
    for marker in ['because', 'therefore', 'for example', 'result', 'impact']:
        if marker in text:
            structure_bonus += 5
    structure_bonus = min(structure_bonus, 20)

    keyword_bonus = 0
    if category == 'technical':
        role_keywords = TECH_ROLE_KEYWORDS.get(role_slug, [])
        matched = [kw for kw in role_keywords if kw.lower() in text]
        keyword_bonus = min(len(matched) * 6, 25)

    pressure_bonus = 0
    if category == 'pressure':
        for token in ['prioritize', 'communicate', 'risk', 'rollback', 'stakeholder', 'tradeoff']:
            if token in text:
                pressure_bonus += 4
        pressure_bonus = min(pressure_bonus, 20)

    final_score = min(round(base_score + structure_bonus + keyword_bonus + pressure_bonus, 1), 100.0)

    if final_score >= 80:
        feedback = 'Strong answer with clear structure and practical thinking.'
    elif final_score >= 65:
        feedback = 'Good answer. Add more specific examples and measurable outcomes.'
    elif final_score >= 45:
        feedback = 'Average answer. Improve depth, structure, and technical precision.'
    else:
        feedback = 'Needs improvement. Use a clearer framework and concrete examples.'

    return final_score, feedback


def _compute_elapsed(interview_state):
    start_time = interview_state.get('start_time')
    end_time = interview_state.get('end_time')
    if not start_time:
        return 0
    if not end_time:
        end_time = time.time()
    return max(0, int(end_time - start_time))


def _complete_interview(interview_state):
    if interview_state.get('status') == 'completed':
        return

    interview_state['status'] = 'completed'
    interview_state['end_time'] = time.time()
    report = _build_report_from_answers(
        interview_state.get('answers', []),
        interview_state.get('role', 'web-developer'),
        interview_state.get('resume_context', {}),
        elapsed_seconds=_compute_elapsed(interview_state),
    )
    interview_state['report'] = report

    db_session_id = interview_state.get('db_session_id')
    if db_session_id:
        try:
            db_row = InterviewSession.query.get(db_session_id)
            if db_row:
                db_row.status = 'completed'
                db_row.overall_score = report.get('overall_score', 0)
                db.session.commit()
        except Exception:
            db.session.rollback()


def _build_report_from_answers(answers, role_slug, resume_context, elapsed_seconds=0):
    intro_scores = [item['score'] for item in answers if item.get('category') == 'intro']
    technical_scores = [item['score'] for item in answers if item.get('category') == 'technical']
    pressure_scores = [item['score'] for item in answers if item.get('category') == 'pressure']

    intro_avg = round(mean(intro_scores), 1) if intro_scores else 0.0
    technical_avg = round(mean(technical_scores), 1) if technical_scores else 0.0
    pressure_avg = round(mean(pressure_scores), 1) if pressure_scores else 0.0

    all_scores = [item.get('score', 0) for item in answers]
    overall = round(mean(all_scores), 1) if all_scores else 0.0

    strengths = []
    improvements = []

    if intro_avg >= 75:
        strengths.append('Your self-introduction and communication clarity are strong.')
    else:
        improvements.append('Refine your 60-second introduction using role relevance and outcomes.')

    if technical_avg >= 75:
        strengths.append('Technical explanations showed good depth and practical understanding.')
    else:
        improvements.append('Increase technical depth with architecture decisions, tradeoffs, and metrics.')

    if pressure_avg >= 70:
        strengths.append('Pressure-handling responses showed calm prioritization and communication.')
    else:
        improvements.append('Use structured incident response: assess risk, communicate, prioritize, then execute.')

    if resume_context.get('has_analysis'):
        strengths.append('Resume analysis context was reused to avoid re-processing profile basics.')
        missing = resume_context.get('missing_keywords', [])
        if missing:
            improvements.append('Practice answers that naturally include missing keywords: ' + ', '.join(missing[:4]) + '.')

    if not strengths:
        strengths.append('You completed a full mock interview session and captured answer history for review.')

    if not improvements:
        improvements.append('Keep practicing concise STAR-style answers and quantify outcomes where possible.')

    recommendations = [
        'Use the STAR format (Situation, Task, Action, Result) for scenario and pressure questions.',
        'Add one concrete project example in every technical answer.',
        'Limit each answer to 60-120 seconds with clear structure.',
        'Track weak questions and repeat them in your next mock session.',
    ]

    detailed_feedback = []
    for idx, item in enumerate(answers, start=1):
        detailed_feedback.append({
            'index': idx,
            'category': item.get('category', 'technical'),
            'question': item.get('question', ''),
            'answer_mode': item.get('answer_mode', 'text'),
            'score': item.get('score', 0),
            'feedback': item.get('feedback', ''),
        })

    return {
        'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
        'role': role_slug.replace('-', ' ').title(),
        'total_questions': len(answers),
        'duration_minutes': round(elapsed_seconds / 60.0, 1) if elapsed_seconds else 0,
        'overall_score': overall,
        'intro_score': intro_avg,
        'technical_score': technical_avg,
        'pressure_score': pressure_avg,
        'resume_context_used': bool(resume_context.get('has_analysis')),
        'resume_ats_score': resume_context.get('ats_score', 0),
        'strengths': strengths,
        'improvements': improvements,
        'recommendations': recommendations,
        'detailed_feedback': detailed_feedback,
    }
