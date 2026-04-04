"""Scraper for Colombian presidential election polls from Wikipedia."""

import urllib.request
from datetime import datetime, date

import polars as pl
from lxml import html


WIKI_URL = (
    "https://es.wikipedia.org/wiki/Anexo:Sondeos_de_intenci%C3%B3n_de_voto_"
    "para_las_elecciones_presidenciales_de_Colombia_de_2026"
)

SECTION_MARKER = "Oficialización de candidaturas"
TABLE_INDEX = 3  # General election table after section marker


def _fetch_page() -> str:
    req = urllib.request.Request(WIKI_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def _find_table(page_html: str) -> html.HtmlElement:
    idx = page_html.find(SECTION_MARKER)
    tree = html.fromstring(page_html[idx:])
    tables = tree.xpath('//table[contains(@class,"wikitable")]')
    return tables[TABLE_INDEX]


def _clean_pct(value: str) -> float | None:
    value = value.replace("\u200b", "").replace("—", "").strip()
    if not value or value == "—":
        return None
    value = value.rstrip("%").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def _extract_candidates(table: html.HtmlElement) -> list[str]:
    rows = table.xpath(".//tr")
    cells = rows[1].xpath(".//th|.//td")
    return [c.text_content().strip().replace("\n", " ") for c in cells]


def _extract_polls(table: html.HtmlElement, candidates: list[str]) -> list[dict]:
    rows = table.xpath(".//tr")
    n_candidates = len(candidates)
    polls = []
    current_encuesta = None
    current_fecha = None
    current_muestra = None

    for row in rows[3:]:
        cells = row.xpath(".//th|.//td")
        texts = [
            c.text_content().strip().replace("\u200b", "").replace("\n", " ")
            for c in cells
        ]
        n_cells = len(texts)

        if n_cells >= 20:
            # Full row: encuesta, fecha, muestra, 14 candidates, otr, blan, nin, ns/nr, margen
            current_encuesta = texts[0].split("[")[0]
            current_fecha = texts[1]
            current_muestra = texts[2]
            candidate_values = texts[3 : 3 + n_candidates]
            extra_start = 3 + n_candidates
        elif n_cells >= 17:
            # Sub-row of previous encuesta (missing encuesta/fecha/muestra)
            candidate_values = texts[0:n_candidates]
            extra_start = n_candidates
        else:
            continue

        record = {
            "encuestadora": current_encuesta,
            "fecha": current_fecha,
            "muestra": current_muestra,
        }
        for cand, val in zip(candidates, candidate_values):
            record[cand] = _clean_pct(val)

        remaining = texts[extra_start:]
        if len(remaining) >= 5:
            record["otros"] = _clean_pct(remaining[0])
            record["blanco"] = _clean_pct(remaining[1])
            record["ninguno"] = _clean_pct(remaining[2])
            record["ns_nr"] = _clean_pct(remaining[3])
            record["margen_error"] = _clean_pct(remaining[4])

        polls.append(record)

    return polls


def scrape_polls() -> pl.DataFrame:
    """Fetch and parse the general election poll table from Wikipedia."""
    page = _fetch_page()
    table = _find_table(page)
    candidates = _extract_candidates(table)
    polls = _extract_polls(table, candidates)
    df = pl.DataFrame(polls)
    df = df.with_columns(pl.lit(datetime.now().isoformat()).alias("fetched_at"))
    return df


def save_polls(output_path: str = "data/processed/encuestas.parquet") -> pl.DataFrame:
    """Scrape polls and save to parquet."""
    df = scrape_polls()
    df.write_parquet(output_path)
    print(f"Saved {len(df)} poll records to {output_path}")
    return df


if __name__ == "__main__":
    df = save_polls()
    print(df)
