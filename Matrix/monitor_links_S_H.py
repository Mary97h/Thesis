import requests
import time

class HostLinkMonitor:
    def __init__(self, controller_ip='127.0.0.1', rest_port=8080):
        self.base = f"http://{controller_ip}:{rest_port}"

    def get_hosts(self):
        """Fetch list of hosts from Ryu topology REST API."""
        try:
            r = requests.get(f"{self.base}/v1/topology/hosts")
            if r.status_code == 200:
                return r.json()
            print(f"Failed to fetch hosts: {r.status_code}")
        except Exception as e:
            print(f"Error fetching hosts: {e}")
        return []

    def _snapshot(self, dpid, port):
        now = time.time()
        try:
            r = requests.get(f"{self.base}/stats/port/{dpid}")
            if r.status_code == 200:
                for p in r.json().get(str(dpid), []):
                    if p['port_no'] == port:
                        return {'tx': p['tx_bytes'], 'rx': p['rx_bytes'], 'time': now}
        except Exception as e:
            print(f"Error fetching port {dpid}:{port} stats: {e}")
        return None

    def measure(self, dpid, port, interval=5):
        a = self._snapshot(dpid, port)
        time.sleep(interval)
        b = self._snapshot(dpid, port)

        if not a or not b:
            print(f"  → {dpid}:{port} missing data, skipping")
            return

        delta = (b['tx'] + b['rx']) - (a['tx'] + a['rx'])
        dt = b['time'] - a['time']
        if dt <= 0:
            print(f"  → {dpid}:{port} invalid time gap, skipping")
            return

        mbps = (delta * 8) / (dt * 1_000_000)
        print(f"  → {dpid}:{port} = {mbps:.2f} Mbps")

    def run(self, interval=5, cycles=3):
        hosts = self.get_hosts()
        if not hosts:
            print("No hosts found")
            return
        print("Discovered host↔switch links:")
        for h in hosts:
            ip = h.get('ip', [''])[0] if isinstance(h.get('ip'), list) else h.get('ip','')
            print(f" • host {h['mac']} ({ip}) on switch {h['dpid']} port {h['port_no']}")

        for c in range(1, cycles+1):
            for h in hosts:
                print(f"Host {h['mac']} → switch-port {h['dpid']}:{h['port_no']}", end='')
                self.measure(h['dpid'], h['port_no'], interval)


if __name__ == "__main__":
    m = HostLinkMonitor(controller_ip="127.0.0.1", rest_port=8080)
    m.run(interval=10, cycles=3)
