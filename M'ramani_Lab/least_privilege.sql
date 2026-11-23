-- À exécuter par un administrateur MariaDB, après création de mramani_lab_app.
-- À lancer depuis le terminal Linux : sudo mariadb < least_privilege.sql
-- Réduit les privilèges existants puis n'accorde que les opérations utilisées.
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'mramani_lab_app'@'localhost';

GRANT SELECT ON mramani_lab.users
    TO 'mramani_lab_app'@'localhost';
GRANT INSERT (username, full_name, classe, email, password_hash)
    ON mramani_lab.users TO 'mramani_lab_app'@'localhost';
GRANT UPDATE (password_hash, score, last_solve)
    ON mramani_lab.users TO 'mramani_lab_app'@'localhost';

GRANT SELECT, INSERT, DELETE
    ON mramani_lab.challenges TO 'mramani_lab_app'@'localhost';
GRANT UPDATE (title, category, difficulty, points, clinical_context, lab_data, hint, flag)
    ON mramani_lab.challenges TO 'mramani_lab_app'@'localhost';

GRANT SELECT ON mramani_lab.solves
    TO 'mramani_lab_app'@'localhost';
GRANT INSERT (user_id, challenge_id, submitted_flag, is_correct)
    ON mramani_lab.solves TO 'mramani_lab_app'@'localhost';

FLUSH PRIVILEGES;
