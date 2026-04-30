"""
Phase 2 — Scanning & Enumeration
Nikto: web server vulnerability scanner
Checks for dangerous files, outdated software, misconfigurations
Requires: nikto installed (apt install nikto)
"""
import subprocess
import re


class Nikto:
    def __init__(self):
        self.name = "nikto_scan"
        self.description = "Web scanning: scan a web server for vulnerabilities, misconfigs, and dangerous files using Nikto"

    def execute(self, target: str, port: int = 80, ssl: bool = False) -> str:
        try:
            cmd = ["nikto", "-h", target, "-p", str(port), "-Format", "txt", "-nointeractive"]
            if ssl:
                cmd.append("-ssl")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            output = result.stdout.strip()

            if not output:
                return f"Nikto returned no output for {target}:{port}"

            # Filter to the most useful lines
            useful_lines = []
            for line in output.split("\n"):
                line = line.strip()
                if line.startswith("+") or line.startswith("-"):
                    useful_lines.append(line)

            if useful_lines:
                return f"Nikto scan results for {target}:{port}:\n" + "\n".join(useful_lines)
            return output[:2000]

        except subprocess.TimeoutExpired:
            return "Nikto scan timeout (180s)"
        except FileNotFoundError:
            return "Error: nikto not installed. Run: apt install nikto"
        except Exception as e:
            return f"Error: {e}"