import io
import os
import sys
import tempfile
import streamlit as st

try:
    from docxtpl import DocxTemplate
except Exception:
    DocxTemplate = None

try:
    import pythoncom
    import win32com.client
except Exception:
    pythoncom = None
    win32com = None


def safe_str(x) -> str:
    if x is None:
        return ""
    return str(x)


def safe_filename_part(s: str, max_len: int = 60) -> str:
    s = safe_str(s)
    s = "".join(ch for ch in s if ch.isalnum() or ch in (" ", "_", "-", "."))
    s = s.strip().replace(" ", "_")
    return (s[:max_len] or "client")


def split_team(s: str) -> list[str]:
    s = safe_str(s).strip()
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def join_team(items: list[str]) -> str:
    return ", ".join([str(x).strip() for x in (items or []) if str(x).strip()])


def atasament_exists(db, client_id: int, filename: str, lucrare_id: int | None = None, sarcina_id: int | None = None) -> bool:
    try:
        df_att = db.lista_atasamente(int(client_id), lucrare_id=lucrare_id, sarcina_id=sarcina_id)
        if df_att is None or df_att.empty:
            return False
        if "filename" not in df_att.columns:
            return False
        return (df_att["filename"] == filename).any()
    except Exception:
        return False


def require_docxtpl() -> bool:
    if DocxTemplate is None:
        st.error("Lipsește pachetul 'docxtpl'. Instalează cu: pip install docxtpl")
        return False
    return True


def require_word_pdf() -> bool:
    if sys.platform != "win32":
        st.error("Generarea PDF prin Word merge doar pe Windows (COM automation).")
        return False
    if pythoncom is None or win32com is None:
        st.error("Lipsește pachetul 'pywin32' pentru PDF. Instalează cu: pip install pywin32")
        return False
    return True


def render_docx(template_path: str, context: dict) -> bytes:
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Nu găsesc template-ul: {template_path}")

    doc = DocxTemplate(template_path)
    try:
        doc.render(context)
    except Exception as e:
        st.error(
            "Eroare în template-ul DOCX. "
            "Cel mai des este din cauza unor variabile {{ ... }} rupte sau scrise greșit în Word.\n\n"
            "Recomandare: șterge și rescrie variabilele problematice direct în Word, "
            "dintr-o singură bucată (Paste → Keep Text Only), fără bold/italic în interiorul {{ }}.\n\n"
            f"Detalii tehnice: {type(e).__name__}: {e}"
        )
        raise

    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


def docx_bytes_to_pdf_bytes_via_word(docx_bytes: bytes, base_name: str = "document") -> bytes:
    if not require_word_pdf():
        raise RuntimeError("PDF conversion not available.")

    tmp_dir = tempfile.mkdtemp(prefix="doc_pdf_")
    docx_path = os.path.join(tmp_dir, f"{base_name}.docx")
    pdf_path = os.path.join(tmp_dir, f"{base_name}.pdf")

    with open(docx_path, "wb") as f:
        f.write(docx_bytes)

    pythoncom.CoInitialize()
    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0

        doc = word.Documents.Open(docx_path, ReadOnly=True)
        doc.ExportAsFixedFormat(
            OutputFileName=pdf_path,
            ExportFormat=17,
            OpenAfterExport=False,
            OptimizeFor=0,
            CreateBookmarks=1,
        )

        with open(pdf_path, "rb") as pf:
            return pf.read()
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

        try:
            if os.path.exists(docx_path):
                os.remove(docx_path)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            if os.path.isdir(tmp_dir):
                os.rmdir(tmp_dir)
        except Exception:
            pass