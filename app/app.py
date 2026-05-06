import os
import pandas as pd
import mysql.connector


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LINKS_CSV = os.path.join(BASE_DIR, "Data", "links.csv")
TERMS_CSV = os.path.join(BASE_DIR, "Data", "Normalaized", "terms_normalized.csv")
FREQUENCIES_CSV = os.path.join(BASE_DIR, "Data", "Normalaized", "frequencies_long_normalized.csv")


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Rakolxd1?",
    "database": "cancer_lsi",
    "port": 3306
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


def main():
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    print("Cargando documentos...")
    load_documents(cursor)

    print("Cargando términos...")
    load_terms(cursor)

    print("Cargando frecuencias...")
    load_frequencies(cursor)

    connection.commit()

    cursor.close()
    connection.close()

    print("Base de datos cargada correctamente.")


if __name__ == "__main__":
    main()