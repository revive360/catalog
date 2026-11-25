from datetime import date
import json
import io
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree

from jsonschema import ValidationError
from PIL import Image
from catalog.build import (ROOT, COMMUNITY_WARNING, badge_svg, effective_status,
                           load_records, project_medal_svg, record_markdown, render, snippet, validate_record)
from catalog.badges import png, NEON, GRAY

TODAY = date(2026, 11, 25)


def fixture(slug="sample-reviewed"):
    return json.loads((ROOT / "data/apps" / f"{slug}.json").read_text())


class CatalogTests(unittest.TestCase):
    def test_all_six_examples_validate(self):
        self.assertEqual(len(load_records(ROOT / "data/apps", TODAY)), 6)

    def test_schema_rejects_unsafe_or_incomplete_inputs(self):
        for key, value in [("sha256", "not-a-hash"), ("source_commit", "123"),
                           ("version", "latest"), ("artifact_url", "javascript:alert(1)")]:
            with self.subTest(key=key), self.assertRaises(ValidationError):
                r = fixture(); r["review"]["release"][key] = value
                validate_record(r, TODAY)
        for mutation in (lambda r: r.pop("license"), lambda r: r.update(id="../../escape"),
                         lambda r: r.update(unexpected=True),
                         lambda r: r["review"].update(reviewed_on="2026-02-30")):
            with self.subTest(mutation=mutation), self.assertRaises(ValidationError):
                r = fixture(); mutation(r); validate_record(r, TODAY)

    def test_only_founder_self_review_allowed(self):
        r = fixture(); r["review"].update(reviewer=r["owner"], self_review_exception=True)
        with self.assertRaisesRegex(ValueError, "Only founder"):
            validate_record(r, TODAY)
        validate_record(fixture("tube360"), TODAY)

    def test_self_review_exception_cannot_be_hidden_or_fabricated(self):
        for slug, flag in [("tube360", False), ("sample-reviewed", True)]:
            with self.subTest(slug=slug), self.assertRaisesRegex(ValueError, "explicitly"):
                r = fixture(slug); r["review"]["self_review_exception"] = flag
                validate_record(r, TODAY)

    def test_project_requires_org_repository_and_ci_attestation(self):
        for mutation in (lambda r: r.update(repository="https://github.com/author/tube360"),
                         lambda r: r["review"].pop("attestation_url"),
                         lambda r: r["review"].update(builder="author"),
                         lambda r: r["review"].update(expires_on="2027-01-01")):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                r = fixture("tube360"); mutation(r); validate_record(r, TODAY)

    def test_project_cannot_claim_unreviewed_published_binary(self):
        r = fixture("tube360"); r["current"]["sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "match"):
            validate_record(r, TODAY)

    def test_external_requires_author_repository_and_expiry(self):
        for mutation in (lambda r: r.update(repository="https://github.com/revive360/notes"),
                         lambda r: r["review"].pop("expires_on"),
                         lambda r: r["review"].update(expires_on="2029-01-01"),
                         lambda r: r["review"].update(author_confirmed_on="2026-12-01")):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                r = fixture(); mutation(r); validate_record(r, TODAY)

    def test_real_certification_cannot_use_illustrated_console_evidence(self):
        r = fixture("tube360"); r["example"] = False
        with self.assertRaisesRegex(ValueError, "real-console"):
            validate_record(r, TODAY)
        r["review"]["console"]["result"] = "passed"
        with self.assertRaisesRegex(ValueError, "demonstration"):
            validate_record(r, TODAY)

    def test_evidence_urls_reject_credentials_or_missing_hosts(self):
        for url in ("https:///missing-host", "https://user:secret@example.invalid/evidence"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                r = fixture(); r["review"]["evidence_url"] = url
                validate_record(r, TODAY)

    def test_future_review_and_revocation_rejected(self):
        for slug, field in [("sample-reviewed", "reviewed_on"), ("sample-revoked", "date")]:
            r = fixture(slug)
            r["review" if field == "reviewed_on" else "revocation"][field] = "2026-12-01"
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_record(r, TODAY)

    def test_changes_in_version_hash_or_source_invalidate_latest(self):
        for key, value in [("version", "v1.2.4"), ("sha256", "a" * 64), ("source_commit", "a" * 40)]:
            r = fixture(); r["current"][key] = value
            with self.subTest(key=key):
                validate_record(r, TODAY)
                self.assertEqual(effective_status(r, TODAY), "current_unreviewed")
                self.assertIn("Reviewed v1.2.3", badge_svg(r, TODAY))
                self.assertIn("Current version not reviewed", record_markdown(r, TODAY))

    def test_expiry_inclusive_boundary_and_revocation_precedence(self):
        r = fixture(); expiry = date.fromisoformat(r["review"]["expires_on"])
        self.assertEqual(effective_status(r, date(2027, 3, 8)), "valid")
        self.assertEqual(effective_status(r, expiry), "expired")
        r["current"]["version"] = "v2.0.0"
        self.assertEqual(effective_status(r, expiry), "expired")
        r["revocation"] = {"date": "2026-11-25", "reason": "test finding"}
        self.assertEqual(effective_status(r, expiry), "revoked")

    def test_project_continuous_validity(self):
        self.assertEqual(effective_status(fixture("tube360"), date(2036, 11, 25)), "valid")

    def test_community_has_warning_and_never_badge_or_review(self):
        r = fixture("sample-community")
        self.assertIsNone(badge_svg(r, TODAY))
        self.assertIn(COMMUNITY_WARNING, record_markdown(r, TODAY))
        self.assertNotIn("![", snippet(r))
        r["review"] = fixture()["review"]
        with self.assertRaises(ValidationError):
            validate_record(r, TODAY)

    def test_svg_is_valid_xml_accessible_and_escaped(self):
        r = fixture("tube360"); r["name"] = '<script>alert("x")</script> & [link]'
        svg = badge_svg(r, TODAY); tree = ElementTree.fromstring(svg)
        self.assertEqual(tree.attrib["role"], "img")
        self.assertNotIn("<script>", svg)
        self.assertIn("data:image/jpeg;base64,", svg)
        self.assertNotIn("<script>", record_markdown(r, TODAY))

    def test_badge_link_targets_matching_canonical_record(self):
        r = fixture()
        text = snippet(r)
        self.assertIn("github.com/revive360/catalog/blob/main/generated/apps/sample-reviewed.md", text)
        self.assertIn("raw.githubusercontent.com/revive360/catalog/main/generated/badges/sample-reviewed.svg", text)

    def test_every_external_record_states_version_scope_and_no_org_updates(self):
        for slug in ("sample-reviewed", "sample-unreviewed", "sample-revoked", "sample-expired"):
            with self.subTest(slug=slug):
                text = record_markdown(fixture(slug), TODAY)
                self.assertIn("only the recorded version/hash/date", text)
                self.assertIn("No org update channel", text)

    def test_readme_badges_are_short_and_do_not_contain_demo_labels(self):
        labels = {"tube360": "Project", "sample-reviewed": "Reviewed v1.2.3",
                  "sample-unreviewed": "Reviewed v1.2.3", "sample-expired": "Reviewed v1.2.3",
                  "sample-revoked": "Revoked"}
        for slug,label in labels.items():
            with self.subTest(slug=slug):
                svg = badge_svg(fixture(slug),TODAY)
                tree = ElementTree.fromstring(svg)
                visible = [node.text for node in tree.findall('.//{http://www.w3.org/2000/svg}text')]
                self.assertEqual(visible, ['Revive360',label])
                self.assertNotIn('Demo',svg)
                self.assertEqual(tree.attrib['height'],'36')
                self.assertIn('data:image/jpeg;base64,',svg)
        for slug in ('sample-unreviewed','sample-expired'):
            self.assertIn(GRAY,badge_svg(fixture(slug),TODAY))
        self.assertIn(NEON,badge_svg(fixture('tube360'),TODAY))

    def test_medal_is_project_only_and_revocation_overrides_green(self):
        for slug in ('sample-reviewed','sample-unreviewed','sample-revoked','sample-expired','sample-community'):
            self.assertIsNone(project_medal_svg(fixture(slug),TODAY))
        r=fixture('tube360'); svg=project_medal_svg(r,TODAY)
        self.assertEqual(ElementTree.fromstring(svg).attrib['width'],'512')
        self.assertNotIn('Demo',svg)
        r['revocation']={'date':'2026-11-25','reason':'Test revocation'}
        revoked=project_medal_svg(r,TODAY)
        self.assertIn('Revoked',revoked)
        self.assertNotIn(NEON,revoked)
        with self.assertRaises(ValueError):
            snippet(fixture(),medal=True)

    def test_pngs_render_at_twice_svg_size_with_transparent_medal_corners(self):
        badge=badge_svg(fixture('tube360'),TODAY)
        rendered=Image.open(io.BytesIO(png(badge)))
        self.assertEqual(rendered.size,(418,72))
        image=Image.open(io.BytesIO(png(project_medal_svg(fixture('tube360'),TODAY))))
        self.assertEqual(image.size,(1024,1024))
        self.assertEqual(image.getpixel((0,0))[3],0)
        self.assertGreater(image.getpixel((512,512))[3],0)
        self.assertIn('tube360-medal.png',snippet(fixture('tube360'),medal=True,extension='png'))

    def test_generation_is_deterministic_and_prunes_stale_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            render(ROOT / "data/apps", output, TODAY)
            before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            (output / "badges/stale.svg").write_text("stale")
            render(ROOT / "data/apps", output, TODAY)
            after = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(len(list((output / "apps").glob("*.md"))), 6)
            self.assertEqual(len(list((output / "badges").glob("*.svg"))), 6)
            self.assertEqual(len(list((output / "badges").glob("*.png"))), 6)
            self.assertTrue((output/'badges/tube360-medal.svg').is_file())
            self.assertFalse(any((output/'badges').glob('sample-*-medal.*')))
            self.assertFalse((output / "badges/sample-community.svg").exists())
            index = (output / "README.md").read_text()
            self.assertLess(index.index("## Revive360 Project"), index.index("## Reviewed"))
            self.assertLess(index.index("## Reviewed"), index.index("## Community list"))

    def test_bad_record_cannot_partially_replace_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, output = Path(tmp) / "data", Path(tmp) / "output"
            data.mkdir(); output.mkdir(); (output / "sentinel").write_text("keep")
            r = fixture(); r["current"]["sha256"] = "invalid"
            (data / "sample-reviewed.json").write_text(json.dumps(r))
            with self.assertRaises(ValueError):
                render(data, output, TODAY)
            self.assertEqual((output / "sentinel").read_text(), "keep")

    def test_empty_or_misnamed_catalog_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            with self.assertRaisesRegex(ValueError, "at least"):
                load_records(data, TODAY)
            (data / "wrong-name.json").write_text(json.dumps(fixture()))
            with self.assertRaisesRegex(ValueError, "filename"):
                load_records(data, TODAY)

    def test_generator_refuses_to_replace_an_unowned_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "apps").mkdir()
            (output / "apps/important.txt").write_text("preserve")
            with self.assertRaisesRegex(ValueError, "previously generated"):
                render(ROOT / "data/apps", output, TODAY)
            self.assertEqual((output / "apps/important.txt").read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
