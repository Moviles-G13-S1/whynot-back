"""Local integration-test helper; refuses to access production Firestore."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
    raise RuntimeError("This helper requires the local Firestore emulator")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
from analytics import endpoint
from google.cloud import firestore
from google.auth.credentials import AnonymousCredentials

db = firestore.Client(project="demo-whynot", credentials=AnonymousCredentials())
request = SimpleNamespace(auth=SimpleNamespace(uid="test-admin", token={"admin": True}), data=json.loads(sys.argv[1]))
with patch.object(endpoint.firestore, "client", return_value=db):
    print(json.dumps(endpoint.get_admin_analytics(request)))
