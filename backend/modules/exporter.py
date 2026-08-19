"""
exporter.py
-----------
Export MCQs to PDF (via reportlab) or CSV format.
"""

import csv
import io
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def export_to_csv(mcqs: List[Dict[str, Any]]) -> bytes:
    """
    Export MCQs to CSV format.
    
    Columns: #, Question, Option A, Option B, Option C, Option D,
             Correct Answer, Explanation, Confidence, Difficulty, Topic
    
    Returns:
        CSV content as bytes
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "#", "Question",
        "Option A", "Option B", "Option C", "Option D",
        "Correct Answer", "Explanation",
        "Confidence Score", "Difficulty", "Topic", "Source Sentence"
    ])

    for i, mcq in enumerate(mcqs, 1):
        options = mcq.get("options", [])
        while len(options) < 4:
            options.append("")

        writer.writerow([
            i,
            mcq.get("question", ""),
            options[0], options[1], options[2], options[3],
            mcq.get("answer", ""),
            mcq.get("explanation", ""),
            f"{mcq.get('confidence_score', 0):.2f}",
            mcq.get("difficulty", "medium"),
            mcq.get("topic", ""),
            mcq.get("source_sentence", "")
        ])

    content = output.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility
    logger.info(f"CSV export: {len(mcqs)} questions")
    return content


def export_to_pdf(mcqs: List[Dict[str, Any]], title: str = "Generated MCQs") -> bytes:
    """
    Export MCQs to PDF using reportlab.
    
    Returns:
        PDF content as bytes
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, HRFlowable
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "Title",
            parent=styles["Title"],
            fontSize=18,
            textColor=colors.HexColor("#1a1a2e"),
            spaceAfter=20
        )
        q_style = ParagraphStyle(
            "Question",
            parent=styles["Normal"],
            fontSize=11,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1a1a2e"),
            spaceAfter=6
        )
        option_style = ParagraphStyle(
            "Option",
            parent=styles["Normal"],
            fontSize=10,
            leftIndent=20,
            spaceAfter=3
        )
        answer_style = ParagraphStyle(
            "Answer",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#16a34a"),
            fontName="Helvetica-Bold",
            spaceAfter=3
        )
        explain_style = ParagraphStyle(
            "Explain",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#4b5563"),
            leftIndent=10,
            spaceAfter=8
        )
        meta_style = ParagraphStyle(
            "Meta",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#9ca3af"),
            spaceAfter=4
        )

        story = []
        story.append(Paragraph(title, title_style))
        story.append(Paragraph(f"Total Questions: {len(mcqs)}", styles["Normal"]))
        story.append(Spacer(1, 0.5 * cm))

        option_labels = ["A", "B", "C", "D"]

        for i, mcq in enumerate(mcqs, 1):
            question = mcq.get("question", "")
            options = mcq.get("options", [])
            answer = mcq.get("answer", "")
            explanation = mcq.get("explanation", "")
            difficulty = mcq.get("difficulty", "medium").upper()
            confidence = mcq.get("confidence_score", 0)
            topic = mcq.get("topic", "")

            # Question
            story.append(Paragraph(f"Q{i}. {question}", q_style))
            story.append(Paragraph(
                f"[{difficulty}] | Confidence: {confidence:.0%} | Topic: {topic}",
                meta_style
            ))

            # Options
            for j, opt in enumerate(options[:4]):
                label = option_labels[j] if j < len(option_labels) else str(j + 1)
                marker = "✓ " if opt == answer else "   "
                p = Paragraph(f"{marker}({label}) {opt}", option_style)
                story.append(p)

            # Answer
            story.append(Paragraph(f"✓ Correct Answer: {answer}", answer_style))

            # Explanation
            if explanation:
                story.append(Paragraph(f"Explanation: {explanation}", explain_style))

            story.append(HRFlowable(color=colors.HexColor("#e5e7eb"), thickness=0.5))
            story.append(Spacer(1, 0.3 * cm))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        logger.info(f"PDF export: {len(mcqs)} questions, {len(pdf_bytes)} bytes")
        return pdf_bytes

    except ImportError:
        logger.error("reportlab not installed. Run: pip install reportlab")
        raise RuntimeError("PDF export requires reportlab: pip install reportlab")
    except Exception as e:
        logger.error(f"PDF export failed: {e}")
        raise
