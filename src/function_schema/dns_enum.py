"""
Phase 1 — Passive/Active Reconnaissance
DNS Enumeration: resolve DNS records, find subdomains via zone transfer attempts
Requires: dnspython (pip install dnspython)
"""
import subprocess


class DNSEnum:
    def __init__(self):
        self.name = "dns_enum"
        self.description = "Recon: enumerate DNS records (A, MX, NS, TXT, CNAME) and attempt zone transfer"

    def execute(self, target: str, record_types: str = "A,MX,NS,TXT,CNAME") -> str:
        results = []
        types = [r.strip().upper() for r in record_types.split(",")]

        for record_type in types:
            try:
                result = subprocess.run(
                    ["dig", "+noall", "+answer", record_type, target],
                    capture_output=True, text=True, timeout=15
                )
                output = result.stdout.strip()
                if output:
                    results.append(f"[{record_type}]\n{output}")
            except subprocess.TimeoutExpired:
                results.append(f"[{record_type}] timeout")
            except FileNotFoundError:
                return "Error: dig not installed. Run: apt install dnsutils"
            except Exception as e:
                results.append(f"[{record_type}] Error: {e}")

        # Attempt zone transfer
        try:
            ns_result = subprocess.run(
                ["dig", "+short", "NS", target],
                capture_output=True, text=True, timeout=10
            )
            nameservers = [ns.strip() for ns in ns_result.stdout.strip().split("\n") if ns.strip()]
            for ns in nameservers[:2]:
                axfr = subprocess.run(
                    ["dig", "AXFR", target, f"@{ns}"],
                    capture_output=True, text=True, timeout=15
                )
                if "Transfer failed" not in axfr.stdout and axfr.stdout.strip():
                    results.append(f"[ZONE TRANSFER via {ns}]\n{axfr.stdout[:500]}")
        except Exception:
            pass

        return f"DNS enumeration for {target}:\n\n" + "\n\n".join(results) if results else f"No DNS records found for {target}"