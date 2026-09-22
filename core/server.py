"""
Flask Server for LANDrop.
Provides REST and SSE endpoints for Safe List folder exploration,
Auto-Save file uploads, clipboard synchronization, and media previews.
"""

import datetime
import io
import json
import mimetypes
import os
import queue
import time
import zipfile
from pathlib import Path
from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
)
from flask_cors import CORS

from core.config import config
from core.network import (
    ZeroconfBroadcaster,
    generate_qr_png_bytes,
    get_connection_urls,
    get_hostname,
    get_local_ip,
)


def format_size(size_bytes: int) -> str:
    """Formats bytes into human readable string (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_file_type_category(filename: str, is_dir: bool = False) -> str:
    """Classifies a file by extension for UI icons and filters."""
    if is_dir:
        return "folder"

    ext = os.path.splitext(filename)[1].lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico", ".heic"}:
        return "image"
    elif ext in {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv"}:
        return "video"
    elif ext in {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}:
        return "audio"
    elif ext in {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".md", ".csv"}:
        return "document"
    elif ext in {".zip", ".tar", ".gz", ".7z", ".rar", ".bz2"}:
        return "archive"
    elif ext in {".py", ".js", ".html", ".css", ".json", ".ts", ".c", ".cpp", ".java", ".go", ".rs", ".sql"}:
        return "code"
    else:
        return "file"


class LandropServer:
    def __init__(self, port: int = 5000):
        self.port = port
        self.base_dir = Path(__file__).resolve().parent.parent
        self.template_dir = self.base_dir / "templates"
        self.static_dir = self.base_dir / "static"

        self.app = Flask(
            __name__,
            template_folder=str(self.template_dir),
            static_folder=str(self.static_dir),
        )
        CORS(self.app)

        # Start Zeroconf mDNS broadcaster for permanent landrop.local address
        self.broadcaster = ZeroconfBroadcaster(name="landrop", port=self.port)
        self.broadcaster.start()

        # In-memory shared state
        self.clipboard_content = ""
        self.clipboard_updated_at = None
        self.received_files_history = []
        self.event_subscribers: list[queue.Queue] = []
        self.activity_callbacks = []

        self._register_routes()

    def shutdown(self):
        """Stops background workers and unregisters mDNS services."""
        if hasattr(self, "broadcaster") and self.broadcaster:
            try:
                self.broadcaster.stop()
            except Exception:
                pass

    def add_activity_callback(self, callback):
        """Registers a callback for desktop GUI activity logging."""
        self.activity_callbacks.append(callback)

    def log_activity(self, message: str, event_type: str = "info"):
        """Logs an activity event and notifies desktop GUI callbacks."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        for cb in self.activity_callbacks:
            try:
                cb(formatted, event_type)
            except Exception:
                pass

    def broadcast_event(self, event_data: dict):
        """Broadcasts an SSE event to all connected web clients."""
        payload = json.dumps(event_data)
        for q in list(self.event_subscribers):
            try:
                q.put_nowait(payload)
            except Exception:
                if q in self.event_subscribers:
                    self.event_subscribers.remove(q)

    def _register_routes(self):
        app = self.app

        @app.route("/")
        def index():
            return render_template("index.html")

        @app.route("/finder")
        def finder():
            return render_template("finder.html")

        @app.route("/api/info")
        def api_info():
            urls = get_connection_urls(self.port)
            safe_folders = config.get_safe_folders()
            return jsonify({
                "app": "LANDrop",
                "hostname": urls["hostname"],
                "landrop_url": urls["landrop_url"],
                "mdns_url": urls["mdns_url"],
                "primary_ip": urls["primary_ip"],
                "primary_url": urls["primary_url"],
                "all_urls": urls["all_urls"],
                "port": self.port,
                "auto_save": config.auto_save_enabled,
                "save_directory": config.save_directory,
                "safe_folders_count": len(safe_folders),
                "has_clipboard": bool(self.clipboard_content),
            })

        # --- Safe List Endpoints ---

        @app.route("/api/safelist")
        def api_safelist():
            """Returns list of all exposed Safe List folders."""
            result = []
            for folder in config.get_safe_folders():
                folder_path = folder["path"]
                exists = os.path.exists(folder_path) and os.path.isdir(folder_path)
                item_count = 0
                if exists:
                    try:
                        item_count = len(os.listdir(folder_path))
                    except Exception:
                        item_count = 0

                result.append({
                    "id": folder["id"],
                    "name": folder["name"],
                    "path": folder_path,
                    "exists": exists,
                    "item_count": item_count,
                })
            return jsonify({"folders": result})

        @app.route("/api/safelist/browse")
        def api_safelist_browse():
            """
            Browses files and subdirectories inside a safe folder.
            Query params: folder_id (required), subpath (optional relative path)
            """
            folder_id = request.args.get("folder_id", "")
            subpath = request.args.get("subpath", "").strip()

            if not folder_id:
                return jsonify({"error": "folder_id is required"}), 400

            safe_folder = config.get_safe_folder_by_id(folder_id)
            if not safe_folder:
                return jsonify({"error": "Safe folder not found"}), 404

            try:
                real_target = config.resolve_safe_path(folder_id, subpath)
            except PermissionError as pe:
                return jsonify({"error": str(pe)}), 403
            except (FileNotFoundError, KeyError) as fe:
                return jsonify({"error": str(fe)}), 404

            if not os.path.isdir(real_target):
                return jsonify({"error": "Path is not a directory"}), 400

            # Build breadcrumbs
            norm_subpath = subpath.replace("\\", "/").strip("/")
            parts = [p for p in norm_subpath.split("/") if p]
            breadcrumbs = [{"name": safe_folder["name"], "subpath": ""}]
            accum = []
            for part in parts:
                accum.append(part)
                breadcrumbs.append({"name": part, "subpath": "/".join(accum)})

            # Read directory entries
            dirs = []
            files = []
            try:
                with os.scandir(real_target) as entries:
                    for entry in entries:
                        try:
                            # Skip hidden files
                            if entry.name.startswith("."):
                                continue

                            rel_entry_subpath = f"{norm_subpath}/{entry.name}" if norm_subpath else entry.name
                            stat = entry.stat()
                            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

                            if entry.is_dir(follow_symlinks=False):
                                dirs.append({
                                    "name": entry.name,
                                    "is_dir": True,
                                    "subpath": rel_entry_subpath,
                                    "modified": mtime,
                                    "category": "folder",
                                })
                            elif entry.is_file(follow_symlinks=False):
                                size = stat.st_size
                                files.append({
                                    "name": entry.name,
                                    "is_dir": False,
                                    "size": size,
                                    "formatted_size": format_size(size),
                                    "subpath": rel_entry_subpath,
                                    "modified": mtime,
                                    "category": get_file_type_category(entry.name),
                                })
                        except (PermissionError, OSError):
                            continue
            except PermissionError:
                return jsonify({"error": "Permission denied reading folder"}), 403

            # Sort alphabetically (folders first, then files)
            dirs.sort(key=lambda x: x["name"].lower())
            files.sort(key=lambda x: x["name"].lower())

            return jsonify({
                "folder_id": folder_id,
                "folder_name": safe_folder["name"],
                "subpath": norm_subpath,
                "breadcrumbs": breadcrumbs,
                "items": dirs + files,
            })

        @app.route("/api/safelist/download")
        def api_safelist_download():
            """Downloads a file from a Safe List folder with HTTP 206 resume support."""
            folder_id = request.args.get("folder_id", "")
            subpath = request.args.get("subpath", "")

            try:
                real_target = config.resolve_safe_path(folder_id, subpath)
            except PermissionError:
                return jsonify({"error": "Access denied"}), 403
            except Exception as e:
                return jsonify({"error": str(e)}), 404

            if not os.path.isfile(real_target):
                return jsonify({"error": "File not found"}), 404

            filename = os.path.basename(real_target)
            self.log_activity(f"File downloaded: {filename} from {request.remote_addr}")
            return send_file(real_target, as_attachment=True, download_name=filename, conditional=True)

        @app.route("/api/safelist/preview")
        def api_safelist_preview():
            """Streams media/text file inline for in-browser preview."""
            folder_id = request.args.get("folder_id", "")
            subpath = request.args.get("subpath", "")

            try:
                real_target = config.resolve_safe_path(folder_id, subpath)
            except PermissionError:
                return jsonify({"error": "Access denied"}), 403
            except Exception as e:
                return jsonify({"error": str(e)}), 404

            if not os.path.isfile(real_target):
                return jsonify({"error": "File not found"}), 404

            mime_type, _ = mimetypes.guess_type(real_target)
            return send_file(real_target, mimetype=mime_type or "application/octet-stream", conditional=True)

        @app.route("/api/safelist/download-zip")
        def api_safelist_download_zip():
            """Packs a Safe List folder or subfolder into a ZIP and sends it."""
            folder_id = request.args.get("folder_id", "")
            subpath = request.args.get("subpath", "")

            try:
                real_target = config.resolve_safe_path(folder_id, subpath)
            except Exception as e:
                return jsonify({"error": str(e)}), 403

            if not os.path.isdir(real_target):
                return jsonify({"error": "Not a directory"}), 400

            folder_name = os.path.basename(real_target) or "shared_folder"
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for root, _, filenames in os.walk(real_target):
                    for filename in filenames:
                        file_path = os.path.join(root, filename)
                        archive_name = os.path.relpath(file_path, real_target)
                        try:
                            zip_file.write(file_path, archive_name)
                        except (PermissionError, OSError):
                            continue

            zip_buffer.seek(0)
            self.log_activity(f"Folder downloaded as ZIP: {folder_name} by {request.remote_addr}")
            return send_file(
                zip_buffer,
                mimetype="application/zip",
                as_attachment=True,
                download_name=f"{folder_name}.zip",
            )

        # --- Auto-Save Upload Endpoints ---

        @app.route("/api/upload", methods=["POST"])
        def api_upload():
            """
            Handles incoming file uploads.
            Auto-saves directly to the host PC's configured save directory.
            """
            if not config.auto_save_enabled:
                return jsonify({"error": "Auto-Save is disabled on host"}), 403

            if "files" not in request.files and "file" not in request.files:
                return jsonify({"error": "No file uploaded"}), 400

            uploaded_files = request.files.getlist("files") or [request.files.get("file")]
            saved_list = []

            for f in uploaded_files:
                if not f or not f.filename:
                    continue

                original_name = f.filename
                dest_path, final_name = config.get_unique_filepath(original_name)

                # Stream save to disk in chunks to avoid memory overflow
                total_bytes = 0
                with open(dest_path, "wb") as out_file:
                    while True:
                        chunk = f.stream.read(64 * 1024)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        total_bytes += len(chunk)

                file_info = {
                    "filename": final_name,
                    "original_name": original_name,
                    "size": total_bytes,
                    "formatted_size": format_size(total_bytes),
                    "saved_path": dest_path,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "category": get_file_type_category(final_name),
                }
                saved_list.append(file_info)
                self.received_files_history.insert(0, file_info)

                # Keep history reasonable
                if len(self.received_files_history) > 100:
                    self.received_files_history.pop()

                # Notify GUI and SSE
                msg = f"Auto-saved '{final_name}' ({format_size(total_bytes)}) from {request.remote_addr}"
                self.log_activity(msg, event_type="upload")
                self.broadcast_event({
                    "type": "file_received",
                    "file": file_info,
                })

            return jsonify({
                "success": True,
                "saved_count": len(saved_list),
                "saved_files": saved_list,
            })

        @app.route("/api/received")
        def api_received():
            """Lists files in the auto-save directory."""
            save_dir = config.save_directory
            files = []
            if os.path.exists(save_dir) and os.path.isdir(save_dir):
                try:
                    with os.scandir(save_dir) as entries:
                        for entry in entries:
                            if entry.is_file() and not entry.name.startswith("."):
                                stat = entry.stat()
                                size = stat.st_size
                                files.append({
                                    "filename": entry.name,
                                    "size": size,
                                    "formatted_size": format_size(size),
                                    "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                                    "category": get_file_type_category(entry.name),
                                })
                except Exception as e:
                    print(f"Error scanning save directory: {e}")

            files.sort(key=lambda x: x["modified"], reverse=True)
            return jsonify({"files": files, "save_directory": save_dir})

        @app.route("/api/received/download/<filename>")
        def api_received_download(filename: str):
            """Downloads an auto-saved file from the save directory."""
            save_dir = config.save_directory
            safe_name = os.path.basename(filename)
            target = os.path.join(save_dir, safe_name)
            if not os.path.isfile(target):
                return jsonify({"error": "File not found"}), 404
            return send_file(target, as_attachment=True, download_name=safe_name, conditional=True)

        @app.route("/api/received/preview/<filename>")
        def api_received_preview(filename: str):
            """Streams an auto-saved file inline for preview."""
            save_dir = config.save_directory
            safe_name = os.path.basename(filename)
            target = os.path.join(save_dir, safe_name)
            if not os.path.isfile(target):
                return jsonify({"error": "File not found"}), 404
            mime_type, _ = mimetypes.guess_type(target)
            return send_file(target, mimetype=mime_type or "application/octet-stream", conditional=True)

        # --- Shared Clipboard Endpoints ---

        @app.route("/api/clipboard", methods=["GET", "POST"])
        def api_clipboard():
            if request.method == "POST":
                data = request.get_json(silent=True) or {}
                text = data.get("text", "")
                self.clipboard_content = text
                self.clipboard_updated_at = datetime.datetime.now().strftime("%H:%M:%S")

                snippet = (text[:35] + "...") if len(text) > 35 else text
                self.log_activity(f"Clipboard updated from {request.remote_addr}: '{snippet}'")
                self.broadcast_event({
                    "type": "clipboard_updated",
                    "text": self.clipboard_content,
                    "updated_at": self.clipboard_updated_at,
                })
                return jsonify({"success": True, "text": self.clipboard_content})

            return jsonify({
                "text": self.clipboard_content,
                "updated_at": self.clipboard_updated_at,
            })

        # --- Real-Time SSE Stream ---

        @app.route("/api/events")
        def api_events():
            """Server-Sent Events endpoint for real-time reactivity."""
            def event_stream():
                client_queue = queue.Queue()
                self.event_subscribers.append(client_queue)
                try:
                    # Initial heartbeat
                    yield f"data: {json.dumps({'type': 'connected'})}\n\n"
                    while True:
                        try:
                            msg = client_queue.get(timeout=25)
                            yield f"data: {msg}\n\n"
                        except queue.Empty:
                            # Keep-alive heartbeat
                            yield f": heartbeat\n\n"
                except GeneratorExit:
                    if client_queue in self.event_subscribers:
                        self.event_subscribers.remove(client_queue)

            return Response(
                event_stream(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        # --- QR Code Endpoint ---

        @app.route("/api/qr")
        def api_qr():
            """Returns QR code image for connection URL."""
            urls = get_connection_urls(self.port)
            target_url = urls["primary_url"]
            png_bytes = generate_qr_png_bytes(target_url)
            if png_bytes:
                return Response(png_bytes, mimetype="image/png")
            return jsonify({"error": "QR code unavailable"}), 500
