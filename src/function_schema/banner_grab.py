"""
Phase 2 — Scanning & Enumeration
Banner grabbing: connect to open ports and grab service banners
Reveals software versions which inform exploitation phase
Requires: nothing beyond stdlib
"""
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed


class BannerGrab:
    def __init__(self):
        self.name = "banner_grab"
        self.description = "Enumeration: grab service banners from open ports to identify software versions"

    def execute(self, target: str, ports: str = "21,22,23,25,80,443,3306,5432,6379,8080,8443") -> str:
        port_list = [int(p.strip()) for p in ports.split(",")]
        results = []

        # Common probes per port
        probes = {
            80:   b"HEAD / HTTP/1.0\r\n\r\n",
            8080: b"HEAD / HTTP/1.0\r\n\r\n",
            443:  b"HEAD / HTTP/1.0\r\n\r\n",
            8443: b"HEAD / HTTP/1.0\r\n\r\n",
            21:   None,   # FTP sends banner immediately
            22:   None,   # SSH sends banner immediately
            23:   None,   # Telnet sends banner immediately
            25:   None,   # SMTP sends banner immediately
            3306: None,   # MySQL sends banner immediately
            5432: None,   # Postgres — needs auth but version leaks
            6379: b"INFO\r\n",  # Redis
        }

        def grab(port):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((target, port))

                probe = probes.get(port, None)
                if probe:
                    sock.send(probe)

                banner = sock.recv(1024).decode("utf-8", errors="ignore").strip()
                sock.close()

                if banner:
                    # Truncate and clean
                    first_lines = "\n".join(banner.split("\n")[:5])
                    return f"Port {port}: {first_lines}"
                return f"Port {port}: open (no banner)"

            except (socket.timeout, ConnectionRefusedError):
                return None
            except Exception as e:
                return f"Port {port}: error — {e}"

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(grab, port): port for port in port_list}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        if results:
            results.sort(key=lambda x: int(x.split(":")[0].replace("Port ", "").strip()))
            return f"Banner grab results for {target}:\n" + "\n\n".join(results)
        return f"No banners retrieved from {target}"