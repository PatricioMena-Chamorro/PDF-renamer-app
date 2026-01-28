from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd
import streamlit as st

import fitz  # PyMuPDF


# -----------------------------
# Utilidades de texto / nombres
# -----------------------------
INVALID_WIN_CHARS = r'<>:"/\|?*'

def sanitize_filename(s: str, max_len: int = 160) -> str:
    """Quita caracteres inválidos y recorta longitud para Windows."""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = "".join("_" if ch in INVALID_WIN_CHARS else ch for ch in s)
    # Evitar puntos/espacios al final (Windows)
    s = s.rstrip(" .")
    if len(s) > max_len:
        s = s[:max_len].rstrip(" .")
    return s

def title_case_soft(title: str) -> str:
    """No fuerza Title Case agresivo; deja el título como venga, pero limpia espacios."""
    title = re.sub(r"\s+", " ", title).strip()
    return title

def extract_year(text: str) -> Optional[int]:
    """
    Extrae el año con heurística:
    - Prioriza años cerca de "Published", "Vol", "Online", "Journal", "2023, Vol."
    - Si hay muchos, prefiere el año más probable (publicación) sobre received/copyright.
    """
    if not text:
        return None

    # normalizar espacios
    t = re.sub(r"\s+", " ", text)

    # buscar todos los años con su contexto
    matches = []
    for m in re.finditer(r"\b(19\d{2}|20\d{2})\b", t):
        y = int(m.group(1))
        start = max(0, m.start() - 60)
        end = min(len(t), m.end() + 60)
        ctx = t[start:end].lower()
        matches.append((y, ctx))

    if not matches:
        return None

    def score(y: int, ctx: str) -> int:
        s = 0
        # señales fuertes de publicación
        if any(k in ctx for k in ["published", "published online", "vol", "volume", "issue", "journal", "psychological research", "quarterly journal"]):
            s += 5
        # señales medias
        if any(k in ctx for k in ["doi", "online", "available online"]):
            s += 2
        # penalizaciones típicas
        if any(k in ctx for k in ["received", "revised", "accepted"]):
            s -= 2
        if "©" in ctx or "copyright" in ctx or "the author(s)" in ctx:
            s -= 1
        # preferir años recientes si todo empata
        s += (y - 1900) // 10
        return s

    # escoger el año con mayor score; si empata, el mayor año
    scored = [(score(y, ctx), y) for y, ctx in matches]
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return scored[0][1]

def normalize_author_surname(author_raw: str) -> str:
    """
    Intenta quedarnos con el apellido del primer autor.
    Soporta caracteres Unicode (turco, alemán, etc.) usando str.isalpha().
    """
    a = author_raw.strip()

    def keep_letters(s: str) -> str:
        # deja letras unicode + guiones/apóstrofes
        return "".join(ch for ch in s if ch.isalpha() or ch in "-'").strip("-'")

    # Caso "Apellido, Nombre"
    if "," in a:
        surname = a.split(",")[0].strip()
        surname = keep_letters(surname)
        return surname or a

    # Caso "Nombre Apellido" -> última palabra limpia
    parts = re.split(r"\s+", a)
    parts = [p for p in parts if p]
    if not parts:
        return a

    last = keep_letters(parts[-1])
    return last or a


# -----------------------------
# Extracción desde PDF (PyMuPDF)
# -----------------------------
@dataclass
class PaperInfo:
    title: Optional[str]
    first_author_surname: Optional[str]
    year: Optional[int]
    confidence: float
    notes: str

def get_first_page_lines_with_font(doc: fitz.Document) -> List[Tuple[str, float]]:
    """
    Devuelve pares (texto, tamaño_fuente) en orden de lectura aproximado
    usando spans de PyMuPDF en la primera página.
    """
    page = doc.load_page(0)
    blocks = page.get_text("dict")["blocks"]
    lines: List[Tuple[str, float]] = []

    for b in blocks:
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            # Tomamos el tamaño máximo de fuente dentro de la línea
            spans = ln.get("spans", [])
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            max_size = max(s.get("size", 0.0) for s in spans)
            # Filtrar ruido típico
            if len(text) < 3:
                continue
            lines.append((text, float(max_size)))

    return lines

def guess_title_and_authors(lines: List[Tuple[str, float]]) -> Tuple[Optional[str], Optional[str], float, str]:
    """
    Heurística:
    - El título suele ser de las líneas con mayor tamaño de fuente, arriba de la página.
    - La línea de autores suele venir inmediatamente después del título y contiene comas/and.
    """
    if not lines:
        return None, None, 0.0, "No se pudo extraer texto de la primera página."

    # Ordenar por tamaño de fuente (desc), tomar top candidates
    sorted_by_size = sorted(lines, key=lambda x: x[1], reverse=True)

    # Candidatos de título: top 5 por tamaño
    title_candidates = [t for (t, sz) in sorted_by_size[:6]]

    # Elegir el candidato "más largo" que no parezca encabezado tipo journal
    title = None
    for cand in title_candidates:
        c = cand.strip()
        # Evitar cosas tipo "Nature", "Elsevier", "www..."
        if re.search(r"\b(journal|doi|www\.|http|volume|issue)\b", c, flags=re.I):
            continue
        # Evitar líneas excesivamente cortas
        if len(c) < 12:
            continue
        title = c
        break

    # Buscar autores: una línea cercana al título que tenga patrón de nombres
    authors_line = None
    if title:
        # buscamos en las primeras ~25 líneas por aparición del título y tomamos líneas siguientes
        first_texts = [t for (t, _) in lines[:40]]
        idx = None
        for i, t in enumerate(first_texts):
            if title[:20] in t or t in title or title in t:
                idx = i
                break
        # si encontramos, buscamos en las siguientes 1-6 líneas una que parezca autores
        if idx is not None:
            window = first_texts[idx+1:idx+8]
            for w in window:
                if len(w) < 6:
                    continue
                # Heurística autores: comas, "and", "&", iniciales, etc.
                if re.search(r",| and | & |et al|·|•|\u00b7", w, flags=re.I):
                    # Evitar affiliations por "University", "Department"
                    if re.search(r"\b(university|department|institute|facult(y|ad)|address)\b", w, flags=re.I):
                        continue
                    authors_line = w.strip()
                    break
    
    # Plan B: si no detectamos autores con separadores típicos,
    # tomamos una línea cercana al título que "parezca" lista de nombres.
    if title and not authors_line:
        first_texts = [t for (t, _) in lines[:50]]
        idx = None
        for i, t in enumerate(first_texts):
            if title[:20] in t or t in title or title in t:
                idx = i
                break

        if idx is not None:
            window = first_texts[idx+1:idx+10]
            for w in window:
                ww = w.strip()

                # descartar afiliaciones típicas
                if re.search(r"\b(university|department|institute|faculty|school|address)\b", ww, flags=re.I):
                    continue
                # descartar cosas tipo "Abstract", "Keywords"
                if re.search(r"\b(abstract|keywords|introduction)\b", ww, flags=re.I):
                    continue

                # Heurística: "parece autores" si hay varias palabras capitalizadas
                caps = re.findall(r"\b[A-ZÁÉÍÓÚÜÑÇĞİÖŞÜ][a-záéíóúüñçğıöşü]+\b", ww)
                if len(caps) >= 2:
                    authors_line = ww
                    break

    confidence = 0.0
    notes = []
    if title:
        confidence += 0.55
    else:
        notes.append("No se detectó título con heurística de tamaño de fuente.")
    if authors_line:
        confidence += 0.30
    else:
        notes.append("No se detectó línea de autores (puede estar en otro formato).")

    return title, authors_line, min(confidence, 0.95), " ".join(notes) if notes else "OK"

def extract_paper_info(pdf_path: Path) -> PaperInfo:
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return PaperInfo(None, None, None, 0.0, f"No se pudo abrir PDF: {e}")

    try:
        lines = get_first_page_lines_with_font(doc)
        title, authors_line, conf, notes = guess_title_and_authors(lines)

        # Texto plano de la primera página para buscar año
        page_text = doc.load_page(0).get_text("text") or ""
        year = extract_year(page_text)

        first_author_surname = None
        if authors_line:
            # Tomar primer fragmento antes de coma o "and"
            first_chunk = re.split(r",| and | & ", authors_line, maxsplit=1, flags=re.I)[0].strip()
            first_author_surname = normalize_author_surname(first_chunk)

        # Ajustar confianza con año
        if year:
            conf = min(conf + 0.10, 0.99)
        else:
            notes = (notes + " " if notes != "OK" else "") + "No se detectó año (se usará fallback)."

        return PaperInfo(
            title=title_case_soft(title) if title else None,
            first_author_surname=first_author_surname,
            year=year,
            confidence=conf,
            notes=notes,
        )
    finally:
        doc.close()

def build_new_name(info: PaperInfo, fallback_year: int, original_stem: str) -> Tuple[str, str]:
    """
    Devuelve (new_stem, reason)
    """
    year = info.year or fallback_year
    title = info.title or original_stem
    author = info.first_author_surname or "Autor"

    # Siempre usamos "et al." para simplificar (si quieres, luego refinamos para 1 autor)
    new_stem = f"{author} et al. ({year}). {title}"
    new_stem = sanitize_filename(new_stem)
    reason_parts = []
    if not info.first_author_surname:
        reason_parts.append("fallback autor")
    if not info.year:
        reason_parts.append("fallback año")
    if not info.title:
        reason_parts.append("fallback título")
    reason = ", ".join(reason_parts) if reason_parts else "OK"
    return new_stem, reason

def avoid_collision(target: Path) -> Path:
    """Si el nombre ya existe, agrega (1), (2)..."""
    if not target.exists():
        return target
    base = target.stem
    suffix = 1
    while True:
        candidate = target.with_name(f"{base} ({suffix}){target.suffix}")
        if not candidate.exists():
            return candidate
        suffix += 1


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="PDF Renamer (papers)", page_icon="📄", layout="wide")

st.title("📄 Renombrador de PDFs científicos (autor-año-título)")

st.markdown(
    """
Esta app propone nombres tipo: **`Mena et al. (2026). Efecto de la tVNS.pdf`**  
- Extrae información principalmente desde la **primera página** del PDF.
- Incluye **modo seguro**: primero revisas, luego renombrar.
"""
)

folder = st.text_input("Ruta de carpeta con PDFs (ej: C:/Users/.../Mousetracker):", value="")
fallback_year = st.number_input("Año fallback (si no se detecta año):", min_value=1900, max_value=2099, value=2026, step=1)
dry_run = st.checkbox("Modo prueba (no renombra, solo simula)", value=True)

if folder:
    folder_path = Path(folder).expanduser()
    if not folder_path.exists():
        st.error("La ruta no existe.")
        st.stop()

    pdfs = sorted([p for p in folder_path.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"])
    if not pdfs:
        st.warning("No encontré PDFs en esa carpeta.")
        st.stop()

    st.write(f"Encontrados **{len(pdfs)}** PDFs.")

    rows = []
    for p in pdfs:
        info = extract_paper_info(p)
        new_stem, reason = build_new_name(info, fallback_year=fallback_year, original_stem=p.stem)
        proposed = p.with_name(new_stem + p.suffix)
        proposed = avoid_collision(proposed)

        rows.append({
            "archivo_actual": p.name,
            "propuesto": proposed.name,
            "confianza": round(info.confidence, 2),
            "notas": info.notes,
            "motivo_fallback": reason,
            "ruta_actual": str(p),
            "ruta_nueva": str(proposed),
        })

    df = pd.DataFrame(rows).sort_values(["confianza", "archivo_actual"], ascending=[True, True])
    view_cols = ["archivo_actual", "propuesto", "confianza", "motivo_fallback", "notas"]

    # Icono de alerta si hay fallback o baja confianza
    df_view = df[view_cols].copy()
    df_view["estado"] = df_view.apply(
    lambda r: "⚠️" if (r["confianza"] < 0.8 or str(r["motivo_fallback"]).strip().lower() != "ok") else "✅",
    axis=1
    )

    # Función de estilo por fila
    def style_row(row):
        conf = float(row["confianza"])
        fallback = str(row["motivo_fallback"]).strip().lower()

        if conf < 0.8 or fallback != "ok":
            return ["background-color: rgba(255, 193, 7, 0.20)"] * len(row)  # amarillo suave
        return ["background-color: rgba(40, 167, 69, 0.15)"] * len(row)  # verde suave

    # Mostrar primero el estado
    df_view = df_view[["estado"] + view_cols]

    st.dataframe(
    df_view.style.apply(style_row, axis=1),
    use_container_width=True
    )

    st.divider()
    st.subheader("Aplicar cambios")

    confirm = st.checkbox("Entiendo que esto renombrará archivos en mi carpeta.", value=False)
    if st.button("Renombrar PDFs ahora", disabled=(not confirm)):
        changed = 0
        errors = 0
        for r in rows:
            src = Path(r["ruta_actual"])
            dst = Path(r["ruta_nueva"])

            try:
                if dry_run:
                    continue
                if src.resolve() == dst.resolve():
                    continue
                os.rename(src, dst)
                changed += 1
            except Exception as e:
                errors += 1
                st.error(f"Error renombrando {src.name}: {e}")

        if dry_run:
            st.success("Modo prueba activado: no se renombró nada. Desmarca 'Modo prueba' para ejecutar.")
        else:
            st.success(f"Listo. Renombrados: {changed}. Errores: {errors}.")
else:
    st.info("Escribe una ruta de carpeta para comenzar.")
