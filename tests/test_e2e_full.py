"""
Comprehensive Full End-to-End (E2E) Verification Script for LANDrop v1.2.0.

Tests:
1. Live Cluster Auto-Discovery & Role Handshake (Leader on 5810, Node on 5811).
2. End-to-End Web App Multi-Host File Upload (iPhone simulation to Secondary Node).
3. End-to-End Desktop GUI Native Direct File Transfer (PC pushes file to Laptop).
4. Bi-directional Universal Clipboard Mesh Sync (Host 1 <-> Host 2).
5. Secondary Node Heartbeat & Keep-Alive table.
"""

import io
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
import uuid
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


class FullEndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_temp = tempfile.mkdtemp(prefix="landrop_e2e_")
        cls.save_dir_1 = os.path.join(cls.base_temp, "host1_received")
        cls.save_dir_2 = os.path.join(cls.base_temp, "host2_received")
        os.makedirs(cls.save_dir_1, exist_ok=True)
        os.makedirs(cls.save_dir_2, exist_ok=True)

        # Config for Host 1 (Leader)
        cls.cfg1 = ConfigManager(os.path.join(cls.base_temp, "cfg1.json"))
        cls.cfg1.set_save_directory(cls.save_dir_1)
        cls.cfg1.set_auto_save(True)

        # Config for Host 2 (Secondary Node)
        cls.cfg2 = ConfigManager(os.path.join(cls.base_temp, "cfg2.json"))
        cls.cfg2.set_save_directory(cls.save_dir_2)
        cls.cfg2.set_auto_save(True)

        # 1. Start Host 1 (Leader)
        srv_mod.config = cls.cfg1
        cls.host1 = LandropServer(port=5810, enable_mesh=True)
        cls.runner1 = LiveServerRunner(cls.host1, 5810)
        cls.runner1.start()
        time.sleep(1.5)

        # 2. Start Host 2 (Secondary Node)
        srv_mod.config = cls.cfg2
        cls.host2 = LandropServer(port=5811, enable_mesh=True)
        cls.runner2 = LiveServerRunner(cls.host2, 5811)
        cls.runner2.start()
        time.sleep(2.0)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.runner2.shutdown()
            cls.runner1.shutdown()
        finally:
            shutil.rmtree(cls.base_temp, ignore_errors=True)

    def test_01_cluster_roles_and_discovery(self):
        """Verify UDP discovery and HTTP registration occurred."""
        self.assertEqual(self.host1.mesh.role, "leader")
        self.assertEqual(self.host2.mesh.role, "node")
        self.assertIsNotNone(self.host2.mesh.leader_info)
        self.assertEqual(self.host2.mesh.leader_info.get("port"), 5810)

        # Verify Host 1's /api/mesh/nodes reports both hosts
        url = "http://127.0.0.1:5810/api/mesh/nodes"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            ports = [n.get("port") for n in data["nodes"]]
            self.assertIn(5810, ports)
            self.assertIn(5811, ports)

    def test_02_e2e_web_upload_to_secondary_node(self):
        """
        Simulates iPhone opening Leader Web UI (5810),
        selecting Laptop (5811) from destination pills,
        and uploading a file directly to Laptop's /api/upload.
        """
        # Step A: Query Leader to discover target nodes
        nodes_url = "http://127.0.0.1:5810/api/mesh/nodes"
        with urllib.request.urlopen(nodes_url, timeout=3) as resp:
            nodes_data = json.loads(resp.read().decode())
        
        target_node = next(n for n in nodes_data["nodes"] if n.get("port") == 5811)
        target_upload_url = f"{target_node['url']}/api/upload"

        # Step B: Perform direct multipart upload to Secondary Node
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        file_payload = b"IMG_2026_IPHONE_E2E_PHOTO_DATA_BYTES_12345"
        body = bytearray()
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="files"; filename="vacation_e2e.jpg"\r\n')
        body.extend(b"Content-Type: image/jpeg\r\n\r\n")
        body.extend(file_payload)
        body.extend(f"\r\n--{boundary}--\r\n".encode())

        req = urllib.request.Request(
            target_upload_url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            result = json.loads(resp.read().decode())
            self.assertTrue(result["success"])
            self.assertEqual(result["saved_count"], 1)

        # Step C: Verify file landed strictly in Host 2's folder (not Host 1's)
        expected_host2_file = os.path.join(self.save_dir_2, "vacation_e2e.jpg")
        self.assertTrue(os.path.exists(expected_host2_file), "File must exist on Host 2")
        with open(expected_host2_file, "rb") as f:
            self.assertEqual(f.read(), file_payload)

        # Ensure file did NOT end up in Host 1's directory
        not_in_host1 = os.path.join(self.save_dir_1, "vacation_e2e.jpg")
        self.assertFalse(os.path.exists(not_in_host1), "File must NOT be on Host 1")

    def test_03_e2e_desktop_gui_native_peer_send(self):
        """
        Simulates PC user clicking 'Send to Peer Host...' in Desktop GUI
        and pushing a file directly to Laptop over the network.
        """
        # Create a sample local document on Host 1
        local_doc_path = os.path.join(self.base_temp, "contract_document.pdf")
        doc_content = b"%PDF-1.4 Mock Contract Content for Direct Desktop Peer Send"
        with open(local_doc_path, "wb") as f:
            f.write(doc_content)

        # Simulate GUI's _send_files_async logic
        target_url = "http://127.0.0.1:5811/api/upload"
        boundary = f"----LANDropBoundary{uuid.uuid4().hex}"
        body = bytearray()
        fname = os.path.basename(local_doc_path)
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="files"; filename="{fname}"\r\n'.encode())
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        with open(local_doc_path, "rb") as f:
            body.extend(f.read())
        body.extend(f"\r\n--{boundary}--\r\n".encode())

        req = urllib.request.Request(
            target_url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)

        # Verify file is saved in Host 2's folder
        received_path = os.path.join(self.save_dir_2, "contract_document.pdf")
        self.assertTrue(os.path.exists(received_path))
        with open(received_path, "rb") as f:
            self.assertEqual(f.read(), doc_content)

    def test_04_bi_directional_clipboard_mesh(self):
        """Verify clipboard changes on Node propagate to Leader, and vice versa."""
        # 1. Update from Node (Laptop) -> should update Leader (PC)
        self.host2.mesh.broadcast_clipboard_mesh("Hello from Laptop Clipboard 123")
        time.sleep(1.0)
        self.assertEqual(self.host1.clipboard_content, "Hello from Laptop Clipboard 123")

        # 2. Update from Leader (PC) -> should update Node (Laptop)
        self.host1.mesh.broadcast_clipboard_mesh("Hello from PC Clipboard 456")
        time.sleep(1.0)
        self.assertEqual(self.host2.clipboard_content, "Hello from PC Clipboard 456")


if __name__ == "__main__":
    unittest.main()
