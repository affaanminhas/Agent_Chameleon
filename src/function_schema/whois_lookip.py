"""
Phase 1 — Passive Reconnaissance
Whois lookup: domain registration, owner, registrar, dates
Requires: whois (pip install python-whois)
"""
import subprocess


class WhoisLookup:
    def __init__(self):
        self.name = "whois_lookup"
        self.description = "Passive recon: lookup domain registration info, owner, registrar, and dates"

    def execute(self, target: str) -> str:
        try:
            result = subprocess.run(
                ["whois", target],
                capture_output=True, text=True, timeout=30
            )
            output = result.stdout.strip()
            if not output:
                return f"No whois data found for {target}"

            # Extract the most useful lines
            useful_keys = [
                "domain name", "registrar", "creation date", "expiry date",
                "updated date", "name server", "registrant", "org", "country",
                "admin email", "tech email"
            ]
            lines = output.split("\n")
            filtered = [
                line for line in lines
                if any(key in line.lower() for key in useful_keys)
                and line.strip() and not line.startswith("%")
            ]

            return f"Whois results for {target}:\n" + "\n".join(filtered[:30]) if filtered else output[:1000]

        except subprocess.TimeoutExpired:
            return "Whois timeout"
        except FileNotFoundError:
            return "Error: whois not installed. Run: apt install whois"
        except Exception as e:
            return f"Error: {e}"