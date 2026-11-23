-- Schéma de données de M'ramani_Lab
CREATE DATABASE IF NOT EXISTS mramani_lab CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mramani_lab;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    classe VARCHAR(30) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'admin') DEFAULT 'student',
    score INT DEFAULT 0,
    last_solve TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS challenges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(120) NOT NULL,
    category ENUM('Mathématiques', 'Informatique', 'Physique-Chimie', 'Robotique', 'Électronique', 'Intelligence artificielle', 'Sciences du vivant', 'Technologie') NOT NULL,
    difficulty ENUM('Facile', 'Moyen', 'Difficile', 'Expert') NOT NULL,
    points INT NOT NULL,
    clinical_context TEXT NOT NULL,
    lab_data TEXT NOT NULL,
    hint TEXT NOT NULL,
    flag VARCHAR(120) NOT NULL
);

CREATE TABLE IF NOT EXISTS solves (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    challenge_id INT NOT NULL,
    submitted_flag VARCHAR(120) NOT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT FALSE,
    solved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE
);

-- Compte administrateur initial désactivé jusqu'à la définition d'un mot de passe.
-- Après l'import : flask --app app set-admin-password
INSERT IGNORE INTO users (username, full_name, classe, email, password_hash, role, score)
VALUES ('prof_admin', 'Professeur M''ramani_Lab', 'Enseignant', 'admin@mramani-lab.local',
    '!disabled-set-password-with-flask-cli!', 'admin', 0);

-- Défis CTF SVT orientés Médecine Moderne (Programme 4ème Collège)
INSERT INTO challenges (title, category, difficulty, points, clinical_context, lab_data, hint, flag) VALUES
(
    'Opération ARN Messager (Vaccin Nouvelle Génération)',
    'Sciences du vivant',
    'Facile',
    100,
    'Un patient est admis au CHU pour une infection virale émergente. Le laboratoire de biotechnologie synthétise un vaccin à ARNm codant pour la protéine Spike de surface afin de déclencher la production d''anticorps spécifiques par les lymphocytes B.',
    'Séquence ADN brin transcrit du virus : 3''- T A C - G G A - T T C - A C T - 5''\nRègle de transcription ARNm : A->U, T->A, C->G, G->C.\nFormat de la réponse : M_LabCTF{SEQUENCE_ARNm_SANS_TIRETS}',
    'Complétez chaque base nucléotidique : T devient A, A devient U, C devient G, G devient C.',
    'M_LabCTF{AUGCCUAAGUGA}'
),
(
    'Ciseaux Moléculaires CRISPR-Cas9 & Drépanocytose',
    'Sciences du vivant',
    'Moyen',
    200,
    'En thérapie génique moderne, on corrige la mutation ponctuelle responsable de la drépanocytose sur le chromosome 11 (gène HBB). Le codon normal GAG (acide glutamique) a muté en GTG (valine), déformant les globules rouges en faucille.',
    'Données du séquenceur génétique patient #402 :\nAllèle 1 : GTG | Allèle 2 : GTG\nPour restaurer l''hémoglobine normale HbA via CRISPR-Cas9, quel triplet ADN doit remplacer GTG, et quel est le nom de la protéine transportant l''O2 ?\nFormat : M_LabCTF{TRIPLET_PROTEINE} (en majuscules, sans accent)',
    'Le triplet normal est GAG et la protéine des hématies est l''HEMOGLOBINE.',
    'M_LabCTF{GAG_HEMOGLOBINE}'
),
(
    'IRM Fonctionnelle & AVC Ischémique',
    'Sciences du vivant',
    'Moyen',
    250,
    'Un patient présente une hémiplégie brutale du côté droit et une aphasie (trouble du langage) suite à l''obstruction d''une artère cérébrale par un caillot. Les urgentistes réalisent une thrombolyse d''urgence.',
    'Observation IRM :\n- Déficit moteur : côté DROIT du corps.\n- Aire de Broca touchée.\nSachant que les voies nerveuses motrices croisent au niveau du bulbe rachidien, quel hémisphère cérébral est lésé (GAUCHE ou DROIT) et quel lobe abrite l''aire motrice principale (FRONTAL, PARIETAL, OCCIPITAL) ?\nFormat : M_LabCTF{HEMISPHERE_LOBE}',
    'Le contrôle moteur est controlatéral (inversé) et l''aire motrice se situe en avant du sillon de Rolando.',
    'M_LabCTF{GAUCHE_FRONTAL}'
),
(
    'Urgence Coronarienne & ECG Numérique',
    'Sciences du vivant',
    'Difficile',
    350,
    'Un sportif de 38 ans ressent une douleur thoracique constrictive. L''électrocardiogramme (ECG) connecté montre un sus-décalage du segment ST. Une coronarographie révèle une occlusion à 95% de l''artère coronaire interventriculaire antérieure.',
    'Télémétrie Moniteur :\n- Fréquence cardiaque : 110 bpm\n- Volume d''éjection systolique (VES) : 50 mL\n1) Calculez le Débit Cardiaque (Qc = FC x VES) en Litres/minute (format X.X).\n2) Quel nom porte la nécrose du muscle cardiaque causée par cette ischémie prolongée ?\nFormat : M_LabCTF{DEBIT_PATHOLOGIE} (ex: M_LabCTF{4.8_ANGINE})',
    '110 x 50 mL = 5500 mL = 5.5 L/min. La nécrose du myocarde est un INFARCTUS.',
    'M_LabCTF{5.5_INFARCTUS}'
),
(
    'Super-Bactérie Nosocomiale & Antibiogramme',
    'Sciences du vivant',
    'Expert',
    500,
    'En service de réanimation, un patient développe une septicémie à Staphylococcus aureus. L''équipe médicale réalise un antibiogramme sur gélose Mueller-Hinton pour identifier l''antibiotique actif capable d''inhiber la croissance bactérienne.',
    'Diamètres des zones d''inhibition mesurés au scanner :\n- Pénicilline G : 6 mm (Seuil sensibilité >= 26 mm)\n- Méthicilline : 8 mm (Seuil sensibilité >= 22 mm)\n- Vancomycine : 24 mm (Seuil sensibilité >= 17 mm)\n- Amoxicilline : 6 mm (Seuil sensibilité >= 21 mm)\nFormat : M_LabCTF{ANTIBIOTIQUE_EFFICACE_DIAMETREMM} (ex: M_LabCTF{PENICILLINE_6MM})',
    'Choisissez l''antibiotique dont le diamètre d''inhibition dépasse le seuil critique de sensibilité.',
    'M_LabCTF{VANCOMYCINE_24MM}'
);
