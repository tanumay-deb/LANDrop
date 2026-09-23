"""
End-to-end integration test for two live LANDrop instances forming a cluster.
Instance 1 (Port 5801): Primary Leader
Instance 2 (Port 5802): Secondary Node joining Leader
"""

import time
import unittest
from werkzeug.serving import make_server
import threading

from core.server import LandropServer


class ServerRunner(threading.Thread):
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
        self.srv.shutdown()
        self.server_obj.shutdown()


class TestMeshLiveCluster(unittest.TestCase):
    def test_two_hosts_cluster_formation(self):
        # 1. Start Host 1 (PC)
        host1 = LandropServer(port=5801, enable_mesh=True)
        runner1 = ServerRunner(host1, 5801)
        runner1.start()

        # Give host 1 a moment to initialize as leader
        time.sleep(1.5)
        self.assertEqual(host1.mesh.role, "leader")

        # 2. Start Host 2 (Laptop)
        host2 = LandropServer(port=5802, enable_mesh=True)
        runner2 = ServerRunner(host2, 5802)
        runner2.start()

        # Wait for discovery and registration
        time.sleep(2.0)

        try:
            # Host 2 should detect Host 1 and assume 'node' role
            self.assertEqual(host2.mesh.role, "node")
            self.assertIsNotNone(host2.mesh.leader_info)
            self.assertEqual(host2.mesh.leader_info.get("port"), 5801)

            # Host 1 should have Host 2 registered in its cluster
            nodes_1 = host1.mesh.get_nodes_list()
            self.assertTrue(len(nodes_1) >= 2)
            registered_ports = [n.get("port") for n in nodes_1]
            self.assertIn(5801, registered_ports)
            self.assertIn(5802, registered_ports)

            # Test cross-host clipboard sync from Host 2 to Host 1
            host2.mesh.broadcast_clipboard_mesh("Synced from Laptop 5802!")
            time.sleep(1.0)
            self.assertEqual(host1.clipboard_content, "Synced from Laptop 5802!")

        finally:
            runner2.shutdown()
            runner1.shutdown()


if __name__ == "__main__":
    unittest.main()
