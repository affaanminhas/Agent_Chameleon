"""
Phase 1 — Active Reconnaissance
Subdomain enumeration via wordlist bruteforce + certificate transparency logs
Requires: requests (pip install requests)
"""
import socket
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


# Common subdomains wordlist — extend as needed
COMMON_SUBDOMAINS = [
    "www", "mail", "ftp", "admin", "api", "dev", "staging", "test",
    "portal", "vpn", "remote", "blog", "shop", "secure", "app",
    "cdn", "static", "images", "assets", "login", "dashboard",
    "support", "help", "docs", "wiki", "git", "gitlab", "jenkins",
    "jira", "confluence", "monitor", "status", "mx", "smtp", "pop",
    "imap", "ns1", "ns2", "dns", "backup", "db", "database", "mysql",
    "redis", "elastic", "kibana", "grafana", "prometheus"
]


class SubdomainEnum:
    def __init__(self):
        self.name = "subdomain_enum"
        self.description = "Active recon: enumerate subdomains via wordlist bruteforce and certificate transparency logs"

    def execute(self, target: str, use_crt_sh: bool = True, threads: int = 20) -> str:
        found = set()

        # 1. Certificate transparency logs (passive, no noise)
        if use_crt_sh:
            try:
                resp = requests.get(
                    f"https://crt.sh/?q=%.{target}&output=json",
                    timeout=15
                )
                if resp.status_code == 200:
                    for entry in resp.json():
                        name = entry.get("name_value", "")
                        for subdomain in name.split("\n"):
                            subdomain = subdomain.strip().lstrip("*.")
                            if subdomain.endswith(target):
                                found.add(subdomain)
            except Exception as e:
                pass

        # 2. Wordlist bruteforce via DNS resolution
        def resolve(sub):
            hostname = f"{sub}.{target}"
            try:
                ip = socket.gethostbyname(hostname)
                return f"{hostname} → {ip}"
            except socket.gaierror:
                return None

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {executor.submit(resolve, sub): sub for sub in COMMON_SUBDOMAINS}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    found.add(result)

        if found:
            sorted_results = sorted(found)
            return f"Subdomains found for {target} ({len(sorted_results)} total):\n" + "\n".join(sorted_results)
        return f"No subdomains found for {target}"