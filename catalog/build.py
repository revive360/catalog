"""Validate records and generate badges, Markdown records and an offline index.

No network, publication, certificate issuance or implicit upstream monitoring.
"""
from __future__ import annotations

import argparse
from datetime import date
from html import escape
import json
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
import markdown

from catalog.badges import compact, compact_label, medal, png

ROOT = Path(__file__).resolve().parents[1]
RECORD_BASE = "https://github.com/revive360/catalog/blob/main/generated/apps"
IMAGE_BASE = "https://raw.githubusercontent.com/revive360/catalog/main/generated/badges"
COMMUNITY_WARNING = (
    "Not verified by Revive360; not a recommendation; use at your own risk. / "
    "Não verificado pela Revive360, não é recomendação, use por sua conta e risco. / "
    "No verificado por Revive360; no es una recomendación; úsalo bajo tu responsabilidad."
)
LABELS = {"project": "Revive360 Project", "reviewed": "Reviewed", "community": "Community list"}
STATES = {"valid": "Valid", "current_unreviewed": "Current version not reviewed",
          "revoked": "Revoked", "expired": "Expired", "unverified": "Unverified"}


def validator() -> Draft202012Validator:
    schema = json.loads((ROOT / "schema/app.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_record(record: dict, today: date) -> None:
    validator().validate(record)
    review = record.get("review")
    if not review:
        return
    owner, reviewer = record["owner"].casefold(), review["reviewer"].casefold()
    is_self = owner == reviewer
    if is_self and owner != "pedrohenrique0713":
        raise ValueError("Only founder Pedro may review his own app")
    if review["self_review_exception"] != is_self:
        raise ValueError("Founder self-review exception must be explicitly and accurately recorded")
    reviewed = date.fromisoformat(review["reviewed_on"])
    if reviewed > today:
        raise ValueError("Review date cannot be in the future")
    revoked = record.get("revocation")
    if revoked and not reviewed <= date.fromisoformat(revoked["date"]) <= today:
        raise ValueError("Revocation date must be between review date and today")
    if record["tier"] == "project":
        if urlsplit(record["repository"]).path.split("/")[1].casefold() != "revive360":
            raise ValueError("Project repository must be inside revive360")
        if review["builder"] != "org-ci" or not all(k in review for k in ("ci_run_url", "attestation_url")):
            raise ValueError("Project needs org CI and signed attestation evidence")
        if "expires_on" in review or "author_confirmed_on" in review:
            raise ValueError("Project status is continuous, with no external-review expiry")
        if record["current"] != review["release"]:
            raise ValueError("Project current release must match its reviewed CI artifact")
    else:
        if urlsplit(record["repository"]).path.split("/")[1].casefold() == "revive360":
            raise ValueError("Reviewed is for repositories outside revive360")
        if review["builder"] != "author" or not all(k in review for k in ("author_confirmed_on", "expires_on")):
            raise ValueError("External review needs author build, confirmation and expiry")
        confirmed = date.fromisoformat(review["author_confirmed_on"])
        expires = date.fromisoformat(review["expires_on"])
        if not reviewed <= confirmed <= today or not confirmed < expires:
            raise ValueError("Invalid author confirmation/expiry chronology")
        if (expires - confirmed).days > 104:
            raise ValueError("External expiry exceeds the initial 90 + 14 day policy")
    if not record["example"] and review["console"]["result"] != "passed":
        raise ValueError("Real certification requires a passed real-console record")
    # URLs are evidence references, not proof: human review is still mandatory.
    urls = [record["current"]["artifact_url"], review["release"]["artifact_url"],
            review["evidence_url"], review["console"]["record_url"]]
    urls += [review[key] for key in ("ci_run_url", "attestation_url") if key in review]
    for value in urls:
        parts = urlsplit(value)
        if not parts.hostname or parts.username or parts.password:
            raise ValueError("Evidence URLs need a hostname and must not contain credentials")
        if not record["example"] and parts.hostname.endswith(".invalid"):
            raise ValueError("Real evidence must not use demonstration URLs")


def effective_status(record: dict, today: date) -> str:
    if record["tier"] == "community":
        return "unverified"
    if record.get("revocation"):
        return "revoked"
    review = record["review"]
    if record["tier"] == "reviewed":
        if today >= date.fromisoformat(review["expires_on"]):
            return "expired"
        if any(record["current"][key] != review["release"][key]
               for key in ("version", "source_commit", "sha256")):
            return "current_unreviewed"
    return "valid"


def md(value: str) -> str:
    """Escape record text for Markdown as well as raw HTML."""
    return re.sub(r"([\\`*{}\[\]()#+.!_|>~-])", r"\\\1", escape(value)).replace("\n", " ")


def badge_svg(record: dict, today: date) -> str | None:
    state = effective_status(record, today)
    return compact(record, state, STATES[state])


def project_medal_svg(record: dict, today: date) -> str | None:
    state = effective_status(record, today)
    return medal(record, state, STATES[state])


def snippet(record: dict, *, medal=False, extension="svg", as_of: date | None = None) -> str:
    if record["tier"] == "community":
        return "No badge for Community list."
    if medal and record["tier"] != "project":
        raise ValueError("Only Project has a medal")
    if extension not in ("svg", "png"):
        raise ValueError("Badge format must be svg or png")
    label = "Revive360 Project" if medal else "Revive360 " + compact_label(record, effective_status(record, as_of or date.today()))[1]
    suffix = "-medal" if medal else ""
    return f'[![{label}]({IMAGE_BASE}/{record["id"]}{suffix}.{extension})]({RECORD_BASE}/{record["id"]}.md)'


def record_markdown(record: dict, today: date) -> str:
    state = effective_status(record, today)
    parts = [f'# {md(record["name"])}', f'**{LABELS[record["tier"]]} — {STATES[state]}**',
             f'Status calculated on **{today.isoformat()}** from the recorded data; not live upstream monitoring.']
    if record["example"]:
        parts += ['> **DEMONSTRATION ONLY — not a certification.** ' + md(record["example_note"])]
    if record["tier"] == "community":
        parts += ['**' + COMMUNITY_WARNING + '**']
    else:
        badge_label = compact_label(record,state)[1]
        parts += [f'![Revive360 {badge_label}](../badges/{record["id"]}.svg)']
    parts += [md(record["summary"]), f'Repository: {record["repository"]}',
              f'Owner: {md(record["owner"])}. License: {md(record["license"])}. Membership is not a badge.']
    if "review" in record:
        r, rel = record["review"], record["review"]["release"]
        parts += [f'## Reviewed release ({r["reviewed_on"]})',
                  f'Version: **{rel["version"]}**. Reviewer: **{md(r["reviewer"])}**.',
                  f'Founder self-review exception: **{str(r["self_review_exception"]).lower()}**.',
                  f'Source commit: `{rel["source_commit"]}`', f'SHA-256: `{rel["sha256"]}`',
                  f'Author/CI artifact: {rel["artifact_url"]}',
                  f'Build producer: **{r["builder"]}**. Review evidence: {r["evidence_url"]}',
                  f'Real-console result: **{r["console"]["result"]}**. Record: {r["console"]["record_url"]}']
        for key in ("ci_run_url", "attestation_url", "author_confirmed_on", "expires_on"):
            if key in r:
                parts += [f'{key}: {r[key]}']
        if record["tier"] == "reviewed":
            parts += ['**External review covers only the recorded version/hash/date.** The author builds and distributes the app; Revive360 checks the hash and source linkage. **No org update channel.** New versions or replaced binaries return to the manual FIFO queue (14-day target). Author disappearance expires the badge.']
        cur = record["current"]
        parts += ['## Current recorded release', f'Version: **{cur["version"]}**',
                  f'Source commit: `{cur["source_commit"]}`', f'SHA-256: `{cur["sha256"]}`']
        if state == "current_unreviewed":
            parts += ['**Current version not reviewed / versão atual não revisada / versión actual no revisada.** Only the historical version/hash above was reviewed. No org update channel.']
        if state == "expired":
            parts += ['**Expired: author confirmation deadline passed.** Historical evidence is retained; no current certification.']
    if record.get("revocation"):
        rev = record["revocation"]
        parts += [f'## Revoked on {rev["date"]}', md(rev["reason"]), 'Do not rely on a copied or cached badge; this tombstone is authoritative.']
    parts += ['## Scope and user risk',
              'Review is not a complete audit or warranty. Software is as is under its license. Homebrew risks Xbox Live bans, data loss and console damage. No collection without opt-in; login/tokens stay on the console. No DRM/paywall bypass. Third-party terms risk belongs to the author.',
              '[Review policy, checklist, response priorities and limits](https://github.com/revive360/.github/blob/main/REVIEW.md). Security response: 48 hours; severe findings revoke immediately. External review queue: FIFO, 14-day target.',
              '## README snippet', '```markdown\n' + snippet(record,as_of=today) + '\n```',
              '[Back to catalog](../README.md)']
    if record["tier"] == "project":
        parts += ['## Project medal for the top of a README',
                  f'![Revive360 Project medal](../badges/{record["id"]}-medal.svg)',
                  '```markdown\n' + snippet(record, medal=True,as_of=today) + '\n```',
                  'PNG alternative:\n\n```markdown\n' + snippet(record, medal=True, extension="png",as_of=today) + '\n```']
    return '\n\n'.join(parts) + '\n'


def load_records(data_dir: Path, today: date) -> list[dict]:
    files = sorted(data_dir.glob("*.json"))
    if not files:
        raise ValueError("Catalog must contain at least one record")
    records, seen = [], set()
    for path in files:
        record = json.loads(path.read_text())
        try:
            validate_record(record, today)
            if record["id"] in seen or path.stem != record["id"]:
                raise ValueError("Record ID must be unique and match its filename")
        except (ValueError, ValidationError) as exc:
            raise ValueError(f'{path.name}: {exc}') from exc
        seen.add(record["id"])
        records.append(record)
    return records


def render(data_dir: Path, output: Path, today: date) -> list[dict]:
    records = load_records(data_dir, today)  # Validate all before producing any output.
    if output.exists() and any(output.iterdir()) and not (output / ".catalog-generated").is_file():
        raise ValueError("Output must be empty or a previously generated catalog directory")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="catalog-") as temporary:
        staging = Path(temporary)
        (staging / "apps").mkdir()
        (staging / "badges").mkdir()
        notice = ('Local demonstration dataset. No entry is an active certification.' if all(r['example'] for r in records)
                  else 'Includes explicitly marked demonstration entries.' if any(r['example'] for r in records)
                  else 'Verify every badge against its linked catalog record.')
        index = ['# Revive360 catalog',
                 f'**{notice}**',
                 f'Generated for {today.isoformat()}. Check the linked record, not a copied image.',
                 'Status is based on manually maintained data. Membership alone is not a badge.']
        sections = []
        for tier in ("project", "reviewed", "community"):
            index += ['## ' + LABELS[tier]]
            cards = []
            if tier == "community":
                index += [COMMUNITY_WARNING]
            for rec in records:
                if rec["tier"] != tier:
                    continue
                slug = rec["id"]
                doc = record_markdown(rec, today)
                (staging / "apps" / f'{slug}.md').write_text(doc)
                badge = badge_svg(rec, today)
                if badge:
                    (staging / "badges" / f'{slug}.svg').write_text(badge)
                    (staging / "badges" / f'{slug}.png').write_bytes(png(badge))
                project_medal = project_medal_svg(rec, today)
                if project_medal:
                    (staging / "badges" / f'{slug}-medal.svg').write_text(project_medal)
                    (staging / "badges" / f'{slug}-medal.png').write_bytes(png(project_medal))
                index += [f'- [{md(rec["name"])}](apps/{slug}.md) — {STATES[effective_status(rec,today)]}; ' + ('demonstration only' if rec['example'] else 'catalog record')]
                body = markdown.markdown(doc, extensions=["fenced_code"])
                if badge:
                    body = re.sub(r'<img[^>]*src="\.\./badges/[^\"]+"[^>]*>', lambda match: project_medal if "-medal.svg" in match.group(0) else badge, body)
                # Index is self-contained and links records internally.
                body = body.replace('href="../README.md"', 'href="#top"')
                cards.append(f'<article id="{slug}">{body}</article>')
            sections.append(f'<section><h2>{LABELS[tier]}</h2>' + ''.join(cards) + '</section>')
        (staging / "README.md").write_text('\n\n'.join(index) + '\n')
        snippets = ['# README badge snippets', 'Examples link to demonstration records. SVG assets contain no demo label; inspect the linked record before use.']
        for rec in records:
            snippets += [f'## {rec["id"]}', 'Compact SVG:\n\n```markdown\n' + snippet(rec,as_of=today) + '\n```']
            if rec["tier"] != "community":
                snippets += ['Compact PNG:\n\n```markdown\n' + snippet(rec, extension="png",as_of=today) + '\n```']
            if rec["tier"] == "project":
                for ext in ("svg", "png"):
                    snippets += [f'Project medal ({ext.upper()}):\n\n```markdown\n' + snippet(rec, medal=True, extension=ext,as_of=today) + '\n```']
        (staging / "snippets.md").write_text('\n\n'.join(snippets) + '\n')
        style = 'body{font:17px/1.65 system-ui,sans-serif;max-width:1000px;margin:32px auto;padding:0 20px;color:#20342c;background:#f5f7f7}article{border-top:2px solid #c7d2cd;padding:24px 0}svg{max-width:100%;height:auto}pre{overflow:auto;padding:16px;background:#e4eae7}a{color:#185d99}blockquote{border-left:5px solid #8d3e15;padding-left:20px}code{overflow-wrap:anywhere}h1,h2,h3{line-height:1.2}'
        (staging / "index.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Revive360 catalog</title><style>' + style + '</style><body id="top"><h1>Revive360 catalog</h1><p><strong>' + notice + '</strong></p>' + ''.join(sections) + '</body></html>')
        # Replace only files owned by the generator; prune removed badges/records.
        for dirname in ("apps", "badges"):
            target = output / dirname
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(staging / dirname, target)
        for filename in ("README.md", "snippets.md", "index.html"):
            shutil.copyfile(staging / filename, output / filename)
        (output / ".catalog-generated").write_text("Owned by python -m catalog.build\n")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/apps")
    parser.add_argument("--output", type=Path, default=ROOT / "generated")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or output in (args.data.resolve(), ROOT / "assets", ROOT / "schema") or output in args.data.resolve().parents or args.data.resolve() in output.parents:
        parser.error("Output must be separate from source/data directories")
    records = render(args.data, output, args.as_of)
    print(f'Validated {len(records)} records; rendered for {args.as_of}; no publication performed.')


if __name__ == "__main__":
    main()
