from __future__ import annotations

import io
import math
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any


@dataclass
class LabResult:
    test: str
    value: float
    unit: str
    reference: str
    flag: str
    nutrition_note: str


LAB_RULES: dict[str, dict[str, Any]] = {
    "HbA1c": {"patterns": [r"(?:hba[li]?1c|hba\s*1c|a1c)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "%", "low": 4.0, "high": 5.6, "critical_high": 10.0, "reference": "4.0–5.6", "note": "Balance carbohydrate portions and emphasize minimally processed, fibre-rich foods."},
    "Fasting glucose": {"patterns": [r"(?:fasting glucose|fbs|fasting blood sugar)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 70, "high": 99, "critical_low": 50, "critical_high": 300, "reference": "70–99", "note": "Review carbohydrate distribution and meal timing; severe abnormalities need medical assessment."},
    "LDL cholesterol": {"patterns": [r"(?:ldl(?: cholesterol)?)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 0, "high": 99, "reference": "<100", "note": "Prioritize soluble fibre and unsaturated fats; reduce excess saturated and trans fats."},
    "HDL cholesterol": {"patterns": [r"(?:hdl(?: cholesterol)?)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 40, "high": 200, "reference": "≥40", "note": "Support overall cardiovascular patterns with activity and suitable unsaturated fats."},
    "Triglycerides": {"patterns": [r"(?:triglycerides|tg)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 0, "high": 149, "critical_high": 500, "reference": "<150", "note": "Limit alcohol and added sugar; urgent clinical review is needed for very high values."},
    "Vitamin D": {"patterns": [r"(?:25[\- ]?oh vitamin d|vitamin d)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "ng/mL", "low": 30, "high": 100, "reference": "30–100", "note": "Use food-first vitamin D sources; therapeutic supplementation requires professional dosing."},
    "Vitamin B12": {"patterns": [r"(?:vitamin b12|b12)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "pg/mL", "low": 200, "high": 900, "reference": "200–900", "note": "Review animal or fortified food intake and discuss confirmed deficiency with a professional."},
    "Haemoglobin": {"patterns": [r"(?:haemoglobin|hemoglobin|hgb|hb)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "g/dL", "low": 12, "high": 17.5, "critical_low": 7, "reference": "12.0–17.5", "note": "Do not assume iron deficiency; the cause of low haemoglobin must be established."},
    "Ferritin": {"patterns": [r"(?:ferritin)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "ng/mL", "low": 15, "high": 300, "reference": "15–300", "note": "Interpret with inflammation and other iron studies before changing intake or supplements."},
    "eGFR": {"patterns": [r"(?:egfr)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mL/min/1.73m²", "low": 60, "high": 200, "critical_low": 30, "reference": "≥60", "note": "Kidney-related diet changes require individualized professional review."},
    "Creatinine": {"patterns": [r"(?:creatinine)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 0.6, "high": 1.3, "critical_high": 5, "reference": "0.6–1.3", "note": "Interpret alongside eGFR, hydration, muscle mass and clinical history."},
    "Potassium": {"patterns": [r"(?:potassium|k\+)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mmol/L", "low": 3.5, "high": 5.1, "critical_low": 3.0, "critical_high": 6.0, "reference": "3.5–5.1", "note": "Both high and low potassium can be dangerous; do not self-prescribe dietary restriction."},
    "Sodium": {"patterns": [r"(?:sodium|na\+)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mmol/L", "low": 135, "high": 145, "critical_low": 125, "critical_high": 155, "reference": "135–145", "note": "Serum sodium is not corrected simply by changing dietary salt; clinical assessment is required."},
    "ALT": {"patterns": [r"(?:alt|sgpt)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "U/L", "low": 0, "high": 45, "critical_high": 300, "reference": "0–45", "note": "Abnormal liver enzymes need clinical interpretation before therapeutic diet changes."},
    "Albumin": {"patterns": [r"(?:albumin)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "g/dL", "low": 3.5, "high": 5.0, "critical_low": 2.5, "reference": "3.5–5.0", "note": "Low albumin may reflect inflammation or organ disease, not only low protein intake."},
    "Uric acid": {"patterns": [r"(?:uric acid)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 3.0, "high": 7.2, "critical_high": 12, "reference": "3.0–7.2", "note": "Hydration and food pattern may help, but medicines and kidney function must be considered."},
    "TSH": {"patterns": [r"(?:tsh)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mIU/L", "low": 0.4, "high": 4.0, "critical_high": 20, "reference": "0.4–4.0", "note": "Thyroid results require clinical interpretation; diet does not replace thyroid treatment."},
    "Total cholesterol": {"patterns": [r"(?:total cholesterol|cholesterol total)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 0, "high": 199, "reference": "<200", "note": "Interpret the complete lipid profile and cardiovascular risk rather than one value alone."},
    "Random glucose": {"patterns": [r"(?:random glucose|random blood sugar|rbs)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 70, "high": 140, "critical_low": 50, "critical_high": 300, "reference": "70–140", "note": "Timing, symptoms and medicines affect interpretation; marked abnormalities require medical assessment."},
    "Urea": {"patterns": [r"(?:blood urea|serum urea|urea)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 15, "high": 45, "critical_high": 150, "reference": "15–45", "note": "Interpret with creatinine, eGFR, hydration and protein intake."},
    "BUN": {"patterns": [r"(?:blood urea nitrogen|bun)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 7, "high": 20, "critical_high": 100, "reference": "7–20", "note": "Interpret with kidney function, hydration and clinical context."},
    "AST": {"patterns": [r"(?:ast|sgot)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "U/L", "low": 0, "high": 40, "critical_high": 300, "reference": "0–40", "note": "Abnormal liver enzymes need clinical interpretation before diet changes."},
    "ALP": {"patterns": [r"(?:alkaline phosphatase|alp)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "U/L", "low": 44, "high": 147, "reference": "44–147", "note": "ALP varies with liver, bone, age and pregnancy; use the reporting laboratory range."},
    "Total bilirubin": {"patterns": [r"(?:total bilirubin|bilirubin total)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 0.1, "high": 1.2, "reference": "0.1–1.2", "note": "Bilirubin abnormalities require interpretation with the complete liver profile."},
    "CRP": {"patterns": [r"(?:c[\- ]?reactive protein|crp)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/L", "low": 0, "high": 5, "critical_high": 100, "reference": "0–5", "note": "CRP reflects inflammation and is not a nutrition diagnosis."},
    "Calcium": {"patterns": [r"(?:corrected calcium|serum calcium|calcium)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 8.5, "high": 10.5, "critical_low": 7, "critical_high": 13, "reference": "8.5–10.5", "note": "Interpret calcium with albumin, kidney function, medicines and symptoms."},
    "Magnesium": {"patterns": [r"(?:serum magnesium|magnesium|mg\+\+)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 1.7, "high": 2.2, "critical_low": 1.0, "critical_high": 4.0, "reference": "1.7–2.2", "note": "Marked magnesium abnormalities require clinical review rather than self-supplementation."},
    "Phosphate": {"patterns": [r"(?:serum phosphate|phosphorus|phosphate)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "mg/dL", "low": 2.5, "high": 4.5, "reference": "2.5–4.5", "note": "Interpret phosphate with kidney function, calcium and parathyroid status."},
    "WBC": {"patterns": [r"(?:white blood cell count|white cell count|wbc)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "×10³/µL", "low": 4, "high": 11, "critical_low": 2, "critical_high": 30, "reference": "4.0–11.0", "note": "White-cell abnormalities require medical interpretation and are not corrected by diet alone."},
    "Platelets": {"patterns": [r"(?:platelet count|platelets|plt)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "×10³/µL", "low": 150, "high": 450, "critical_low": 50, "critical_high": 1000, "reference": "150–450", "note": "Marked platelet abnormalities need prompt clinical assessment."},
    "Haematocrit": {"patterns": [r"(?:haematocrit|hematocrit|hct|pcv)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "%", "low": 36, "high": 54, "reference": "36–54", "note": "Interpret with haemoglobin, hydration and the reporting laboratory range."},
    "MCV": {"patterns": [r"(?:mean corpuscular volume|mcv)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "fL", "low": 80, "high": 100, "reference": "80–100", "note": "MCV helps classify anaemia but does not identify the cause by itself."},
    "MCH": {"patterns": [r"(?:mean corpuscular haemoglobin|mean corpuscular hemoglobin|mch)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "pg", "low": 27, "high": 33, "reference": "27–33", "note": "Interpret red-cell indices together with haemoglobin and iron studies."},
    "MCHC": {"patterns": [r"(?:mean corpuscular haemoglobin concentration|mean corpuscular hemoglobin concentration|mchc)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "g/dL", "low": 32, "high": 36, "reference": "32–36", "note": "Interpret red-cell indices together with the full blood count."},
    "Free T4": {"patterns": [r"(?:free t4|ft4)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "ng/dL", "low": 0.8, "high": 1.8, "reference": "0.8–1.8", "note": "Thyroid results require clinical interpretation with TSH and symptoms."},
    "Folate": {"patterns": [r"(?:serum folate|folate|folic acid)\s*[:\-]?\s*(\d+(?:\.\d+)?)"], "unit": "ng/mL", "low": 4, "high": 20, "reference": "4–20", "note": "Interpret folate with B12 status, blood count and clinical context."},
}

MAX_REPORT_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_OCR_PDF_PAGES = 8


def flag_value(value: float, rule: dict[str, Any]) -> str:
    if value <= rule.get("critical_low", float("-inf")) or value >= rule.get("critical_high", float("inf")):
        return "critical"
    if value < rule["low"]:
        return "low"
    if value > rule["high"]:
        return "high"
    return "normal"


def parse_lab_text(text: str) -> list[dict[str, Any]]:
    normalized = str(text or "").replace("−", "-").replace("—", "-")
    normalized = re.sub(r"[,|]", " ", normalized.lower())
    normalized = re.sub(r"\b(?:result|value)\b\s*[:=]?", " ", normalized)
    results: list[dict[str, Any]] = []
    for test, rule in LAB_RULES.items():
        value = None
        for pattern in rule["patterns"]:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                value = float(match.group(1))
                break
        if value is None:
            continue
        results.append(asdict(LabResult(
            test=test,
            value=value,
            unit=rule["unit"],
            reference=rule["reference"],
            flag=flag_value(value, rule),
            nutrition_note=rule["note"],
        )))
    known_names = {row["test"].lower() for row in results}
    known_test_terms = {test.lower() for test in LAB_RULES}
    unit_pattern = re.compile(
        r"(?P<name>[A-Za-z][A-Za-z0-9 ()+\-/]{2,60}?)\s*[:=]?\s*"
        r"(?P<value>-?\d+(?:\.\d+)?)\s*"
        r"(?P<unit>%|mg/dl|mg/l|g/dl|g/l|ng/ml|pg/ml|ug/dl|µg/dl|mmol/l|miu/l|u/l|iu/l|fl|pg|x?10\^?[369]/(?:ul|µl))\b",
        re.IGNORECASE,
    )
    blocked_names = {"age", "date", "time", "patient id", "phone", "mobile", "invoice"}
    for line in str(text or "").splitlines():
        for match in unit_pattern.finditer(" ".join(line.split())):
            name = match.group("name").strip(" :-")
            lowered_name = name.lower()
            if (
                lowered_name in known_names
                or any(word in lowered_name for word in blocked_names)
                or any(term in lowered_name for term in known_test_terms)
            ):
                continue
            value = float(match.group("value"))
            if not math.isfinite(value) or value < 0:
                continue
            results.append(asdict(LabResult(
                name[:80], value, match.group("unit"), "Verify report range", "unverified",
                "Extracted as an additional laboratory test; professional interpretation and range verification are required.",
            )))
            known_names.add(lowered_name)
    return results


def classify_manual_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    classified = []
    for row in rows:
        test = str(row.get("test", "")).strip()
        if not test or row.get("value") in ("", None):
            continue
        try:
            value = float(row["value"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{test}: enter a numeric laboratory value.") from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{test}: laboratory value must be a finite, non-negative number.")
        rule = LAB_RULES.get(test)
        if rule:
            classified.append(asdict(LabResult(test, value, rule["unit"], rule["reference"],
                                                  flag_value(value, rule), rule["note"])))
        else:
            classified.append(asdict(LabResult(
                test, value, str(row.get("unit", "")), str(row.get("reference", "")),
                "unverified", "No validated nutrition rule is available; professional interpretation is required.",
            )))
    return classified


def assess_safety(results: list[dict[str, Any]], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    critical = [row for row in results if row.get("flag") == "critical"]
    conditions = {str(item).lower() for item in (profile or {}).get("conditions", [])}
    high_risk_conditions = {
        "advanced kidney disease", "pregnancy", "eating disorder",
        "insulin-treated diabetes", "advanced liver disease",
    }
    reasons = [f"{row['test']} is in a critical range" for row in critical]
    reasons.extend(f"High-risk profile: {condition}" for condition in conditions & high_risk_conditions)
    if reasons:
        return {"level": "blocked", "reasons": reasons, "can_generate": False}
    abnormal = [row for row in results if row.get("flag") in {"high", "low"}]
    return {
        "level": "clinician-review" if abnormal or conditions else "wellness",
        "reasons": [f"{row['test']} is {row['flag']}" for row in abnormal],
        "can_generate": True,
    }


@lru_cache(maxsize=1)
def _rapidocr_engine() -> Any:
    from rapidocr import RapidOCR

    return RapidOCR()


def _rapidocr_image_text(image: Any) -> str:
    import numpy as np

    output = _rapidocr_engine()(np.asarray(image.convert("RGB")))
    texts = getattr(output, "txts", None)
    scores = getattr(output, "scores", None)
    boxes = getattr(output, "boxes", None)
    if texts:
        accepted: list[tuple[float, float, float, str]] = []
        for index, text in enumerate(texts):
            cleaned = str(text).strip()
            if not cleaned or (scores and float(scores[index]) < 0.45):
                continue
            if boxes is None or index >= len(boxes):
                accepted.append((float(index), 0.0, 1.0, cleaned))
                continue
            points = np.asarray(boxes[index], dtype=float)
            accepted.append((float(points[:, 1].mean()), float(points[:, 0].min()), float(np.ptp(points[:, 1])), cleaned))
        if boxes is None:
            return "\n".join(item[3] for item in accepted)
        rows: list[list[tuple[float, float, float, str]]] = []
        for item in sorted(accepted, key=lambda value: (value[0], value[1])):
            if not rows:
                rows.append([item])
                continue
            row_y = sum(value[0] for value in rows[-1]) / len(rows[-1])
            tolerance = max(8.0, 0.65 * max(item[2], *(value[2] for value in rows[-1])))
            if abs(item[0] - row_y) <= tolerance:
                rows[-1].append(item)
            else:
                rows.append([item])
        return "\n".join(" ".join(item[3] for item in sorted(row, key=lambda value: value[1])) for row in rows)
    if isinstance(output, (tuple, list)) and output:
        rows = output[0] or []
        return "\n".join(str(row[1]).strip() for row in rows if len(row) >= 2 and str(row[1]).strip())
    return ""


def _tesseract_image_text(image: Any) -> str:
    import pytesseract
    from PIL import ImageEnhance, ImageFilter, ImageOps

    gray = ImageOps.grayscale(image)
    scale = max(1, min(3, round(2200 / max(gray.width, 1))))
    if scale > 1:
        gray = gray.resize((gray.width * scale, gray.height * scale))
    gray = ImageOps.autocontrast(gray).filter(ImageFilter.SHARPEN)
    gray = ImageEnhance.Contrast(gray).enhance(1.6)
    attempts = [
        pytesseract.image_to_string(gray, config="--oem 3 --psm 6"),
        pytesseract.image_to_string(gray, config="--oem 3 --psm 11"),
    ]
    return max(attempts, key=lambda value: len(value.strip()), default="")


def _extract_image_text(image: Any) -> tuple[str, str]:
    errors: list[str] = []
    try:
        text = _rapidocr_image_text(image)
        if text.strip():
            return text, "Bundled RapidOCR"
        errors.append("RapidOCR found no text")
    except Exception as exc:
        errors.append(f"RapidOCR unavailable: {exc}")
    try:
        text = _tesseract_image_text(image)
        if text.strip():
            return text, "Tesseract OCR fallback"
        errors.append("Tesseract found no text")
    except Exception as exc:
        errors.append(f"Tesseract unavailable: {exc}")
    return "", "; ".join(errors)


def _ocr_pdf_pages(data: bytes) -> tuple[str, str]:
    try:
        import pypdfium2 as pdfium
    except Exception as exc:
        return "", f"Scanned-PDF rendering unavailable: {exc}"
    texts: list[str] = []
    methods: list[str] = []
    try:
        document = pdfium.PdfDocument(data)
        page_limit = min(len(document), MAX_OCR_PDF_PAGES)
        for page_index in range(page_limit):
            page = document[page_index]
            image = page.render(scale=2.2).to_pil()
            text, method = _extract_image_text(image)
            if text.strip():
                texts.append(f"--- Page {page_index + 1} ---\n{text}")
                methods.append(method)
        suffix = f" (first {MAX_OCR_PDF_PAGES} pages)" if len(document) > MAX_OCR_PDF_PAGES else ""
        if texts:
            return "\n".join(texts), f"Scanned PDF · {methods[0]}{suffix}"
        return "", "No readable text was detected in the scanned PDF"
    except Exception as exc:
        return "", f"Scanned-PDF OCR unavailable: {exc}"


def extract_text_from_upload(uploaded_file: Any) -> tuple[str, str]:
    if uploaded_file is None:
        raise ValueError("Choose a laboratory report before extraction.")
    name = str(getattr(uploaded_file, "name", "report")).lower()
    data = uploaded_file.getvalue()
    if not data:
        raise ValueError("The uploaded laboratory report is empty.")
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError("The laboratory report exceeds the 20 MB safety limit.")
    if name.endswith(".pdf"):
        if not data.startswith(b"%PDF"):
            raise ValueError("The uploaded file does not appear to be a valid PDF.")
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                page_count = len(pdf.pages)
                blocks: list[str] = []
                for page in pdf.pages[:MAX_PDF_PAGES]:
                    page_text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                    blocks.append(page_text)
                    for table in page.extract_tables() or []:
                        blocks.extend(" | ".join(str(cell or "").strip() for cell in row) for row in table)
                text = "\n".join(block for block in blocks if block.strip())
            suffix = f" (first {MAX_PDF_PAGES} pages)" if page_count > MAX_PDF_PAGES else ""
            if text.strip() and parse_lab_text(text):
                return text, "PDF text and table extraction" + suffix
            ocr_text, ocr_method = _ocr_pdf_pages(data)
            if ocr_text.strip():
                combined = "\n".join(item for item in (text, ocr_text) if item.strip())
                return combined, ocr_method
            if text.strip():
                return text, "PDF text extracted, but no supported values were recognized"
            return "", ocr_method
        except Exception as exc:
            ocr_text, ocr_method = _ocr_pdf_pages(data)
            return ocr_text, ocr_method if ocr_text else f"PDF extraction unavailable: {exc}; {ocr_method}"
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(data))
        image.verify()
        image = Image.open(io.BytesIO(data)).convert("RGB")
        return _extract_image_text(image)
    except Exception as exc:
        return "", f"OCR unavailable: {exc}"
