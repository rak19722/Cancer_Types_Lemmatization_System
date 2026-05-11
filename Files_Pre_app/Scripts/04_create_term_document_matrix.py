import os
import pandas as pd
from collections import Counter


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEMMATIZED_DIR = os.path.join(BASE_DIR, "Data", "lemmatized_txt")

MATRIX_OUTPUT = os.path.join(BASE_DIR, "Data", "term_document_matrix.csv")
FREQUENCIES_OUTPUT = os.path.join(BASE_DIR, "Data", "frequencies_long.csv")
TERMS_OUTPUT = os.path.join(BASE_DIR, "Data", "terms.csv")
DOCUMENT_TERM_IDS_OUTPUT = os.path.join(BASE_DIR, "Data", "document_term_with_ids.csv")


def read_terms_from_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()

    terms = text.split()
    return terms


def main():
    files = sorted(
        [file for file in os.listdir(LEMMATIZED_DIR) if file.endswith(".txt")],
        key=lambda name: int(name.replace(".txt", ""))
    )

    document_counters = {}
    all_terms = set()

    # 1. Leer cada documento lematizado
    for filename in files:
        document_id = int(filename.replace(".txt", ""))
        file_path = os.path.join(LEMMATIZED_DIR, filename)

        terms = read_terms_from_file(file_path)

        counter = Counter(terms)

        document_counters[document_id] = counter
        all_terms.update(counter.keys())

        print(f"Documento {document_id} leído")
        print(f"Términos totales: {len(terms)}")
        print(f"Términos únicos: {len(counter)}")
        print("-" * 50)

    sorted_terms = sorted(all_terms)
    sorted_documents = sorted(document_counters.keys())

    # 2. Crear tabla TERM
    terms_df = pd.DataFrame([
        {
            "term_id": index + 1,
            "name": term
        }
        for index, term in enumerate(sorted_terms)
    ])

    terms_df.to_csv(TERMS_OUTPUT, index=False, encoding="utf-8-sig")

    # Diccionario para convertir término a ID
    term_to_id = {
        row["name"]: row["term_id"]
        for _, row in terms_df.iterrows()
    }

    # 3. Crear matriz término-documento
    matrix_rows = []

    for term in sorted_terms:
        row = {
            "term": term
        }

        for document_id in sorted_documents:
            row[f"doc_{document_id}"] = document_counters[document_id].get(term, 0)

        matrix_rows.append(row)

    matrix_df = pd.DataFrame(matrix_rows)
    matrix_df.to_csv(MATRIX_OUTPUT, index=False, encoding="utf-8-sig")

    # 4. Crear formato largo para HAS
    frequency_rows = []
    frequency_rows_with_ids = []

    for document_id, counter in document_counters.items():
        for term, frequency in counter.items():
            # Formato usando nombre del término
            frequency_rows.append({
                "document_id": document_id,
                "term": term,
                "frequency": frequency
            })

            # Formato usando term_id
            frequency_rows_with_ids.append({
                "document_id": document_id,
                "term_id": term_to_id[term],
                "term": term,
                "frequency": frequency
            })

    frequencies_df = pd.DataFrame(frequency_rows)
    frequencies_df = frequencies_df.sort_values(
        by=["document_id", "term"]
    )

    frequencies_df.to_csv(FREQUENCIES_OUTPUT, index=False, encoding="utf-8-sig")

    document_term_ids_df = pd.DataFrame(frequency_rows_with_ids)
    document_term_ids_df = document_term_ids_df.sort_values(
        by=["document_id", "term_id"]
    )

    document_term_ids_df.to_csv(
        DOCUMENT_TERM_IDS_OUTPUT,
        index=False,
        encoding="utf-8-sig"
    )

    print("Matriz término-documento creada correctamente.")
    print(f"Matriz FrecT: {MATRIX_OUTPUT}")
    print(f"Frecuencias formato HAS: {FREQUENCIES_OUTPUT}")
    print(f"Términos: {TERMS_OUTPUT}")
    print(f"Frecuencias con term_id: {DOCUMENT_TERM_IDS_OUTPUT}")


if __name__ == "__main__":
    main()