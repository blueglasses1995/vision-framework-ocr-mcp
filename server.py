#!/usr/bin/env python3
"""Vision framework OCR MCP server.

This server exposes OCR tools powered by macOS Vision framework via a Swift helper.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

NAME = "vision-framework-ocr"
VERSION = "0.1.0"

SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_SCRIPT = SCRIPT_DIR / "vision_ocr.swift"
HELPER_BIN = SCRIPT_DIR / ".build" / "vision_ocr"

DEFAULT_LANGUAGES = ["ja-JP", "en-US"]
ALLOWED_LEVELS = {"accurate", "fast"}

mcp = FastMCP(
    name=NAME,
    instructions=(
        "OCR images on macOS with Vision framework. "
        "Use ocr_image for one image, ocr_batch for many images, and ocr_text for plain text output."
    ),
    log_level="WARNING",
)


class OCRError(RuntimeError):
    """OCR operation failed."""


def _as_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Cannot parse boolean: {value}")


def _resolve_image_path(path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not candidate.exists():
        raise OCRError(f"File not found: {candidate}")
    if not candidate.is_file():
        raise OCRError(f"Path is not a file: {candidate}")

    allowed = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic", ".heif", ".bmp", ".gif", ".webp"}
    if candidate.suffix.lower() not in allowed:
        raise OCRError(
            f"Unsupported extension: {candidate.suffix}. Supported: {', '.join(sorted(allowed))}"
        )

    return candidate


def _helper_command() -> list[str]:
    if HELPER_BIN.exists() and os.access(HELPER_BIN, os.X_OK):
        return [str(HELPER_BIN)]

    if not HELPER_SCRIPT.exists():
        raise OCRError(f"Swift helper script not found: {HELPER_SCRIPT}")

    return ["xcrun", "swift", str(HELPER_SCRIPT)]


def _run_helper(
    image_path: Path,
    languages: list[str],
    recognition_level: str,
    language_correction: bool,
    sort_reading_order: bool,
    min_confidence: float,
) -> dict[str, Any]:
    if recognition_level not in ALLOWED_LEVELS:
        raise OCRError(f"recognition_level must be one of {sorted(ALLOWED_LEVELS)}")
    if not (0.0 <= min_confidence <= 1.0):
        raise OCRError("min_confidence must be between 0.0 and 1.0")

    command = _helper_command() + [
        "--input",
        str(image_path),
        "--languages",
        ",".join(languages),
        "--recognition-level",
        recognition_level,
        "--language-correction",
        str(language_correction).lower(),
        "--sort-reading-order",
        str(sort_reading_order).lower(),
        "--min-confidence",
        f"{min_confidence:.3f}",
    ]

    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        if not stderr:
            stderr = "Swift OCR helper failed without stderr output."
        raise OCRError(stderr)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise OCRError(f"Helper returned invalid JSON: {exc}") from exc

    return _normalize_payload(payload)


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)

    if "resolvedPath" in normalized and "resolved_path" not in normalized:
        normalized["resolved_path"] = normalized.pop("resolvedPath")
    if "lineCount" in normalized and "line_count" not in normalized:
        normalized["line_count"] = normalized.pop("lineCount")
    if "fullText" in normalized and "full_text" not in normalized:
        normalized["full_text"] = normalized.pop("fullText")

    lines = normalized.get("lines")
    if isinstance(lines, list):
        converted_lines: list[dict[str, Any]] = []
        for line in lines:
            if not isinstance(line, dict):
                continue
            converted_line = dict(line)
            bbox = converted_line.get("bbox")
            if isinstance(bbox, dict):
                converted_bbox = dict(bbox)
                if "minX" in converted_bbox and "min_x" not in converted_bbox:
                    converted_bbox["min_x"] = converted_bbox.pop("minX")
                if "minY" in converted_bbox and "min_y" not in converted_bbox:
                    converted_bbox["min_y"] = converted_bbox.pop("minY")
                converted_line["bbox"] = converted_bbox
            converted_lines.append(converted_line)
        normalized["lines"] = converted_lines

    return normalized


def _default_languages(languages: list[str] | None) -> list[str]:
    if languages is None or len(languages) == 0:
        return DEFAULT_LANGUAGES
    return languages


@mcp.tool(
    description=(
        "Run OCR for a single image with Apple Vision and return structured output "
        "(lines, confidence, bounding boxes, full text)."
    )
)
def ocr_image(
    path: str,
    languages: list[str] | None = None,
    recognition_level: str = "accurate",
    language_correction: bool = True,
    sort_reading_order: bool = True,
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    """OCR one image file and return structured result."""
    image_path = _resolve_image_path(path)
    return _run_helper(
        image_path=image_path,
        languages=_default_languages(languages),
        recognition_level=recognition_level,
        language_correction=language_correction,
        sort_reading_order=sort_reading_order,
        min_confidence=min_confidence,
    )


@mcp.tool(
    description=(
        "Run OCR for multiple images. Returns per-image results plus an error list "
        "for files that failed."
    )
)
def ocr_batch(
    paths: list[str],
    languages: list[str] | None = None,
    recognition_level: str = "accurate",
    language_correction: bool = True,
    sort_reading_order: bool = True,
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    """OCR many image files and return aggregated output."""
    effective_languages = _default_languages(languages)

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for path in paths:
        try:
            image_path = _resolve_image_path(path)
            result = _run_helper(
                image_path=image_path,
                languages=effective_languages,
                recognition_level=recognition_level,
                language_correction=language_correction,
                sort_reading_order=sort_reading_order,
                min_confidence=min_confidence,
            )
            results.append(result)
        except Exception as exc:  # noqa: BLE001
            errors.append({"path": path, "error": str(exc)})

    return {
        "total": len(paths),
        "succeeded": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


@mcp.tool(
    description=(
        "Run OCR for a single image and return plain text only (newline-separated). "
        "Useful when structured metadata is unnecessary."
    )
)
def ocr_text(
    path: str,
    languages: list[str] | None = None,
    recognition_level: str = "accurate",
    language_correction: bool = True,
    sort_reading_order: bool = True,
    min_confidence: float = 0.0,
) -> str:
    """OCR one image and return full_text only."""
    result = ocr_image(
        path=path,
        languages=languages,
        recognition_level=recognition_level,
        language_correction=language_correction,
        sort_reading_order=sort_reading_order,
        min_confidence=min_confidence,
    )
    full_text = result.get("full_text")
    if full_text is None:
        full_text = result.get("fullText", "")
    return str(full_text)


@mcp.tool(
    description=(
        "Compile the Swift helper to a native binary for faster OCR calls. "
        "By default the server runs the Swift script directly."
    )
)
def compile_helper() -> dict[str, str]:
    """Compile vision_ocr.swift to .build/vision_ocr."""
    if not HELPER_SCRIPT.exists():
        raise OCRError(f"Swift helper script not found: {HELPER_SCRIPT}")

    out_dir = HELPER_BIN.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    command = [
        "xcrun",
        "swiftc",
        "-O",
        str(HELPER_SCRIPT),
        "-o",
        str(HELPER_BIN),
    ]

    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise OCRError(stderr or "swiftc failed")

    return {
        "binary": str(HELPER_BIN),
        "status": "compiled",
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
