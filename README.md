# ResumAi

ResumAi is a Flask web app that helps candidates:
- Analyze resumes for ATS readiness by role.
- Practice structured mock interviews.
- Generate downloadable PDF reports for resume and interview performance.

## Current Workflow

1. User opens the home page (`/`).
2. User logs in using Google OAuth (`/login` -> `/auth/google`).
3. User uploads a PDF resume at `/resume` and selects a target role.
4. App extracts text, scores ATS readiness, and shows a detailed report.
5. User can download the resume report PDF from `/resume/report/download`.
6. User starts an interview at `/interview`.
7. App creates role-specific question rounds (intro, technical, pressure), collects answers, and scores responses.
8. User views interview report (`/interview/report`) and can download PDF.
9. Dashboard (`/dashboard`) and History (`/history`) show saved resume/interview results and allow report re-download.

## Feature Summary

- Resume ATS scoring with role-based keywords.
- Interview engine with dynamic technical questions from role keyword sets.
- Logic-based scoring for both resume and interview flows.
- User account/session handling via Google OAuth + Flask-Login.
- Persistent history with SQLAlchemy models.
- PDF report generation using ReportLab.

## Supported Tech Roles

Currently defined role slugs include:
- `web-developer`
- `python-developer`
- `java-developer`
- `cpp-developer`
- `fullstack-developer`
- `frontend-developer`
- `backend-developer`
- `mern-stack`
- `ai-engineer`
- `data-analyst`
- `devops-engineer`

## Tech Stack

- Python
- Flask, Flask-Login, Flask-SQLAlchemy
- Authlib (Google OAuth)
- pdfplumber (resume text extraction)
- ReportLab (PDF reports)
- SQLite or PostgreSQL (via `DATABASE_URL`)

## Project Structure

- `run.py`: app entry point.
- `ResumAi/__init__.py`: app factory, extension init, blueprint registration.
- `ResumAi/auth/routes.py`: login/logout + Google callback.
- `ResumAi/resume/routes.py`: upload, ATS analysis, report screens/download.
- `ResumAi/interview/routes.py`: interview APIs, scoring, report screens/download.
- `ResumAi/dashboard/routes.py`: dashboard/profile/history views.
- `ResumAi/models.py`: SQLAlchemy models.
- `ResumAi/resume/reporting.py`: PDF generation for reports.

## Setup

### 1. Clone and enter project

```powershell
git clone <your-repo-url>
cd ResumAi
```

### 2. Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Create `.env`

Create a `.env` file in the project root with:

```env
SECRET_KEY=change-this-secret
FLASK_ENV=development
DATABASE_URL=sqlite:///dev.db
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

Notes:
- For local development, SQLite works out of the box.
- For PostgreSQL, set `DATABASE_URL` accordingly, for example:
  `postgresql+psycopg2://user:password@localhost:5432/resumai`

### 5. Run the app

```powershell
python run.py
```

Open `http://127.0.0.1:5000`.

## Basic Verification

Run local checks included in the repo:

```powershell
python test_db_connection.py
python test_auth.py
```

## Main Routes

- `/` Home
- `/login` Login page
- `/dashboard` User dashboard
- `/profile` User profile
- `/history` Resume/interview history
- `/resume` Resume analyzer page
- `/resume/report` Last resume report view
- `/interview` Interview page
- `/interview/report` Latest interview report view

## Notes

- The app creates database tables automatically on startup (`db.create_all()`).
- Uploads and generated reports are written under `uploads/resumes` and `uploads/reports`.
- Ensure your OAuth redirect URI is configured to match `/auth/google/callback`.
