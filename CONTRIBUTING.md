# Contributing

Thanks for looking at Unfaded. Bug reports with a sample scan, a screenshot of the change view and the command you ran are the most useful thing you can send.

## Setup

```bash
git clone https://github.com/Arthur031221/Unfaded
cd Unfaded
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

The model weights are not needed for the default test run. To run the tests that use them, fetch them once with `unfaded models --fetch` and add `-m models`.

## Checks

```bash
ruff check .
ruff format --check .
pytest                      # unit tests, no weights, no GPU
pytest -m models            # end to end tests with the real weights
pytest -m browser           # Playwright test of the demo page (needs Chrome or `playwright install chromium`)
python -m build             # sdist and wheel
```

CI runs the first four on every push and pull request. The `models` job is not part of CI because the weights are about 1.3 GB.

## Code style

- Python 3.10 or newer, type hints on public functions, line length 120, `ruff format`.
- Keep a step self contained. A step takes an RGB `uint8` array and returns a `StepResult` that says what it changed, with the model name and the time it took.
- Anything a model invents must be reported through `StepResult.invented` so the web interface can label it.
- The original file is never modified. Output goes next to it or to `--out`, with an XMP sidecar.

## Adding a language

Copy `src/unfaded/web/locales/en.json` to `<code>.json`, translate the values, then add the code to `LANGUAGES` in `src/unfaded/web/i18n.js`. A test checks that every locale has exactly the keys of `en.json`.

## Adding a model

Add a `ModelSpec` to `src/unfaded/models.py` with a pinned sha256 and license, add the license text under `src/unfaded/vendor` if you vendor code, and list it in `THIRD_PARTY_NOTICES.md`. Weights are loaded with `weights_only=True`, except TorchScript files, which are trusted only through the pinned sha256.

## Commit messages

Short imperative subject line, for example `Fix crop when the print touches the scanner edge`.
