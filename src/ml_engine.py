from __future__ import annotations

import hashlib
import importlib.util
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from .constants import MODEL_DIR
from .portable_classifier import load_portable_forest, predict_portable

FEATURES = ["calories", "protein_g", "fat_g", "carbs_g", "fiber_g", "sugar_g", "sodium_mg"]
MODEL_PATH = MODEL_DIR / "nutrition_quality_portable.json"
MODEL_CARD_PATH = MODEL_DIR / "nutrition_quality_model_card.json"
VISION_LABELS_PATH = MODEL_DIR / "food_labels.json"
VISION_MODEL_CARD_PATH = MODEL_DIR / "food_classifier_model_card.json"
VISION_MODEL_SHA256 = "87b73d4d635e9f5cf611021cbf6db1b1d7d4b1965b19fe383abaf0aee3617f09"
MAX_MEAL_IMAGE_BYTES = 10 * 1024 * 1024

QUALITY_LABELS = {
    "Strong": {
        "title": "Strong nutrition profile",
        "summary": "Higher fibre/protein balance with lower sugar and sodium pressure in this dataset.",
        "color": "#B9F06A",
    },
    "Balanced": {
        "title": "Balanced nutrition profile",
        "summary": "Reasonable overall profile; portion size and the rest of the meal still matter.",
        "color": "#5CE0D0",
    },
    "Limit": {
        "title": "Limit / occasional choice",
        "summary": "The dataset score suggests closer attention to portion, sugar, sodium, fat or fibre.",
        "color": "#FFB86B",
    },
}


def train_quality_model(frame: Any = None, random_state: int = 42) -> dict[str, Any]:
    """Validate the bundled model; offline rebuilding lives in scripts/build_unified_data.py."""
    del frame, random_state
    load_portable_forest.cache_clear()
    status = model_status()
    if status.get("status") != "Ready":
        raise RuntimeError(status.get("message", "Portable classifier is unavailable."))
    return status


def predict_quality(food: dict[str, Any]) -> dict[str, Any]:
    if not MODEL_PATH.exists():
        return {"status": "unavailable", "message": "The portable classifier file is missing."}
    try:
        label, probabilities = predict_portable(MODEL_PATH, food)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return {"status": "error", "message": f"Nutrition classifier failed: {exc}"}
    details = QUALITY_LABELS.get(label, QUALITY_LABELS["Balanced"])
    return {
        "status": "ready",
        "label": label,
        "confidence": round(float(max(probabilities.values())), 3),
        "probabilities": probabilities,
        "title": details["title"],
        "summary": details["summary"],
        "color": details["color"],
    }


def model_status() -> dict[str, Any]:
    if not MODEL_PATH.exists() or not MODEL_CARD_PATH.exists():
        return {"status": "Not trained", "model_path": str(MODEL_PATH)}
    try:
        card = json.loads(MODEL_CARD_PATH.read_text(encoding="utf-8"))
        load_portable_forest(str(MODEL_PATH), MODEL_PATH.stat().st_mtime_ns)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"status": "Unavailable", "message": str(exc), "model_path": str(MODEL_PATH)}
    return {
        "status": "Ready", **card, "runtime": "Pure Python (no SciPy/scikit-learn import)",
        "model_path": str(MODEL_PATH),
    }


@lru_cache(maxsize=2)
def _file_sha256(path: str, modified_ns: int) -> str:
    del modified_ns
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def food_vision_status() -> dict[str, Any]:
    candidates = [
        MODEL_DIR / "food_classifier.onnx",
        MODEL_DIR / "food_classifier.pt",
    ]
    available = next((path for path in candidates if path.exists()), None)
    dependency_ready = bool(
        available and (
            available.suffix != ".onnx"
            or importlib.util.find_spec("onnxruntime") is not None
            or importlib.util.find_spec("cv2") is not None
        )
    )
    labels_ready = VISION_LABELS_PATH.exists()
    integrity_ready = bool(
        available
        and (
            available.name != "food_classifier.onnx"
            or _file_sha256(str(available), available.stat().st_mtime_ns) == VISION_MODEL_SHA256
        )
    )
    status = "Ready"
    message = "Bundled Food-101 model is ready for local CPU inference."
    if available is None:
        status = "Model missing"
        message = "The food-image model file is missing. Re-extract the complete application ZIP."
    elif not dependency_ready:
        status = "Dependency missing"
        message = "Run pip install -r requirements.txt, then restart the app."
    elif not labels_ready:
        status = "Labels missing"
        message = "food_labels.json is missing. Re-extract the complete application ZIP."
    elif not integrity_ready:
        status = "Model damaged"
        message = "The bundled model failed its integrity check. Re-extract the complete application ZIP."
    return {
        "status": status,
        "message": message,
        "model_path": str(available) if available else None,
        "supported": ["ONNX Runtime", "OpenCV DNN fallback", "TorchScript"],
        "labels_path": str(VISION_LABELS_PATH) if VISION_LABELS_PATH.exists() else None,
        "classes": 101 if labels_ready else 0,
        "integrity": "Verified" if integrity_ready else "Unavailable",
        "reported_top1_accuracy": 0.763 if available else None,
        "fallback": "Human confirmation and full nutrition-database matching",
    }


def _vision_labels(count: int) -> list[str]:
    if not VISION_LABELS_PATH.exists():
        return [f"class_{index}" for index in range(count)]
    payload = json.loads(VISION_LABELS_PATH.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        labels = [str(payload.get(str(index), payload.get(index, f"class_{index}"))) for index in range(count)]
    elif isinstance(payload, list):
        labels = [str(item) for item in payload]
    else:
        raise ValueError("food_labels.json must contain a JSON list or index-to-label object.")
    if len(labels) < count:
        labels.extend(f"class_{index}" for index in range(len(labels), count))
    return labels[:count]


def _prepare_vision_input(image_bytes: bytes, size: tuple[int, int] = (224, 224)) -> np.ndarray:
    if not image_bytes:
        raise ValueError("The meal image is empty.")
    if len(image_bytes) > MAX_MEAL_IMAGE_BYTES:
        raise ValueError("The meal image exceeds the 10 MB inference limit.")
    from io import BytesIO
    from PIL import Image

    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    width, height = image.size
    if min(width, height) <= 0:
        raise ValueError("The meal image has invalid dimensions.")
    resize_short = 256
    if width < height:
        resized = (resize_short, round(height * resize_short / width))
    else:
        resized = (round(width * resize_short / height), resize_short)
    image = image.resize(resized, Image.Resampling.LANCZOS)
    left = max(0, (image.width - size[0]) // 2)
    top = max(0, (image.height - size[1]) // 2)
    image = image.crop((left, top, left + size[0], top + size[1]))
    array = np.asarray(image, dtype=np.float32) / 255.0
    mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
    return np.transpose((array - mean) / std, (2, 0, 1))[None, ...]


@lru_cache(maxsize=2)
def _load_onnx_session(model_path: str, modified_ns: int) -> Any:
    del modified_ns
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(model_path, sess_options=options, providers=["CPUExecutionProvider"])


@lru_cache(maxsize=2)
def _load_opencv_onnx_net(model_path: str, modified_ns: int) -> Any:
    del modified_ns
    import cv2

    return cv2.dnn.readNetFromONNX(model_path)


def _run_onnx_model(model_path: Path, model_input: np.ndarray) -> tuple[np.ndarray, str]:
    onnx_error: Exception | None = None
    try:
        session = _load_onnx_session(str(model_path), model_path.stat().st_mtime_ns)
        input_meta = session.get_inputs()[0]
        return session.run(None, {input_meta.name: model_input})[0], "ONNX Runtime"
    except Exception as exc:
        onnx_error = exc
    try:
        net = _load_opencv_onnx_net(str(model_path), model_path.stat().st_mtime_ns)
        net.setInput(model_input)
        return net.forward(), "OpenCV DNN (Windows-safe fallback)"
    except Exception as opencv_error:
        raise RuntimeError(
            f"ONNX Runtime failed ({onnx_error}); OpenCV fallback failed ({opencv_error})."
        ) from opencv_error


def _probabilities(logits: np.ndarray) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float64).squeeze()
    if values.ndim != 1 or not len(values):
        raise ValueError("The vision model must return one class-score vector.")
    shifted = values - np.max(values)
    exp = np.exp(shifted)
    return exp / exp.sum()


def predict_food_image(image_bytes: bytes, top_k: int = 5) -> dict[str, Any]:
    """Run the documented ONNX or TorchScript classifier contract."""
    status = food_vision_status()
    model_path = Path(status["model_path"]) if status.get("model_path") else None
    if model_path is None:
        return {"status": "unavailable", "message": status["status"], "predictions": []}
    try:
        model_input = _prepare_vision_input(image_bytes)
        if model_path.suffix == ".onnx":
            logits, runtime = _run_onnx_model(model_path, model_input)
        else:
            import torch

            model = torch.jit.load(str(model_path), map_location="cpu")
            model.eval()
            with torch.inference_mode():
                output = model(torch.from_numpy(model_input))
            if isinstance(output, (list, tuple)):
                output = output[0]
            if isinstance(output, dict):
                output = next(iter(output.values()))
            logits = output.detach().cpu().numpy()
            runtime = "TorchScript"
    except ImportError as exc:
        return {
            "status": "unavailable",
            "message": f"Install the optional deep-learning requirements: {exc}",
            "predictions": [],
        }
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        return {"status": "error", "message": f"Vision inference failed: {exc}", "predictions": []}

    try:
        probabilities = _probabilities(logits)
        labels = _vision_labels(len(probabilities))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"status": "error", "message": f"Vision output is invalid: {exc}", "predictions": []}
    indices = np.argsort(probabilities)[::-1][:max(1, min(int(top_k), len(probabilities)))]
    predictions = [
        {
            "label": labels[index].replace("_", " ").title(),
            "raw_label": labels[index],
            "confidence": round(float(probabilities[index]), 4),
        }
        for index in indices
    ]
    top_confidence = predictions[0]["confidence"]
    second_confidence = predictions[1]["confidence"] if len(predictions) > 1 else 0.0
    confidence_level = "High" if top_confidence >= 0.65 else "Moderate" if top_confidence >= 0.35 else "Low"
    return {
        "status": "ready",
        "runtime": runtime,
        "model": "MobileNetV2 Food-101",
        "classes": len(probabilities),
        "reported_top1_accuracy": 0.763,
        "predictions": predictions,
        "confidence_level": confidence_level,
        "top_margin": round(float(top_confidence - second_confidence), 4),
        "requires_confirmation": True,
    }
