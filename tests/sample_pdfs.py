"""Self-made PDFs, not official pdf/ competition cases. Generated files stay under data/."""

from pathlib import Path

from reportlab.pdfgen import canvas


def make_pdf(path: Path, *, version="v1", samples=12, scan=False, blank_cover=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    document = canvas.Canvas(str(path), pagesize=(612, 792), invariant=1)
    document.setTitle("Synthetic ScholarGraph Study")
    document.setAuthor("Demo Author")
    if blank_cover:
        document.showPage()
    if scan:
        from PIL import Image, ImageDraw, ImageFont
        from reportlab.lib.utils import ImageReader
        image = Image.new("RGB", (1224, 1584), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32)
        for index, text in enumerate(["Synthetic scanned page", "1 Introduction", "The synthetic study uses 12 samples."]):
            draw.text((120, 120 + index * 90), text, font=font, fill="black")
        document.drawImage(ImageReader(image), 0, 0, width=612, height=792)
    else:
        document.setFont("Helvetica-Bold", 20)
        document.drawString(60, 740, "Synthetic ScholarGraph Study")
        document.setFont("Helvetica", 11)
        for index, text in enumerate([f"Version: {version}", "DOI: https://doi.org/10.5555/scholar-synthetic", "Year: 2026"]):
            document.drawString(60, 700 - index * 22, text)
        document.setFont("Helvetica-Bold", 16)
        document.drawString(60, 600, "1 Introduction")
        document.setFont("Helvetica", 11)
        document.drawString(60, 560, f"The synthetic study uses {samples} samples and cites [1].")
        if version != "v1":
            document.setFont("Helvetica-Bold", 16)
            document.drawString(60, 500, "2 Protocol")
            document.setFont("Helvetica", 11)
            document.drawString(60, 460, "The revised synthetic protocol records additional controls.")
        document.showPage()
        document.setFont("Helvetica-Bold", 18)
        document.drawString(60, 740, "References")
        document.setFont("Helvetica", 11)
        document.drawString(40, 700, "[1] Example Author (2025). Synthetic Prior Study.")
        document.drawString(40, 680, "Synthetic Proceedings. doi:10.5555/prior")
    document.save()
    return path
