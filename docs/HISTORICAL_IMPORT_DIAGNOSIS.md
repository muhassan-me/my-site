# Historical Import Diagnosis

Inspected on 2026-10-11. No archive or production data was modified during diagnosis.

## Stored Archive Facts

`data/archive.json` is schema version 1. At the latest stable read it contained 235 imports / 234 detail records for 2021 and 230 imports / 229 detail records for 2022. Every stored detail record in both editions had `locationName: "s"` (234/234 and 229/229); each edition also has one separate Universal Event import. During diagnosis the two collector processes were stopped to prevent further malformed rows. The archive remains untracked user data and was not edited or cleaned.

The affected records retain individual source URLs, including:

- 2021 ordinary: `https://2021.spaceappschallenge.org/locations/aaruush-chennai/`
- 2021 global: `https://2021.spaceappschallenge.org/locations/universal-event/`
- 2022 ordinary: `https://2022.spaceappschallenge.org/locations/bengaluru/`
- 2022 global: `https://2022.spaceappschallenge.org/locations/universal-event/`

Downloaded listing manifests are present in the user Downloads folder: `space-apps-2021-locations.json` (329 URLs) and `space-apps-2022-locations.json` (333 URLs). They contain listing text and location URLs, not detail-page HTML. No retry report was present at diagnosis time. Archive imports retain extracted visible text in `sourceText`; they do not retain raw HTML.

## Root Cause

Collection fetched the detail pages and retained their visible text, but `tools/historical.py::_label_fields` used `^(country|city|location)` without a word boundary. It matched the navigation label `Locations` and set the location value to the trailing `s`, overriding the real page heading/title. It also did not extract the old pages' unlabelled country/city sequence.

The count parser did not support `Teams(453)` or text joined at markup boundaries such as `the3596people`. Consequently, the 2021 Universal Event's stored source text contains 3,596 participants and 453 teams, but both fields were imported as null. The stored 2022 Universal Event text contains `Teams(629)`; the inspected text does not contain a participant count, so participants must remain unavailable.

The dashboard currently renders whatever `locationName`, participant, and team fields the resolver supplies. It displays teams in the detail drawer when numeric, but the resolver did not use the full location identity consistently for these malformed records. Thus the primary corruption is at parsing/normalization, with rendering also needing to show the source and unavailable values clearly.

## Evidence and Limits

The archive contains source URLs and extracted visible text; it does not retain raw HTML response files. The two downloaded listing manifests contain 329 (2021) and 333 (2022) location URLs; no collector retry report was present. Read-only GETs during this diagnosis verified four live pages:

| Page | Actual heading structure | Available details |
| --- | --- | --- |
| 2021 Universal Event | `h2: Anywhere in the World`, `h1: Universal Event` | `Teams(453)` and `the3596people` |
| 2021 Aaruush, Chennai | `h2: India`, `h1: Aaruush, Chennai` | `Teams(125)` and `the1126people` |
| 2022 Universal Event | `h2: Anywhere in the World`, `h1: Universal Event` | `Teams(629)`; no participant count in visible text |
| 2022 Bengaluru | `h2: India`, `h1: Bengaluru` | `Teams(15)`; no participant count in visible text |

All four live GETs succeeded. The live Universal Event text confirms 3,596 participants and 453 teams for 2021; no 2022 participant total was shown, so that value remains unavailable. The dashboard now repairs display values from stored visible text without writing to the archive. A persistent cleanup/re-import is still unapplied and requires a reviewed backup-and-replacement plan plus user confirmation. Because the current importer deduplicates identical page URL/content hashes, a normal repeated import will be reported as a duplicate rather than replacing the stored malformed parse.

The diagnosis fixture before-fix reproduces the bug: an HTML list navigation item `Locations` is reduced to its own visible line; `_label_fields()` returns `{"location": "s"}` and `parse_historical_detail()` returns `locationName: "s"`, null counts, and no country/city. The fixture also mirrors the observed headings, `Teams(n)`, and joined participant phrase.

## Proposed Persistent Repair (Not Applied)

The dashboard currently reconstructs valid display rows from each import's retained `sourceText`; it does not write those reconstructions back. The source URLs and raw visible text are sufficient to reproduce the corrected names/counts. A normal re-import of the same URL and identical visible text is currently deduplicated by URL plus SHA-256 content hash, so it will not replace the malformed parsed fields.

Before any persistent cleanup, create a timestamped backup of `data/archive.json`, then build a candidate archive copy under `data_test/`. Re-fetch only the existing 2021/2022 detail URLs or reparse their retained visible text using the fixed parser; update only the corresponding import's parsed `records`, `globalEvents`, and `unverified` fields in the candidate. Preserve every import's source URL, listing URL, capture timestamps, content hash, source text, and unrelated editions. Compare candidate versus original and verify that no valid location becomes `s`, the 2021 Universal Event is 3,596/453, and 2022 participant counts remain null when absent. Review that diff and obtain confirmation before promoting the candidate. No such candidate or promotion was performed during this investigation.
