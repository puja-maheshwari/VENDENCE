import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from config import load_local_env, public_configuration_errors, setting


class ConfigurationTests(unittest.TestCase):
    def test_literal_env_loading_precedence_and_no_execution(self):
        with tempfile.TemporaryDirectory() as t, patch.dict(os.environ, {"GEMINI_MODEL": "configured-model"}, clear=True):
            path = Path(t) / ".env"
            path.write_text('GEMINI_MODEL=other-model\nVENDENCE_DATA_DIR="literal$(command)"\nSMTP_PASSWORD=ignored\nHOME=ignored\n# comment\nGEMINI_API_KEY=\n')
            load_local_env(path)
            self.assertEqual(os.environ["GEMINI_MODEL"], "configured-model")
            self.assertEqual(os.environ["VENDENCE_DATA_DIR"], "literal$(command)")
            self.assertNotIn("SMTP_PASSWORD", os.environ)
            self.assertNotIn("HOME", os.environ)
            self.assertNotIn("GEMINI_API_KEY", os.environ)

    def test_secret_fallback_and_environment_precedence(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(setting("GEMINI_API_KEY", {"GEMINI_API_KEY": "test"}), "test")
            os.environ["GEMINI_API_KEY"] = "preferred"
            self.assertEqual(setting("GEMINI_API_KEY", {"GEMINI_API_KEY": "test"}), "preferred")

    def test_public_security_configuration(self):
        with patch.dict(os.environ, {"VENDENCE_PUBLIC": "1"}, clear=True):
            self.assertEqual(len(public_configuration_errors()), 3)
            os.environ.update(VENDENCE_ACCESS_PASSWORD="AccessExample123", VENDENCE_REVIEWER_PASSWORD="ReviewExample123", VENDENCE_DATA_DIR="/data")
            self.assertEqual(public_configuration_errors(), [])
