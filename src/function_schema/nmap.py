import subprocess
import xml.etree.ElementTree as ET

class Nmap:
    def __init__(self):
        self.name = "nmap_scan"
        self.description = "Scan a target for open ports"
    
    def execute(self, target: str, ports: str = "1-1000"):
        try:
            cmd = ["nmap", "-p", ports, target, "-oX", "-"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                return f"Scan failed: {result.stderr}"
            root = ET.fromstring(result.stdout)
            open_ports = []
            for port in root.findall(".//port"):
                state = port.find("state")
                if state is not None and state.get("state") == "open":
                    port_id = port.get("portid")
                    service = port.find("service")
                    service_name = service.get("name", "unknown") if service is not None else "unknown"
                    open_ports.append(f"Port {port_id}: {service_name}")
            if open_ports:
                return f"Open ports on {target}:\n" + "\n".join(open_ports)
            return f"No open ports found on {target}"
        except subprocess.TimeoutExpired:
            return "Scan timeout"
        except Exception as e:
            return f"Error: {e}"