# M'ramani_Lab

**M'ramani_Lab** est une plateforme pédagogique développée en partenariat avec le **Groupe Scolaire Generation 2000 de M'ramani**. Elle a vocation à proposer des activités en sciences du vivant, mathématiques, physique, informatique et technologies (robotique, électronique, intelligence artificielle). **À ce jour, les défis disponibles dans le code portent sur les sciences du vivant.**

Ce guide accompagne une personne qui découvre le projet : prérequis, installation, base de données, lancement, utilisation des comptes, tests et dépannage.

## Sommaire

1. [Ce que contient la plateforme](#ce-que-contient-la-plateforme)
2. [Prérequis](#prérequis)
3. [Installation sur Ubuntu](#installation-sur-ubuntu)
4. [Créer la base et le compte MariaDB](#créer-la-base-et-le-compte-mariadb)
5. [Configurer le fichier `.env`](#configurer-le-fichier-env)
6. [Créer le compte administrateur](#créer-le-compte-administrateur)
7. [Lancer et utiliser la plateforme](#lancer-et-utiliser-la-plateforme)
8. [Format des réponses aux défis](#format-des-réponses-aux-défis)
9. [Tests](#tests)
10. [Sécurité et limites de déploiement](#sécurité-et-limites-de-déploiement)
11. [Dépannage](#dépannage)
12. [Organisation des fichiers](#organisation-des-fichiers)

## Ce que contient la plateforme

### Pour les élèves

- Création d’un compte avec nom, classe, pseudo, adresse e-mail et mot de passe.
- Tableau de bord avec défis, points, rang et progression.
- Soumission d’une réponse au format `M_LabCTF{REPONSE}`.
- Classement des élèves.
- Choix du thème clair ou sombre, conservé dans le navigateur.

### Pour le professeur administrateur

- Consultation des comptes élèves et du journal des 100 dernières tentatives.
- Création, modification et suppression des défis.
- Les opérations d’administration sont réservées au rôle administrateur.

### Défis inclus

Le schéma de départ fournit cinq défis autour de l’immunologie, de la génétique, du système nerveux, de la cardiologie et de la microbiologie. Les catégories et difficultés possibles sont définies dans la base de données.

## Prérequis

- Ubuntu ou une autre distribution Linux.
- Python 3 et le module `venv`.
- MariaDB (compatible MySQL) et le client `mariadb`.
- Un navigateur web moderne.

Les dépendances Python sont listées dans [requirements.txt](requirements.txt) : Flask, le connecteur MariaDB/MySQL, Werkzeug et python-dotenv.

Sur Ubuntu, si Python, `venv` ou MariaDB ne sont pas encore installés :

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip mariadb-server mariadb-client
sudo systemctl enable --now mariadb
```

## Installation sur Ubuntu

> **Où taper les commandes ?** Les commandes de ce guide avec préfixe `bash` se tapent dans le terminal Linux. Les commandes SQL se tapent après avoir ouvert MariaDB et vu une invite comme `MariaDB [(none)]>`. Ne tape pas du SQL directement dans Bash.

1. Ouvre un terminal dans le dossier du projet :

   ```bash
   cd "$HOME/Downloads/M'ramani_Lab"
   ```

   Si ton dossier se trouve ailleurs, adapte le chemin. Vérifie que le terminal contient les fichiers `app.py` et `schema.sql` avec `ls`.

2. Crée et active un environnement Python, puis installe les dépendances :

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

   Quand l’environnement est actif, le terminal affiche généralement `(.venv)`.

3. Vérifie que MariaDB est installé et démarré. Sur Ubuntu, la commande de connexion locale est souvent :

   ```bash
   sudo mariadb
   ```

   `sudo` peut demander le mot de passe de ta session Ubuntu. Dans MariaDB, quitte avec `exit;`.

## Créer la base et le compte MariaDB

### 1. Importer le schéma initial

Depuis le terminal Linux, dans le dossier du projet :

```bash
sudo mariadb < schema.sql
```

Cette commande crée la base `mramani_lab`, ses tables, le compte administrateur désactivé et les cinq défis initiaux. **À faire une seule fois sur une nouvelle base** : le fichier ajoute les défis de départ et ne doit pas être réimporté à chaque démarrage.

Pour vérifier que la base et ses tables existent :

```bash
sudo mariadb -e "SHOW TABLES FROM mramani_lab;"
```

### 2. Créer un compte applicatif dédié

N’utilise pas le compte MariaDB `root` dans l’application. Ouvre le client MariaDB :

```bash
sudo mariadb
```

À l’invite `MariaDB>`, crée le compte. Remplace `CHOISIS_UN_MOT_DE_PASSE_FORT` par un secret neuf. Ne le partage pas et ne le mets pas dans ce document :

```sql
CREATE USER IF NOT EXISTS 'mramani_lab_app'@'localhost' IDENTIFIED BY 'CHOISIS_UN_MOT_DE_PASSE_FORT';
ALTER USER 'mramani_lab_app'@'localhost' IDENTIFIED BY 'CHOISIS_UN_MOT_DE_PASSE_FORT';
EXIT;
```

La seconde commande fixe aussi le mot de passe si le compte existait déjà. Utilise exactement le même secret dans `.env` à l’étape suivante.

Ensuite, depuis le terminal Linux, applique les droits minimaux du projet :

```bash
sudo mariadb < least_privilege.sql
```

Vérifie les droits attribués :

```bash
sudo mariadb -e "SHOW GRANTS FOR 'mramani_lab_app'@'localhost';"
```

Le script retire les privilèges précédents de ce compte, puis accorde uniquement les opérations utilisées par l’application sur les tables `users`, `challenges` et `solves`. Il ne donne ni accès global, ni droit de créer/modifier le schéma, ni possibilité de changer les rôles. Il est prévu pour le compte `mramani_lab_app`.

## Migrer une ancienne installation

Cette section sert uniquement si tu as déjà une installation qui utilise l’ancien dossier et la base `biohack_medctf`. Elle conserve les comptes, les défis et les résultats en copiant la base. **Ne supprime pas l’ancienne base avant d’avoir vérifié la nouvelle installation.**

### 1. Arrêter et sauvegarder

Arrête Flask avec `Ctrl+C`. Depuis un terminal, sauvegarde la base existante dans ton dossier personnel :

```bash
umask 077
sudo mariadb-dump --single-transaction biohack_medctf > "$HOME/mramani_lab_backup.sql"
```

Le fichier de sauvegarde contient des données de comptes : garde-le privé.

### 2. Renommer le dossier du projet

Si ton dossier est encore dans `Downloads/BioHack_MedCTF_SVT_4eme`, déplace-le sous son nouveau nom :

```bash
mv "$HOME/Downloads/BioHack_MedCTF_SVT_4eme/BioHack_MedCTF_SVT" "$HOME/Downloads/M'ramani_Lab"
rmdir "$HOME/Downloads/BioHack_MedCTF_SVT_4eme" 2>/dev/null || true
cd "$HOME/Downloads/M'ramani_Lab"
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

L’environnement virtuel contient des chemins absolus et ne doit pas être déplacé : le recréer après le déplacement évite les erreurs de lancement.

### 3. Copier les données dans la nouvelle base

Crée la nouvelle base, puis importe la sauvegarde :

```bash
sudo mariadb -e "CREATE DATABASE mramani_lab CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mariadb mramani_lab < "$HOME/mramani_lab_backup.sql"
sudo mariadb mramani_lab < migrate_flag_prefix.sql
```

Si `mramani_lab` existe déjà, arrête-toi et vérifie son contenu avant de continuer : ne réimporte pas la sauvegarde dans une base déjà remplie.

### 4. Créer le nouveau compte applicatif et appliquer ses droits

Dans MariaDB, crée `mramani_lab_app` avec un nouveau mot de passe fort (ne le partage pas) :

```bash
sudo mariadb
```

À l’invite `MariaDB>`, exécute, en remplaçant le texte entre apostrophes par ton nouveau mot de passe :

```sql
CREATE USER 'mramani_lab_app'@'localhost' IDENTIFIED BY 'NOUVEAU_SECRET_FORT';
EXIT;
```

Puis, dans le terminal Linux :

```bash
sudo mariadb < least_privilege.sql
```

### 5. Mettre à jour `.env` et tester

Dans le fichier `.env` déjà existant, change seulement `MYSQL_USER` en `mramani_lab_app`, `MYSQL_DATABASE` en `mramani_lab` et `MYSQL_PASSWORD` en le nouveau secret choisi. Conserve ta clé `FLASK_SECRET_KEY` actuelle pour éviter d’invalider les sessions inutilement. Ne remplace pas tout `.env` par le modèle, car cela effacerait tes paramètres privés.

Vérifie la connexion et les défis :

```bash
source .venv/bin/activate
python -c "import app; c=app.get_db_connection(); print('Connexion MariaDB OK' if c else 'Connexion MariaDB échouée'); c and c.close()"
python app.py
```

Connecte-toi et confirme que les comptes et les défis sont présents. Une fois tout vérifié et une sauvegarde conservée, tu peux supprimer l’ancienne base et l’ancien compte MariaDB si tu n’en as plus besoin. Ne lance pas de commande `DROP` avant d’avoir validé la migration.

## Configurer le fichier `.env`

Le fichier `.env.example` est un modèle ; l’application charge le fichier **`.env`**. Crée-le :

```bash
cp .env.example .env
```

Ouvre `.env` dans un éditeur, par exemple `nano .env`, et remplace au minimum :

```dotenv
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=mramani_lab_app
MYSQL_PASSWORD=LE_MEME_SECRET_QUE_DANS_MARIADB
MYSQL_DATABASE=mramani_lab
COOKIE_SECURE=false
```

Pour générer une clé Flask aléatoire, garde l’environnement `.venv` actif et lance :

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copie le résultat dans `FLASK_SECRET_KEY` de `.env`. Garde-le privé et stable : si tu le changes, les sessions existantes seront invalidées. L’application peut aussi générer une clé locale persistante si elle détecte la valeur fictive du modèle.

Enregistre `.env`, puis vérifie que le fichier est ignoré par Git. **Ne publie et ne partage jamais `.env`** : il contient des secrets. Les paramètres SMTP sont facultatifs ; laisse `SMTP_ENABLED=False` si tu n’actives pas les courriels.

## Créer le compte administrateur

Le pseudo initial est `prof_admin`. Il n’existe **aucun mot de passe par défaut**. Après avoir configuré `.env` et créé la base, active `.venv` puis exécute :

```bash
flask --app app set-admin-password
```

Le terminal demande deux fois un nouveau mot de passe d’au moins 12 caractères ; la saisie reste masquée. Connecte-toi ensuite avec le pseudo `prof_admin` et ce mot de passe.

Si tu oublies ce mot de passe, relance cette commande pour le remplacer. Si la commande dit que le compte n’existe pas, vérifie que `schema.sql` a été importé dans la base configurée dans `.env`.

## Lancer et utiliser la plateforme

Dans le dossier du projet, avec l’environnement virtuel actif :

```bash
python app.py
```

Ouvre ensuite **http://127.0.0.1:5000** sur le même ordinateur. Garde le terminal ouvert pendant l’utilisation ; `Ctrl+C` arrête le serveur.

- Les élèves choisissent **Créer un compte**, puis se connectent.
- Le professeur se connecte avec `prof_admin` et le mot de passe défini plus haut.
- L’administrateur gère les défis depuis **Administration**.

### Accès depuis un autre appareil du réseau local

Le serveur écoute sur les interfaces réseau. Sur l’ordinateur qui l’héberge, trouve l’adresse locale avec :

```bash
hostname -I
```

Sur un autre appareil du même réseau, ouvre `http://ADRESSE_LOCALE:5000` (remplace `ADRESSE_LOCALE` par l’adresse affichée). Le pare-feu peut nécessiter une règle limitée au réseau de l’école. Cet accès HTTP est adapté à un essai local uniquement : les données de connexion ne sont pas chiffrées en HTTP.

## Format des réponses aux défis

Chaque réponse doit respecter le format **`M_LabCTF{REPONSE}`**, par exemple `M_LabCTF{AUGCCUAAGUGA}`. Le texte entre accolades accepte les lettres ASCII, chiffres, `_`, `.` et `-` (1 à 110 caractères). La validation est faite côté serveur lors de la création, de la modification et de l’envoi d’une réponse. Le flag attendu n’est pas transmis au navigateur élève.

Si une base existante contient encore des flags au format précédent ou des réponses libres, exécute une fois la migration depuis le terminal Linux :

```bash
sudo mariadb mramani_lab < migrate_flag_prefix.sql
```

La migration normalise les anciennes réponses pour les placer dans le nouveau format. Vérifie ensuite les défis depuis l’administration. Ne réimporte pas `schema.sql` pour effectuer cette mise à jour.

### Mettre à jour les catégories des défis

Les catégories disponibles sont désormais des matières générales : Mathématiques, Informatique, Physique-Chimie, Robotique, Électronique, Intelligence artificielle, Sciences du vivant et Technologie. Après cette mise à jour du code, applique une fois la migration aux bases déjà créées :

```bash
sudo mariadb mramani_lab < migrate_categories.sql
```

Les anciennes catégories des défis sont converties en « Sciences du vivant ». Une nouvelle installation utilise déjà les catégories à jour via `schema.sql` ; ne relance pas cette migration sur une ancienne base après l’avoir déjà appliquée.

## Tests

Active `.venv`, puis lance les tests automatisés :

```bash
python -m compileall -q app.py tests
python -m unittest discover -s tests -v
```

Les tests vérifient notamment les en-têtes HTTP, le CSRF, les rôles élève/admin, les flags, les privilèges prévus et l’absence de construction SQL par interpolation. Les tests ne remplacent pas un audit de sécurité ni un test complet du déploiement réel.

## Sécurité et limites de déploiement

- Les valeurs SQL variables sont transmises séparément avec des curseurs préparés côté serveur. Ne construis jamais une requête SQL en concaténant une entrée utilisateur.
- Les actions de modification utilisent un jeton CSRF ; les sessions ont des cookies `HttpOnly` et `SameSite=Lax`. Les routes élèves et admin vérifient le rôle côté serveur et en base.
- Les réponses HTTP incluent une CSP avec nonce, des protections anti-iframe, `nosniff`, COOP/COEP/CORP, une politique de référent et de permissions, ainsi que des règles de cache. CORS n’est pas activé. HSTS n’est envoyé que sur HTTPS.
- En local HTTP, laisse `COOKIE_SECURE=false`. Pour une utilisation réelle sur le réseau, configure HTTPS et `COOKIE_SECURE=true`, puis déploie derrière un serveur WSGI et un proxy TLS configurés correctement. Le serveur intégré de Flask sert au développement et ne doit pas être exposé directement à Internet.
- Le limiteur de tentatives est stocké en mémoire dans un processus Python. Pour plusieurs workers ou plusieurs serveurs, il faut un limiteur partagé et une configuration de déploiement adaptée.
- Les courriels de notification sont facultatifs. Le journal `activite_eleves.log` peut contenir des informations personnelles et les réponses envoyées ; protège l’accès au fichier et respecte les règles de l’école concernant ces données.
- Les mots de passe ne doivent pas être réutilisés. Tout secret déjà communiqué ou inscrit dans un historique doit être remplacé.

## Dépannage

### `ModuleNotFoundError: No module named 'flask'`

Active l’environnement virtuel, puis installe les dépendances :

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### « Erreur de connexion à la base de données » ou erreur MariaDB `1698`/`1045`

Vérifie que MariaDB fonctionne, que `.env` existe (et non seulement `.env.example`), que ses paramètres correspondent à la base `mramani_lab` et au compte `mramani_lab_app`, et que tu as appliqué `least_privilege.sql`. Ubuntu peut refuser l’authentification par mot de passe de `root` ; l’application doit utiliser le compte dédié configuré dans `.env`.

Pour tester les paramètres sans afficher le mot de passe :

```bash
source .venv/bin/activate
python -c "import app; c=app.get_db_connection(); print('Connexion MariaDB OK' if c else 'Connexion MariaDB échouée'); c and c.close()"
```

### `sudo mariadb` fonctionne mais les commandes `CREATE USER` donnent une erreur dans Bash

`CREATE USER`, `ALTER USER` et `GRANT` sont des commandes SQL. Il faut d’abord lancer `sudo mariadb` et attendre l’invite `MariaDB>`, puis taper les commandes SQL. Pour revenir à Bash, tape `exit;`.

### La connexion de l’administrateur échoue

Le compte est `prof_admin`, sans mot de passe par défaut. Configure `.env`, vérifie l’import du schéma, puis définis/réinitialise le mot de passe avec `flask --app app set-admin-password`.

### Le changement de code ne s’affiche pas

Arrête le serveur avec `Ctrl+C`, relance `python app.py`, puis actualise le navigateur. Un rechargement forcé peut être nécessaire pour les feuilles CSS.

## Organisation des fichiers

```text
app.py                    Application Flask, routes, validations et accès MariaDB
schema.sql                Création initiale de la base, des tables et des défis
least_privilege.sql       Privilèges MariaDB minimaux pour le compte applicatif
migrate_flag_prefix.sql   Migration des flags vers M_LabCTF{...}
migrate_categories.sql    Migration des catégories vers les matières générales
requirements.txt          Dépendances Python
.env.example              Modèle de configuration (à copier vers .env)
static/css/style.css      Styles et thèmes clair/sombre
templates/                Pages HTML rendues par Flask/Jinja
tests/test_security.py    Tests automatisés des contrôles de sécurité
activite_eleves.log       Journal créé à l’exécution (ne pas publier)
```
