import os
import json
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.parse
from uuid import uuid4
from werkzeug.serving import make_server

from core.config import ConfigManager
import core.server as srv_mod
from core.server import LandropServer

class LiveServerRunner(threading.Thread):
    def __init__(self, server_obj, port: int):
        super().__init__(daemon=True)
        self.server_obj = server_obj
        self.port = port
        self.srv = make_server("0.0.0.0", port, server_obj.app, threaded=True)

    def run(self):
        try:
            self.srv.serve_forever()
        except Exception:
            pass

    def shutdown(self):
        try:
            self.srv.shutdown()
        except Exception:
            pass
        self.server_obj.shutdown()

def multipart_post(url, fields, files):
    boundary = f"----WebKitFormBoundary{uuid4().hex}"
    body = bytearray()
    
    for k, v in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        body.extend(f"{v}\r\n".encode())
        
    for k, filename, content in files:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{k}"; filename="{filename}"\r\n'.encode())
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        body.extend(content)
        body.extend(b"\r\n")
        
    body.extend(f"--{boundary}--\r\n".encode())
    
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode())

class FeaturesE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_temp = tempfile.mkdtemp(prefix="landrop_features_")
        cls.save_dir = os.path.join(cls.base_temp, "received")
        os.makedirs(cls.save_dir, exist_ok=True)

        cls.cfg = ConfigManager(os.path.join(cls.base_temp, "cfg.json"))
        cls.cfg.set_save_directory(cls.save_dir)
        cls.cfg.set_auto_save(True)

        srv_mod.config = cls.cfg
        cls.server = LandropServer(port=5820, enable_mesh=False)
        cls.runner = LiveServerRunner(cls.server, 5820)
        cls.runner.start()
        time.sleep(1.0)

    @classmethod
    def tearDownClass(cls):
        cls.runner.shutdown()
        import shutil
        shutil.rmtree(cls.base_temp, ignore_errors=True)

    def test_01_chunked_upload_folder(self):
        """Test Chunked Upload with relative directory (Simulating Drag and Drop folder)."""
        url = "http://127.0.0.1:5820/api/upload/chunk"
        session_id = uuid4().hex
        
        chunk1 = b"Hello from chunk 1. "
        chunk2 = b"Hello from chunk 2. "
        chunk3 = b"Hello from chunk 3."
        
        # Send chunk 0
        fields = {
            "session_id": session_id,
            "filename": "test_doc.txt",
            "chunk_index": "0",
            "total_chunks": "3",
            "relative_dir": "MyDraggedFolder/Subfolder"
        }
        status, data = multipart_post(url, fields, [("file", "test_doc.txt", chunk1)])
        self.assertEqual(status, 200)
        self.assertFalse(data["completed"])
        
        # Send chunk 1
        fields["chunk_index"] = "1"
        status, data = multipart_post(url, fields, [("file", "test_doc.txt", chunk2)])
        self.assertEqual(status, 200)
        self.assertFalse(data["completed"])

        # Send chunk 2
        fields["chunk_index"] = "2"
        status, data = multipart_post(url, fields, [("file", "test_doc.txt", chunk3)])
        self.assertEqual(status, 200)
        self.assertTrue(data["completed"])
        
        # Verify file on disk
        expected_path = os.path.join(self.save_dir, "MyDraggedFolder", "Subfolder", "test_doc.txt")
        self.assertTrue(os.path.exists(expected_path))
        with open(expected_path, "rb") as f:
            self.assertEqual(f.read(), chunk1 + chunk2 + chunk3)

    def test_02_guest_drop_zone(self):
        """Test creating a Guest Drop Zone and uploading chunks to it."""
        # Create drop zone
        create_url = "http://127.0.0.1:5820/api/drop/create"
        req = urllib.request.Request(create_url, method="POST")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            self.assertTrue(data["success"])
            token = data["token"]
            
        # Verify drop page renders
        drop_page_url = f"http://127.0.0.1:5820/drop/{token}"
        with urllib.request.urlopen(drop_page_url) as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode()
            self.assertIn("Guest Drop Zone", html)
            
        # Upload file via chunked drop api
        upload_url = f"http://127.0.0.1:5820/api/drop/{token}/upload/chunk"
        session_id = uuid4().hex
        
        fields = {
            "session_id": session_id,
            "filename": "guest_photo.jpg",
            "chunk_index": "0",
            "total_chunks": "1",
            "relative_dir": ""
        }
        content = b"fake image bytes here"
        status, res_data = multipart_post(upload_url, fields, [("file", "guest_photo.jpg", content)])
        self.assertEqual(status, 200)
        self.assertTrue(res_data["completed"])
        
        # Verify file is in Guest Drops folder
        expected_path = os.path.join(self.save_dir, "Guest Drops", "guest_photo.jpg")
        self.assertTrue(os.path.exists(expected_path))
        with open(expected_path, "rb") as f:
            self.assertEqual(f.read(), content)

if __name__ == "__main__":
    unittest.main()
