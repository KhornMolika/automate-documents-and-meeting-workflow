import csv
import io
import json
from datetime import datetime
from docx import Document as DocxDocument
from docx.shared import Pt


def _discussion_points(summary) -> list[str]:
    try:
        points = json.loads(summary.discussion_highlights or "[]")
        return points if isinstance(points, list) else []
    except Exception:
        return []


def _attendee_name(participant) -> str:
    if getattr(participant, "user", None) and participant.user.full_name:
        return participant.user.full_name
    return participant.external_name or "Unnamed attendee"


def build_mom_docx(meeting, summary) -> bytes:
    document = DocxDocument()
    document.add_heading("ACLEDA UNIVERSITY OF BUSINESS", level=0)
    document.add_paragraph("Faculty of Science & Technology · Official Minutes of Meeting")
    document.add_heading(meeting.title, level=1)
    department = getattr(getattr(meeting, "department", None), "name", None)
    if department:
        document.add_paragraph(f"Department: {department}")
    document.add_paragraph(
        f"Meeting date: {meeting.scheduled_start:%d %B %Y, %H:%M}–{meeting.scheduled_end:%H:%M}"
    )
    document.add_paragraph(f"Status: {meeting.status}")
    document.add_paragraph(f"Verified by: {summary.verified_by or 'Pending'}")

    document.add_heading("Attendees", level=2)
    participants = list(getattr(meeting, "participants", []) or [])
    if participants:
        table = document.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        for cell, label in zip(table.rows[0].cells, ["Name", "Role", "Attendance"]):
            cell.text = label
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True
        for participant in participants:
            cells = table.add_row().cells
            cells[0].text = _attendee_name(participant)
            cells[1].text = participant.role_in_meeting or "Attendee"
            cells[2].text = participant.attendance_status or "Invited"
    else:
        document.add_paragraph("No attendee records were captured.")

    agendas = list(getattr(meeting, "agendas", []) or [])
    document.add_heading("Agenda", level=2)
    if agendas:
        for agenda in agendas:
            paragraph = document.add_paragraph(style="List Number")
            paragraph.add_run(agenda.title)
            if agenda.duration_minutes:
                paragraph.add_run(f" ({agenda.duration_minutes} min)")
    else:
        document.add_paragraph("No agenda was recorded.")

    document.add_heading("1. Executive summary", level=2)
    document.add_paragraph(summary.executive_summary)

    points = _discussion_points(summary)
    if points:
        document.add_heading("2. Key discussion points", level=2)
        for point in points:
            paragraph = document.add_paragraph(style="List Bullet")
            paragraph.add_run(str(point))

    decisions = list(summary.decisions)
    if decisions:
        document.add_heading("3. Formal decisions", level=2)
        for index, decision in enumerate(decisions, start=1):
            paragraph = document.add_paragraph(style="List Number")
            run = paragraph.add_run(decision.decision_text)
            run.bold = True
            if decision.agenda_topic:
                paragraph.add_run(f" ({decision.agenda_topic})")

    action_items = list(summary.action_items)
    if action_items:
        document.add_heading("4. Action items", level=2)
        table = document.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        for cell, label in zip(table.rows[0].cells, ["Task", "Assignee", "Deadline", "Status"]):
            cell.text = label
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True
                    run.font.size = Pt(10)
        for item in action_items:
            cells = table.add_row().cells
            cells[0].text = item.task_description
            cells[1].text = item.raw_assignee_name or "Unassigned"
            cells[2].text = item.deadline.isoformat() if item.deadline else "—"
            cells[3].text = item.status

    document.add_paragraph()
    document.add_paragraph(f"Generated {datetime.utcnow():%d %B %Y, %H:%M} UTC")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def build_action_items_csv(meeting, summary) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Meeting", "Task", "Assignee", "Deadline", "Status"])
    for item in summary.action_items:
        writer.writerow(
            [
                meeting.title,
                item.task_description,
                item.raw_assignee_name or "",
                item.deadline.isoformat() if item.deadline else "",
                item.status,
            ]
        )
    return buffer.getvalue()
