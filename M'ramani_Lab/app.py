import os
import re
import secrets
import hashlib
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock
from time import monotonic
from flask import Flask, abort, g, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
configured_secret = os.getenv("FLASK_SECRET_KEY")
if (configured_secret and len(configured_secret) >= 32
    and hashlib.sha256(configured_secret.encode("utf-8")).hexdigest()
        != "1049c9da70d6398d53eb31ee0265a83888dc29e9dd67d1534ac97f52002758e3"
    and not configured_secret.startswith("GENEREZ_")):
    app.secret_key = configured_secret
else:
    # Generate a persistent local key instead of relying on a public/default secret.
    os.makedirs(app.instance_path, mode=0o700, exist_ok=True)
    os.chmod(app.instance_path, 0o700)
    secret_path = os.path.join(app.instance_path, ".flask_secret_key")
    try:
        secret_fd = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        os.chmod(secret_path, 0o600)
        with open(secret_path, "r", encoding="ascii") as secret_file:
            app.secret_key = secret_file.read().strip()
    else:
        with os.fdopen(secret_fd, "w", encoding="ascii") as secret_file:
            app.secret_key = secrets.token_urlsafe(48)
            secret_file.write(app.secret_key)

app.config.update(
    SESSION_COOKIE_NAME="__Host-mramani_lab_session" if cookie_secure else "mramani_lab_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=cookie_secure,
    SESSION_COOKIE_PATH="/",
    SESSION_COOKIE_DOMAIN=None,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=64 * 1024,
)

_rate_lock = Lock()
_rate_limits = {}
_DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_urlsafe(32))
FLAG_PATTERN = re.compile(r"M_LabCTF\{[A-Za-z0-9_.-]{1,110}\}\Z")
CHALLENGE_CATEGORIES = (
    "Mathématiques",
    "Informatique",
    "Physique-Chimie",
    "Robotique",
    "Électronique",
    "Intelligence artificielle",
    "Sciences du vivant",
    "Technologie",
)
LEGACY_CATEGORY_DISPLAY = {
    "Immunologie & Vaccins": "Sciences du vivant",
    "Génétique & CRISPR": "Sciences du vivant",
    "Système Nerveux & Imagerie": "Sciences du vivant",
    "Cardiologie & Réanimation": "Sciences du vivant",
    "Microbiologie & Antibiogramme": "Sciences du vivant",
}

def display_challenge_category(category):
    return LEGACY_CATEGORY_DISPLAY.get(category, category)

def is_valid_flag(value):
    return isinstance(value, str) and FLAG_PATTERN.fullmatch(value) is not None

def rate_limit_exceeded(bucket, limit, window_seconds):
    """Simple per-process throttle; configure a shared limiter for multi-worker deployments."""
    now = monotonic()
    with _rate_lock:
        attempts = [stamp for stamp in _rate_limits.get(bucket, []) if now - stamp < window_seconds]
        if len(attempts) >= limit:
            _rate_limits[bucket] = attempts
            return True
        attempts.append(now)
        _rate_limits[bucket] = attempts
        if len(_rate_limits) > 5000:
            expired = [key for key, stamps in _rate_limits.items() if not stamps or now - stamps[-1] >= window_seconds]
            for key in expired:
                _rate_limits.pop(key, None)
            if len(_rate_limits) > 5000:
                oldest = sorted(_rate_limits, key=lambda key: _rate_limits[key][-1])[:1000]
                for key in oldest:
                    _rate_limits.pop(key, None)
        return False

@app.before_request
def protect_requests():
    g.csp_nonce = secrets.token_urlsafe(18)
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        supplied_token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        expected_token = session.get("_csrf_token", "")
        if not supplied_token or not secrets.compare_digest(supplied_token, expected_token):
            if request.is_json:
                return jsonify({"status": "error", "message": "Requête expirée. Rechargez la page et réessayez."}), 400
            abort(400, description="Jeton de sécurité absent ou invalide. Rechargez la page.")

@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=(), "
        "accelerometer=(), gyroscope=(), magnetometer=()"
    )
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Embedder-Policy", "require-corp")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("X-DNS-Prefetch-Control", "off")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault(
        "Content-Security-Policy",
        f"default-src 'none'; script-src 'self' 'nonce-{g.csp_nonce}'; "
        "script-src-attr 'none'; style-src 'self'; style-src-attr 'none'; "
        "font-src 'self'; img-src 'self'; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
        "frame-src 'none'; frame-ancestors 'none'; manifest-src 'self'; worker-src 'self'"
    )
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    if not request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    if request.endpoint == "logout":
        response.headers["Clear-Site-Data"] = '"cookies"'
    return response

@app.context_processor
def inject_security_helpers():
    return {"csrf_token": lambda: session.get("_csrf_token", ""), "csp_nonce": lambda: g.csp_nonce}

@app.cli.command("set-admin-password")
def set_admin_password():
    """Set a new password for the seeded administrator account."""
    import getpass
    password = getpass.getpass("Nouveau mot de passe admin (12 caractères minimum) : ")
    confirmation = getpass.getpass("Confirmer le mot de passe : ")
    if len(password) < 12 or len(password) > 256 or password != confirmation:
        raise SystemExit("Mot de passe invalide ou confirmation différente.")
    conn = get_db_connection()
    if not conn:
        raise SystemExit("Connexion à la base de données impossible.")
    cursor = get_prepared_cursor(conn)
    cursor.execute(
        "UPDATE users SET password_hash = %s WHERE username = %s AND role = %s",
        (generate_password_hash(password), "prof_admin", "admin")
    )
    conn.commit()
    updated = cursor.rowcount
    cursor.close()
    conn.close()
    if not updated:
        raise SystemExit("Compte admin prof_admin absent. Importez d’abord schema.sql.")
    print("Mot de passe administrateur mis à jour.")

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            user=os.getenv("MYSQL_USER", "mramani_lab_app"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "mramani_lab"),
            connection_timeout=5,
        )
        return conn
    except Error as e:
        print(f"[ERREUR MYSQL] Impossible de se connecter : {e}")
        return None

def get_prepared_cursor(conn, dictionary=False):
    """Crée un curseur utilisant des requêtes préparées côté serveur."""
    return conn.cursor(prepared=True, dictionary=dictionary)

def notify_teacher(subject, body):
    """Enregistre chaque événement dans un journal et envoie un email au professeur si SMTP est activé."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {subject} | {body}\n"
    log_fd = os.open("activite_eleves.log", os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    os.fchmod(log_fd, 0o600)
    with os.fdopen(log_fd, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)

    if os.getenv("SMTP_ENABLED", "False").lower() == "true":
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = f"[M'ramani_Lab] {subject}"
            msg["From"] = os.getenv("SMTP_EMAIL")
            msg["To"] = os.getenv("TEACHER_EMAIL")

            with smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT", 587))) as server:
                server.starttls()
                server.login(os.getenv("SMTP_EMAIL"), os.getenv("SMTP_PASSWORD"))
                server.send_message(msg)
        except Exception as e:
            print(f"[ALERTE SMTP] Échec d'envoi email : {e}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Veuillez vous connecter pour accéder à M'ramani_Lab.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        conn = get_db_connection()
        if not conn:
            abort(503, description="Vérification du compte indisponible.")
        cursor = get_prepared_cursor(conn)
        cursor.execute("SELECT role FROM users WHERE id = %s", (session.get("user_id"),))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user or user[0] != "admin":
            session.clear()
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "student":
            abort(403)
        conn = get_db_connection()
        if not conn:
            abort(503, description="Vérification du compte indisponible.")
        cursor = get_prepared_cursor(conn)
        cursor.execute("SELECT role FROM users WHERE id = %s", (session.get("user_id"),))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user or user[0] != "student":
            session.clear()
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def recalculate_student_scores(cursor):
    """Synchronise les scores avec les défis encore publiés et résolus."""
    cursor.execute("""
        UPDATE users AS u
        SET score = COALESCE((
                SELECT SUM(c.points)
                FROM solves AS s
                JOIN challenges AS c ON c.id = s.challenge_id
                WHERE s.user_id = u.id AND s.is_correct = TRUE
            ), 0),
            last_solve = (
                SELECT MAX(s.solved_at)
                FROM solves AS s
                WHERE s.user_id = u.id AND s.is_correct = TRUE
            )
        WHERE u.role = 'student'
    """)

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if rate_limit_exceeded(("register", request.remote_addr), 8, 3600):
            flash("Trop de tentatives d’inscription. Réessayez plus tard.", "danger")
            return redirect(url_for("register"))

        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        classe = request.form.get("classe", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        email = email.lower()

        if (not all([username, full_name, classe, email, password])
                or len(username) > 50 or len(full_name) > 100 or len(classe) > 30
                or len(email) > 120 or len(password) < 12 or len(password) > 256
                or "@" not in email):
            flash("Vérifiez les champs. Le mot de passe doit contenir au moins 12 caractères.", "danger")
            return redirect(url_for("register"))

        conn = get_db_connection()
        if not conn:
            flash("Erreur de connexion à la base de données MySQL.", "danger")
            return redirect(url_for("register"))

        cursor = get_prepared_cursor(conn, dictionary=True)
        try:
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            if cursor.fetchone():
                flash("Ce pseudo ou cette adresse e-mail est déjà utilisé.", "danger")
                return redirect(url_for("register"))

            pw_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, full_name, classe, email, password_hash) VALUES (%s, %s, %s, %s, %s)",
                (username, full_name, classe, email, pw_hash)
            )
            conn.commit()
        except Error:
            conn.rollback()
            flash("Inscription impossible. Vérifiez le pseudo et l’adresse e-mail.", "danger")
            return redirect(url_for("register"))
        finally:
            cursor.close()
            conn.close()

        notify_teacher(
            "Nouvelle inscription élève",
            f"Un nouveau compte élève a été créé : @{username}, classe {classe}."
        )
        flash("Inscription réussie ! Vous pouvez maintenant vous connecter.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or len(username) > 50 or len(password) > 256:
            flash("Identifiant ou mot de passe incorrect.", "danger")
            return redirect(url_for("login"))

        account_bucket = ("login-account", request.remote_addr, username[:50].lower())
        address_bucket = ("login-address", request.remote_addr)
        if (rate_limit_exceeded(account_bucket, 8, 900)
            or rate_limit_exceeded(address_bucket, 30, 900)):
            flash("Trop de tentatives. Patientez 15 minutes avant de réessayer.", "danger")
            return redirect(url_for("login"))

        conn = get_db_connection()
        if not conn:
            flash("Erreur de connexion à la base de données MySQL.", "danger")
            return redirect(url_for("login"))

        cursor = get_prepared_cursor(conn, dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

        stored_hash = user["password_hash"] if user else _DUMMY_PASSWORD_HASH
        try:
            is_valid = check_password_hash(stored_hash, password)
        except (ValueError, TypeError):
            is_valid = False

        if user and is_valid:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["classe"] = user["classe"]
            session["role"] = user["role"]
            session.permanent = True
            flash(f"Bonjour {user['full_name']}, vous êtes connecté.", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin_panel"))
            return redirect(url_for("dashboard"))
        else:
            flash("Identifiant ou mot de passe incorrect.", "danger")

    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
@student_required
def dashboard():
    conn = get_db_connection()
    if not conn:
        flash("Connexion à la base de données impossible.", "danger")
        abort(503, description="Base de données temporairement indisponible.")
    cursor = get_prepared_cursor(conn, dictionary=True)

    # Récupérer infos de l'utilisateur et son rang
    cursor.execute("SELECT id, username, full_name, classe, score FROM users WHERE role = 'student' ORDER BY score DESC, last_solve ASC")
    ranking = cursor.fetchall()

    user_rank = "-"
    user_score = 0
    for idx, student in enumerate(ranking, start=1):
        if student["id"] == session["user_id"]:
            user_rank = idx
            user_score = student["score"]
            break

    # Récupérer tous les défis
    # Never send answer flags to the browser: they must remain server-side.
    cursor.execute("SELECT id, title, category, difficulty, points, clinical_context, lab_data, hint FROM challenges ORDER BY points ASC")
    challenges = cursor.fetchall()
    for challenge in challenges:
        challenge["category"] = display_challenge_category(challenge["category"])

    # Récupérer les défis déjà résolus par cet élève
    cursor.execute("SELECT DISTINCT challenge_id FROM solves WHERE user_id = %s AND is_correct = TRUE", (session["user_id"],))
    solved_ids = {row["challenge_id"] for row in cursor.fetchall()}

    # Compter le nombre de résolutions par défi
    cursor.execute("SELECT challenge_id, COUNT(DISTINCT user_id) as solve_count FROM solves WHERE is_correct = TRUE GROUP BY challenge_id")
    solve_counts = {row["challenge_id"]: row["solve_count"] for row in cursor.fetchall()}

    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        challenges=challenges,
        solved_ids=solved_ids,
        solve_counts=solve_counts,
        user_rank=user_rank,
        user_score=user_score,
        total_students=len(ranking)
    )

@app.route("/submit_flag", methods=["POST"])
@login_required
@student_required
def submit_flag():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Requête invalide."}), 400
    try:
        challenge_id = int(data.get("challenge_id"))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Défi invalide."}), 400
    submitted_flag = data.get("flag", "")
    if not isinstance(submitted_flag, str) or not is_valid_flag(submitted_flag.strip()):
        return jsonify({"status": "error", "message": "Réponse invalide."}), 400
    submitted_flag = submitted_flag.strip()
    if (rate_limit_exceeded(("flag-user", session["user_id"]), 20, 60)
            or rate_limit_exceeded(("flag-address", request.remote_addr), 60, 60)):
        return jsonify({"status": "error", "message": "Trop de tentatives. Attendez une minute."}), 429

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Service temporairement indisponible."}), 503
    cursor = get_prepared_cursor(conn, dictionary=True)

    # Serialize submissions by this account to prevent double scoring from parallel requests.
    cursor.execute("SELECT id, role FROM users WHERE id = %s FOR UPDATE", (session["user_id"],))
    submitting_user = cursor.fetchone()
    if not submitting_user or submitting_user["role"] != "student":
        cursor.close()
        conn.close()
        session.clear()
        return jsonify({"status": "error", "message": "Session expirée. Reconnectez-vous."}), 401

    cursor.execute("SELECT * FROM challenges WHERE id = %s", (challenge_id,))
    challenge = cursor.fetchone()
    if not challenge:
        cursor.close()
        conn.close()
        return jsonify({"status": "error", "message": "Défi introuvable."}), 404

    # Vérifier si déjà validé
    cursor.execute("SELECT id FROM solves WHERE user_id = %s AND challenge_id = %s AND is_correct = TRUE", (session["user_id"], challenge_id))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"status": "info", "message": "Vous avez déjà validé ce cas clinique !"})

    is_correct = (submitted_flag == challenge["flag"])

    # Enregistrer la tentative (bonne ou mauvaise) pour le suivi du professeur
    cursor.execute(
        "INSERT INTO solves (user_id, challenge_id, submitted_flag, is_correct) VALUES (%s, %s, %s, %s)",
        (session["user_id"], challenge_id, submitted_flag, is_correct)
    )

    if is_correct:
        cursor.execute(
            "UPDATE users SET score = score + %s, last_solve = NOW() WHERE id = %s",
            (challenge["points"], session["user_id"])
        )
        conn.commit()
        notify_teacher(
            f"FLAG VALIDÉ (+{challenge['points']} pts)",
            f"Élève : {session['full_name']} ({session['classe']}) a résolu '{challenge['title']}'."
        )
        cursor.close()
        conn.close()
        return jsonify({
            "status": "success",
            "message": f"Bonne réponse. {challenge['points']} points ont été ajoutés à votre score."
        })
    else:
        conn.commit()
        notify_teacher(
            "Tentative échouée",
            f"Élève : {session['full_name']} ({session['classe']}) a soumis une réponse incorrecte pour '{challenge['title']}'."
        )
        cursor.close()
        conn.close()
        return jsonify({
            "status": "error",
            "message": "Ce n’est pas la bonne réponse. Relisez les indices et réessayez."
        })

@app.route("/scoreboard")
@login_required
@student_required
def scoreboard():
    conn = get_db_connection()
    if not conn:
        flash("Connexion à la base de données impossible.", "danger")
        return redirect(url_for("dashboard"))
    cursor = get_prepared_cursor(conn, dictionary=True)

    cursor.execute("""
        SELECT u.id, u.username, u.full_name, u.classe, u.score, u.last_solve,
               COUNT(DISTINCT s.challenge_id) AS solved_count
        FROM users u
        LEFT JOIN solves s ON u.id = s.user_id AND s.is_correct = TRUE
        WHERE u.role = 'student'
        GROUP BY u.id
        ORDER BY u.score DESC, u.last_solve ASC, u.created_at ASC
    """)
    leaderboard = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as total FROM challenges")
    total_challenges = cursor.fetchone()["total"]

    cursor.close()
    conn.close()

    return render_template("scoreboard.html", leaderboard=leaderboard, total_challenges=total_challenges)

@app.route("/admin", methods=["GET", "POST"])
@login_required
@admin_required
def admin_panel():
    conn = get_db_connection()
    if not conn:
        flash("Connexion à la base de données impossible.", "danger")
        return redirect(url_for("admin_panel"))
    cursor = get_prepared_cursor(conn, dictionary=True)

    # Permet au professeur d'ajouter un nouveau défi CTF directement depuis l'interface
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "")
        difficulty = request.form.get("difficulty", "")
        try:
            points = int(request.form.get("points", "100"))
        except ValueError:
            points = 0
        clinical_context = request.form.get("clinical_context", "").strip()
        lab_data = request.form.get("lab_data", "").strip()
        hint = request.form.get("hint", "").strip()
        flag = request.form.get("flag", "").strip()

        allowed_difficulties = {"Facile", "Moyen", "Difficile", "Expert"}
        if (not all([title, clinical_context, lab_data, hint, flag])
            or len(title) > 120 or not is_valid_flag(flag) or points > 1000000
                or category not in CHALLENGE_CATEGORIES or difficulty not in allowed_difficulties
                or points <= 0):
            cursor.close()
            conn.close()
            flash("Vérifiez les champs. La réponse attendue doit respecter le format M_LabCTF{REPONSE}.", "danger")
            return redirect(url_for("admin_panel"))

        cursor.execute(
            """INSERT INTO challenges (title, category, difficulty, points, clinical_context, lab_data, hint, flag)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (title, category, difficulty, points, clinical_context, lab_data, hint, flag)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Nouveau cas clinique CTF publié avec succès !", "success")
        return redirect(url_for("admin_panel"))

    # Liste complète des élèves inscrits avec emails et scores
    cursor.execute("SELECT * FROM users WHERE role = 'student' ORDER BY score DESC, created_at DESC")
    students = cursor.fetchall()

    # Journal en temps réel de toutes les soumissions (réussies et échouées)
    cursor.execute("""
        SELECT s.id, s.submitted_flag, s.is_correct, s.solved_at,
               u.full_name, u.username, u.classe, u.email,
               c.title AS challenge_title, c.points
        FROM solves s
        JOIN users u ON s.user_id = u.id
        JOIN challenges c ON s.challenge_id = c.id
        ORDER BY s.solved_at DESC
        LIMIT 100
    """)
    recent_submissions = cursor.fetchall()

    cursor.execute("SELECT * FROM challenges ORDER BY id ASC")
    challenges = cursor.fetchall()
    for challenge in challenges:
        challenge["category"] = display_challenge_category(challenge["category"])

    cursor.close()
    conn.close()

    return render_template(
        "admin.html",
        students=students,
        recent_submissions=recent_submissions,
        challenges=challenges,
        categories=CHALLENGE_CATEGORIES
    )

@app.route("/admin/challenges/<int:challenge_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_challenge(challenge_id):
    conn = get_db_connection()
    if not conn:
        flash("Connexion à la base de données impossible.", "danger")
        return redirect(url_for("admin_panel"))

    cursor = get_prepared_cursor(conn, dictionary=True)
    cursor.execute("SELECT * FROM challenges WHERE id = %s", (challenge_id,))
    challenge = cursor.fetchone()
    if not challenge:
        cursor.close()
        conn.close()
        flash("Défi introuvable.", "danger")
        return redirect(url_for("admin_panel"))
    challenge["category"] = display_challenge_category(challenge["category"])

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "")
        difficulty = request.form.get("difficulty", "")
        clinical_context = request.form.get("clinical_context", "").strip()
        lab_data = request.form.get("lab_data", "").strip()
        hint = request.form.get("hint", "").strip()
        flag = request.form.get("flag", "").strip()
        try:
            points = int(request.form.get("points", ""))
        except ValueError:
            points = 0

        allowed_difficulties = {"Facile", "Moyen", "Difficile", "Expert"}
        if (not all([title, clinical_context, lab_data, hint, flag])
                or category not in CHALLENGE_CATEGORIES
                or difficulty not in allowed_difficulties
            or points <= 0 or points > 1000000
            or len(title) > 120 or not is_valid_flag(flag)):
            flash("Vérifiez les champs. La réponse attendue doit respecter le format M_LabCTF{REPONSE}.", "danger")
        else:
            cursor.execute(
                """UPDATE challenges
                   SET title = %s, category = %s, difficulty = %s, points = %s,
                       clinical_context = %s, lab_data = %s, hint = %s, flag = %s
                   WHERE id = %s""",
                (title, category, difficulty, points, clinical_context, lab_data, hint, flag, challenge_id)
            )
            recalculate_student_scores(cursor)
            conn.commit()
            cursor.close()
            conn.close()
            flash("Défi modifié. Les scores des élèves ont été recalculés.", "success")
            return redirect(url_for("admin_panel"))

        challenge.update({
            "title": title,
            "category": category,
            "difficulty": difficulty,
            "points": points,
            "clinical_context": clinical_context,
            "lab_data": lab_data,
            "hint": hint,
            "flag": flag,
        })

    cursor.close()
    conn.close()
    return render_template(
        "edit_challenge.html", challenge=challenge, categories=CHALLENGE_CATEGORIES
    )

@app.route("/admin/challenges/<int:challenge_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_challenge(challenge_id):
    conn = get_db_connection()
    if not conn:
        flash("Connexion à la base de données impossible.", "danger")
        return redirect(url_for("admin_panel"))

    cursor = get_prepared_cursor(conn)
    cursor.execute("DELETE FROM challenges WHERE id = %s", (challenge_id,))
    if cursor.rowcount:
        # La clé étrangère supprime aussi les tentatives liées au défi.
        recalculate_student_scores(cursor)
        conn.commit()
        flash("Défi supprimé. Ses tentatives associées ont été effacées et les scores recalculés.", "success")
    else:
        conn.rollback()
        flash("Défi introuvable ou déjà supprimé.", "warning")
    cursor.close()
    conn.close()
    return redirect(url_for("admin_panel"))

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
