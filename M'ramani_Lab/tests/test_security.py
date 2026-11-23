import unittest
import ast
from pathlib import Path

import app as application


class SecurityControlsTest(unittest.TestCase):
    def setUp(self):
        self.client = application.app.test_client()

    def test_security_headers_are_present(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertEqual(response.headers["Cross-Origin-Embedder-Policy"], "require-corp")
        self.assertEqual(response.headers["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        csp = response.headers["Content-Security-Policy"]
        self.assertIn("default-src 'none'", csp)
        self.assertIn("script-src-attr 'none'", csp)
        self.assertNotIn("'unsafe-inline'", csp)
        self.assertNotIn("Strict-Transport-Security", response.headers)

    def test_hsts_is_only_sent_for_https(self):
        response = self.client.get("/", base_url="https://localhost")
        self.assertEqual(response.headers["Strict-Transport-Security"], "max-age=31536000")

    def test_state_change_requires_csrf(self):
        response = self.client.post("/login", data={"username": "nobody", "password": "invalid"})
        self.assertEqual(response.status_code, 400)

    def test_application_sql_is_static_and_not_interpolated(self):
        source = Path(application.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        execute_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
        ]
        self.assertTrue(execute_calls, "Aucune requête SQL trouvée")
        for call in execute_calls:
            with self.subTest(line=call.lineno):
                self.assertIsInstance(call.args[0], ast.Constant)
                self.assertIsInstance(call.args[0].value, str)
                self.assertNotIsInstance(call.args[0], ast.JoinedStr)

    def test_cursor_factory_uses_server_prepared_statements(self):
        class FakeConnection:
            def cursor(self, **kwargs):
                return kwargs

        self.assertEqual(
            application.get_prepared_cursor(FakeConnection(), dictionary=True),
            {"prepared": True, "dictionary": True},
        )

    def test_database_grant_script_has_no_excessive_grants(self):
        grant_script = Path(application.app.root_path, "least_privilege.sql").read_text(encoding="utf-8").upper()
        self.assertNotIn("GRANT ALL", grant_script)
        self.assertNotIn(" ON *.* ", grant_script)
        self.assertNotIn("GRANT DELETE ON MRAMANI_LAB.SOLVES", grant_script)
        self.assertIn("INSERT (USERNAME, FULL_NAME, CLASSE, EMAIL, PASSWORD_HASH)", grant_script)
        self.assertIn("UPDATE (PASSWORD_HASH, SCORE, LAST_SOLVE)", grant_script)

    def test_registration_does_not_set_account_role(self):
        source = Path(application.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "INSERT INTO users (username, full_name, classe, email, password_hash)",
            source,
        )
        self.assertNotIn(
            "INSERT INTO users (username, full_name, classe, email, password_hash, role, score)",
            source,
        )

    def test_flag_format_is_branded_and_strict(self):
        self.assertTrue(application.is_valid_flag("M_LabCTF{AUGCCUAAGUGA}"))
        self.assertTrue(application.is_valid_flag("M_LabCTF{5.5_INFARCTUS}"))
        for invalid_flag in (
            "LEGACYCTF{AUGCCUAAGUGA}",
            "M_LabCTF{}",
            "M_LabCTF{AUG CCU}",
            "xM_LabCTF{AUG}",
            "M_LabCTF{AUG}\n",
        ):
            with self.subTest(flag=invalid_flag):
                self.assertFalse(application.is_valid_flag(invalid_flag))

    def test_seeded_flags_use_the_new_prefix(self):
        schema = Path(application.app.root_path, "schema.sql").read_text(encoding="utf-8")
        self.assertIn("M_LabCTF{AUGCCUAAGUGA}", schema)

    def test_challenge_categories_are_school_subjects(self):
        self.assertEqual(
            application.CHALLENGE_CATEGORIES,
            (
                "Mathématiques",
                "Informatique",
                "Physique-Chimie",
                "Robotique",
                "Électronique",
                "Intelligence artificielle",
                "Sciences du vivant",
                "Technologie",
            ),
        )
        schema = Path(application.app.root_path, "schema.sql").read_text(encoding="utf-8")
        self.assertIn("'Sciences du vivant'", schema)
        self.assertNotIn("Immunologie & Vaccins", schema)
        self.assertEqual(
            application.display_challenge_category("Immunologie & Vaccins"),
            "Sciences du vivant",
        )

    def test_admin_cannot_access_student_views_or_submit_flags(self):
        token = "test-csrf-token"
        with self.client.session_transaction() as user_session:
            user_session.update(user_id=1, role="admin", _csrf_token=token)

        self.assertEqual(self.client.get("/dashboard").status_code, 403)
        self.assertEqual(self.client.get("/scoreboard").status_code, 403)
        response = self.client.post(
            "/submit_flag",
            json={"challenge_id": 1, "flag": "M_LabCTF{NOT_A_REAL_FLAG}"},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access_admin_object_routes(self):
        token = "student-csrf-token"
        with self.client.session_transaction() as user_session:
            user_session.update(user_id=2, role="student", _csrf_token=token)

        self.assertEqual(self.client.get("/admin").status_code, 403)
        self.assertEqual(self.client.get("/admin/challenges/1/edit").status_code, 403)
        response = self.client.post(
            "/admin/challenges/1/delete",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 403)

    def test_logout_clears_site_cookies(self):
        token = "test-logout-csrf-token"
        with self.client.session_transaction() as user_session:
            user_session.update(user_id=1, role="student", _csrf_token=token)

        response = self.client.post("/logout", data={"csrf_token": token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Clear-Site-Data"], '"cookies"')


if __name__ == "__main__":
    unittest.main()
