# PortfolioCheck

A web application that checks a coursework portfolio submission against the
formal submission requirements **before** it is handed in.

Formal requirements are worth 10% of the portfolio grade and are entirely
mechanical: a naming pattern, a prescribed folder structure, permitted file
formats, a size limit, a links file, and a code archive that must be identical
to the public repository. They are also easy to get wrong the night before a
deadline. PortfolioCheck reads the zip folder you are about to submit and tells
you, rule by rule, what passes and exactly what to change.

It checks form, not content. It does not assess or grade your work.

- **Live application:** _add the Render URL here after deployment_
- **Course:** Project: Software Engineering (DLMCSPSE01)
- **Version:** 1.0.0

---

## 1. Installation and running

### Option A — Docker (recommended)

Requirements: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
(includes Docker Compose).

```bash
git clone https://github.com/<user>/<repository>.git
cd <repository>
docker compose up --build
```

Open <http://localhost:8000>. Stop with `Ctrl+C`, remove with `docker compose down`.

### Option B — Python directly

Requirements: Python 3.11 or newer.

```bash
git clone https://github.com/<user>/<repository>.git
cd <repository>
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

Open <http://localhost:8000>.

### Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `8000` | Port the server listens on. Cloud hosts set this automatically. |
| `GITHUB_TOKEN` | unset | Optional. Raises GitHub's anonymous limit of 60 API requests per hour used by the repository comparison (R07). A fine-grained token with **no permissions** is enough, because only public repositories are read. |

With Docker: `GITHUB_TOKEN=... docker compose up`.

### Deploying to the cloud (Render)

The repository contains a [Render Blueprint](render.yaml).

1. Push the repository to GitHub.
2. Sign in at <https://render.com> with GitHub.
3. **New → Blueprint**, select the repository, confirm.
4. Render builds the `Dockerfile` and publishes the service at
   `https://portfoliocheck-xxxx.onrender.com`. `/health` is used as health check.
5. Optionally set `GITHUB_TOKEN` under **Environment**.

No login is required to use the application.

## 2. Using the application

1. Open the start page and choose your zip folder.
2. Select the portfolio phase (1, 2 or 3) — only the rules for that phase run.
3. Click **Check submission**.
4. Read the report: every rule shows **pass**, **warn** or **fail**, the
   provision of the brief it comes from, and for every problem exactly how to
   fix it.

Starting from nothing? **Download an empty folder structure** on the start page
gives you a correctly named skeleton to fill in.

### Try it with the sample data

[`samples/`](samples/) contains nine realistic submissions, each built to
trigger one specific result, together with the
[manual test cases](samples/README.md) that describe the input and the expected
behaviour for each.

## 3. Rules

| ID | Rule | Phases |
|----|------|--------|
| R01 | Main directory named `Surname-FirstName_MatrNo_Course` | 1, 2, 3 |
| R02 | The four required subdirectories exist and are named exactly | 1, 2, 3 |
| R03 | `04-Implementation` holds a correctly named code archive | 3 |
| R04 | A `.txt` file contains the GitHub URL and the application URL | 3 |
| R05 | Files with a `.pdf` extension really are PDFs | 1, 2, 3 |
| R06 | No file exceeds the 15 MB limit | 1, 2, 3 |
| R07 | The public GitHub repository and the code archive are identical | 3 |

The same catalogue is available as JSON at `/rules`.

**How R07 works.** It reads the repository URL from your `.txt` file, fetches
the repository's file list from the GitHub API, and compares it with the code
archive using git blob hashes — the same content fingerprint git itself uses —
so it detects missing files, extra files *and* files whose content differs,
without downloading anything. Windows line endings, the wrapper folder added by
GitHub's *Download ZIP*, and `__MACOSX`/`.git` folders are ignored.

**Adding a rule.** Write one class in `app/rules/`, decorate it with
`@register`, import its module in `app/rules/__init__.py`, and add a test.
Nothing else changes.

## 4. Tests

```bash
python -m pytest
```

| Test module | What it verifies |
|-------------|------------------|
| `tests/test_rules.py` | Every rule against a compliant submission and one violating exactly that rule; resilience when a rule crashes (NFR8); response time (NFR5) |
| `tests/test_repository.py` | R07 outcomes and the GitHub client, against an in-memory repository — no test uses the network |
| `tests/test_extraction.py` | Path traversal, absolute paths, zip bombs and entry limits are rejected (NFR1, NFR2) |
| `tests/test_web.py` | The complete upload-to-report path through HTTP |
| `tests/test_samples.py` | Every sample in `samples/` produces exactly the result documented for it |

## 5. Architecture

The source tree maps one-to-one onto the components of the architecture
documentation:

| Component | Module | Provides |
|-----------|--------|----------|
| WebInterface | `app/main.py`, `app/templates/` | HTTP endpoints, report view, rule catalogue |
| CheckService | `app/checker.py` | `ICheckService` — runs applicable rules, aggregates the report |
| RuleRegistry | `app/rules/base.py` | `IRuleCatalogue`; defines `IRule` |
| RuleSet | `app/rules/naming.py`, `structure.py`, `artifacts.py`, `integrity.py`, `repository_match.py`, `patterns.py` | The individual rules |
| DomainModel | `app/models.py` | `ISubmissionModel` — Submission, Finding, Report |
| ArchiveExtractor | `app/extraction.py` | `IExtraction` — defensive extraction |
| RepositoryClient | `app/repository.py` | `IRepositoryInventory` — GitHub file inventory |

Each module's docstring names the component it realises. Full documentation is
in [`docs/`](docs/); known shortcuts are listed in
[`docs/technical-debt.md`](docs/technical-debt.md).

## 6. Security

Uploads are treated as hostile input. Before anything is written to disk, the
archive — and the code archive nested inside it — is rejected if it contains
absolute paths or `../` traversal, more than 5,000 entries, more than 200 MB
once expanded, or any entry compressed more than 200:1. Uploaded files are
deleted before the response is returned; nothing is stored. The container runs
as an unprivileged user on a read-only filesystem.

## 7. Third-party libraries

| Library | Purpose | Licence |
|---------|---------|---------|
| [FastAPI](https://fastapi.tiangolo.com/) | HTTP routing, upload handling, validation | MIT |
| [Uvicorn](https://www.uvicorn.org/) | ASGI server | BSD-3-Clause |
| [Jinja](https://jinja.palletsprojects.com/) | Server-side templates | BSD-3-Clause |
| [python-multipart](https://github.com/Kludex/python-multipart) | Multipart upload parsing | Apache-2.0 |
| [pytest](https://docs.pytest.org/) | Test framework (development only) | MIT |
| [httpx](https://www.python-httpx.org/) | Test client transport (development only) | BSD-3-Clause |

Archive handling and the GitHub client use only the Python standard library
(`zipfile`, `hashlib`, `urllib`).
