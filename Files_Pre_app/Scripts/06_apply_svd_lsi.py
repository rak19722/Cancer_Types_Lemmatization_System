import os
import sys
import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity
from itertools import combinations


# ─── Rutas ────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NORMALIZED_DIR = os.path.join(BASE_DIR, "Data", "Normalaized")

MATRIX_CSV       = os.path.join(NORMALIZED_DIR, "term_document_matrix_normalized.csv")
DOC_VECTORS_CSV  = os.path.join(NORMALIZED_DIR, "lsi_document_vectors.csv")
TERMS_IMP_CSV    = os.path.join(NORMALIZED_DIR, "lsi_terms_importance.csv")
TOP_TERMS_CSV    = os.path.join(NORMALIZED_DIR, "lsi_top_terms_by_component.csv")
SIMILARITY_CSV   = os.path.join(NORMALIZED_DIR, "lsi_document_similarity.csv")

# Número de componentes latentes (fácil de cambiar)
K = 3
TOP_N_TERMS = 20


# ─── 1. Carga de la matriz ────────────────────────────────────────────────────

def load_matrix(path: str):
    """
    Lee el CSV término-documento.
    Retorna:
        matrix (np.ndarray): documentos x términos
        terms  (list[str]):   nombres de términos
        doc_ids(list[int]):   IDs de documentos (1..n)
    """
    if not os.path.exists(path):
        print(f"[ERROR] No se encontró el archivo: {path}")
        sys.exit(1)

    df = pd.read_csv(path)

    if "term" not in df.columns:
        print("[ERROR] El CSV no tiene una columna llamada 'term'.")
        sys.exit(1)

    terms = df["term"].tolist()

    # Columnas de documentos (todas menos 'term')
    doc_columns = [c for c in df.columns if c != "term"]
    doc_ids = [int(c.replace("doc_", "")) for c in doc_columns]

    # Matriz términos x documentos → transponemos a documentos x términos
    term_doc_matrix = df[doc_columns].values          # shape: (n_terms, n_docs)
    matrix = term_doc_matrix.T                         # shape: (n_docs, n_terms)

    return matrix, terms, doc_ids


# ─── 2. Aplicar SVD/LSI ───────────────────────────────────────────────────────

def apply_svd(matrix: np.ndarray, doc_ids: list, terms: list, k: int):
    """
    Aplica TruncatedSVD (LSI) a la matriz documentos x términos.
    Ajusta k si es >= número de documentos.
    Retorna el modelo ajustado y los vectores LSI de documentos.
    """
    n_docs, n_terms = matrix.shape

    # Validación: k debe ser < n_docs
    if k >= n_docs:
        k_adjusted = n_docs - 1
        print(f"[AVISO] k={k} >= n_docs={n_docs}. Se ajusta automáticamente a k={k_adjusted}.")
        k = k_adjusted

    print("\n" + "=" * 55)
    print("  SVD / LSI — Resultados")
    print("=" * 55)
    print(f"  Dimensiones de la matriz original : {matrix.shape}")
    print(f"  Número de documentos              : {n_docs}")
    print(f"  Número de términos                : {n_terms}")
    print(f"  Componentes latentes (k)          : {k}")

    svd = TruncatedSVD(n_components=k, random_state=42)
    doc_vectors = svd.fit_transform(matrix)   # shape: (n_docs, k)

    print("\n  Varianza explicada por componente:")
    for i, var in enumerate(svd.explained_variance_ratio_):
        print(f"    Componente {i + 1}: {var:.4f} ({var * 100:.2f}%)")

    total_var = svd.explained_variance_ratio_.sum()
    print(f"\n  Varianza total explicada          : {total_var:.4f} ({total_var * 100:.2f}%)")
    print("=" * 55 + "\n")

    return svd, doc_vectors, k


# ─── 3. Guardar vectores LSI de documentos ───────────────────────────────────

def save_document_vectors(doc_vectors: np.ndarray, doc_ids: list, k: int, path: str):
    """
    Guarda los vectores LSI de documentos en CSV.
    Columnas: document_id, component_1, ..., component_k
    """
    cols = {"document_id": doc_ids}
    for i in range(k):
        cols[f"component_{i + 1}"] = doc_vectors[:, i]

    df = pd.DataFrame(cols)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[OK] Vectores LSI de documentos guardados en:\n     {path}")


# ─── 4. Guardar importancia de términos por componente ───────────────────────

def save_terms_importance(svd: TruncatedSVD, terms: list, k: int, path: str):
    """
    Guarda el peso de cada término en cada componente.
    Columnas: component, term, weight
    """
    rows = []
    for i in range(k):
        for term, weight in zip(terms, svd.components_[i]):
            rows.append({
                "component": i + 1,
                "term": term,
                "weight": round(weight, 6)
            })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[OK] Importancia de términos guardada en:\n     {path}")


# ─── 5. Guardar top N términos por componente ────────────────────────────────

def save_top_terms(svd: TruncatedSVD, terms: list, k: int, top_n: int, path: str):
    """
    Para cada componente guarda los top_n términos con mayor peso absoluto.
    Columnas: component, term, weight, abs_weight, rank
    """
    rows = []
    for i in range(k):
        weights = svd.components_[i]
        abs_weights = np.abs(weights)
        top_indices = np.argsort(abs_weights)[::-1][:top_n]

        for rank, idx in enumerate(top_indices, start=1):
            rows.append({
                "component": i + 1,
                "term": terms[idx],
                "weight": round(weights[idx], 6),
                "abs_weight": round(abs_weights[idx], 6),
                "rank": rank
            })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[OK] Top {top_n} términos por componente guardados en:\n     {path}")


# ─── 6. Similitud coseno entre documentos ────────────────────────────────────

def compute_document_similarities(doc_vectors: np.ndarray, doc_ids: list, path: str):
    """
    Calcula la similitud coseno entre cada par de documentos en el espacio LSI.
    Columnas: document_id_1, document_id_2, cosine_similarity_lsi
    """
    sim_matrix = cosine_similarity(doc_vectors)   # shape: (n_docs, n_docs)

    rows = []
    for i, j in combinations(range(len(doc_ids)), 2):
        rows.append({
            "document_id_1": doc_ids[i],
            "document_id_2": doc_ids[j],
            "cosine_similarity_lsi": round(sim_matrix[i, j], 6)
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("cosine_similarity_lsi", ascending=False).reset_index(drop=True)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[OK] Similitudes entre documentos guardadas en:\n     {path}")


# ─── 7. Main ─────────────────────────────────────────────────────────────────

def main():
    print("Cargando matriz término-documento...")
    matrix, terms, doc_ids = load_matrix(MATRIX_CSV)

    print("Aplicando SVD / LSI...")
    svd, doc_vectors, k = apply_svd(matrix, doc_ids, terms, K)

    os.makedirs(NORMALIZED_DIR, exist_ok=True)

    save_document_vectors(doc_vectors, doc_ids, k, DOC_VECTORS_CSV)
    save_terms_importance(svd, terms, k, TERMS_IMP_CSV)
    save_top_terms(svd, terms, k, TOP_N_TERMS, TOP_TERMS_CSV)
    compute_document_similarities(doc_vectors, doc_ids, SIMILARITY_CSV)

    print("\nSVD / LSI completado correctamente.")


if __name__ == "__main__":
    main()
