# echopile

`echopile` is a Dash application for pile integrity signal loading, processing, and visual analysis.

First public release: [v0.95.0](https://github.com/ilozovsky/echopile/releases/tag/v0.95.0)

Documentation is still under construction. If you need help using `echopile`, feel free to open a GitHub Discussion or contact the author.

## Requirements

- Python 3.10 or newer

## Install

Install from the repository:

```bash
pip install .
```

Install with SEG-Y support:

```bash
pip install .[segy]
```

Install from the first public release artifact:

```bash
pip install https://github.com/ilozovsky/echopile/releases/download/v0.95.0/echopile-0.95.0-py3-none-any.whl
```

## Run

From an installed package:

```bash
echopile
```

Or directly from source:

```bash
python -m echopile
```

The app starts on `http://127.0.0.1:8050` by default.

## Examples

The curated public example set is under [`examples/`](examples/):

- [`Vel (Z_component) (big probe)_F_2000.snc`](examples/Vel%20(Z_component)%20(big%20probe)_F_2000.snc) for SNC workflow validation
- [`A_9_kazachya.pp.CSV`](examples/A_9_kazachya.pp.CSV) for PET CSV import
- [`ZBL1.txt`](examples/ZBL1.txt) for ZBL text import
- [`signal.txt`](examples/signal.txt) for plain text signal loading
- [`0305_no-arm.sgy`](examples/0305_no-arm.sgy) for SEG-Y loading when installed with `.[segy]`

## Tests

Run the current regression suite from the project root:

```bash
python -m unittest discover -s tests
```

## Release checklist

- Build source and wheel artifacts:

```bash
python -m build
```

- Smoke test the installed wheel:

```bash
pip install dist/*.whl
echopile --host 127.0.0.1 --port 8050
```
