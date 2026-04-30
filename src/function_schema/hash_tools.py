"""
Phase 3 — Gaining Access
Hash tools: identify hash type and attempt to crack using hashcat/john
Requires: hashcat or john (apt install hashcat john)
"""
import subprocess
import re


# Hash format signatures for identification
HASH_SIGNATURES = [
    (r"^\$2[ayb]\$.{56}$", "bcrypt"),
    (r"^\$6\$.{8,16}\$.{86}$", "sha512crypt"),
    (r"^\$5\$.{8,16}\$.{43}$", "sha256crypt"),
    (r"^\$1\$.{8}\$.{22}$", "md5crypt"),
    (r"^[a-f0-9]{32}$", "MD5"),
    (r"^[a-f0-9]{40}$", "SHA1"),
    (r"^[a-f0-9]{56}$", "SHA224"),
    (r"^[a-f0-9]{64}$", "SHA256"),
    (r"^[a-f0-9]{96}$", "SHA384"),
    (r"^[a-f0-9]{128}$", "SHA512"),
    (r"^[a-f0-9]{8}:[a-f0-9]{32}$", "NTLM (with salt)"),
    (r"^[A-Z]{13}$", "ROT13"),
]

# Hashcat mode map
HASHCAT_MODES = {
    "MD5": "0",
    "SHA1": "100",
    "SHA256": "1400",
    "SHA512": "1700",
    "NTLM": "1000",
    "md5crypt": "500",
    "sha512crypt": "1800",
    "bcrypt": "3200",
}


class HashTools:
    def __init__(self):
        self.name = "hash_tools"
        self.description = (
            "Post-exploitation: identify hash type and attempt to crack hashes "
            "using hashcat or john the ripper"
        )

    def execute(
        self,
        hash_value: str,
        action: str = "identify",
        wordlist: str = "/usr/share/wordlists/rockyou.txt",
        hash_type: str = ""
    ) -> str:

        hash_value = hash_value.strip()

        if action == "identify":
            return self._identify(hash_value)

        elif action == "crack":
            identified = hash_type or self._identify_type(hash_value)
            if not identified:
                return f"Could not identify hash type for: {hash_value}"
            return self._crack(hash_value, identified, wordlist)

        return f"Unknown action: {action}. Use 'identify' or 'crack'"

    def _identify(self, hash_value: str) -> str:
        hash_type = self._identify_type(hash_value)
        if hash_type:
            mode = HASHCAT_MODES.get(hash_type, "unknown")
            return (
                f"Hash: {hash_value}\n"
                f"Type: {hash_type}\n"
                f"Hashcat mode: {mode}\n"
                f"To crack: use action='crack'"
            )
        return f"Could not identify hash type for: {hash_value}\nLength: {len(hash_value)}"

    def _identify_type(self, hash_value: str) -> str:
        for pattern, name in HASH_SIGNATURES:
            if re.match(pattern, hash_value, re.IGNORECASE):
                return name
        return ""

    def _crack(self, hash_value: str, hash_type: str, wordlist: str) -> str:
        import tempfile, os

        # Write hash to temp file
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        tmp.write(hash_value)
        tmp.close()

        try:
            # Try hashcat first
            mode = HASHCAT_MODES.get(hash_type)
            if mode:
                cmd = [
                    "hashcat", "-m", mode,
                    tmp.name, wordlist,
                    "--quiet", "--potfile-disable"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                output = result.stdout.strip()

                if ":" in output:
                    cracked = output.split(":")[-1]
                    return f"✅ Hash cracked!\nHash: {hash_value}\nPlaintext: {cracked}"
                return f"Hashcat could not crack hash with wordlist: {wordlist}"

            # Fallback to john
            cmd = ["john", "--wordlist=" + wordlist, tmp.name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            show = subprocess.run(["john", "--show", tmp.name], capture_output=True, text=True)
            if show.stdout.strip():
                return f"John cracked:\n{show.stdout.strip()}"

            return "Could not crack hash with provided wordlist"

        except FileNotFoundError:
            return "Error: hashcat/john not installed. Run: apt install hashcat john"
        except subprocess.TimeoutExpired:
            return "Hash cracking timeout (120s)"
        except Exception as e:
            return f"Error: {e}"
        finally:
            os.unlink(tmp.name)