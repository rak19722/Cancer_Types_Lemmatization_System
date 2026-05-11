import os
import pandas as pd
import mysql.connector


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LINKS_CSV = os.path.join(BASE_DIR, "Data", "links.csv")
TERMS_CSV = os.path.join(BASE_DIR, "Data", "Normalaized", "terms_normalized.csv")
FREQUENCIES_CSV = os.path.join(BASE_DIR, "Data", "Normalaized", "frequencies_long_normalized.csv")

LSI_DOC_VECTORS_CSV = os.path.join(BASE_DIR, "Data", "LSI", "lsi_document_vectors.csv")
LSI_TOP_TERMS_CSV = os.path.join(BASE_DIR, "Data", "LSI", "lsi_top_terms_by_component.csv")
LSI_SIMILARITY_CSV = os.path.join(BASE_DIR, "Data", "LSI", "lsi_document_similarity.csv")

DB_CONFIG = {
    "host": "viaduct.proxy.rlwy.net",
    "user": "root",
    "password": "uZZIGGLoCuMTUvpcarCdfpoIAcpWzFBt",
    "database": "railway",
    "port": 54458
}


def read_csv_safely(path):
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")


def load_documents(cursor):
    df = read_csv_safely(LINKS_CSV)

    for _, row in df.iterrows():
        doc_id = int(row["id"])

        cursor.execute(
            """
            INSERT IGNORE INTO document (id)
            VALUES (%s)
            """,
            (doc_id,)
        )

        cursor.execute(
            """
            INSERT INTO text_document (id, url, title, source, type, language)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                url = VALUES(url),
                title = VALUES(title),
                source = VALUES(source),
                type = VALUES(type),
                language = VALUES(language)
            """,
            (
                doc_id,
                row["url"],
                row["title"],
                row["source"],
                row["type"],
                row["language"]
            )
        )


def load_terms(cursor):
    df = read_csv_safely(TERMS_CSV)

    for _, row in df.iterrows():
        cursor.execute(
            """
            INSERT IGNORE INTO term (name)
            VALUES (%s)
            """,
            (row["name"],)
        )


def load_frequencies(cursor):
    df = read_csv_safely(FREQUENCIES_CSV)

    for _, row in df.iterrows():
        cursor.execute(
            """
            INSERT INTO has_term (document_id, term_name, frequency)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                frequency = VALUES(frequency)
            """,
            (
                int(row["document_id"]),
                row["term"],
                float(row["frequency"])
            )
        )

def create_lsi_model(cursor):
    cursor.execute(
        """
        INSERT INTO lsi_model (name, k_components, source_matrix, explained_variance_total)
        VALUES (%s, %s, %s, %s)
        """,
        (
            "LSI modelo base",
            3,
            "term_document_matrix_normalized.csv",
            None
        )
    )

    return cursor.lastrowid


def load_lsi_document_vectors(cursor, model_id):
    if not os.path.exists(LSI_DOC_VECTORS_CSV):
        print("No se encontró lsi_document_vectors.csv. Saltando vectores LSI.")
        return

    df = read_csv_safely(LSI_DOC_VECTORS_CSV)

    component_columns = [
        col for col in df.columns
        if col.startswith("component_")
    ]

    for _, row in df.iterrows():
        document_id = int(row["document_id"])

        for col in component_columns:
            component_number = int(col.replace("component_", ""))
            value = float(row[col])

            cursor.execute(
                """
                INSERT INTO lsi_document_vector 
                (model_id, document_id, component_number, value)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    value = VALUES(value)
                """,
                (
                    model_id,
                    document_id,
                    component_number,
                    value
                )
            )


def load_lsi_top_terms(cursor, model_id):
    if not os.path.exists(LSI_TOP_TERMS_CSV):
        print("No se encontró lsi_top_terms_by_component.csv. Saltando pesos de términos LSI.")
        return

    df = read_csv_safely(LSI_TOP_TERMS_CSV)

    for _, row in df.iterrows():
        component_number = int(row["component"])
        term_name = str(row["term"])
        weight = float(row["weight"])
        abs_weight = float(row["abs_weight"])
        term_rank = int(row["rank"])

        # Por si el término no está en term, lo insertamos.
        cursor.execute(
            """
            INSERT IGNORE INTO term (name)
            VALUES (%s)
            """,
            (term_name,)
        )

        cursor.execute(
            """
            INSERT INTO lsi_term_weight
            (model_id, component_number, term_name, weight, abs_weight, term_rank)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                weight = VALUES(weight),
                abs_weight = VALUES(abs_weight),
                term_rank = VALUES(term_rank)
            """,
            (
                model_id,
                component_number,
                term_name,
                weight,
                abs_weight,
                term_rank
            )
        )


def load_lsi_document_similarity(cursor, model_id):
    if not os.path.exists(LSI_SIMILARITY_CSV):
        print("No se encontró lsi_document_similarity.csv. Saltando similitudes LSI.")
        return

    df = read_csv_safely(LSI_SIMILARITY_CSV)

    for _, row in df.iterrows():
        cursor.execute(
            """
            INSERT INTO lsi_document_similarity
            (model_id, document_id_1, document_id_2, cosine_similarity_lsi)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                cosine_similarity_lsi = VALUES(cosine_similarity_lsi)
            """,
            (
                model_id,
                int(row["document_id_1"]),
                int(row["document_id_2"]),
                float(row["cosine_similarity_lsi"])
            )
        )        


def main():
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    print("Cargando documentos...")
    load_documents(cursor)

    print("Cargando términos...")
    load_terms(cursor)

    print("Cargando frecuencias...")
    load_frequencies(cursor)

    print("Creando modelo LSI...")
    model_id = create_lsi_model(cursor)

    print(f"Cargando vectores LSI para model_id = {model_id}...")
    load_lsi_document_vectors(cursor, model_id)

    print("Cargando términos importantes por componente LSI...")
    load_lsi_top_terms(cursor, model_id)

    print("Cargando similitudes documento-documento en espacio LSI...")
    load_lsi_document_similarity(cursor, model_id)

    connection.commit()

    cursor.close()
    connection.close()

    print("Base de datos y datos LSI cargados correctamente.")


if __name__ == "__main__":
    main()