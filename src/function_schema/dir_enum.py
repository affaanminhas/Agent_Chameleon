"""
Phase 2 — Scanning & Enumeration
Directory enumeration: bruteforce web paths to find hidden endpoints
Reveals admin panels, config files, backup files
Requires: gobuster (apt install gobuster) or falls back to dirb
"""
import subprocess


# Embedded minimal wordlist — no file dependency
# For serious engagements, point wordlist_path to /usr/share/wordlists/dirb/common.txt
MINI_WORDLIST = [
    "admin", "login", "dashboard", "api", "config", "backup", "test",
    "dev", "staging", "wp-admin", "wp-login", "phpmyadmin", "panel",
    "manager", "console", "portal", ".env", ".git", "robots.txt",
    "sitemap.xml", "web.config", "phpinfo.php", "info.php", "server-status",
    "uploads", "files", "images", "static", "assets", "js", "css",
    "docs", "swagger", "api/v1", "api/v2", "graphql", "metrics",
    "health", "status", "actuator", "debug", "trace"
]


class DirEnum:
    def __init__(self):
        self.name = "dir_enum"
        self.description = "Web enumeration: bruteforce directories and files on a web server to find hidden endpoints"

    def execute(self, target: str, port: int = 80, ssl: bool = False, wordlist_path: str = "") -> str:
        protocol = "https" if ssl else "http"
        url = f"{protocol}://{target}:{port}"

        # Try gobuster first
        try:
            if wordlist_path:
                wordlist_arg = wordlist_path
            else:
                # Write mini wordlist to temp file
                import tempfile, os
                tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
                tmp.write("\n".join(MINI_WORDLIST))
                tmp.close()
                wordlist_arg = tmp.name

            cmd = [
                "gobuster", "dir",
                "-u", url,
                "-w", wordlist_arg,
                "-t", "20",
                "--no-progress",
                "-q"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if wordlist_path == "":
                os.unlink(wordlist_arg)

            output = result.stdout.strip()
            if output:
                return f"Directory enumeration results for {url}:\n{output}"
            return f"No directories found on {url}"

        except FileNotFoundError:
            pass  # gobuster not found, fall through

        # Fallback: simple requests-based check
        try:
            import requests
            from concurrent.futures import ThreadPoolExecutor, as_completed

            found = []

            def check_path(path):
                try:
                    resp = requests.get(f"{url}/{path}", timeout=5, allow_redirects=False)
                    if resp.status_code not in [404, 400]:
                        return f"/{path} [{resp.status_code}]"
                except Exception:
                    return None

            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = {executor.submit(check_path, path): path for path in MINI_WORDLIST}
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        found.append(result)

            if found:
                return f"Directory enumeration results for {url}:\n" + "\n".join(sorted(found))
            return f"No accessible paths found on {url}"

        except Exception as e:
            return f"Error: {e}"