from ResumAi.extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, LoginManager
# from ResumAi import db, login_manager  # Import login_manager

class User(UserMixin,db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(100))  # 'candidate', 'recruiter'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    resumes = db.relationship('Resume', backref='user', lazy=True)
    interviews = db.relationship('InterviewSession', backref='user', lazy=True)


class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    ats_score = db.Column(db.Float, default=0.0)
    analysis = db.Column(db.Text)  # JSON string of analysis
    role_target = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    rounds = db.relationship('InterviewRound', backref='resume', lazy=True)


class InterviewSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    resume_id = db.Column(db.Integer, db.ForeignKey('resume.id'))
    role = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, active, completed
    overall_score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    rounds = db.relationship('InterviewRound', backref='session', lazy=True)


class InterviewRound(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_session.id'), nullable=False)
    resume_id = db.Column(db.Integer, db.ForeignKey('resume.id'), nullable=False)
    round_number = db.Column(db.Integer, nullable=False)  # 1, 2, 3
    question = db.Column(db.Text, nullable=False)
    audio_path = db.Column(db.String(500))
    video_path = db.Column(db.String(500))
    ai_score = db.Column(db.Float, default=0.0)
    feedback = db.Column(db.Text)
    body_language_score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class InterviewQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role_slug = db.Column(db.String(100), nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False)  # intro, technical, pressure
    question_text = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(30), default='medium')
    order_index = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class InterviewResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_session.id'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('interview_question.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), nullable=False)
    answer_mode = db.Column(db.String(20), default='text')  # text, oral
    answer_text = db.Column(db.Text)
    response_seconds = db.Column(db.Integer, default=0)
    logic_score = db.Column(db.Float, default=0.0)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    question = db.relationship('InterviewQuestion', backref='responses')


InterviewSession.responses = db.relationship('InterviewResponse', backref='session', lazy=True, cascade='all, delete-orphan')

# @login_manager.user_loader
# def load_user(user_id):
#     return User.query.get(int(user_id))