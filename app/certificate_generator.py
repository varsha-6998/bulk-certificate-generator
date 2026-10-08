from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


def generate_certificate(
    recipient_name: str, event_name: str, event_date: date, output_path: Path
) -> None:
    """Create a single printable certificate at the supplied, application-owned path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = landscape(letter)
    pdf = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))

    pdf.setFillColor(colors.HexColor("#f8fafc"))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#0f766e"))
    pdf.setLineWidth(4)
    pdf.rect(0.38 * inch, 0.38 * inch, page_width - 0.76 * inch, page_height - 0.76 * inch)
    pdf.setStrokeColor(colors.HexColor("#cbd5e1"))
    pdf.setLineWidth(1)
    pdf.rect(0.52 * inch, 0.52 * inch, page_width - 1.04 * inch, page_height - 1.04 * inch)

    pdf.setFillColor(colors.HexColor("#0f766e"))
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawCentredString(page_width / 2, page_height - 1.35 * inch, "CERTIFICATE OF ACHIEVEMENT")
    pdf.setFillColor(colors.HexColor("#172554"))
    pdf.setFont("Helvetica-Bold", 31)
    pdf.drawCentredString(page_width / 2, page_height - 2.15 * inch, "Certificate")
    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(page_width / 2, page_height - 2.65 * inch, "This certificate is proudly presented to")

    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.setFont("Helvetica-Bold", 27)
    pdf.drawCentredString(page_width / 2, page_height - 3.45 * inch, recipient_name)
    pdf.setStrokeColor(colors.HexColor("#94a3b8"))
    pdf.line(page_width * 0.24, page_height - 3.65 * inch, page_width * 0.76, page_height - 3.65 * inch)

    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(page_width / 2, page_height - 4.15 * inch, "in recognition of participation in")
    pdf.setFillColor(colors.HexColor("#0f766e"))
    pdf.setFont("Helvetica-Bold", 19)
    pdf.drawCentredString(page_width / 2, page_height - 4.6 * inch, event_name)
    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(page_width / 2, 1.05 * inch, f"Presented on {event_date.strftime('%B %d, %Y')}")

    pdf.showPage()
    pdf.save()
