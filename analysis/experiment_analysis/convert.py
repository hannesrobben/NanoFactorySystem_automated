##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Conversion of HDF5 objects into files that a Windows PC opens without extra software.

Rules (one HDF5 dataset gives one file or one folder):

=====================================  ===========================================
Dataset                                File
=====================================  ===========================================
text (scalar or list)                  ``<name>.txt``
bytes with attribute ``format``        ``<name>.<format>`` (``.png``, ``.zdc``, …)
compound table                         ``<name>.csv`` with a header row
scalar number                          ``<name>.txt``
1-D numbers                            ``<name>.csv`` (one column)
2-D ``uint8``/``uint16``/bool          ``<name>.png`` (8 or 16 bit, lossless)
2-D other numbers                      ``<name>.csv``; large ones also ``<name>_preview.png``
3-D stack                              folder ``<name>/`` with one file per slice
anything else                          ``<name>.npy`` (NumPy) and a note in the README
=====================================  ===========================================

Attributes of a group go into ``attributes.json`` in its folder, attributes
of a dataset into ``<name>.attributes.json``. Attributes named ``<x>_json``
hold JSON text; they are decoded and written as ``<x>``.
"""
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import h5py
import numpy as np

# Two CSV styles: German Excel expects ";" and a decimal comma, everything else "," and a point.
CSV_STYLES = {"de": (";", ","), "en": (",", ".")}
PREVIEW_MIN_SIZE = 32
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class ConvertOptions:
    """ Options of the conversion.

    Parameters
    ----------
    csv_style : {"de", "en"}
        ``"de"``: separator ``;`` and decimal comma (German Excel opens it by
        double click); ``"en"``: separator ``,`` and decimal point.
    previews : bool
        Write an 8-bit ``_preview.png`` next to large 2-D float arrays.
    """

    csv_style: str = "de"
    previews: bool = True

    def __post_init__(self):
        if self.csv_style not in CSV_STYLES:
            raise ValueError(f"csv_style must be one of {sorted(CSV_STYLES)}, not {self.csv_style!r}")

    @property
    def separator(self) -> str:
        return CSV_STYLES[self.csv_style][0]

    @property
    def decimal(self) -> str:
        return CSV_STYLES[self.csv_style][1]


def safe_name(name: str) -> str:
    """ Return an HDF5 object name that is a valid Windows file name.

    Parameters
    ----------
    name : str
        Name of an HDF5 group or dataset.

    Returns
    -------
    str
        The name with the characters ``<>:"/\\|?*`` and control characters
        replaced by ``_``.
    """

    cleaned = _INVALID.sub("_", name).rstrip(". ")
    return cleaned or "_"


def plain(value: Any) -> Any:
    """ Convert NumPy values, bytes and NaN into JSON-compatible Python values.

    Parameters
    ----------
    value : Any
        Attribute value or nested structure.

    Returns
    -------
    Any
        ``None`` for NaN and infinity, lists for arrays, str for bytes.
    """

    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def attributes(obj: h5py.HLObject) -> dict:
    """ Return the attributes of an HDF5 object as JSON-compatible dict.

    Attributes named ``<x>_json`` are decoded and returned as ``<x>``; text
    that is not valid JSON is kept under the original name.

    Parameters
    ----------
    obj : h5py.Group or h5py.Dataset

    Returns
    -------
    dict
    """

    values = {}
    for name in obj.attrs:
        try:
            value = plain(obj.attrs[name])
        except (OSError, TypeError):  # attribute types h5py cannot read
            value = "<unreadable attribute>"
        if name.endswith("_json") and isinstance(value, str):
            try:
                values[name[:-5]] = json.loads(value)
                continue
            except ValueError:
                pass
        values[name] = value
    return values


def write_json(path: Path, data: Any) -> Path:
    """ Write JSON with indentation (UTF-8) and return the path. """

    path.write_text(json.dumps(plain(data), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _number(value, decimal: str) -> str:
    if isinstance(value, (bool, np.bool_)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(value):
            return "" if math.isnan(value) else ("inf" if value > 0 else "-inf")
        text = repr(float(value))
        return text.replace(".", decimal) if decimal != "." else text
    if isinstance(value, (bytes, np.bytes_)):
        value = value.decode("utf-8", errors="replace")
    return str(value)


def _cell(value, options: ConvertOptions) -> str:
    text = _number(value, options.decimal)
    if isinstance(value, (str, bytes, np.str_, np.bytes_)) and (
            options.separator in text or '"' in text or "\n" in text):
        text = '"' + text.replace('"', '""') + '"'
    return text


def write_csv(path: Path, rows, header=None, options: ConvertOptions = ConvertOptions()) -> Path:
    """ Write a table as CSV in the chosen style.

    Parameters
    ----------
    path : Path
        Target file.
    rows : iterable of sequences
        Table rows.
    header : sequence of str, optional
        Column names.
    options : ConvertOptions

    Returns
    -------
    Path
    """

    lines = []
    if header is not None:
        lines.append(options.separator.join(_cell(str(h), options) for h in header))
    for row in rows:
        lines.append(options.separator.join(_cell(v, options) for v in row))
    # utf-8-sig: Excel recognises the encoding by the byte order mark (µ in units, umlauts)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return path


def write_records_csv(path: Path, records: list[dict], options: ConvertOptions = ConvertOptions()) -> Path:
    """ Write a list of dicts as CSV; lists and dicts in a cell are written as JSON.

    Parameters
    ----------
    path : Path
    records : list of dict
        One dict per row; the columns are the union of all keys in order of
        appearance.
    options : ConvertOptions

    Returns
    -------
    Path
    """

    header = []
    for record in records:
        header.extend(k for k in record if k not in header)
    rows = []
    for record in records:
        row = []
        for key in header:
            value = plain(record.get(key, ""))
            row.append("" if value is None else json.dumps(value) if isinstance(value, (list, dict)) else value)
        rows.append(row)
    return write_csv(path, rows, header, options)


def write_png(path: Path, image: np.ndarray) -> Path:
    """ Write a 2-D ``uint8``, ``uint16`` or bool array as lossless PNG. """

    from PIL import Image

    image = np.asarray(image)
    if image.dtype == bool:
        image = image.astype(np.uint8) * 255
    if image.dtype == np.uint16:
        Image.fromarray(np.ascontiguousarray(image)).save(path)
    else:
        Image.fromarray(np.ascontiguousarray(image.astype(np.uint8)), mode="L").save(path)
    return path


def preview(data: np.ndarray) -> np.ndarray:
    """ Scale a 2-D array linearly between its finite minimum and maximum to ``uint8``.

    Non-finite values become 0.
    """

    data = np.asarray(data, dtype=float)
    finite = np.isfinite(data)
    if not finite.any():
        return np.zeros(data.shape, dtype=np.uint8)
    low, high = float(data[finite].min()), float(data[finite].max())
    scaled = np.zeros(data.shape) if high == low else (data - low) / (high - low)
    scaled[~finite] = 0.0
    return np.round(np.clip(scaled, 0.0, 1.0) * 255).astype(np.uint8)


def _is_image(data: np.ndarray) -> bool:
    return data.ndim == 2 and (data.dtype in (np.uint8, np.uint16) or data.dtype == bool)


def _write_array(folder: Path, name: str, data: np.ndarray, options: ConvertOptions,
                 header=None) -> list[Path]:
    """ Write one numeric array; returns the written files. """

    if data.ndim == 0:
        path = folder / f"{name}.txt"
        path.write_text(_number(data.item(), options.decimal) + "\n", encoding="utf-8")
        return [path]
    if data.ndim == 1:
        return [write_csv(folder / f"{name}.csv", ([v] for v in data.tolist()), header, options)]
    if _is_image(data):
        return [write_png(folder / f"{name}.png", data)]
    if data.ndim == 2:
        files = [write_csv(folder / f"{name}.csv", data.tolist(), header, options)]
        if (options.previews and data.dtype.kind in "fiu" and min(data.shape) >= PREVIEW_MIN_SIZE):
            files.append(write_png(folder / f"{name}_preview.png", preview(data)))
        return files
    if data.ndim == 3:
        stack = folder / name
        stack.mkdir(exist_ok=True)
        files = []
        digits = max(3, len(str(len(data) - 1)))
        for i, layer in enumerate(data):
            files.extend(_write_array(stack, f"{name}_{i:0{digits}d}", layer, options))
        return files
    path = folder / f"{name}.npy"
    np.save(path, data)
    return [path]


def write_dataset(dataset: h5py.Dataset, folder: Path, options: ConvertOptions = ConvertOptions()) -> list[Path]:
    """ Write one HDF5 dataset as file(s) into ``folder``.

    Parameters
    ----------
    dataset : h5py.Dataset
        Dataset to convert (see the module docstring for the rules).
    folder : Path
        Existing target folder.
    options : ConvertOptions

    Returns
    -------
    list of Path
        All files written, including ``<name>.attributes.json``.
    """

    name = safe_name(dataset.name.rsplit("/", 1)[-1])
    attrs = attributes(dataset)
    files: list[Path] = []
    fmt = attrs.get("format")
    data = dataset[()]
    if h5py.check_string_dtype(dataset.dtype) is not None or dataset.dtype.kind in "OSU":
        lines = [data] if np.ndim(data) == 0 else list(np.ravel(data))
        text = "\n".join(plain(v) if isinstance(v, (bytes, np.bytes_)) else str(v) for v in lines)
        path = folder / f"{name}.txt"
        path.write_text(text, encoding="utf-8")
        files.append(path)
    elif isinstance(fmt, str) and dataset.dtype == np.uint8 and dataset.ndim == 1:
        suffix = "." + fmt.lower().lstrip(".")
        path = folder / (name if name.lower().endswith(suffix) else name + suffix)
        path.write_bytes(np.asarray(data).tobytes())
        files.append(path)
    elif dataset.dtype.names is not None:
        header = list(dataset.dtype.names)
        rows = [[row[n] for n in header] for row in np.atleast_1d(data)]
        files.append(write_csv(folder / f"{name}.csv", rows, header, options))
    else:
        data = np.asarray(data)
        columns = attrs.get("columns")
        header = [c.strip() for c in columns.split(",")] if isinstance(columns, str) else None
        if header is not None and not (data.ndim == 2 and data.shape[1] == len(header) or
                                       data.ndim == 1 and len(header) == 1):
            header = None
        files.extend(_write_array(folder, name, data, options, header))
    if attrs:
        files.append(write_json(folder / f"{name}.attributes.json", attrs))
    return files


def write_tree(group: h5py.Group, folder: Path, options: ConvertOptions = ConvertOptions()) -> list[Path]:
    """ Mirror an HDF5 group and everything below it into ``folder``.

    Parameters
    ----------
    group : h5py.Group
        Group (or open file) to convert.
    folder : Path
        Target folder; created if needed.
    options : ConvertOptions

    Returns
    -------
    list of Path
        All files written.
    """

    folder.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    attrs = attributes(group)
    if attrs:
        files.append(write_json(folder / "attributes.json", attrs))
    for key in group:
        obj = group.get(key)
        if obj is None:  # dangling soft or external link
            continue
        if isinstance(obj, h5py.Group):
            files.extend(write_tree(obj, folder / safe_name(key), options))
        else:
            files.extend(write_dataset(obj, folder, options))
    return files
