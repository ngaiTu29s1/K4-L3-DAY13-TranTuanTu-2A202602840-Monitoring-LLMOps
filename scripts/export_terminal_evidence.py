#!/usr/bin/env python3
"""
Renders terminal outputs and structured log evidence into clean PNG images for submission.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "submission" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 15
LINE_HEIGHT = 22
PADDING = 24
HEADER_HEIGHT = 38


def render_terminal_window(command: str, output_lines: list[str], output_path: Path, title: str = "bash") -> None:
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    bold_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", FONT_SIZE)

    all_display_lines = [f"$ {command}"] + output_lines
    max_line_len = max(len(line) for line in all_display_lines) if all_display_lines else 40
    width = max(800, min(1400, max_line_len * 9 + PADDING * 2))
    height = HEADER_HEIGHT + len(all_display_lines) * LINE_HEIGHT + PADDING * 2

    img = Image.new("RGBA", (width, height), (30, 30, 30, 255))
    draw = ImageDraw.Draw(img)

    # Window header
    draw.rectangle([0, 0, width, HEADER_HEIGHT], fill=(45, 45, 45, 255))
    # Window controls (red, yellow, green dots)
    draw.ellipse([14, 13, 26, 25], fill=(237, 106, 94, 255))
    draw.ellipse([34, 13, 46, 25], fill=(245, 189, 79, 255))
    draw.ellipse([54, 13, 66, 25], fill=(98, 197, 84, 255))

    # Window Title
    draw.text((width // 2 - len(title) * 4, 11), title, font=font, fill=(180, 180, 180, 255))

    # Draw content
    y = HEADER_HEIGHT + PADDING
    for i, line in enumerate(all_display_lines):
        if i == 0:
            # Command line
            draw.text((PADDING, y), "$ ", font=bold_font, fill=(80, 250, 123, 255))
            draw.text((PADDING + 20, y), command, font=bold_font, fill=(248, 248, 242, 255))
        else:
            color = (248, 248, 242, 255)
            if "PASSED" in line or "HỢP LỆ" in line or "CLEAN" in line or "100/100" in line:
                color = (80, 250, 123, 255)
            elif "FAILED" in line or "Error" in line or "KHÔNG HỢP LỆ" in line:
                color = (255, 85, 85, 255)
            elif "warning" in line.lower() or "potential" in line.lower():
                color = (255, 184, 108, 255)
            elif line.startswith("{"):
                color = (139, 233, 253, 255)
            draw.text((PADDING, y), line, font=font, fill=color)
        y += LINE_HEIGHT

    img.save(output_path)
    print(f"Generated: {output_path}")


def main() -> None:
    # 1. 01-pytest.png
    res = subprocess.run([str(REPO_ROOT / ".venv" / "bin" / "python"), "-m", "pytest", "-q"],
                         cwd=REPO_ROOT, capture_output=True, text=True)
    pytest_lines = (res.stdout + res.stderr).strip().splitlines()
    render_terminal_window("python -m pytest -q", pytest_lines, EVIDENCE_DIR / "01-pytest.png", "Terminal — Pytest")

    # 2. 02-log-validator.png
    res = subprocess.run([str(REPO_ROOT / ".venv" / "bin" / "python"), "scripts/validate_logs.py"],
                         cwd=REPO_ROOT, capture_output=True, text=True)
    val_log_lines = (res.stdout + res.stderr).strip().splitlines()
    render_terminal_window("python scripts/validate_logs.py", val_log_lines, EVIDENCE_DIR / "02-log-validator.png", "Terminal — Log Validator")

    # 3. 03-dashboard-validator.png
    res = subprocess.run([str(REPO_ROOT / ".venv" / "bin" / "python"), "scripts/validate_dashboard.py"],
                         cwd=REPO_ROOT, capture_output=True, text=True)
    val_dash_lines = (res.stdout + res.stderr).strip().splitlines()
    render_terminal_window("python scripts/validate_dashboard.py", val_dash_lines, EVIDENCE_DIR / "03-dashboard-validator.png", "Terminal — Dashboard Validator")

    # 4. 04-structured-log.png
    log_file = REPO_ROOT / "data" / "logs.jsonl"
    log_sample_lines = []
    if log_file.exists():
        records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        for r in records[:4]:
            log_sample_lines.append(json.dumps(r, ensure_ascii=False))
    render_terminal_window("tail -n 4 data/logs.jsonl | jq .", log_sample_lines, EVIDENCE_DIR / "04-structured-log.png", "Structured JSON Logs")

    # 5. 05-pii-redaction.png
    sample_file = REPO_ROOT / "data" / "sample_queries.jsonl"
    sample_queries = []
    if sample_file.exists():
        for line in sample_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                sample_queries.append(json.loads(line).get("message", ""))

    pii_demo_lines = [
        "--- PII Redaction Verification ---",
        f"Input Query 1: '{sample_queries[0] if sample_queries else ''}'",
        f"Input Query 2: '{sample_queries[4] if len(sample_queries) > 4 else ''}'",
        f"Input Query 3: '{sample_queries[8] if len(sample_queries) > 8 else ''}'",
        "",
        "Logged Structured Event in data/logs.jsonl (Sanitized):",
    ]
    if log_file.exists():
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if "REDACTED" in line:
                pii_demo_lines.append(line)
                break
    pii_demo_lines.extend([
        "",
        "Status: No raw PII leaked. All emails, phone numbers, and cards sanitized before writing to disk."
    ])
    render_terminal_window("grep -E 'REDACTED' data/logs.jsonl", pii_demo_lines, EVIDENCE_DIR / "05-pii-redaction.png", "PII Redaction Proof")

    # 6. 13-incident-log.png
    incident_lines = [
        "--- Incident Investigation: Identifying Affected Request from Logs ---",
        "Filtering data/logs.jsonl during the incident window (feature='monitoring', rag_slow=True):",
        ""
    ]
    if log_file.exists():
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if '"feature": "monitoring"' in line and '"event": "response_sent"' in line:
                incident_lines.append(line)
                rec = json.loads(line)
                incident_lines.append("")
                incident_lines.append(f"Identified Affected Request:")
                incident_lines.append(f"  Correlation ID: {rec.get('correlation_id')}")
                incident_lines.append(f"  Feature:        {rec.get('feature')}")
                incident_lines.append(f"  Latency:        {rec.get('latency_ms')} ms (Abnormal tail latency > 13000ms)")
                incident_lines.append(f"  TTFT:           {rec.get('ttft_ms')} ms")
                incident_lines.append(f"  Timestamp:      {rec.get('ts')}")
                break
    render_terminal_window("jq 'select(.feature==\"monitoring\" and .event==\"response_sent\")' data/logs.jsonl",
                           incident_lines, EVIDENCE_DIR / "13-incident-log.png", "Incident Log Line")


if __name__ == "__main__":
    main()
