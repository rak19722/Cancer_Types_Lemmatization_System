import os
import re
import unicodedata
import nltk
from nltk.corpus import stopwords


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RAW_DIR = os.path.join(BASE_DIR, "Data", "raw_txt")
OUTPUT_DIR = os.path.join(BASE_DIR, "Data", "processed_txt")


# Descargar stopwords si no existen
nltk.download("stopwords")


# Stop words en español e inglés
spanish_stopwords = set(stopwords.words("spanish"))
english_stopwords = set(stopwords.words("english"))


# Stop words extra por basura de páginas web
custom_stopwords = {
    "menu", "buscar", "inicio", "contacto", "compartir",
    "facebook", "twitter", "instagram", "youtube",
    "pagina", "sitio", "web", "informacion", "contenido",
    "leer", "mas", "ver", "articulo", "seccion",
    "correo", "email", "imprimir", "servicios",
    "instituto", "nacional", "cancer", "nci",
    "gov", "espanol", "english", "unidos", "estados"
}


all_stopwords = spanish_stopwords.union(english_stopwords).union(custom_stopwords)


def remove_accents(text):
    # Convierte cáncer → cancer, pulmón → pulmon
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore")
    text = text.decode("utf-8")
    return text


def normalize_text(text):
    # 1. Minúsculas
    text = text.lower()

    # 2. Quitar acentos
    text = remove_accents(text)

    # 3. Quitar números, signos y caracteres raros
    text = re.sub(r"[^a-zA-Z\s]", " ", text)

    # 4. Quitar espacios repetidos
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tokenize(text):
    # Separar texto en palabras
    return text.split()


def remove_stopwords(words):
    clean_words = []

    for word in words:
        # Quitar palabras muy cortas
        if len(word) < 3:
            continue

        # Quitar stop words
        if word in all_stopwords:
            continue

        clean_words.append(word)

    return clean_words


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    files = sorted(
        [file for file in os.listdir(RAW_DIR) if file.endswith(".txt")],
        key=lambda name: int(name.replace(".txt", ""))
    )

    for filename in files:
        input_path = os.path.join(RAW_DIR, filename)
        output_path = os.path.join(OUTPUT_DIR, filename)

        with open(input_path, "r", encoding="utf-8") as file:
            original_text = file.read()

        # Paso 1: normalizar
        normalized_text = normalize_text(original_text)

        # Paso 2: separar palabras
        words = tokenize(normalized_text)

        # Paso 3: quitar stop words
        clean_words = remove_stopwords(words)

        # Guardar texto limpio
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(" ".join(clean_words))

        print(f"Archivo procesado: {filename}")
        print(f"Palabras originales: {len(original_text.split())}")
        print(f"Palabras después de limpiar: {len(clean_words)}")
        print("-" * 50)


if __name__ == "__main__":
    main()