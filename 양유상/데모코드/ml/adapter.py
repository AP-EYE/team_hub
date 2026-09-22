"""Dependency-free local worker client; never silently substitutes model results."""
import json
import os
import urllib.error
import urllib.request

URL = os.environ.get("LOCAL_CLASSIFIER_URL", "http://127.0.0.1:8812")


def classify(text, field_path="", description=""):
    payload = json.dumps({"text": text, "field_path": field_path, "description": description}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(URL + "/classify", data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {"label": "UNKNOWN", "confidence": None, "model": "unavailable", "status": "unavailable", "error": type(exc).__name__, "confidence_is_calibrated": False}


def normalize(field_path, description=""):
    payload = json.dumps({"field_path": field_path, "description": description}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(URL + "/normalize", data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {"canonical_field": "unknown", "confidence": None, "model": "unavailable", "status": "unavailable", "approved": False, "error": type(exc).__name__}
