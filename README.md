# echopile

`echopile` is a Dash application for pile integrity signal loading, processing, and visual analysis.

## Requirements

- Python 3.10 or newer

## Install

Core install:

```bash
pip install .
```

Install with SEG-Y support:

```bash
pip install .[segy]
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

## Example workflow

1. Launch the app.
2. Load one of the files from [`examples/`](examples/).
3. Start with [`Vel (Z_component) (big probe)_F_2000.snc`](examples/Vel%20(Z_component)%20(big%20probe)_F_2000.snc) to verify the full SNC workflow.
4. Use [`A_9_kazachya.pp.CSV`](examples/A_9_kazachya.pp.CSV) for PET import and [`ZBL1.txt`](examples/ZBL1.txt) for ZBL text import.
5. If SEG-Y support is installed, load [`0305_no-arm.sgy`](examples/0305_no-arm.sgy).

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
