DROP DATABASE IF EXISTS cancer_lsi;

CREATE DATABASE cancer_lsi
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE cancer_lsi;

CREATE TABLE document (
    id INT PRIMARY KEY
) ENGINE=InnoDB;

CREATE TABLE text_document (
    id INT PRIMARY KEY,
    url TEXT,
    title VARCHAR(255),
    source VARCHAR(255),
    type VARCHAR(50),
    language VARCHAR(10),
    FOREIGN KEY (id) REFERENCES document(id)
) ENGINE=InnoDB;

CREATE TABLE term (
    name VARCHAR(255) PRIMARY KEY
) ENGINE=InnoDB;

CREATE TABLE has_term (
    document_id INT,
    term_name VARCHAR(255),
    frequency DOUBLE,
    PRIMARY KEY (document_id, term_name),
    FOREIGN KEY (document_id) REFERENCES document(id),
    FOREIGN KEY (term_name) REFERENCES term(name)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS lsi_model (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    k_components INT,
    source_matrix VARCHAR(255),
    explained_variance_total DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS lsi_component_variance (
    model_id INT,
    component_number INT,
    explained_variance_ratio DOUBLE,
    PRIMARY KEY (model_id, component_number),
    FOREIGN KEY (model_id) REFERENCES lsi_model(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS lsi_document_vector (
    model_id INT,
    document_id INT,
    component_number INT,
    value DOUBLE,
    PRIMARY KEY (model_id, document_id, component_number),
    FOREIGN KEY (model_id) REFERENCES lsi_model(id),
    FOREIGN KEY (document_id) REFERENCES document(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS lsi_term_weight (
    model_id INT,
    component_number INT,
    term_name VARCHAR(255),
    weight DOUBLE,
    abs_weight DOUBLE,
    term_rank INT,
    PRIMARY KEY (model_id, component_number, term_name),
    FOREIGN KEY (model_id) REFERENCES lsi_model(id),
    FOREIGN KEY (term_name) REFERENCES term(name)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS lsi_document_similarity (
    model_id INT,
    document_id_1 INT,
    document_id_2 INT,
    cosine_similarity_lsi DOUBLE,
    PRIMARY KEY (model_id, document_id_1, document_id_2),
    FOREIGN KEY (model_id) REFERENCES lsi_model(id),
    FOREIGN KEY (document_id_1) REFERENCES document(id),
    FOREIGN KEY (document_id_2) REFERENCES document(id)
) ENGINE=InnoDB;    

#vista

CREATE OR REPLACE VIEW complete_has AS
SELECT 
    d.id AS document_id,
    t.name AS term_name,
    COALESCE(ht.frequency, 0) AS frequency
FROM document d
CROSS JOIN term t
LEFT JOIN has_term ht 
    ON ht.document_id = d.id 
    AND ht.term_name = t.name;
    

    
#Comparar dos documentos con distancia euclidiana
    
SELECT 
    SQRT(SUM(POWER(d1.frequency - d2.frequency, 2))) AS euclidean_distance
FROM complete_has d1
JOIN complete_has d2 
    ON d1.term_name = d2.term_name
WHERE d1.document_id = 1
  AND d2.document_id = 2;
  
#Comparar dos documentos con distancia Manhattan

SELECT 
    SUM(ABS(d1.frequency - d2.frequency)) AS manhattan_distance
FROM complete_has d1
JOIN complete_has d2 
    ON d1.term_name = d2.term_name
WHERE d1.document_id = 1
  AND d2.document_id = 2;
  
  #Comparar dos documentos con similitud coseno
  
SELECT 
    SUM(d1.frequency * d2.frequency) /
    (
        NULLIF(SQRT(SUM(POWER(d1.frequency, 2))), 0) *
        NULLIF(SQRT(SUM(POWER(d2.frequency, 2))), 0)
    ) AS cosine_similarity_estomago_colon
FROM complete_has d1
JOIN complete_has d2 
    ON d1.term_name = d2.term_name
WHERE d1.document_id = 6
  AND d2.document_id = 3;
  
  #Comparar un documento contra todos
  
  SELECT 
    td.title,
    d2.document_id,
    SUM(d6.frequency * d2.frequency) /
    (
        SQRT(SUM(POWER(d6.frequency, 2))) *
        SQRT(SUM(POWER(d2.frequency, 2)))
    ) AS cosine_similarity
FROM complete_has d6
JOIN complete_has d2 
    ON d6.term_name = d2.term_name
JOIN text_document td 
    ON td.id = d2.document_id
WHERE d6.document_id = 1
  AND d2.document_id <> 1
GROUP BY d2.document_id, td.title
ORDER BY cosine_similarity DESC;


#Experimento

DROP TEMPORARY TABLE IF EXISTS temp_query_terms;

CREATE TEMPORARY TABLE temp_query_terms (
    term_name VARCHAR(255) PRIMARY KEY,
    frequency DOUBLE
);

INSERT INTO temp_query_terms (term_name, frequency)
VALUES
('tos_persistente', 1),
('dolor_pecho', 1),
('dificultad_respirar', 1),
('perdida_peso', 1);

INSERT IGNORE INTO temp_query_terms (term_name, frequency)
VALUES
('tos', 1),
('persistente', 1),
('dolor', 1),
('pecho', 1),
('dificultad', 1),
('respirar', 1),
('perdida', 1),
('peso', 1);

#cosine sintomas
WITH query_terms AS (
    SELECT 'tos_persistente' AS term_name, 1 AS frequency
    UNION ALL
    SELECT 'dolor_pecho', 1
    UNION ALL
    SELECT 'dificultad_respirar', 1
    UNION ALL
    SELECT 'perdida_peso', 1
),
doc_norms AS (
    SELECT 
        document_id,
        SQRT(SUM(POWER(frequency, 2))) AS doc_norm
    FROM has_term
    GROUP BY document_id
),
query_norm AS (
    SELECT 
        SQRT(SUM(POWER(frequency, 2))) AS q_norm
    FROM query_terms
),
dot_products AS (
    SELECT 
        ht.document_id,
        SUM(ht.frequency * qt.frequency) AS dot_product
    FROM has_term ht
    JOIN query_terms qt
        ON ht.term_name = qt.term_name
    GROUP BY ht.document_id
)
SELECT 
    td.title,
    td.id AS document_id,
    COALESCE(dp.dot_product, 0) /
    (
        NULLIF(dn.doc_norm, 0) * NULLIF(qn.q_norm, 0)
    ) AS cosine_similarity
FROM text_document td
JOIN doc_norms dn 
    ON dn.document_id = td.id
CROSS JOIN query_norm qn
LEFT JOIN dot_products dp 
    ON dp.document_id = td.id
ORDER BY cosine_similarity DESC
LIMIT 5;


#1. Manhattan para búsqueda por síntomas

WITH query_terms AS (
    SELECT 'vomito' AS term_name, 1 AS frequency
    UNION ALL
    SELECT 'negro', 1
    UNION ALL
    SELECT 'sangrado', 1
    UNION ALL
    SELECT 'acidez', 1
    UNION ALL
    SELECT 'perdida_peso', 1
),
manhattan_scores AS (
    SELECT 
        td.id AS document_id,
        td.title,
        SUM(
            ABS(
                CASE 
                    WHEN ht.frequency IS NULL THEN 0
                    ELSE 1
                END - qt.frequency
            )
        ) AS manhattan_distance
    FROM text_document td
    CROSS JOIN query_terms qt
    LEFT JOIN has_term ht
        ON ht.document_id = td.id
        AND ht.term_name = qt.term_name
    GROUP BY td.id, td.title
)
SELECT 
    title,
    document_id,
    manhattan_distance
FROM manhattan_scores
ORDER BY manhattan_distance ASC
LIMIT 5;

#Jaccard para búsqueda por síntomas

WITH query_terms AS (
    SELECT 'Fatiga' AS term_name
    UNION ALL
    SELECT 'sangrado'
    UNION ALL
    SELECT 'globulos'
    UNION ALL
    SELECT 'perdida_peso'
),
doc_intersections AS (
    SELECT 
        td.id AS document_id,
        td.title,
        COUNT(ht.term_name) AS intersection_count
    FROM text_document td
    CROSS JOIN query_terms qt
    LEFT JOIN has_term ht
        ON ht.document_id = td.id
        AND ht.term_name = qt.term_name
    GROUP BY td.id, td.title
),
doc_term_counts AS (
    SELECT 
        document_id,
        COUNT(*) AS document_term_count
    FROM has_term
    WHERE frequency > 0
    GROUP BY document_id
),
query_count AS (
    SELECT COUNT(*) AS query_term_count
    FROM query_terms
)
SELECT 
    di.title,
    di.document_id,
    di.intersection_count,
    (
        di.intersection_count /
        NULLIF((dtc.document_term_count + qc.query_term_count - di.intersection_count), 0)
    ) AS jaccard_similarity
FROM doc_intersections di
JOIN doc_term_counts dtc
    ON dtc.document_id = di.document_id
CROSS JOIN query_count qc
ORDER BY jaccard_similarity DESC
LIMIT 5;

#Coseno para documento contra todos
WITH query_terms AS (
    SELECT 'vomito' AS term_name, 1 AS frequency
    UNION ALL
    SELECT 'negro', 1
    UNION ALL
    SELECT 'sangrado', 1
    UNION ALL
    SELECT 'acidez', 1
    UNION ALL
    SELECT 'perdida_peso', 1
),
doc_norms AS (
    SELECT 
        document_id,
        SQRT(SUM(POWER(frequency, 2))) AS doc_norm
    FROM has_term
    GROUP BY document_id
),
query_norm AS (
    SELECT 
        SQRT(SUM(POWER(frequency, 2))) AS q_norm
    FROM query_terms
),
dot_products AS (
    SELECT 
        ht.document_id,
        SUM(ht.frequency * qt.frequency) AS dot_product
    FROM has_term ht
    JOIN query_terms qt
        ON ht.term_name = qt.term_name
    GROUP BY ht.document_id
)
SELECT 
    td.title,
    td.id AS document_id,
    COALESCE(dp.dot_product, 0) /
    (
        NULLIF(dn.doc_norm, 0) * NULLIF(qn.q_norm, 0)
    ) AS cosine_similarity
FROM text_document td
JOIN doc_norms dn 
    ON dn.document_id = td.id
CROSS JOIN query_norm qn
LEFT JOIN dot_products dp 
    ON dp.document_id = td.id
ORDER BY cosine_similarity DESC
LIMIT 10;

#Manhattan para documento contra todos

SELECT 
    td.title,
    d2.document_id,
    SUM(ABS(d1.frequency - d2.frequency)) AS manhattan_distance
FROM complete_has d1
JOIN complete_has d2 
    ON d1.term_name = d2.term_name
JOIN text_document td 
    ON td.id = d2.document_id
WHERE d1.document_id = 6
  AND d2.document_id <> 6
GROUP BY d2.document_id, td.title
ORDER BY manhattan_distance ASC;

#Jaccard para documento contra todos

SELECT 
    td.title,
    ht2.document_id,
    COUNT(DISTINCT ht1.term_name) / 
    NULLIF(
        (
            (SELECT COUNT(DISTINCT term_name) 
             FROM has_term 
             WHERE document_id = 6)
            +
            COUNT(DISTINCT ht2.term_name)
            -
            COUNT(DISTINCT ht1.term_name)
        ),
        0
    ) AS jaccard_similarity
FROM has_term ht1
JOIN has_term ht2
    ON ht1.term_name = ht2.term_name
JOIN text_document td
    ON td.id = ht2.document_id
WHERE ht1.document_id = 6
  AND ht2.document_id <> 6
GROUP BY ht2.document_id, td.title
ORDER BY jaccard_similarity DESC;



#Para ver similitudes LSI de estómago contra todos:

SELECT 
    td.title,
    lds.document_id_2,
    lds.cosine_similarity_lsi
FROM lsi_document_similarity lds
JOIN text_document td 
    ON td.id = lds.document_id_2
WHERE lds.model_id = (
    SELECT MAX(id) FROM lsi_model
)
AND lds.document_id_1 = 6
ORDER BY lds.cosine_similarity_lsi DESC;


#Para ver similitudes LSI de estómago contra todos

SELECT 
    component_number,
    term_name,
    weight,
    abs_weight,
    term_rank
FROM lsi_term_weight
WHERE model_id = (
    SELECT MAX(id) FROM lsi_model
)
ORDER BY component_number, term_rank
LIMIT 60;
  