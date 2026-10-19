"""Verify SQLite/files/audit survive a separate Python process restart locally."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class RestartPersistenceTests(unittest.TestCase):
    def test_storage_survives_process_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ, VENDENCE_DATA_DIR=directory)
            source = '''
import database as db
from tests.test_workflow import DATA, Upload
db.initialize_database()
sid = db.create_vendor_submission(**DATA)
u = Upload()
document = db.save_document(sid, 'GST_CERTIFICATE', u.name, u.getvalue(), 'image/png')
db.save_extraction(document, {'synthetic': 'saved extraction'})
db.revise_submission(sid, DATA, 1, correction_reason='Synthetic correction reuses saved extraction.')
db.log_event(sid, 'RESTART_TEST', 'SUCCESS', 'Synthetic restart persistence test.')
print(sid)
'''
            first = subprocess.run([sys.executable, "-c", source], env=environment, capture_output=True, text=True, check=True)
            sid = int(first.stdout.strip())
            check = '''
import database as db, json
from pathlib import Path
db.initialize_database()
rows = db.get_submissions(); sid = rows[0]['submission_id']
docs = db.get_documents(sid)
print(json.dumps({'count':len(rows), 'sid':sid, 'file_exists':Path(docs[0]['file_path']).is_file(),
                  'event_preserved':any(e['stage']=='RESTART_TEST' for e in db.get_events(sid)),
                  'revision':db.get_submission(sid)['current_revision'],
                  'extraction_count':db.get_connection().execute('SELECT count(*) FROM document_extractions').fetchone()[0]}))
'''
            second = subprocess.run([sys.executable, "-c", check], env=environment, capture_output=True, text=True, check=True)
            result = json.loads(second.stdout)
            self.assertEqual(result, {"count": 1, "sid": sid, "file_exists": True, "event_preserved": True,
                                      "revision": 2, "extraction_count": 1})
