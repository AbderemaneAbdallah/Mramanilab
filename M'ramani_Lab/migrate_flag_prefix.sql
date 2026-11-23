-- Migration idempotente des défis existants vers le préfixe M_LabCTF{...}.
-- À lancer depuis le terminal : sudo mariadb mramani_lab < migrate_flag_prefix.sql
UPDATE challenges
SET flag = CONCAT('M_LabCTF{', SUBSTRING(flag, 8, CHAR_LENGTH(flag) - 8), '}'),
    lab_data = REPLACE(lab_data, 'BIOCTF{', 'M_LabCTF{')
WHERE flag LIKE 'BIOCTF{%'
  AND RIGHT(flag, 1) = '}';

-- Convertit les anciennes réponses libres en contenu de flag sûr et uniforme.
-- Les caractères hors format deviennent des underscores ; les valeurs dépassant
-- la limite de contenu sont laissées pour correction manuelle.
UPDATE challenges
SET flag = CONCAT(
    'M_LabCTF{',
    LEFT(REGEXP_REPLACE(UPPER(TRIM(flag)), '[^A-Z0-9_.-]+', '_'), 110),
    '}'
)
WHERE flag NOT LIKE 'M_LabCTF{%'
  AND CHAR_LENGTH(flag) <= 110;
