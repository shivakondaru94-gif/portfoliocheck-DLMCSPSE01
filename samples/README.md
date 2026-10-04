# Sample submissions and manual test cases

These archives are realistic portfolio submissions for a fictional student
project, *RoomSpot*, a study-room booking system. They use the example name
from the assignment brief (`Mustermann-Max_12345678_PSE`). Each archive differs
from the compliant one in exactly one respect, so each test case exercises
exactly one rule.

Regenerate them at any time with `python samples/build_samples.py`; the output
is byte-identical on every run. The expected results below are also executed
automatically by `tests/test_samples.py`, so this table cannot drift away from
the behaviour of the application.

## How to run a manual test case

1. Start the application (`docker compose up`, or see the main README) and
   open <http://localhost:8000>, or open the deployed instance.
2. Under **Your zip folder**, choose the input file named in the table.
3. Under **Portfolio phase**, select the phase named in the table.
4. Click **Check submission**.
5. Compare the headline and the listed rule verdicts with the expected result.

## Test cases

| ID | Input file | Phase | Expected headline | Expected rule verdicts | Expected message contains |
|----|------------|-------|-------------------|------------------------|---------------------------|
| M01 | `M01-phase1-compliant.zip` | 1 | Ready to submit | R01, R02, R05, R06 **pass** | `follows the required pattern` |
| M02 | `M02-phase1-main-directory-underscore.zip` — main folder `Mustermann_Max_12345678_PSE` (underscore instead of hyphen) | 1 | Not ready to submit | R01 **fail**; R02, R05, R06 pass | `does not follow the required pattern` |
| M03 | `M03-phase1-near-miss-folder.zip` — folder `02_requirements` instead of `02-Requirements` | 1 | Not ready to submit | R02 **fail**; R01, R05, R06 pass | `A folder named '02_requirements' exists` |
| M04 | `M04-phase1-short-matriculation.zip` — matriculation number `123456` (6 digits) | 1 | Almost there | R01 **warn**; R02, R05, R06 pass | `is not 8 digits long` |
| M05 | `M05-phase2-renamed-docx.zip` — `architecture.pdf` is a Word document renamed to `.pdf` | 2 | Not ready to submit | R05 **fail**; R01, R02, R06 pass | `has a .pdf extension but is not a PDF file` |
| M06 | `M06-phase3-wrong-code-archive-name.zip` — code archive named `code.zip` | 3 | Not ready to submit | R03 **fail**; R01, R02, R04, R05, R06 pass | `No correctly named code archive` |
| M07 | `M07-phase3-missing-application-link.zip` — `links.txt` holds only the GitHub URL | 3 | Not ready to submit* | R04 **warn**; R01, R02, R03, R05, R06 pass | `contains no second URL for the deployed application` |
| M08 | `M08-unsafe-path-traversal.zip` — contains the entry `../outside-the-upload-folder.txt` | any | Error page, HTTP 400 | no rule runs; nothing is extracted | `The archive was rejected: Unsafe path in archive` |
| M09 | `M09-not-a-zip.zip` — a text file renamed to `.zip` | any | Error page, HTTP 400 | no rule runs | `That file is not a valid ZIP archive` |

\* For M06 and M07 the headline also depends on R07, see below.

### R07 in the phase-3 samples

The samples link to `https://github.com/maxmustermann/pse_myproject`, the example
URL from the brief. That repository is not the one the sample code archive was
built from, so R07 is expected to report **fail** (repository not public, or
contents not identical) — or **warn** if GitHub cannot be reached from the
machine running the check. R07 is verified properly by the two cases below,
which use a real repository.

## Manual test cases for R07 (repository comparison)

These need your own public repository and network access.

| ID | Input | Phase | Expected result |
|----|-------|-------|-----------------|
| M10 | Your final submission folder, zipped, with the code archive created from the current state of the repository and `links.txt` naming that repository | 3 | R07 **pass**: `All N files in the code archive are identical to <user>/<repo>` |
| M11 | As M10, but after zipping, edit one line of `app/main.py` in the repository and push | 3 | R07 **fail**: message names `app/main.py` under `with different content` |
| M12 | As M10, with the repository visibility switched to Private | 3 | R07 **fail**: `does not exist or is not public` |
| M13 | As M10, run on a machine with networking disabled | 3 | R07 **warn**: `GitHub could not be reached`; all other rules still evaluated |
