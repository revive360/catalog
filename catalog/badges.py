"""Compact README badges and the Project-only cartoon medal.

SVGs carry no demonstration label; the local preview and catalog record do.
PNG rendering uses a pinned Rust renderer and a bundled, licensed font.
"""
import base64
from functools import lru_cache
from html import escape
import math
from pathlib import Path

import resvg_py

ASSETS = Path(__file__).resolve().parents[1] / "assets"
NEON = "#9dff45"
RED = "#ff695e"
GRAY = "#bbc1c5"
FONT = "Droid Sans,Arial,sans-serif"


@lru_cache(maxsize=3)
def bitmap(name: str) -> str:
    return "data:image/jpeg;base64," + base64.b64encode((ASSETS / name).read_bytes()).decode()


def compact(record: dict, state: str, state_label: str) -> str | None:
    if record["tier"] == "community":
        return None
    project = record["tier"] == "project"
    label = "Project" if project else "Reviewed " + record["review"]["release"]["version"]
    if state == "revoked":
        label = "Revoked"
    if state == "valid" and project:
        border, left, right, ink = NEON, "#11170f", "#243d17", NEON
    elif state == "valid":
        border, left, right, ink = "#75898c", "#242b2e", "#4e6268", "#e7edef"
    elif state == "revoked":
        border, left, right, ink = RED, "#271b1b", "#7a2927", "#fff1ed"
    else:
        border, left, right, ink = GRAY, "#303437", "#565d61", "#e2e5e7"
    left_width = 125
    right_width = max(84, len(label) * 8 + 24)
    width = left_width + right_width
    mascot = bitmap("mascot-small.jpg" if project and state == "valid" else "mascot-muted.jpg")
    accessible = escape(f'Revive360 {label}: {state_label}; {record["name"]}', quote=True)
    clip_id = "badge-clip-" + record["id"]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="36" viewBox="0 0 {width} 36" role="img" aria-label="{accessible}" data-state="{state}">'
        f'<title>{accessible}</title><defs><clipPath id="{clip_id}"><rect x="2" y="2" width="{width-4}" height="32" rx="6"/></clipPath></defs>'
        f'<rect x="1" y="1" width="{width-2}" height="34" rx="8" fill="#080b08" stroke="#080b08" stroke-width="2"/>'
        f'<g clip-path="url(#{clip_id})"><path fill="{left}" d="M2 2h{left_width-2}v32H2z"/>'
        f'<path fill="{right}" d="M{left_width} 2h{right_width}v32H{left_width}z"/>'
        f'<image xlink:href="{mascot}" x="5" y="5" width="26" height="26"/>'
        f'<path d="M{left_width} 2v32" stroke="#080b08" stroke-width="2"/></g>'
        f'<g font-family="{FONT}" font-weight="700" fill="{ink}">'
        '<text x="37" y="23" font-size="14">Revive360</text>'
        f'<text x="{left_width+right_width/2:g}" y="23" text-anchor="middle" font-size="14">{escape(label)}</text></g>'
        f'<rect x="1.5" y="1.5" width="{width-3}" height="33" rx="7" fill="none" stroke="{border}" stroke-width="2"/></svg>\n'
    )


def ring_letters(text: str, start: float, end: float, radius: int, bottom=False) -> str:
    letters = []
    for i, character in enumerate(text):
        angle = start + (end-start) * i / max(1, len(text)-1)
        theta = math.radians(angle)
        x, y = 256 + radius * math.cos(theta), 256 + radius * math.sin(theta)
        rotation = angle - 90 if bottom else angle + 90
        letters.append(f'<text transform="translate({x:.3f} {y:.3f}) rotate({rotation:.3f})" text-anchor="middle" dominant-baseline="central">{character}</text>')
    return "".join(letters)


def medal(record: dict, state: str, state_label: str) -> str | None:
    if record["tier"] != "project":
        return None
    accent = NEON if state == "valid" else RED if state == "revoked" else GRAY
    lower = "REVOKED" if state == "revoked" else "PROJECT"
    points = []
    for i in range(120):
        theta = 2 * math.pi * i / 120
        radius = 245 if i % 3 == 0 else 239
        points.append(f'{256+radius*math.cos(theta):.2f},{256+radius*math.sin(theta):.2f}')
    title = escape(f'Revive360 Project: {state_label}; {record["name"]}', quote=True)
    clip_id = "medal-clip-" + record["id"]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="512" height="512" viewBox="0 0 512 512" role="img" aria-label="{title}" data-state="{state}">'
        f'<title>{title}</title><polygon points="{" ".join(points)}" fill="{accent}" stroke="#070b06" stroke-width="12" stroke-linejoin="round"/>'
        '<circle cx="256" cy="256" r="224" fill="#10170d" stroke="#070b06" stroke-width="8"/>'
        f'<circle cx="256" cy="256" r="215" fill="none" stroke="{accent}" stroke-width="3"/>'
        f'<defs><clipPath id="{clip_id}"><circle cx="256" cy="256" r="160"/></clipPath></defs>'
        f'<circle cx="256" cy="256" r="167" fill="{accent}" stroke="#070b06" stroke-width="6"/>'
        f'<image xlink:href="{bitmap("mascot-medal.jpg")}" x="96" y="96" width="320" height="320" clip-path="url(#{clip_id})"/>'
        f'<circle cx="256" cy="256" r="160" fill="none" stroke="#070b06" stroke-width="5"/>'
        f'<g font-family="{FONT}" font-size="31" font-weight="700" fill="{accent}" stroke="#070b06" stroke-width="1" paint-order="stroke">'
        + ring_letters("REVIVE360", -148, -32, 190) + ring_letters(lower, 140, 40, 190, bottom=True) + '</g>'
        f'<g fill="{accent}" stroke="#070b06" stroke-width="3"><path d="M59 239l5 11 12 5-12 5-5 11-5-11-12-5 12-5z"/>'
        '<path d="M453 239l5 11 12 5-12 5-5 11-5-11-12-5 12-5z"/></g></svg>\n'
    )


def png(svg: str) -> bytes:
    return resvg_py.svg_to_bytes(svg_string=svg, zoom=2.0, skip_system_fonts=True,
                                 font_files=[str(ASSETS / "fonts/DroidSans-Bold.ttf")])
