from __future__ import annotations

import io
import json
from typing import Any
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def plan_to_dataframe(plan: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for day in plan["days"]:
        for meal in day["meals"]:
            rows.append({
                "Day": day["day"], "Time": meal["time"], "Meal": meal["name"],
                "Details": meal["detail"], "Calories": meal["calories"],
                "Protein_g": meal["protein_g"],
            })
    return pd.DataFrame(rows)


def plan_to_csv(plan: dict[str, Any]) -> bytes:
    return plan_to_dataframe(plan).to_csv(index=False).encode("utf-8")


def plan_to_json(plan: dict[str, Any]) -> bytes:
    return json.dumps(plan, indent=2, ensure_ascii=False).encode("utf-8")


def plan_to_pdf(plan: dict[str, Any], patient_name: str) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="NPTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=24, leading=28, textColor=colors.HexColor("#16423C"), alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="NPHeading", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=14, leading=18, textColor=colors.HexColor("#1E6A5C"), spaceBefore=8,
    ))
    styles.add(ParagraphStyle(
        name="NPBody", parent=styles["BodyText"], fontSize=9, leading=13,
        textColor=colors.HexColor("#344A46"),
    ))
    story = [
        Paragraph("NutriPulse AI Nutrition Plan", styles["NPTitle"]),
        Paragraph(f"Prepared for: {escape(str(patient_name))}", styles["NPBody"]),
        Spacer(1, 5 * mm),
    ]
    summary = [
        ["Energy", "Protein", "Carbohydrates", "Fat", "Fibre", "Water"],
        [
            f"{plan['calories']} kcal", f"{plan['protein_g']} g", f"{plan['carbs_g']} g",
            f"{plan['fat_g']} g", f"{plan['fiber_g']} g", f"{plan['water_l']} L",
        ],
    ]
    summary_table = Table(summary, colWidths=[28 * mm] * 6)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DFF4A6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#16423C")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#B8CBC6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([summary_table, Spacer(1, 4 * mm)])
    story.append(Paragraph("Nutrition focus", styles["NPHeading"]))
    story.append(Paragraph(escape(" • ".join(map(str, plan["focus"]))), styles["NPBody"]))
    story.append(Spacer(1, 3 * mm))
    for index, day in enumerate(plan["days"]):
        story.append(Paragraph(escape(str(day["day"])), styles["NPHeading"]))
        data = [["Time", "Meal", "Details", "kcal", "Protein"]]
        data.extend([
            [
                escape(str(meal["time"])), escape(str(meal["name"])),
                escape(str(meal["detail"])), str(meal["calories"]),
                f"{meal['protein_g']} g",
            ]
            for meal in day["meals"]
        ])
        table = Table(data, colWidths=[17 * mm, 39 * mm, 77 * mm, 17 * mm, 19 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16423C")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.2),
            ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#C9D7D3")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F7F5")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)
        if index == 3:
            story.append(PageBreak())
    story.extend([
        Spacer(1, 5 * mm),
        Paragraph(
            "Clinical decision-support draft. This document does not diagnose disease, prescribe medicines "
            "or replace a qualified doctor or registered dietitian. High-risk conditions require professional approval.",
            styles["NPBody"],
        ),
    ])
    document.build(story)
    buffer.seek(0)
    return buffer.read()
