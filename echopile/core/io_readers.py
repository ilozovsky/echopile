"""Helpers for reading uploaded files"""

from __future__ import annotations

from typing import List, Optional, Tuple, Union

import base64
import io
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from .snc_io import parse_snc_text
from .settings_defaults import SNC_UI_SETTING_KEYS

try:
    import fsspec
    from segy import SegyFile
    from segy.standards.registry import register_segy_standard
    from segy.standards.spec import REV0, REV1, REV2
except ImportError:
    fsspec = None
    SegyFile = None
    register_segy_standard = None
    REV0 = REV1 = REV2 = None


_ENCODINGS = ("utf-8", "utf-8-sig", "cp1251", "gb18030")
_PET_ENCODINGS = ("utf-16", "utf-16-le", "utf-8-sig", "cp1251")
SEGY_REVISION_GUARDS = (("REV0", REV0), ("REV1", REV1), ("REV2", REV2))

def validate_uniform_time_axis(
    time_values: np.ndarray,
    *,
    frac_tol: float = 0.02,
) -> Tuple[np.ndarray, float]:
    """Validate a strictly increasing, near-uniform time axis in its original units."""
    time_values = np.asarray(time_values, dtype=float)

    if time_values.ndim != 1 or len(time_values) < 2:
        raise ValueError("Plain text file must contain at least two time samples")

    if not np.all(np.isfinite(time_values)):
        raise ValueError("Plain text file contains invalid time values")

    dt = np.diff(time_values)
    if not np.all(dt > 0):
        raise ValueError("Plain text time axis must be strictly increasing")

    dt_ref = float(np.median(dt))
    expected = time_values[0] + np.arange(len(time_values), dtype=float) * dt_ref
    residual = np.abs(time_values - expected)
    tolerance = frac_tol * abs(dt_ref)

    if residual.max() > tolerance:
        raise ValueError("Plain text time axis must be uniformly sampled")

    normalized_time = time_values - time_values[0]
    return normalized_time, dt_ref


def decode_txt_upload(blob: bytes) -> Optional[str]:
    """Try several encodings and return the first text that looks readable."""
    for enc in _ENCODINGS:
        try:
            text = blob.decode(enc)
        except UnicodeDecodeError:
            continue

        sample = text[:5000]
        if "\x00" in sample:
            continue

        bad_controls = sum(
            1
            for ch in sample
            if ord(ch) < 32 and ch not in {"\n", "\r", "\t"}
        )
        if sample and bad_controls / len(sample) > 0.02:
            continue

        return text
    return None


def is_zbl_txt(file_data: Optional[str]) -> bool:
    """Check whether a text file looks like a ZBL export"""
    if file_data is None:
        return False

    has_sampling_length = "Sampling Length" in file_data
    has_sampling_interval = "Sampling Interval" in file_data
    has_waveform_data = "Waveform data" in file_data
    return has_sampling_length and has_sampling_interval and has_waveform_data


def decode_pet_upload(blob: bytes) -> Optional[str]:
    """Decode a Piletest PET export."""
    for enc in _PET_ENCODINGS:
        try:
            text = blob.decode(enc)
        except UnicodeDecodeError:
            continue

        if "Pile name:" in text and "Blows:" in text:
            return text
    return None


def parse_plain_columns_table(file_data: str) -> pd.DataFrame:
    """Read a simple text table with time in column 0 and signals in later columns."""
    df = pd.read_csv(io.StringIO(file_data), sep=r"[\s,;]+", engine="python", header=None)
    # Turn headers or text rows into NaN so they can be removed safely.
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna(axis=1, how="all")

    if df.shape[1] < 2:
        raise ValueError("Plain text file must contain at least time and one signal column")

    df = df[df.iloc[:, 0].notna() & df.iloc[:, 1].notna()].reset_index(drop=True)

    if len(df) < 2:
        raise ValueError("Plain text file must contain at least two numeric rows")

    return df


def parse_plain_columns(file_data: str, channel: int) -> Tuple[pd.DataFrame, List[dict], dict]:
    """Parse one selected signal from a simple multi-column text file."""
    df_raw = parse_plain_columns_table(file_data)
    signal_count = df_raw.shape[1] - 1

    if channel < 1 or channel > signal_count:
        raise ValueError(
            f"Channel {channel} is out of range for plain text file with {signal_count} signals"
        )

    time_raw, _plain_sampling = validate_uniform_time_axis(
        df_raw.iloc[:, 0].to_numpy(dtype=float)
    )
    amp_plain = -1.0 * df_raw.iloc[:, channel]

    df = pd.DataFrame({
        "time_raw": time_raw,
        "amp": amp_plain.to_numpy(dtype=float),
    })

    if signal_count > 1:
        channel_list = [
            {"label": f"Blow {i + 1}", "value": i + 1}
            for i in range(signal_count)
        ]
        channel_div_style = {"display": "block"}
    else:
        channel_list = [{"label": "1", "value": 1}]
        channel_div_style = {"display": "none"}

    return df, channel_list, channel_div_style


def parse_pet_pp_csv(file_data: str, channel: int) -> Tuple[pd.DataFrame, List[dict], dict]:
    """Parse one selected signal from a Piletest PET export."""
    lines = file_data.splitlines()

    try:
        blows_index = next(i for i, line in enumerate(lines) if line.strip() == "Blows:")
    except StopIteration as exc:
        raise ValueError("Unable to find PET signal table") from exc

    try:
        sample_rate_line = next(line for line in lines if line.strip().startswith("at "))
        sample_rate_khz = float(sample_rate_line.strip().split()[1].rstrip("KHz"))
    except (StopIteration, ValueError, IndexError) as exc:
        raise ValueError("Unable to read PET sampling rate") from exc

    table_text = "\n".join(lines[blows_index + 1:])
    df_raw = pd.read_csv(io.StringIO(table_text), sep="\t")
    df_raw = df_raw.apply(pd.to_numeric, errors="coerce").dropna(how="all").reset_index(drop=True)

    if df_raw.empty or df_raw.shape[1] < 1:
        raise ValueError("PET file does not contain readable signals")

    signal_count = df_raw.shape[1]
    if channel < 1 or channel > signal_count:
        raise ValueError(f"Channel {channel} is out of range for PET file with {signal_count} signals")

    fs_hz = sample_rate_khz * 1000.0
    dt_ms = 1000.0 / fs_hz
    amp_pet = -1.0 * df_raw.iloc[:, channel - 1].to_numpy(dtype=float)

    df = pd.DataFrame({
        "time": np.arange(len(df_raw), dtype=float) * dt_ms,
        "amp": amp_pet,
    })

    labels = [
        "Avg" if str(col).strip().lower() == "avg" else str(i)
        for i, col in enumerate(df_raw.columns, start=0)
    ]
    channel_list = [{"label": labels[i], "value": i + 1} for i in range(signal_count)]
    return df, channel_list, {"display": "block"}


def parse_zbl_sections(lines: List[str]) -> Tuple[List[List[float]], Optional[float], List[Optional[str]], Optional[int]]:
    """Split a ZBL text export into waveform blocks and collect basic metadata."""
    sampling_interval = None
    blow_times = None
    sections: List[List[float]] = []
    section_keys: List[Optional[str]] = []
    current_values: Optional[List[float]] = None
    current_key: Optional[str] = None
    pending_key: Optional[str] = None
    collecting_waveform = False

    def flush_current() -> None:
        nonlocal current_values, current_key, collecting_waveform
        if current_values:
            sections.append(current_values)
            section_keys.append(current_key)
        current_values = None
        current_key = None
        collecting_waveform = False

    for line in lines:
        stripped = line.strip()

        if "Sampling Interval" in line:
            sampling_interval = float(stripped.split()[-1]) / 1000.0
            continue

        if "Blow Times" in line:
            try:
                blow_times = int(stripped.split()[-1])
            except ValueError:
                pass
            continue

        # Numbered headers like ?1?: tell us which blow this block belongs to.
        if stripped.startswith("?") and stripped.endswith("?:"):
            flush_current()
            key = stripped[1:-2].strip()
            pending_key = key if key else None
            continue

        if stripped and set(stripped) == {"?"}:
            flush_current()
            pending_key = None
            continue

        # This line starts the actual waveform samples for one section.
        if "Waveform data" in stripped:
            flush_current()
            current_values = []
            current_key = pending_key
            pending_key = None
            collecting_waveform = True
            continue

        if not collecting_waveform:
            continue

        try:
            value = float(stripped)
        except ValueError:
            flush_current()
            continue

        if current_values is None:
            current_values = []
        current_values.append(value)

    flush_current()
    return sections, sampling_interval, section_keys, blow_times


def build_zbl_labels(section_keys: List[Optional[str]], blow_times: Optional[int] = None) -> List[str]:
    """Build simple labels for ZBL waveform blocks."""
    def base_label(key: Optional[str], position: int) -> str:
        if key is not None:
            key = str(key).strip()
            if key.isdigit():
                return str(int(key))
        return str(position)

    section_count = len(section_keys)
    processed_split = None
    if section_count >= 2 and section_count % 2 == 0:
        # Some ZBL exports contain two matching halves of signals.
        half = section_count // 2
        first_numeric = []
        second_numeric = []
        for key in section_keys[:half]:
            first_numeric.append(base_label(key, 0) if key is not None and str(key).strip().isdigit() else None)
        for key in section_keys[half:]:
            second_numeric.append(base_label(key, 0) if key is not None and str(key).strip().isdigit() else None)

        # In this app, the first matching half is treated as processed data.
        if any(key is not None for key in first_numeric) and first_numeric == second_numeric:
            if blow_times is None or section_count == 2 * blow_times:
                processed_split = half
        elif all(key is None for key in section_keys) and section_count == 2:
            processed_split = 1

    if processed_split is not None:
        base_labels = [base_label(section_keys[index], index + 1) for index in range(processed_split)]
        processed_labels = [f"{label} (processed)" for label in base_labels]
        return processed_labels + base_labels

    total_counts = {}
    for key in section_keys:
        numeric_key = None
        if key is not None:
            key = str(key).strip()
            if key.isdigit():
                numeric_key = str(int(key))
        total_counts[numeric_key] = total_counts.get(numeric_key, 0) + 1

    labels = []
    seen_counts = {}
    for index, key in enumerate(section_keys, start=1):
        numeric_key = None
        if key is not None:
            key = str(key).strip()
            if key.isdigit():
                numeric_key = str(int(key))

        seen_counts[numeric_key] = seen_counts.get(numeric_key, 0) + 1
        label = base_label(key, index)
        if numeric_key is not None and total_counts[numeric_key] > 1:
            labels.append(f"{label} ({seen_counts[numeric_key]})")
        else:
            labels.append(label)

    return labels


def parse_zbl(lines: List[str], channel: int) -> Tuple[pd.DataFrame, List[dict], dict]:
    """Parse one selected waveform from a ZBL text export."""
    sections, sampling_interval, section_keys, blow_times = parse_zbl_sections(lines)

    if not sections or sampling_interval is None:
        raise ValueError("Unable to parse ZBL waveform sections")

    if channel < 1 or channel > len(sections):
        raise ValueError(f"Channel {channel} is out of range for ZBL file with {len(sections)} blows")

    amp_zbl = np.asarray(sections[channel - 1], dtype=float)
    time_zbl = np.arange(len(amp_zbl), dtype=float) * sampling_interval

    out = pd.DataFrame({"time": time_zbl, "amp": amp_zbl})
    labels = build_zbl_labels(section_keys, blow_times)
    ch_list = [{"label": labels[i], "value": i + 1} for i in range(len(labels))]
    return out, ch_list, {"display": "block"}


def read_sgy_from_memory(decoded: bytes) -> dict:
    """Read SEG-Y bytes without writing a real temp file on disk."""
    if fsspec is None or SegyFile is None or register_segy_standard is None:
        raise ImportError("SEGY in-memory reader dependencies are unavailable")

    # Put the uploaded bytes into an in-memory filesystem so segy can open them by path.
    fs = fsspec.filesystem("memory")
    memory_path = f"uploads/{uuid.uuid4().hex}.sgy"
    memory_url = f"memory://{memory_path}"

    with fs.open(memory_path, "wb") as handle:
        handle.write(decoded)

    traces = {"time": [], "amp": []}
    last_error = None

    try:
        # Some files report revision 0.1 but still parse correctly with the REV0 schema.
        # If that fails, fall back to REV1 and REV2 before giving up.
        for _, revision_spec in SEGY_REVISION_GUARDS:
            try:
                register_segy_standard(0.1, revision_spec)
                segy_file = SegyFile(memory_url)

                for i in range(segy_file.num_traces):
                    n_samples = int(segy_file.samples_per_trace)
                    sample_interval_us = int(segy_file.sample_interval)
                    sample_interval_ms = sample_interval_us / 1000.0
                    traces["time"].append(
                        np.linspace(0.0, n_samples * sample_interval_ms, n_samples, endpoint=False)
                    )
                    traces["amp"].append(np.asarray(segy_file.trace[i]["data"], dtype=np.float64))

                return traces
            except Exception as exc:
                last_error = exc
    finally:
        try:
            fs.rm(memory_path)
        except Exception:
            pass

    raise last_error if last_error is not None else RuntimeError("Unable to parse SEG-Y data")


def parse_contents(
    contents: str,
    filename: str,
    channel: int,
) -> Tuple[Union[pd.DataFrame, List[dict]], List, dict, List, Union[dict, List[dict]]]:
    """Read one uploaded file and return signal data in the format the app expects."""
    _, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)
    suffix = Path(filename).suffix.lower()
    lower_name = filename.lower()
    settings: List = []

    if lower_name.endswith(".pp.csv"):
        text = decode_pet_upload(decoded)
        if text is None:
            raise ValueError("Unable to decode PET file")

        df, ch_list, div_style = parse_pet_pp_csv(text, channel)
        meta = {
            "assumed_input": "Acceleration",
            "default_integrations": 1,
            "time_unit": "ms",
            "time_unit_known": True,
        }
        return df, ch_list, div_style, [], meta

    if suffix == ".txt":
        text = decode_txt_upload(decoded)
        if text is None:
            raise ValueError("Unable to decode text file")

        # ZBL exports have their own block structure. Other text files fall back to plain columns.
        if is_zbl_txt(text):
            df, ch_list, div_style = parse_zbl(text.splitlines(), channel)
            label = ch_list[channel - 1]["label"] if 0 < channel <= len(ch_list) else ""
            has_processed_set = any("(processed)" in str(item.get("label", "")) for item in ch_list)
            if has_processed_set and "(processed)" in str(label):
                meta = {
                    "assumed_input": "Velocity",
                    "default_integrations": 0,
                    "time_unit": "ms",
                    "time_unit_known": True,
                }
            elif has_processed_set:
                meta = {
                    "assumed_input": "Acceleration",
                    "default_integrations": 1,
                    "time_unit": "ms",
                    "time_unit_known": True,
                }
            else:
                meta = {
                    "assumed_input": "Unknown",
                    "default_integrations": 0,
                    "time_unit": "ms",
                    "time_unit_known": True,
                }
            return df, ch_list, div_style, [], meta

        df, ch_list, div_style = parse_plain_columns(text, channel)
        meta = {
            "assumed_input": "Unknown",
            "default_integrations": 0,
            "time_unit": "s",
            "time_unit_known": False,
        }
        return df, ch_list, div_style, [], meta
    if suffix == ".sgy":
        if fsspec is None or SegyFile is None or register_segy_standard is None:
            raise ImportError("SEG-Y reader dependencies are unavailable")

        traces = read_sgy_from_memory(decoded)
        if not traces["time"]:
            raise RuntimeError("SEG-Y file does not contain readable traces")

        if channel < 1 or channel > len(traces["time"]):
            raise ValueError(
                f"Channel {channel} is out of range for SEG-Y file with {len(traces['time'])} traces"
            )

        idx = channel - 1
        df = pd.DataFrame({"time": traces["time"][idx], "amp": traces["amp"][idx]})
        ch_list = [
            {"label": f"Trace {i + 1}", "value": i + 1}
            for i in range(len(traces["time"]))
        ]
        meta = {
            "assumed_input": "Velocity",
            "default_integrations": 0,
            "time_unit": "ms",
            "time_unit_known": True,
        }
        return df, ch_list, {"display": "block"}, [], meta

    if suffix == ".snc":
        text = decode_txt_upload(decoded)
        if text is None:
            raise ValueError("Unable to decode SNC file")
        out_list, names, settings, meta_list = parse_snc_text(text)
        return out_list, names, {"display": "block"}, settings, meta_list

    return pd.DataFrame(), [], {"display": "none"}, [], {}




