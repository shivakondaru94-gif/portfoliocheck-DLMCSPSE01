# Technical debt

Technical debt here means shortcuts in the implementation that allowed faster
delivery at the cost of internal quality. It is not a list of missing features:
every functional requirement FR1–FR13 is implemented. Each item states the
shortcut, why it was taken, what it costs, and how it would be repaid.

## Open debt

| ID | Shortcut | Why it was taken | Consequence | Repayment | Effort |
|----|----------|------------------|-------------|-----------|--------|
| TD1 | The rule registry is a module-level global list filled as a side effect of importing the rule modules (`app/rules/base.py`, `app/rules/__init__.py`). | A decorator is the fastest way to make a new rule known without editing a central list. | A rule module that is not imported in `rules/__init__.py` is silently inactive. Tests cannot build an isolated registry and must patch the shared rule instances instead (see `tests/conftest.py`). | Construct an explicit `RuleRegistry` object at start-up and inject it into the check service and the web layer. | ~0.5 day |
| TD2 | Operating limits are hard-coded module constants: upload size, expanded size, entry count and compression ratio (`extraction.py`, `main.py`), the 15 MB file limit (`rules/integrity.py`) and the GitHub timeout (`repository.py`). | Constants were quicker than designing a configuration mechanism. | Adjusting any limit means a code change and a redeployment; the limits are scattered over four modules. | One settings object read from environment variables at start-up, passed to the components that need it. | ~0.5 day |
| TD3 | GitHub API responses are not cached. Each phase-3 check makes two API requests. | Caching needs an invalidation policy, which was out of proportion for the first release. | Anonymous access allows 60 requests per hour per IP address, so a shared deployment without `GITHUB_TOKEN` can serve only about 30 phase-3 checks an hour before R07 degrades to a warning. | A short-lived cache keyed by owner, repository and commit; or make the token mandatory in production. | ~0.5 day |
| TD4 | The PDF integrity rule (R05) reads only the first five bytes of a file (`%PDF-`). | A header check catches the common failure — a renamed Word file — at almost no cost and with no new dependency. | A truncated or corrupted PDF that still starts with a valid header passes R05, although the examiner could not open it. | Parse each PDF with a PDF library and fail if the document structure cannot be read. | ~0.5 day |
| TD5 | R07 re-implements the search for the GitHub link and for the code archive instead of reusing the logic of R04 and R03 (`rules/repository_match.py`). | Rules are independent by design; copying two small loops was faster than introducing a shared lookup. | The three rules could come to disagree about which link or which archive is "the" one if one copy is changed and the others are not. | Move the two lookups into shared functions used by R03, R04 and R07. | ~2 hours |
| TD6 | Interface tests recognise outcomes by searching the rendered HTML for text and CSS class names (`tests/test_web.py`, `tests/test_samples.py`). | The HTML page was the only representation of a report, so asserting on it was the quickest route to end-to-end coverage. | A purely visual change to the templates can break tests although the behaviour is unchanged. | Offer the report as JSON as well, and point the end-to-end tests at that representation. | ~0.5 day |
| TD7 | User-facing messages and corrective actions are English strings embedded in the rule classes. | Writing each message next to the check that produces it was fastest while the rules were being developed. | Wording cannot be reviewed or changed without editing rule logic, and a German version (the brief exists in German too) would mean touching every rule. | Move the texts into a message catalogue keyed by rule and outcome. | ~1 day |

## Debt repaid during the development phase

| Shortcut | Repayment |
|----------|-----------|
| The name/matriculation/course pattern and the GitHub URL pattern were duplicated between `naming.py` and `artifacts.py`. | Moved into `app/rules/patterns.py` and shared by all rules. |
| The upload endpoint is asynchronous but performed blocking extraction and rule evaluation directly, stalling every other request while one check ran — which would have become serious once R07 added network calls. | Extraction and evaluation now run in a worker thread (`run_in_threadpool` in `app/main.py`). |
| The rule engine's error path, which keeps a report alive when one rule fails (NFR8), was excluded from test coverage. | Covered by `test_failing_rule_does_not_stop_the_others`. |
