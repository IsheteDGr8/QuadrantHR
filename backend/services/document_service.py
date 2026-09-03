"""Ticket document generation with persisted conversation history."""

from __future__ import annotations

import io
from html import escape
from typing import Optional

from database.crud import get_ticket_by_id, get_ticket_comments


def _export_data(
    ticket_id: str,
    *,
    ticket: Optional[dict] = None,
    comments: Optional[list[dict]] = None,
) -> tuple[dict, list[dict]]:
    resolved_ticket = ticket or get_ticket_by_id(ticket_id)
    if not resolved_ticket:
        # Preserve the service's legacy direct-call behavior used by automation and
        # offline report generation. The authenticated API validates existence and
        # authorization before calling this service with a concrete ticket.
        resolved_ticket = {
            "id": ticket_id,
            "title": "Ticket Summary",
            "department": "Support",
            "category": "General",
            "priority": "Medium",
            "status": "Open",
            "description": "No description provided.",
        }
    return resolved_ticket, comments if comments is not None else get_ticket_comments(
        ticket_id
    )


def generate_ticket_pdf(
    ticket_id: str,
    *,
    ticket: Optional[dict] = None,
    comments: Optional[list[dict]] = None,
) -> bytes:
    """Generate a PDF report containing ticket metadata and conversation."""
    ticket, comments = _export_data(ticket_id, ticket=ticket, comments=comments)

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=f"TicketGenie Ticket {ticket.get('id', ticket_id)}",
        author="TicketGenie",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TicketTitle",
        parent=styles["Heading1"],
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=12,
    )

    def cell(value: object) -> Paragraph:
        return Paragraph(
            escape(str(value if value is not None else "N/A")), styles["BodyText"]
        )

    elements = [
        Paragraph("TicketGenie - Ticket Report", title_style),
        Paragraph(
            f"Complete record for Ticket ID: <b>{escape(str(ticket.get('id', ticket_id)))}</b>",
            styles["Heading3"],
        ),
        Spacer(1, 16),
    ]
    reason_val = ticket.get("reason") or ticket.get("classification_reason")
    conf_val = ticket.get("confidence") or ticket.get("classification_confidence")
    conf_pct = ""
    if conf_val is not None:
        try:
            conf_pct = f" ({int(float(conf_val) * 100)}% confidence)"
        except Exception:
            pass

    details = [
        ["Field", "Value"],
        ["Ticket ID", cell(ticket.get("id", ticket_id))],
        ["Title", cell(ticket.get("title", "N/A"))],
        ["Department", cell(ticket.get("department", "N/A"))],
        ["Category", cell(ticket.get("category", "N/A"))],
        ["Priority", cell(ticket.get("priority", "N/A"))],
        ["Status", cell(ticket.get("status", "N/A"))],
        ["Created", cell(ticket.get("createdAt") or ticket.get("date", "N/A"))],
        ["Last Updated", cell(ticket.get("updatedAt", "N/A"))],
    ]

    if reason_val:
        details.append(
            [
                "AI Classification",
                cell(f"AI Auto-Classification{conf_pct}: {reason_val}"),
            ]
        )

    details.append(["Description", cell(ticket.get("description", "N/A"))])

    details_table = Table(details, colWidths=[125, 405], repeatRows=1)
    details_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f8fafc")],
                ),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    elements.extend(
        [
            details_table,
            Spacer(1, 22),
            Paragraph("Conversation History", styles["Heading2"]),
            Spacer(1, 8),
        ]
    )

    export_comments = list(comments) if comments else []
    if reason_val and not any(
        c.get("sender_role") == "AI Genie (System)" or c.get("sender_role") == "System"
        for c in export_comments
    ):
        export_comments.insert(
            0,
            {
                "createdAt": "Auto-Triaged",
                "sender_role": "AI Genie (System)",
                "message": f"AI Auto-Classification{conf_pct}: {reason_val}",
            },
        )

    if export_comments:
        rows = [["Date / Time", "Sender", "Message"]]
        rows.extend(
            [
                cell(c.get("createdAt", "N/A")),
                cell(c.get("sender_role", "Unknown")),
                cell(c.get("message", "")),
            ]
            for c in export_comments
        )
        conversation = Table(rows, colWidths=[115, 90, 325], repeatRows=1)
        conversation.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f8fafc")],
                    ),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(conversation)
    else:
        elements.append(
            Paragraph(
                "No conversation messages have been recorded.", styles["BodyText"]
            )
        )

    elements.extend(
        [
            Spacer(1, 24),
            Paragraph(
                "<i>Generated by TicketGenie. This report contains the ticket record and public support conversation available to the requesting user.</i>",
                styles["Italic"],
            ),
        ]
    )
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generate_conversation_pdf(conversation: dict, messages: list[dict]) -> bytes:
    """Generate a readable PDF transcript for one persisted Genie conversation."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    title = str(conversation.get("title") or "Genie conversation")
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
        title=f"TicketGenie - {title}",
        author="TicketGenie",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ConversationTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        "ConversationMeta",
        parent=styles["BodyText"],
        fontSize=9,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=16,
    )
    message_style = ParagraphStyle(
        "ConversationMessage",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
    )

    elements = [
        Paragraph("TicketGenie - Genie AI Conversation", title_style),
        Paragraph(escape(title), styles["Heading2"]),
        Paragraph(
            "Created: "
            + escape(
                str(
                    conversation.get("createdAt")
                    or conversation.get("created_at")
                    or "N/A"
                )
            )
            + " &nbsp;&nbsp; Updated: "
            + escape(
                str(
                    conversation.get("updatedAt")
                    or conversation.get("updated_at")
                    or "N/A"
                )
            ),
            meta_style,
        ),
    ]

    rows = [["Speaker", "Time", "Message"]]
    for message in messages:
        role = "User" if message.get("role") == "user" else "Genie AI"
        created_at = message.get("createdAt") or message.get("created_at") or "N/A"
        content = escape(str(message.get("content") or "")).replace("\n", "<br/>")
        rows.append(
            [
                Paragraph(role, message_style),
                Paragraph(escape(str(created_at)), message_style),
                Paragraph(content, message_style),
            ]
        )

    if len(rows) == 1:
        elements.append(
            Paragraph("No messages have been recorded.", styles["BodyText"])
        )
    else:
        transcript = Table(rows, colWidths=[70, 105, 335], repeatRows=1)
        transcript.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b1b38")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        elements.extend([transcript, Spacer(1, 14)])

    elements.append(
        Paragraph(
            "Generated by TicketGenie for the authenticated conversation owner.",
            meta_style,
        )
    )
    doc.build(elements)
    return buffer.getvalue()


def generate_ticket_docx(
    ticket_id: str,
    *,
    ticket: Optional[dict] = None,
    comments: Optional[list[dict]] = None,
) -> bytes:
    """Generate a text-compatible DOCX export containing the same report data."""
    ticket, comments = _export_data(ticket_id, ticket=ticket, comments=comments)
    reason_val = ticket.get("reason") or ticket.get("classification_reason")
    conf_val = ticket.get("confidence") or ticket.get("classification_confidence")
    conf_pct = (
        f" ({int(float(conf_val) * 100)}% confidence)" if conf_val is not None else ""
    )

    export_comments = list(comments) if comments else []
    if reason_val and not any(
        c.get("sender_role") == "AI Genie (System)" or c.get("sender_role") == "System"
        for c in export_comments
    ):
        export_comments.insert(
            0,
            {
                "createdAt": "Auto-Triaged",
                "sender_role": "AI Genie (System)",
                "message": f"AI Auto-Classification{conf_pct}: {reason_val}",
            },
        )

    conversation = (
        "\n".join(
            f"[{c.get('createdAt', 'N/A')}] {c.get('sender_role', 'Unknown')}: {c.get('message', '')}"
            for c in export_comments
        )
        or "No conversation messages have been recorded."
    )
    ai_line = (
        f"AI Classification: AI Auto-Classification{conf_pct}: {reason_val}\n"
        if reason_val
        else ""
    )

    return f"""TICKETGENIE TICKET REPORT
Ticket ID: {ticket.get("id", ticket_id)}
Title: {ticket.get("title", "N/A")}
Department: {ticket.get("department", "N/A")}
Category: {ticket.get("category", "N/A")}
Priority: {ticket.get("priority", "N/A")}
Status: {ticket.get("status", "N/A")}
Created: {ticket.get("createdAt") or ticket.get("date", "N/A")}
{ai_line}
DESCRIPTION
{ticket.get("description", "No description provided.")}

CONVERSATION HISTORY
{conversation}
""".encode("utf-8")
