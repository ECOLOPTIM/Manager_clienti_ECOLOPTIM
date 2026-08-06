"""Tests for shared reporting/export helpers in utils.utils_documents."""

import re
import sys
import types

# ---------------------------------------------------------------------------
# Minimal stub for streamlit so that utils_documents can be imported without
# a running Streamlit server.
# ---------------------------------------------------------------------------
_st_stub = types.ModuleType("streamlit")
_st_stub.error = lambda *a, **k: None
sys.modules.setdefault("streamlit", _st_stub)

# Stub for pandas used inside fmt_date
import importlib
import pandas as pd  # real pandas is available in the project

from utils.utils_documents import (
    fmt_date,
    fmt_currency,
    make_export_filename,
    safe_filename_part,
    safe_str,
)


# ---------------------------------------------------------------------------
# safe_str
# ---------------------------------------------------------------------------

def test_safe_str_none():
    assert safe_str(None) == ""


def test_safe_str_value():
    assert safe_str(42) == "42"
    assert safe_str("abc") == "abc"


# ---------------------------------------------------------------------------
# safe_filename_part
# ---------------------------------------------------------------------------

def test_safe_filename_part_basic():
    assert safe_filename_part("Ion Popescu") == "Ion_Popescu"


def test_safe_filename_part_special_chars():
    result = safe_filename_part("Client: #1 (Test)")
    # Colons, hash and parens should be removed
    assert ":" not in result
    assert "#" not in result
    assert "(" not in result


def test_safe_filename_part_truncate():
    long_name = "A" * 100
    result = safe_filename_part(long_name, max_len=20)
    assert len(result) <= 20


def test_safe_filename_part_empty():
    result = safe_filename_part("")
    assert result == "client"


# ---------------------------------------------------------------------------
# fmt_date
# ---------------------------------------------------------------------------

def test_fmt_date_none():
    assert fmt_date(None) == ""


def test_fmt_date_string():
    result = fmt_date("2024-03-15")
    assert result == "2024-03-15"


def test_fmt_date_custom_format():
    result = fmt_date("2024-03-15", fmt="%d.%m.%Y")
    assert result == "15.03.2024"


def test_fmt_date_pandas_nat():
    result = fmt_date(pd.NaT)
    assert result == ""


def test_fmt_date_pandas_timestamp():
    ts = pd.Timestamp("2024-06-01")
    result = fmt_date(ts)
    assert result == "2024-06-01"


# ---------------------------------------------------------------------------
# fmt_currency
# ---------------------------------------------------------------------------

def test_fmt_currency_none():
    assert fmt_currency(None) == ""


def test_fmt_currency_zero():
    assert fmt_currency(0) == "0.00 RON"


def test_fmt_currency_positive():
    result = fmt_currency(1234.5)
    assert "1,234.50" in result
    assert "RON" in result


def test_fmt_currency_no_suffix():
    result = fmt_currency(500.0, suffix="")
    assert result == "500.00"


def test_fmt_currency_invalid():
    # Non-numeric should be returned as-is string
    result = fmt_currency("N/A")
    assert result == "N/A"


# ---------------------------------------------------------------------------
# make_export_filename
# ---------------------------------------------------------------------------

_TIMESTAMP_RE = re.compile(r"\d{8}_\d{6}")


def test_make_export_filename_basic():
    name = make_export_filename("Raport_lucrari", ext="xlsx")
    assert name.endswith(".xlsx")
    assert "Raport_lucrari" in name
    assert _TIMESTAMP_RE.search(name)


def test_make_export_filename_with_client():
    name = make_export_filename("facturi", client_name="Ion Popescu", ext="xlsx")
    assert "facturi" in name
    assert "Ion_Popescu" in name
    assert name.endswith(".xlsx")


def test_make_export_filename_no_timestamp():
    name = make_export_filename("backup", ext="csv", with_timestamp=False)
    assert name == "backup.csv"
    assert not _TIMESTAMP_RE.search(name)


def test_make_export_filename_ext_without_dot():
    name = make_export_filename("test", ext="csv")
    assert name.endswith(".csv")
    # No double dots
    assert ".." not in name


def test_make_export_filename_special_chars_in_client():
    name = make_export_filename("export", client_name="Firma: SRL #1", ext="xlsx")
    assert ":" not in name
    assert "#" not in name
    assert name.endswith(".xlsx")
