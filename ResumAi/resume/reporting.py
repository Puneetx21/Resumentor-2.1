import os
import re
from datetime import datetime
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", (value or "").strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "user"


def _role_short_slug(role: str) -> str:
    normalized = _safe_filename_part(role)
    if not normalized:
        return "role"
    return normalized.split("-")[0]


def build_report_filename(username: str, role: str) -> str:
    # Example: punit-python_report.pdf
    return f"{_safe_filename_part(username)}-{_role_short_slug(role)}_report.pdf"


def _bulleted(items: List[str]) -> str:
    if not items:
        return "- None"
    return "<br/>".join(f"- {item}" for item in items)


def _create_card_section(title: str, items: List[str], color_hex: str, doc_width: float) -> Table:
    """Create a modern card-style section with color-coded header."""
    if not items or len(items) == 0:
        items = ["No data available"]
    
    # Format bullet points with proper indentation
    bullet_rows = [[f"• {item}"] for item in items]
    
    # Create header row
    title_row = [[Paragraph(f"<b>{title}</b>", ParagraphStyle(
        "CardTitle",
        fontSize=11,
        textColor=colors.white,
        fontName="Helvetica-Bold"
    ))]]
    
    # Build card table
    card_data = title_row + bullet_rows
    card_table = Table(card_data, colWidths=[doc_width - 72])
    
    card_table.setStyle(TableStyle([
        # Header styling
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(color_hex)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        
        # Content styling
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#1e293b")),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("LEFTPADDING", (0, 1), (-1, -1), 12),
        
        # Borders
        ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
    ]))
    
    return card_table


def _create_feedback_section(label: str, items: List[str], status_color: str, doc_width: float) -> Table:
    """Create a feedback card with status indicator and bullet points."""
    if not items or len(items) == 0:
        items = ["No feedback at this time"]
    
    # Format bullet points with icon prefix
    icon_map = {
        "Good": "✓",
        "Weak": "⚠",
        "Add": "➕",
        "Keywords": "🔑",
        "Layout": "📐"
    }
    icon = icon_map.get(label.split()[0], "•")
    
    # Build rows
    rows = []
    for i, item in enumerate(items):
        if i == 0:
            # First row with header
            rows.append([Paragraph(f"<b>{label}</b>", ParagraphStyle(
                "FeedbackTitle",
                fontSize=11,
                textColor=colors.HexColor(status_color),
                fontName="Helvetica-Bold"
            )), Paragraph(f"<b>{item}</b>", ParagraphStyle(
                "FeedbackItem",
                fontSize=10,
                textColor=colors.HexColor("#1e293b"),
                fontName="Helvetica"
            ))])
        else:
            rows.append(["", Paragraph(item, ParagraphStyle(
                "FeedbackItem",
                fontSize=10,
                textColor=colors.HexColor("#1e293b"),
                fontName="Helvetica"
            ))])
    
    table = Table(rows, colWidths=[doc_width * 0.15, doc_width * 0.85 - 72])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    
    return table


def _draw_header_footer(canvas, doc, candidate_name: str, role_label: str) -> None:
    """Draw header/footer on each page for both first and later pages."""
    w, h = doc.pagesize

    canvas.saveState()

    # Top header bar
    canvas.setFillColor(colors.HexColor("#1e40af"))
    canvas.rect(0, h - 35, w, 35, fill=1, stroke=0)

    canvas.setFont("Helvetica-Bold", 12)
    canvas.setFillColor(colors.white)
    canvas.drawString(40, h - 22, "SmartATS Resume Report")

    canvas.setFont("Helvetica", 10)
    name_width = canvas.stringWidth(candidate_name, "Helvetica", 10)
    canvas.drawString(w - 40 - name_width, h - 22, candidate_name)

    # Bottom footer bar
    canvas.setFillColor(colors.HexColor("#f1f5f9"))
    canvas.rect(0, 0, w, 28, fill=1, stroke=0)

    canvas.setLineWidth(1)
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.line(0, 28, w, 28)

    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(40, 12, f"Role: {role_label}")

    page_text = f"Page {canvas.getPageNumber()}"
    page_width = canvas.stringWidth(page_text, "Helvetica", 9)
    canvas.drawString(w - 40 - page_width, 12, page_text)

    canvas.restoreState()


def _metric_table_rows(metrics: List[Dict]) -> List[List[str]]:
    rows = [["Metric", "Score"]]
    for metric in metrics:
        rows.append([metric.get("label", "Metric"), f"{metric.get('value', 0)}/100"])
    return rows


def generate_resume_report_pdf(output_path: str, analysis: Dict) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report_title = analysis.get("report_title", "Resume ATS Analysis Report")
    role = analysis.get("role_label", analysis.get("job_role", "unknown").replace("-", " ").title())
    candidate_name = analysis.get("candidate_name", "Candidate")

    # Create document with adjusted margins for header/footer
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        title=report_title,
        leftMargin=36,
        rightMargin=36,
        topMargin=65,  # Increased for header space (35pt header + 30pt buffer)
        bottomMargin=50,  # Increased for footer space (28pt footer + 22pt buffer)
    )

    def draw_page(canvas, document):
        _draw_header_footer(canvas, document, candidate_name, role)

    styles = getSampleStyleSheet()
    normal = styles["BodyText"]
    heading = styles["Heading2"]

    banner_style = ParagraphStyle(
        "Banner",
        parent=styles["Heading1"],
        fontSize=16,
        leading=19,
        textColor=colors.white,
        spaceBefore=0,
        spaceAfter=0,
    )

    section_header = ParagraphStyle(
        "SectionHeader",
        parent=heading,
        fontSize=12,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=8,
        spaceAfter=6,
    )

    role = analysis.get("role_label", analysis.get("job_role", "unknown").replace("-", " ").title())
    candidate_name = analysis.get("candidate_name", "Candidate")
    score = analysis.get("ats_score", 0)
    keyword_coverage = analysis.get("keyword_coverage", 0)
    experience_level = analysis.get("experience_level", "Junior (0-3 YoE)")
    score_label = analysis.get("score_label", "Good")
    score_explanation = analysis.get("score_explanation", "Resume has reasonable ATS readiness.")
    detailed_metrics = analysis.get("detailed_metrics", [])

    banner = Table([[Paragraph(report_title, banner_style)]], colWidths=[doc.width])
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1e40af")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    score_band = Table(
        [[f"Overall ATS Score: {score}/100", f"Keyword Coverage: {keyword_coverage}%"]],
        colWidths=[doc.width / 2, doc.width / 2],
    )
    score_band.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e2e8f0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1e3a8a")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#bfdbfe")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    summary_rows = [
        ["Candidate Name", candidate_name],
        ["Target Role", role],
        ["Overall ATS Score", f"{score}/100"],
        ["Experience Level", experience_level],
        ["Keyword Coverage", f"{keyword_coverage}%"],
    ]
    summary_table = Table(summary_rows, colWidths=[doc.width * 0.33, doc.width * 0.67])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    metrics_table = Table(_metric_table_rows(detailed_metrics), colWidths=[doc.width * 0.67, doc.width * 0.33])
    metrics_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    recommendation_rows = []
    for rec in analysis.get("section_recommendations", []):
        status = "GOOD" if rec.get("status") == "good" else "IMPROVE"
        recommendation_rows.append([rec.get("section", "Section"), status, rec.get("message", "")])
    if not recommendation_rows:
        recommendation_rows = [["Sections", "GOOD", "Core sections detected"]]

    section_table = Table(
        [["Section", "Status", "Recommendation"]] + recommendation_rows,
        colWidths=[doc.width * 0.22, doc.width * 0.16, doc.width * 0.62],
    )
    section_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    story = [
        banner,
        Spacer(1, 8),
        Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", normal),
        Spacer(1, 8),
        score_band,
        Spacer(1, 10),
        Paragraph("Summary", section_header),
        summary_table,
        Spacer(1, 10),
        Paragraph("Score Explanation", section_header),
        Paragraph(f"<b>{score_label.upper()}</b> - {score_explanation}", normal),
        Spacer(1, 10),
        Paragraph("Detailed Metrics", section_header),
        metrics_table,
        Spacer(1, 10),
        Paragraph("Resume Section Recommendations", section_header),
        section_table,
        Spacer(1, 14),
        Paragraph("Analysis & Feedback", ParagraphStyle(
            "PageSectionTitle",
            parent=heading,
            fontSize=13,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=6,
            spaceAfter=6,
            fontName="Helvetica-Bold"
        )),
        Spacer(1, 8),
        
        # Modern card-based feedback sections
        _create_card_section("✓ Good Points", analysis.get("strong_points", []), "#10b981", doc.width),
        Spacer(1, 8),
        _create_card_section("⚠ What Needs Improvement", analysis.get("weak_points", []), "#f59e0b", doc.width),
        Spacer(1, 8),
        _create_card_section("➕ What You Can Add", analysis.get("recommended_additions", []), "#8b5cf6", doc.width),
        Spacer(1, 8),
        _create_card_section("🔑 Missing Keywords", analysis.get("missing_keywords", []), "#3b82f6", doc.width),
        Spacer(1, 10),
        Paragraph("📐 Layout Feedback", ParagraphStyle(
            "FeedbackHeader",
            parent=heading,
            fontSize=11,
            textColor=colors.HexColor("#1e40af"),
            fontName="Helvetica-Bold"
        )),
        Paragraph(analysis.get("layout_feedback", "Use ATS-friendly formatting and concise bullets."), ParagraphStyle(
            "FeedbackText",
            fontSize=10,
            textColor=colors.HexColor("#1e293b"),
            leftIndent=12,
            rightIndent=12
        )),
    ]

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)


def generate_interview_report_pdf(output_path: str, report: Dict, candidate_name: str = "Candidate") -> None:
    """Generate a PDF report for mock interview performance."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    role = report.get("role", "Tech Role")
    report_title = f"Interview Report - {candidate_name} ({role})"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        title=report_title,
        leftMargin=36,
        rightMargin=36,
        topMargin=65,
        bottomMargin=50,
    )

    def draw_page(canvas, document):
        w, h = document.pagesize
        canvas.saveState()

        # Header bar
        canvas.setFillColor(colors.HexColor("#1e40af"))
        canvas.rect(0, h - 35, w, 35, fill=1, stroke=0)

        canvas.setFont("Helvetica-Bold", 12)
        canvas.setFillColor(colors.white)
        canvas.drawString(40, h - 22, "SmartATS Interview Report")

        canvas.setFont("Helvetica", 10)
        name_width = canvas.stringWidth(candidate_name, "Helvetica", 10)
        canvas.drawString(w - 40 - name_width, h - 22, candidate_name)

        # Footer bar
        canvas.setFillColor(colors.HexColor("#f1f5f9"))
        canvas.rect(0, 0, w, 28, fill=1, stroke=0)

        canvas.setLineWidth(1)
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.line(0, 28, w, 28)

        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(40, 12, f"Role: {role}")

        page_text = f"Page {canvas.getPageNumber()}"
        page_width = canvas.stringWidth(page_text, "Helvetica", 9)
        canvas.drawString(w - 40 - page_width, 12, page_text)

        canvas.restoreState()

    styles = getSampleStyleSheet()
    normal = styles["BodyText"]
    heading = styles["Heading2"]

    banner_style = ParagraphStyle(
        "Banner",
        parent=styles["Heading1"],
        fontSize=16,
        leading=19,
        textColor=colors.white,
        spaceBefore=0,
        spaceAfter=0,
    )

    section_header = ParagraphStyle(
        "SectionHeader",
        parent=heading,
        fontSize=12,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=8,
        spaceAfter=6,
    )

    # Banner
    banner = Table([[Paragraph(report_title, banner_style)]], colWidths=[doc.width])
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1e40af")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    # Summary metrics
    overall_score = report.get("overall_score", 0)
    total_questions = report.get("total_questions", 0)
    duration = report.get("duration_minutes", 0)

    metrics_band = Table(
        [[f"Overall Score: {overall_score}/100", f"Questions: {total_questions}", f"Duration: {duration} min"]],
        colWidths=[doc.width / 3, doc.width / 3, doc.width / 3],
    )
    metrics_band.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e2e8f0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1e3a8a")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#bfdbfe")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    # Round scores
    intro_score = report.get("intro_score", 0)
    technical_score = report.get("technical_score", 0)
    pressure_score = report.get("pressure_score", 0)

    round_scores_table = Table(
        [["Round", "Score"], ["Introduction", f"{intro_score}/100"], ["Technical", f"{technical_score}/100"], ["Pressure", f"{pressure_score}/100"]],
        colWidths=[doc.width * 0.5, doc.width * 0.5],
    )
    round_scores_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    # Strengths
    strengths_table = _create_card_section("✓ Strengths", report.get("strengths", []), "#10b981", doc.width)

    # Improvements
    improvements_table = _create_card_section("⚠ Improvements", report.get("improvements", []), "#f59e0b", doc.width)

    # Recommendations
    recommendations_list = "\n".join([f"• {item}" for item in report.get("recommendations", [])])

    # Detailed feedback table
    detailed_feedback = report.get("detailed_feedback", [])
    feedback_rows = [["#", "Round", "Mode", "Score", "Feedback"]]
    for item in detailed_feedback:
        feedback_rows.append([str(item.get("index", "")), item.get("category", "").capitalize(), item.get("answer_mode", "").capitalize(), f"{item.get('score', 0)}/100", item.get("feedback", "")])

    feedback_table = Table(feedback_rows, colWidths=[doc.width * 0.08, doc.width * 0.15, doc.width * 0.12, doc.width * 0.12, doc.width * 0.53])
    feedback_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )

    story = [
        banner,
        Spacer(1, 8),
        Paragraph(f"Generated on {report.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M'))}", normal),
        Spacer(1, 8),
        metrics_band,
        Spacer(1, 12),
        Paragraph("Round-wise Scores", section_header),
        round_scores_table,
        Spacer(1, 12),
        strengths_table,
        Spacer(1, 10),
        improvements_table,
        Spacer(1, 12),
        Paragraph("Action Plan", section_header),
        Paragraph(recommendations_list, normal),
        Spacer(1, 12),
        Paragraph("Question-by-Question Feedback", section_header),
        feedback_table,
    ]

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
