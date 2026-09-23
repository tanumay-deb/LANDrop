"""
Main entry point for LANDrop.
Supports both Desktop GUI (default) and Headless CLI mode (--headless).
"""

import argparse
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.config import config
from core.network import (
    find_available_port,
    get_connection_urls,
    get_hostname,
    get_local_ip,
)
from core.server import LandropServer


def run_headless(port: int = 5000):
    actual_port = find_available_port(port)
    server = LandropServer(port=actual_port)
    urls = get_connection_urls(actual_port)

    print("\n" + "=" * 60)
    print("  🚀 LANDrop Server is ONLINE & READY ON WI-FI")
    print("=" * 60)
    print(f"\n  ⭐ Permanent URL:          {urls['landrop_url']}")
    print(f"  👉 Hostname URL:           {urls['mdns_url']}")
    print(f"  👉 Direct IP URL:          {urls['primary_url']}")
    print(f"  🔍 Network Auto-Finder:    {urls['primary_url']}/finder")
    print("\n  💡 Tip: Bookmark 'http://landrop.local:5000' on your phone.")
    print("  It automatically stays connected even if your router changes your IP!\n")
    print(f"  📁 Auto-Save Destination:  {config.save_directory}")
    print(f"  🔒 Safe List Folders:      {len(config.get_safe_folders())} folder(s) shared")
    print("=" * 60)
    print("  Press Ctrl+C to stop the server.\n")

    def cli_logger(msg, etype="info"):
        print(f"  {msg}")

    server.add_activity_callback(cli_logger)

    try:
        from werkzeug.serving import WSGIRequestHandler
        WSGIRequestHandler.timeout = 15
        server.app.run(host="0.0.0.0", port=actual_port, threaded=True)
    except KeyboardInterrupt:
        print("\n  Shutting down LANDrop server...")
    finally:
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="LANDrop - Wi-Fi File Sharing & Explorer")
    parser.add_argument(
        "--headless",
        "--cli",
        action="store_true",
        help="Run in headless terminal mode without desktop GUI",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.data.get("port", 5000),
        help="Port to run the server on (default: 5000)",
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Start LANDrop minimized directly to the Windows system tray",
    )
    args = parser.parse_args()

    if args.headless:
        run_headless(args.port)
    else:
        try:
            from gui import run_gui
            run_gui(start_minimized=args.minimized)
        except Exception as e:
            print(f"Failed to launch GUI ({e}), falling back to headless CLI mode...\n")
            run_headless(args.port)


if __name__ == "__main__":
    main()
