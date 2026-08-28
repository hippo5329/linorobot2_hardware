#!/usr/bin/env python3
"""
Linorobot2 Robot Configuration Engine - Local HTTP Server with Live Command Execution API
Zero-Dependency, Pure Standard Library Python 3 (Multi-Threaded)

Usage:
    python3 server.py [PORT]
    (Defaults to port 8000)
"""

import os
import sys
import json
import time
import signal
import platform
import threading
import subprocess
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(WEB_DIR, "..", "..", ".."))

active_process = None
active_process_lock = threading.Lock()


import glob
import shutil

def get_robot_host_info():
    info = {
        "system": platform.system(),
        "node": platform.node(),
        "release": platform.release(),
        "machine": platform.machine(),
        "distro_id": "",
        "distro_name": platform.system(),
        "has_apt": shutil.which("apt-get") is not None,
        "has_dnf": shutil.which("dnf") is not None,
        "has_distrobox": shutil.which("distrobox") is not None,
        "is_container": os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"),
        "has_pio": shutil.which("pio") is not None or os.path.exists(os.path.expanduser("~/.platformio/penv/bin/pio")),
        "installed_ros_distros": [],
        "serial_ports": []
    }
    # Check OS Release
    if os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("ID="):
                        info["distro_id"] = line.split("=", 1)[1].strip().strip('"').lower()
                    elif line.startswith("PRETTY_NAME="):
                        info["distro_name"] = line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass

    # Check installed ROS 2 distros
    if os.path.isdir("/opt/ros"):
        try:
            info["installed_ros_distros"] = sorted(os.listdir("/opt/ros"))
        except Exception:
            pass

    # Scan attached MCU serial ports
    patterns = ["/dev/ttyACM*", "/dev/ttyUSB*", "/dev/ttyTHS*", "/dev/serial0"]
    found_ports = []
    for pat in patterns:
        found_ports.extend(glob.glob(pat))
    info["serial_ports"] = sorted(list(set(found_ports)))

    return info


class LinorobotEngineHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return
        return super().do_HEAD()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            host_info = get_robot_host_info()
            status_data = {
                "status": "ok",
                "exec_supported": True,
                "os": host_info["system"],
                "node": host_info["node"],
                "release": host_info["release"],
                "machine": host_info["machine"],
                "distro_id": host_info["distro_id"],
                "distro_name": host_info["distro_name"],
                "has_apt": host_info["has_apt"],
                "has_dnf": host_info["has_dnf"],
                "has_distrobox": host_info["has_distrobox"],
                "is_container": host_info["is_container"],
                "has_pio": host_info["has_pio"],
                "installed_ros_distros": host_info["installed_ros_distros"],
                "serial_ports": host_info["serial_ports"],
                "repo_root": REPO_ROOT
            }
            try:
                self.wfile.write(json.dumps(status_data).encode("utf-8"))
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        try:
            return super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        global active_process
        parsed = urlparse(self.path)

        if parsed.path == "/api/kill":
            with active_process_lock:
                if active_process and active_process.poll() is None:
                    try:
                        active_process.terminate()
                        time.sleep(0.2)
                        if active_process.poll() is None:
                            active_process.kill()
                    except Exception:
                        pass
                    active_process = None

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                self.wfile.write(json.dumps({"status": "killed"}).encode("utf-8"))
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        if parsed.path == "/api/exec":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON: {e}"}).encode("utf-8"))
                return

            command = data.get("command", "").strip()
            cwd = data.get("cwd", REPO_ROOT)
            if not os.path.isabs(cwd):
                cwd = os.path.join(REPO_ROOT, cwd)

            if not command:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Empty command"}).encode("utf-8"))
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            env = os.environ.copy()
            penv_path = os.path.expanduser("~/.platformio/penv/bin")
            local_bin = os.path.expanduser("~/.local/bin")
            env["PATH"] = f"{penv_path}:{local_bin}:{env.get('PATH', '')}"
            if "ROS_DISTRO" not in env or not env["ROS_DISTRO"]:
                env["ROS_DISTRO"] = "jazzy"

            def send_event(event_type, payload):
                msg = f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
                try:
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

            # Adaptive execution: If host lacks /opt/ros but distrobox has jazzy container, route commands into distrobox
            has_distrobox = shutil.which("distrobox") is not None
            has_host_ros = os.path.exists("/opt/ros")
            if (not has_host_ros) and has_distrobox and ("ros2" in command or "source /opt/ros" in command):
                escaped_cmd = command.replace('"', '\\"')
                command = f'distrobox enter jazzy -- bash -c "source /opt/ros/jazzy/setup.bash 2>/dev/null; [ -f /home/ubuntu/box/jazzy/uros_ws/install/setup.bash ] && source /home/ubuntu/box/jazzy/uros_ws/install/setup.bash; {escaped_cmd}"'

            send_event("start", {"command": command, "cwd": cwd})

            try:
                with active_process_lock:
                    active_process = subprocess.Popen(
                        command,
                        cwd=cwd,
                        shell=True,
                        executable="/bin/bash",
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        env=env,
                        preexec_fn=os.setsid if hasattr(os, "setsid") else None
                    )

                if active_process and active_process.stdout:
                    for line in iter(active_process.stdout.readline, ""):
                        if not line:
                            break
                        send_event("output", {"line": line.rstrip("\r\n")})
                    try:
                        active_process.stdout.close()
                    except Exception:
                        pass

                return_code = active_process.wait() if active_process else -1
                with active_process_lock:
                    active_process = None

                send_event("done", {"code": return_code})
                self.close_connection = True

            except Exception as e:
                send_event("error", {"error": str(e)})
                self.close_connection = True
            return

        self.send_response(404)
        self.end_headers()


def run_server(port=PORT):
    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, LinorobotEngineHandler)
    print("=" * 65)
    print(f" 🤖 Linorobot2 Configuration Engine & Multi-Threaded Runner")
    print(f" 🌐 URL: http://localhost:{port}")
    print(f" 📁 Serving Web UI from: {WEB_DIR}")
    print(f" 📂 Repository Root:    {REPO_ROOT}")
    print(f" ⚡ Local Execution API: Active at http://localhost:{port}/api/exec")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Linorobot2 server...")
        httpd.server_close()


if __name__ == "__main__":
    run_server(PORT)
