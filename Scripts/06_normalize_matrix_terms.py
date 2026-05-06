import os
import pandas as pd
import spacy
import unicodedata
import re


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_MATRIX = os.path.join(BASE_DIR, "Data", "term_document_matrix.csv")

OUTPUT_MATRIX = os.path.join(BASE_DIR, "Data", "term_document_matrix_normalized.csv")
OUTPUT_TERMS = os.path.join(BASE_DIR, "Data", "terms_normalized.csv")
OUTPUT_FREQUENCIES = os.path.join(BASE_DIR, "Data", "frequencies_long_normalized.csv")


nlp = spacy.load("es_core_news_sm", disable=["parser", "ner"])


# Aquí fuerzas términos médicos a una forma común.
# Puedes ir agregando más conforme veas errores.
CUSTOM_CANONICAL_TERMS = {
    "orinar": "orina",
    "orin": "orina",
    "urinario": "orina",
    "urinaria": "orina",
    "miccion": "orina",

    "sangrar": "sangrado",
    "sangre": "sangrado",
    "hemorragia": "sangrado",

    "dolores": "dolor",
    "doloroso": "dolor",

    "pulmones": "pulmon",
    "pulmonar": "pulmon",

    "pancrea": "pancreas",
    "pancreatico": "pancreas",

    "hepatico": "higado",
    "hepatica": "higado",

    "prostatico": "prostata",
    "prostatica": "prostata",

    "uterino": "utero",
    "uterina": "utero",

    "mamas": "mama",
    "mamario": "mama",
    "mamaria": "mama",

    "fatiga": "cansancio",
    "debilidad": "cansancio",
    "agotamiento": "cansancio",

    "adelgazamiento": "perdida_peso",
    "peso": "perdida_peso",

    "tumor": "masa",
    "nodulo": "masa",
    "nodulos": "masa",

    "lesiones": "lesion",
    "manchas": "mancha"
}


def remove_accents(text):
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore")
    text = text.decode("utf-8")
    return text


def clean_term(term):
    term = str(term).lower()
    term = remove_accents(term)
    term = re.sub(r"[^a-zA-Z_]", "", term)
    return term.strip()


def lemmatize_term(term):
    term = clean_term(term)

    if term in CUSTOM_CANONICAL_TERMS:
        return CUSTOM_CANONICAL_TERMS[term]

    doc = nlp(term)

    if len(doc) == 0:
        return term

    lemma = clean_term(doc[0].lemma_)

    if lemma in CUSTOM_CANONICAL_TERMS:
        return CUSTOM_CANONICAL_TERMS[lemma]

    return lemma


def main():
    df = pd.read_csv(INPUT_MATRIX)

    if "term" not in df.columns:
        raise ValueError("La matriz debe tener una columna llamada 'term'.")

    doc_columns = [col for col in df.columns if col.startswith("doc_")]

    # Crear término normalizado
    df["normalized_term"] = df["term"].apply(lemmatize_term)

    # Agrupar términos repetidos y sumar frecuencias
    normalized_matrix = (
        df.groupby("normalized_term")[doc_columns]
        .sum()
        .reset_index()
        .rename(columns={"normalized_term": "term"})
        .sort_values("term")
    )

    normalized_matrix.to_csv(OUTPUT_MATRIX, index=False, encoding="utf-8-sig")

    # Crear terms_normalized.csv
    terms_df = pd.DataFrame({
        "term_id": range(1, len(normalized_matrix) + 1),
        "name": normalized_matrix["term"]
    })

    terms_df.to_csv(OUTPUT_TERMS, index=False, encoding="utf-8-sig")

    # Crear frequencies_long_normalized.csv para HAS
    frequency_rows = []

    for _, row in normalized_matrix.iterrows():
        term = row["term"]

        for doc_col in doc_columns:
            frequency = int(row[doc_col])

            if frequency > 0:
                document_id = int(doc_col.replace("doc_", ""))

                frequency_rows.append({
                    "document_id": document_id,
                    "term": term,
                    "frequency": frequency
                })

    frequencies_df = pd.DataFrame(frequency_rows)
    frequencies_df.to_csv(OUTPUT_FREQUENCIES, index=False, encoding="utf-8-sig")

    print("Matriz normalizada creada.")
    print(f"Matriz nueva: {OUTPUT_MATRIX}")
    print(f"Términos nuevos: {OUTPUT_TERMS}")
    print(f"Frecuencias nuevas: {OUTPUT_FREQUENCIES}")


if __name__ == "__main__":
    main()