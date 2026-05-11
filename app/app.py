import os
import re
import unicodedata
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for

# ─── Configuración ────────────────────────────────────────────────────────────

DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "user":     os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "cancer_lsi"),
    "port":     int(os.environ.get("DB_PORT", 3306)),
}


app = Flask(__name__)

# ─── Stop words básicas para normalización de consulta ───────────────────────

BASIC_STOPWORDS = {
    "de", "la", "el", "en", "que", "y", "a", "los", "del", "un", "una",
    "con", "por", "es", "se", "al", "las", "lo", "como", "me", "mi",
    "the", "and", "or", "of", "to", "a", "in", "is", "it", "on",
    "tengo", "siento", "siento", "hay", "tiene", "tener",
}

# Mapeo de frases compuestas a términos del vocabulario
COMPOUND_TERMS = {
    "tos persistente": "tos_persistente",
    "dolor pecho": "dolor_pecho",
    "dolor de pecho": "dolor_pecho",
    "dificultad respirar": "dificultad_respirar",
    "dificultad para respirar": "dificultad_respirar",
    "perdida peso": "perdida_peso",
    "perdida de peso": "perdida_peso",
    "heces negras": "heces_negras",
    "sangrado rectal": "sangrado_rectal",
    "fatiga extrema": "fatiga_extrema",
    "dolor abdominal": "dolor_abdominal",
    "nauseas vomitos": "nauseas_vomitos",
    "ictericia piel": "ictericia",
    "piel amarilla": "ictericia",
    "bulto mama": "bulto_mama",
    "cambio piel": "cambio_piel",
    "sangrado vaginal": "sangrado_vaginal",
    "dolor huesos": "dolor_oseo",
    "orina sangre": "hematuria",
}

# ─── Helpers de base de datos ─────────────────────────────────────────────────

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def query_db(sql, params=None, fetchone=False):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql, params or [])
    result = cursor.fetchone() if fetchone else cursor.fetchall()
    cursor.close()
    conn.close()
    return result


# ─── Normalización de consulta ────────────────────────────────────────────────

def remove_accents(text):
    text = unicodedata.normalize("NFD", text)
    return text.encode("ascii", "ignore").decode("utf-8")


def normalize_query(raw_text):
    """
    Normaliza la consulta del usuario:
    1. Minúsculas y sin acentos.
    2. Detecta términos compuestos.
    3. Tokeniza y filtra stop words.
    Retorna lista de términos finales.
    """
    text = raw_text.lower().strip()
    text = remove_accents(text)
    text = re.sub(r"[^a-z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Detectar términos compuestos
    detected_terms = []
    remaining = text
    for phrase, term in sorted(COMPOUND_TERMS.items(), key=lambda x: -len(x[0])):
        phrase_norm = remove_accents(phrase.lower())
        if phrase_norm in remaining:
            detected_terms.append(term)
            remaining = remaining.replace(phrase_norm, " ")

    # Tokenizar el resto
    for word in remaining.split():
        if word not in BASIC_STOPWORDS and len(word) >= 3:
            detected_terms.append(word)

    return list(dict.fromkeys(detected_terms))  # eliminar duplicados


def validate_terms(terms):
    """
    Verifica qué términos existen en la tabla term.
    Retorna (found_terms, missing_terms).
    """
    if not terms:
        return [], []

    placeholders = ", ".join(["%s"] * len(terms))
    rows = query_db(
        f"SELECT name FROM term WHERE name IN ({placeholders})", terms
    )
    found = [r["name"] for r in rows]
    missing = [t for t in terms if t not in found]
    return found, missing


# ─── Consultas de similitud ───────────────────────────────────────────────────

def search_cosine(terms):
    if not terms:
        return []
    placeholders = ", ".join(["%s"] * len(terms))
    sql = f"""
        WITH query_terms AS (
            SELECT name AS term_name, 1.0 AS q_freq
            FROM term
            WHERE name IN ({placeholders})
        ),
        dot_product AS (
            SELECT ht.document_id,
                   SUM(ht.frequency * qt.q_freq) AS dot
            FROM has_term ht
            JOIN query_terms qt ON qt.term_name = ht.term_name
            GROUP BY ht.document_id
        ),
        doc_norm AS (
            SELECT document_id,
                   SQRT(SUM(frequency * frequency)) AS norm_doc
            FROM has_term
            GROUP BY document_id
        )
        SELECT td.id, td.title, td.source, td.url,
               dp.dot / (dn.norm_doc * SQRT({len(terms)})) AS score
        FROM dot_product dp
        JOIN doc_norm dn ON dn.document_id = dp.document_id
        JOIN text_document td ON td.id = dp.document_id
        ORDER BY score DESC
    """
    return query_db(sql, terms)


def search_jaccard(terms):
    if not terms:
        return []
    placeholders = ", ".join(["%s"] * len(terms))
    sql = f"""
        WITH query_set AS (
            SELECT name AS term_name FROM term WHERE name IN ({placeholders})
        ),
        doc_has AS (
            SELECT DISTINCT document_id, term_name FROM has_term WHERE frequency > 0
        ),
        intersection AS (
            SELECT dh.document_id, COUNT(*) AS inter
            FROM doc_has dh JOIN query_set qs ON qs.term_name = dh.term_name
            GROUP BY dh.document_id
        ),
        doc_count AS (
            SELECT document_id, COUNT(*) AS doc_terms
            FROM doc_has GROUP BY document_id
        )
        SELECT td.id, td.title, td.source, td.url,
               i.inter / ({len(terms)} + dc.doc_terms - i.inter) AS score
        FROM intersection i
        JOIN doc_count dc ON dc.document_id = i.document_id
        JOIN text_document td ON td.id = i.document_id
        ORDER BY score DESC
    """
    return query_db(sql, terms)


def search_manhattan(terms):
    if not terms:
        return []
    placeholders = ", ".join(["%s"] * len(terms))
    sql = f"""
        WITH query_set AS (
            SELECT name AS term_name FROM term WHERE name IN ({placeholders})
        ),
        doc_has AS (
            SELECT DISTINCT document_id, term_name FROM has_term WHERE frequency > 0
        ),
        matches AS (
            SELECT dh.document_id, COUNT(*) AS matches
            FROM doc_has dh JOIN query_set qs ON qs.term_name = dh.term_name
            GROUP BY dh.document_id
        )
        SELECT td.id, td.title, td.source, td.url,
               ({len(terms)} - COALESCE(m.matches, 0)) AS score
        FROM text_document td
        LEFT JOIN matches m ON m.document_id = td.id
        ORDER BY score ASC
    """
    return query_db(sql, terms)


def search_lsi(terms):
    if not terms:
        return []
    placeholders = ", ".join(["%s"] * len(terms))
    sql = f"""
        SELECT td.id, td.title, td.source, td.url,
               AVG(ls.cosine_similarity_lsi) AS score
        FROM lsi_document_similarity ls
        JOIN text_document td ON td.id = ls.document_id_2
        JOIN (
            SELECT document_id
            FROM has_term
            WHERE term_name IN ({placeholders})
            GROUP BY document_id
            ORDER BY SUM(frequency) DESC
            LIMIT 3
        ) AS top_docs ON top_docs.document_id = ls.document_id_1
        GROUP BY td.id, td.title, td.source, td.url
        ORDER BY score DESC
    """
    return query_db(sql, terms)


def compare_cosine(doc_id):
    sql = """
        WITH d1 AS (SELECT term_name, frequency FROM complete_has WHERE document_id = %s),
             d2 AS (SELECT document_id, term_name, frequency FROM complete_has WHERE document_id != %s),
             dot AS (
                SELECT d2.document_id, SUM(d1.frequency * d2.frequency) AS dot
                FROM d1 JOIN d2 ON d1.term_name = d2.term_name
                GROUP BY d2.document_id
             ),
             n1 AS (SELECT SQRT(SUM(frequency*frequency)) AS norm FROM d1),
             n2 AS (SELECT document_id, SQRT(SUM(frequency*frequency)) AS norm FROM d2 GROUP BY document_id)
        SELECT td.id, td.title, td.source,
               dot.dot / (n1.norm * n2.norm) AS cosine
        FROM dot
        JOIN n2 ON n2.document_id = dot.document_id
        CROSS JOIN n1
        JOIN text_document td ON td.id = dot.document_id
        ORDER BY cosine DESC
    """
    return query_db(sql, [doc_id, doc_id])


def compare_manhattan(doc_id):
    sql = """
        SELECT td.id, td.title, td.source,
               SUM(ABS(d1.frequency - d2.frequency)) AS manhattan
        FROM complete_has d1
        JOIN complete_has d2 ON d1.term_name = d2.term_name AND d2.document_id != %s
        JOIN text_document td ON td.id = d2.document_id
        WHERE d1.document_id = %s
        GROUP BY td.id, td.title, td.source
        ORDER BY manhattan ASC
    """
    return query_db(sql, [doc_id, doc_id])


def compare_jaccard(doc_id):
    sql = """
        WITH d1 AS (SELECT term_name FROM has_term WHERE document_id = %s AND frequency > 0),
             d2 AS (SELECT document_id, term_name FROM has_term WHERE document_id != %s AND frequency > 0),
             inter AS (
                SELECT d2.document_id, COUNT(*) AS i
                FROM d1 JOIN d2 ON d1.term_name = d2.term_name
                GROUP BY d2.document_id
             ),
             cnt1 AS (SELECT COUNT(*) AS c FROM d1),
             cnt2 AS (SELECT document_id, COUNT(*) AS c FROM d2 GROUP BY document_id)
        SELECT td.id, td.title, td.source,
               inter.i / (cnt1.c + cnt2.c - inter.i) AS jaccard
        FROM inter
        JOIN cnt2 ON cnt2.document_id = inter.document_id
        CROSS JOIN cnt1
        JOIN text_document td ON td.id = inter.document_id
        ORDER BY jaccard DESC
    """
    return query_db(sql, [doc_id, doc_id])


def compare_lsi(doc_id):
    sql = """
        SELECT td.id, td.title, td.source,
               ls.cosine_similarity_lsi AS lsi_sim
        FROM lsi_document_similarity ls
        JOIN text_document td ON td.id = ls.document_id_2
        WHERE ls.document_id_1 = %s
        ORDER BY lsi_sim DESC
    """
    return query_db(sql, [doc_id])


# ─── Rutas Flask ──────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    query_text = ""
    method = "cosine"
    detected_terms = []
    missing_terms = []
    warning = None

    if request.method == "POST":
        query_text = request.form.get("symptoms", "").strip()
        method = request.form.get("method", "cosine")

        raw_terms = normalize_query(query_text)
        detected_terms, missing_terms = validate_terms(raw_terms)

        if missing_terms:
            warning = f"Algunos términos no fueron encontrados en la base: {', '.join(missing_terms)}"

        if detected_terms:
            if method == "cosine":
                results = search_cosine(detected_terms)
            elif method == "jaccard":
                results = search_jaccard(detected_terms)
            elif method == "manhattan":
                results = search_manhattan(detected_terms)
            elif method == "lsi":
                results = search_lsi(detected_terms)

    return render_template("index.html",
                           results=results,
                           query_text=query_text,
                           method=method,
                           detected_terms=detected_terms,
                           missing_terms=missing_terms,
                           warning=warning)


@app.route("/compare", methods=["GET", "POST"])
def compare():
    documents = query_db("SELECT id, title FROM text_document ORDER BY id")
    results_cosine = []
    results_manhattan = []
    results_jaccard = []
    results_lsi = []
    selected_doc = None
    method = "cosine"

    if request.method == "POST":
        doc_id = int(request.form.get("doc_id"))
        method = request.form.get("method", "cosine")
        selected_doc = query_db(
            "SELECT id, title FROM text_document WHERE id = %s", [doc_id], fetchone=True
        )
        if method == "cosine":
            results_cosine = compare_cosine(doc_id)
        elif method == "manhattan":
            results_manhattan = compare_manhattan(doc_id)
        elif method == "jaccard":
            results_jaccard = compare_jaccard(doc_id)
        elif method == "lsi":
            results_lsi = compare_lsi(doc_id)

    return render_template("compare.html",
                           documents=documents,
                           results_cosine=results_cosine,
                           results_manhattan=results_manhattan,
                           results_jaccard=results_jaccard,
                           results_lsi=results_lsi,
                           selected_doc=selected_doc,
                           method=method)


@app.route("/document/<int:doc_id>")
def document_detail(doc_id):
    doc = query_db(
        "SELECT * FROM text_document WHERE id = %s", [doc_id], fetchone=True
    )
    if not doc:
        return render_template("404.html"), 404

    terms = query_db(
        """SELECT term_name, frequency FROM has_term
           WHERE document_id = %s ORDER BY frequency DESC LIMIT 30""",
        [doc_id]
    )
    similar = query_db(
        """SELECT td.id, td.title, ls.cosine_similarity_lsi AS sim
           FROM lsi_document_similarity ls
           JOIN text_document td ON td.id = ls.document_id_2
           WHERE ls.document_id_1 = %s
           ORDER BY sim DESC LIMIT 5""",
        [doc_id]
    )
    return render_template("document_detail.html", doc=doc, terms=terms, similar=similar)


@app.route("/lsi")
def lsi():
    model = query_db(
        """
        SELECT 
            id,
            name,
            k_components,
            source_matrix,
            explained_variance_total AS total_variance,
            created_at
        FROM lsi_model
        ORDER BY id DESC
        LIMIT 1
        """,
        fetchone=True
    )

    top_terms = []
    similarities = []
    components = {}

    if model:
        counts = query_db(
            """
            SELECT 
                (SELECT COUNT(*) FROM document) AS n_documents,
                (SELECT COUNT(*) FROM term) AS n_terms
            """,
            fetchone=True
        )

        model["n_documents"] = counts["n_documents"]
        model["n_terms"] = counts["n_terms"]

        top_terms = query_db(
            """
            SELECT 
                component_number AS component,
                term_name AS term,
                weight,
                abs_weight,
                term_rank
            FROM lsi_term_weight
            WHERE model_id = %s
            ORDER BY component_number ASC, term_rank ASC
            """,
            [model["id"]]
        )

        similarities = query_db(
            """
            SELECT 
                ls.document_id_1,
                ls.document_id_2,
                t1.title AS title_1,
                t2.title AS title_2,
                ls.cosine_similarity_lsi
            FROM lsi_document_similarity ls
            JOIN text_document t1 ON t1.id = ls.document_id_1
            JOIN text_document t2 ON t2.id = ls.document_id_2
            WHERE ls.model_id = %s
            ORDER BY ls.cosine_similarity_lsi DESC
            """,
            [model["id"]]
        )

        for row in top_terms:
            c = row["component"]

            if c not in components:
                components[c] = []

            if len(components[c]) < 15:
                components[c].append(row)

    return render_template(
        "lsi.html",
        model=model,
        components=components,
        similarities=similarities
    )


# ─── Arranque ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
