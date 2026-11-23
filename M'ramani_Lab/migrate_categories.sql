-- Migration unique pour remplacer les anciennes catégories médicales.
-- À exécuter sur une base existante avec : sudo mariadb mramani_lab < migrate_categories.sql
USE mramani_lab;

ALTER TABLE challenges
    MODIFY category VARCHAR(100) NOT NULL;

UPDATE challenges
SET category = 'Sciences du vivant'
WHERE category IN (
    'Immunologie & Vaccins',
    'Génétique & CRISPR',
    'Système Nerveux & Imagerie',
    'Cardiologie & Réanimation',
    'Microbiologie & Antibiogramme'
);

ALTER TABLE challenges
    MODIFY category ENUM(
        'Mathématiques',
        'Informatique',
        'Physique-Chimie',
        'Robotique',
        'Électronique',
        'Intelligence artificielle',
        'Sciences du vivant',
        'Technologie'
    ) NOT NULL;
