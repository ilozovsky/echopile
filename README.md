# echopile

[![PyPI version](https://img.shields.io/pypi/v/echopile)](https://pypi.org/project/echopile/)
[![Python versions](https://img.shields.io/pypi/pyversions/echopile)](https://pypi.org/project/echopile/)

`echopile` is a Python application for low-strain impact pile integrity signal review and interpretation for deep foundations. It is built for practical work with reflection-based test records, pile length estimation, anomaly review, and comparison of traces from multiple input formats. Its main advanced capability is superlet time-frequency analysis, which helps inspect reflections and likely anomalies with higher time-frequency resolution than standard spectral views alone.

Links: [PyPI](https://pypi.org/project/echopile/) | [GitHub repository](https://github.com/ilozovsky/echopile) | [Release v0.95.0](https://github.com/ilozovsky/echopile/releases/tag/v0.95.0) | [GitHub Discussions](https://github.com/ilozovsky/echopile/discussions)

Documentation is under construction. Questions are welcome in GitHub Discussions, and direct help is available at `i.n.lozovsky@gmail.com`.

![echopile main analysis view](docs/readme-main-analysis.png)

## Features

- Superlet-based time-frequency analysis for detailed inspection of reflections and likely anomalies in pile integrity signals.
- Import of common pile integrity test data formats, including SNC, PET `.pp.CSV`, ZBL text exports, plain text signals, and optional SEG-Y.
- Review of signals in time and pile-length domains using wave speed conversion and reference markers.
- Practical preprocessing controls, including integration, zero shift, amplification, detrending, downsampling, and Butterworth filtering.
- Standard spectral views together with superlet-derived 1D curves to support interpretation.
- Comparative review of multiple loaded traces and their averaged response.

## Installation

`echopile` requires Python 3.10 or newer.

Install from PyPI:

```bash
pip install echopile
```

Install with optional SEG-Y support:

```bash
pip install "echopile[segy]"
```

Install from source for local development:

```bash
pip install .
```

## Quick Start

Run the application:

```bash
echopile
```

Alternative entry point:

```bash
python -m echopile
```

The app starts on `http://127.0.0.1:8050` by default.

Suggested first run:

1. Start `echopile`.
2. Load the SNC example from [`Vel (Z_component) (big probe)_F_2000.snc`](https://github.com/ilozovsky/echopile/blob/main/examples/Vel%20(Z_component)%20(big%20probe)_F_2000.snc).
3. Review the trace in the main signal view, then inspect the superlet panel and filter settings.
4. Compare with the PET, ZBL, plain text, or SEG-Y examples as needed.

## Supported Inputs And Example Files

The curated example set is kept in [`examples/`](https://github.com/ilozovsky/echopile/tree/main/examples):

- [`Vel (Z_component) (big probe)_F_2000.snc`](https://github.com/ilozovsky/echopile/blob/main/examples/Vel%20(Z_component)%20(big%20probe)_F_2000.snc) - SNC example for the main workflow and current regression fixture.
- [`A_9_kazachya.pp.CSV`](https://github.com/ilozovsky/echopile/blob/main/examples/A_9_kazachya.pp.CSV) - PET export example.
- [`ZBL1.txt`](https://github.com/ilozovsky/echopile/blob/main/examples/ZBL1.txt) - ZBL text export example.
- [`signal.txt`](https://github.com/ilozovsky/echopile/blob/main/examples/signal.txt) - plain text two-column signal example.
- [`0305_no-arm.sgy`](https://github.com/ilozovsky/echopile/blob/main/examples/0305_no-arm.sgy) - SEG-Y example for installations that include the optional `segy` extra.

## Superlet Analysis

Superlet analysis is the main advanced analysis feature in `echopile`. It provides high-resolution time-frequency inspection of pile integrity signals and is intended to support interpretation of reflections, pile length response, and likely anomalies that may be harder to separate in the raw trace or a conventional spectrum alone.

The application includes fixed and adaptive superlet modes, configurable frequency limits, and optional 1D SLT-derived curves for practical interpretation alongside the main signal plot.

Reference:

Moca, V. V., Buzsaki, G., and Draguhn, A. (2021). Superlets: time-frequency super-resolution using wavelet sets. *Nature Communications*, 12, 337. https://doi.org/10.1038/s41467-020-20539-9

## Support

- Documentation is still under construction.
- Questions about usage, workflow, or interpretation should go to [GitHub Discussions](https://github.com/ilozovsky/echopile/discussions).
- Reproducible bugs and feature requests should go to [GitHub Issues](https://github.com/ilozovsky/echopile/issues).
- Direct contact: `i.n.lozovsky@gmail.com`

## Developer Notes

Run the regression suite from the project root:

```bash
python -m unittest discover -s tests
```

Build wheel and source distribution:

```bash
python -m build
```
