"""Mocked SDK tests: no test key or vendor content is sent to a provider."""
import json
import os
import types
import unittest
from unittest.mock import MagicMock, patch

import ai_service as ai


def extraction(**overrides):
    result = {field: "" for field in ai.EXTRACTION_FIELDS}
    result.update({"document_type": "GST_CERTIFICATE", "document_subtype": "GST_REGISTRATION_CERTIFICATE",
                   "document_title": "Registration Certificate", "classification_evidence": "Form GST REG-06",
                   "registration_form": "GST REG-06", "legal_name": "Example Synthetic Private Limited",
                   "trade_name": "Example Synthetic", "gstin": "29ABCDE1234F1ZW"})
    result.update(overrides)
    return result


class ExtractionSchemaTests(unittest.TestCase):
    def test_gst_structured_evidence_and_trade_name_preserved(self):
        result = ai.validate_extraction(extraction())
        self.assertEqual(result["document_type"], "GST_CERTIFICATE")
        self.assertNotEqual(result["legal_name"], result["trade_name"])

    def test_certificate_requires_both_heading_and_form(self):
        for updates in ({"document_title": "GSTIN information"}, {"registration_form": ""}, {"classification_evidence": ""}):
            result = ai.validate_extraction(extraction(**updates))
            self.assertEqual(result["document_type"], "OTHER")

    def test_all_document_subtypes(self):
        for subtype in ai.DOCUMENT_SUBTYPES["OTHER"]:
            result = ai.validate_extraction(extraction(document_type="OTHER", document_subtype=subtype))
            self.assertEqual(result["document_type"], "OTHER")
        for subtype in ai.DOCUMENT_SUBTYPES["BANK_PROOF"]:
            result = ai.validate_extraction(extraction(document_type="BANK_PROOF", document_subtype=subtype,
                                                      classification_evidence="Account holder"))
            self.assertEqual(result["document_type"], "BANK_PROOF")

    def test_invalid_response_never_silently_accepted(self):
        for invalid in ([], None, "not-json", {}, {**extraction(), "gstin": None},
                        {**extraction(), "document_type": "APPROVED"},
                        {**extraction(), "document_subtype": "INVENTED"},
                        {**extraction(), "document_subtype": "GSTIN_INFOGRAPHIC"},
                        {**extraction(), "legal_name": "x" * 4001}):
            with self.subTest(invalid_type=type(invalid).__name__):
                with self.assertRaises(ValueError):
                    ai.validate_extraction(invalid)

    def test_extra_keys_removed_and_values_not_invented(self):
        result = ai.validate_extraction(extraction(legal_name="", invented_decision="APPROVED"))
        self.assertNotIn("invented_decision", result)
        self.assertEqual(result["legal_name"], "")

    def test_fabricated_appearance_does_not_claim_authenticity(self):
        result = ai.validate_extraction(extraction())
        self.assertNotIn("authenticity", result)
        self.assertNotIn("decision", result)
        # A plausible category alone can never establish the separate authenticity state.
        from validation import check_authenticity
        self.assertEqual(check_authenticity(result["document_type"])["outcome"], "PENDING")


class GeminiContractTests(unittest.TestCase):
    def fake_sdk(self, text=None, error=None, close_error=None):
        client = MagicMock()
        if error:
            client.models.generate_content.side_effect = error
        else:
            client.models.generate_content.return_value.text = text if text is not None else json.dumps(extraction())
        if close_error:
            client.close.side_effect = close_error
        sdk = types.ModuleType("google.genai")
        sdk.Client = MagicMock(return_value=client)
        sdk_types = types.ModuleType("google.genai.types")
        sdk_types.HttpOptions = MagicMock(side_effect=lambda **kw: kw)
        sdk_types.HttpRetryOptions = MagicMock(side_effect=lambda **kw: kw)
        sdk_types.GenerateContentConfig = MagicMock(side_effect=lambda **kw: kw)
        sdk_types.Part = types.SimpleNamespace(from_bytes=MagicMock(side_effect=lambda **kw: kw))
        sdk.types = sdk_types
        google = types.ModuleType("google")
        google.genai = sdk
        return client, sdk, {"google": google, "google.genai": sdk, "google.genai.types": sdk_types}

    def test_success_explicit_credentials_and_timeout(self):
        client, sdk, modules = self.fake_sdk()
        with patch.dict("sys.modules", modules):
            result, error = ai.extract_document("GST_CERTIFICATE", b"synthetic bytes", "application/pdf",
                                                api_key="mock-key-never-sent", model="mock-model")
        self.assertIsNone(error)
        self.assertEqual(result["document_type"], "GST_CERTIFICATE")
        self.assertEqual(sdk.Client.call_args.kwargs["http_options"]["timeout"], 60000)
        self.assertEqual(sdk.Client.call_args.kwargs["http_options"]["retry_options"]["attempts"], 1)
        self.assertEqual(client.models.generate_content.call_args.kwargs["model"], "mock-model")
        client.close.assert_called_once()

    def test_timeout_outage_invalid_json_and_response(self):
        configurations = ({"error": TimeoutError("secret-token request contents")},
                          {"error": ConnectionError("private bank account")},
                          {"text": "not valid JSON"}, {"text": "[]"}, {"text": "{}"})
        for config in configurations:
            with self.subTest(config=list(config)):
                client, _, modules = self.fake_sdk(**config)
                with patch.dict("sys.modules", modules):
                    result, error = ai.extract_document("GST_CERTIFICATE", b"synthetic", "application/pdf", api_key="mock-key")
                self.assertIsNone(result)
                self.assertIsInstance(error, str)
                self.assertNotIn("secret-token", error)
                self.assertNotIn("private bank account", error)
                client.close.assert_called_once()

    def test_api_http_status_only_is_reported(self):
        class ProviderError(Exception):
            code = 503
        client, _, modules = self.fake_sdk(error=ProviderError("provider details secret"))
        with patch.dict("sys.modules", modules):
            _, error = ai.extract_document("BANK_PROOF", b"synthetic", "image/png", api_key="mock-key")
        self.assertIn("HTTP 503", error)
        self.assertNotIn("provider details", error)

    def test_close_failure_does_not_escape_return_contract(self):
        _, _, modules = self.fake_sdk(close_error=RuntimeError("cleanup secret"))
        with patch.dict("sys.modules", modules):
            result, error = ai.extract_document("GST_CERTIFICATE", b"synthetic", "application/pdf", api_key="mock-key")
        self.assertIsNotNone(result)
        self.assertIsNone(error)

    def test_missing_key_and_unsupported_inputs_do_not_call_api(self):
        _, sdk, modules = self.fake_sdk()
        with patch.dict("sys.modules", modules), patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(ai.extract_document("GST_CERTIFICATE", b"synthetic", "application/pdf")[0])
            self.assertIsNone(ai.extract_document("UNKNOWN", b"synthetic", "application/pdf", api_key="mock-key")[0])
            self.assertIsNone(ai.extract_document("GST_CERTIFICATE", b"synthetic", "application/msword", api_key="mock-key")[0])
            self.assertIsNone(ai.extract_document("GST_CERTIFICATE", b"", "application/pdf", api_key="mock-key")[0])
        sdk.Client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
