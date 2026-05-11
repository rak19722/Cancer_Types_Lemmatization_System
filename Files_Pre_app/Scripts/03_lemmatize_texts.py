import os
import re
import csv
import unicodedata
import spacy
import nltk
from nltk.corpus import stopwords


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RAW_DIR = os.path.join(BASE_DIR, "Data", "processed_txt")
OUTPUT_DIR = os.path.join(BASE_DIR, "Data", "lemmatized_txt")

WORD_TERM_OUTPUT = os.path.join(BASE_DIR, "Data", "word_term_mapping.csv")


nltk.download("stopwords")


# Cargar modelo en español
# Desactivamos parser y ner porque no los necesitamos para este paso.
nlp = spacy.load("es_core_news_sm", disable=["parser", "ner"])


spanish_stopwords = set(stopwords.words("spanish"))
english_stopwords = set(stopwords.words("english"))


custom_stopwords = {
    "menu", "buscar", "inicio", "contacto", "compartir",
    "facebook", "twitter", "instagram", "youtube",
    "pagina", "sitio", "web", "informacion", "contenido",
    "leer", "mas", "ver", "articulo", "seccion",
    "correo", "email", "imprimir", "servicios",
    "instituto", "nacional", "nci", "gov",
    "espanol", "english", "unidos", "estados"
}


all_stopwords = spanish_stopwords.union(english_stopwords).union(custom_stopwords)


# Si quieres distinguir tipos de cáncer, puedes dejar "cancer" como stop word.
# Si después agregas enfermedades similares, conviene quitarlo de aquí.
all_stopwords.add("cancer")


def remove_accents(text):
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore")
    text = text.decode("utf-8")
    return text


def normalize_word(word):
    word = word.lower()
    word = remove_accents(word)
    word = re.sub(r"[^a-zA-Z]", "", word)
    return word.strip()


def is_valid_word(word):
    if not word:
        return False

    if len(word) < 3:
        return False

    if word in all_stopwords:
        return False

    return True


def lemmatize_text(text):
    doc = nlp(text)

    lemmas = []
    word_term_pairs = set()

    for token in doc:
        original_word = normalize_word(token.text)
        lemma = normalize_word(token.lemma_)

        if not is_valid_word(original_word):
            continue

        if not is_valid_word(lemma):
            continue

        lemmas.append(lemma)
        word_term_pairs.add((original_word, lemma))

    return lemmas, word_term_pairs


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    files = sorted(
        [file for file in os.listdir(RAW_DIR) if file.endswith(".txt")],
        key=lambda name: int(name.replace(".txt", ""))
    )

    all_word_term_pairs = set()

    for filename in files:
        input_path = os.path.join(RAW_DIR, filename)
        output_path = os.path.join(OUTPUT_DIR, filename)

        with open(input_path, "r", encoding="utf-8") as file:
            original_text = file.read()

        lemmas, word_term_pairs = lemmatize_text(original_text)

        all_word_term_pairs.update(word_term_pairs)

        with open(output_path, "w", encoding="utf-8") as file:
            file.write(" ".join(lemmas))

        print(f"Archivo lematizado: {filename}")
        print(f"Palabras originales aproximadas: {len(original_text.split())}")
        print(f"Lemas finales: {len(lemmas)}")
        print("-" * 50)

    # Guardar relación WORD -> TERM
    with open(WORD_TERM_OUTPUT, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["word", "term"])

        for word, term in sorted(all_word_term_pairs):
            writer.writerow([word, term])

    print("Lematización terminada.")
    print(f"Archivos guardados en: {OUTPUT_DIR}")
    print(f"Relación WORD -> TERM guardada en: {WORD_TERM_OUTPUT}")


if __name__ == "__main__":
    main()