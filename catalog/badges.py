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

# Each state has its own word, vector icon and palette. All type is drawn on
# opaque fills, so README themes cannot change the text/background contrast.
PALETTES = {
    "official": {"border": NEON, "left": "#11170f", "right": "#203c12", "ink": NEON},
    "reviewed": {"border": "#459e9b", "left": "#182b2d", "right": "#135458", "ink": "#d4fff8"},
    "outdated": {"border": "#e1aa3a", "left": "#2d2517", "right": "#664512", "ink": "#ffe6a9"},
    "expired": {"border": "#9aa4ad", "left": "#2b3035", "right": "#4b5158", "ink": "#e6e9ed"},
    "revoked": {"border": "#fb7b70", "left": "#321d1d", "right": "#8c2925", "ink": "#ffe7e2"},
}


def compact_label(record: dict, state: str) -> tuple[str, str]:
    if state == "revoked":
        return "revoked", "Revoked"
    if state == "expired":
        return "expired", "Expired"
    if state == "current_unreviewed":
        return "outdated", "Outdated " + record["review"]["release"]["version"]
    if record["tier"] == "project":
        return "official", "Official"
    return "reviewed", "Reviewed " + record["review"]["release"]["version"]


def state_icon(kind: str, x: float, ink: str, background: str) -> str:
    paths = {
        "official": '<path d="M0-9l2.8 5.7 6.3.9-4.6 4.5 1.1 6.3L0 4.4l-5.6 3 1.1-6.3-4.6-4.5 6.3-.9z"/>',
        "reviewed": '<path d="M-7 0l4.5 4.5L7-6" fill="none" stroke-width="2.8"/>',
        "outdated": '<path d="M0-9L9 7H-9z" stroke-width="1.3"/>'
                    f'<path d="M0-3v4" stroke="{background}" stroke-width="2"/>'
                    f'<circle cx="0" cy="4" r="1" fill="{background}" stroke="none"/>',
        "expired": '<path d="M-6-8H6M-6 8H6M-5-8v4l10 8v4M5-8v4L-5 4v4" fill="none" stroke-width="1.8"/>',
        "revoked": '<path d="M-6-6L6 6M6-6L-6 6" fill="none" stroke-width="2.8"/>',
    }
    return (f'<g data-icon="{kind}" aria-hidden="true" transform="translate({x:g} 18)" '
            f'fill="{ink}" stroke="{ink}" stroke-linecap="round" stroke-linejoin="round">'
            + paths[kind] + '</g>')


@lru_cache(maxsize=3)
def bitmap(name: str) -> str:
    return "data:image/jpeg;base64," + base64.b64encode((ASSETS / name).read_bytes()).decode()


def compact(record: dict, state: str, state_label: str) -> str | None:
    if record["tier"] == "community":
        return None
    kind, label = compact_label(record, state)
    palette = PALETTES[kind]
    border, left, right, ink = (palette[key] for key in ("border", "left", "right", "ink"))
    left_width = 125
    right_width = max(106, len(label) * 8 + 48)
    width = left_width + right_width
    official = kind == "official"
    mascot = bitmap("mascot-small.jpg" if official else "mascot-muted.jpg")
    scope = "Revive360 Project, highest level, continuous while compliant; " if official else ""
    accessible = escape(f'Revive360 {label}: {scope}{state_label}; {record["name"]}', quote=True)
    clip_id = "badge-clip-" + record["id"]
    glow_id = "badge-glow-" + record["id"]
    glow_definition = (f'<filter id="{glow_id}" x="-15%" y="-60%" width="130%" height="220%">'
                       '<feGaussianBlur stdDeviation="1.3"/></filter>') if official else ""
    glow = (f'<rect x="2" y="2" width="{width-4}" height="32" rx="7" fill="none" '
            f'stroke="{NEON}" stroke-width="4" opacity=".85" filter="url(#{glow_id})"/>') if official else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="36" viewBox="0 0 {width} 36" role="img" aria-label="{accessible}" data-state="{state}">'
        f'<title>{accessible}</title><defs>{glow_definition}<clipPath id="{clip_id}"><rect x="2" y="2" width="{width-4}" height="32" rx="6"/></clipPath></defs>{glow}'
        f'<rect x="1" y="1" width="{width-2}" height="34" rx="8" fill="#080b08" stroke="#080b08" stroke-width="2"/>'
        f'<g clip-path="url(#{clip_id})"><path fill="{left}" d="M2 2h{left_width-2}v32H2z"/>'
        f'<path fill="{right}" d="M{left_width} 2h{right_width}v32H{left_width}z"/>'
        f'<image xlink:href="{mascot}" x="5" y="5" width="26" height="26"/>'
        f'<path d="M{left_width} 2v32" stroke="#080b08" stroke-width="2"/></g>'
        + state_icon(kind, left_width+17, ink, right) +
        f'<g font-family="{FONT}" font-weight="700" fill="{ink}">'
        '<text x="37" y="23" font-size="14">Revive360</text>'
        f'<text x="{left_width+34}" y="23" font-size="14">{escape(label)}</text></g>'
        f'<rect x="1.5" y="1.5" width="{width-3}" height="33" rx="7" fill="none" stroke="{border}" stroke-width="{2.8 if official else 1.8}"/></svg>\n'
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
