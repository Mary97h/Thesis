import requests
import time

class SimpleLinkMonitor:
    def __init__(self, controller_ip='127.0.0.1', rest_port=8080):
        self.base_url = f"http://{controller_ip}:{rest_port}"
        
        self.link = {
            'src': (1, 1),  
            'dst': (2, 1)   
        }

    def _get_port_list(self, dpid):
        try:
            r = requests.get(f"{self.base_url}/stats/port/{dpid}")
            if r.status_code == 200:
                return r.json().get(str(dpid), [])
        except Exception as e:
            print(f"Error fetching stats for DPID {dpid}: {e}")
        return []

    def _snapshot(self):
        snap = {}
        now = time.time()
        for side in ('src','dst'):
            dpid, port = self.link[side]
            for p in self._get_port_list(dpid):
                if p['port_no'] == port:
                    snap.setdefault(dpid, {})[port] = {
                        'tx': p['tx_bytes'],
                        'rx': p['rx_bytes'],
                        'time': now
                    }
        return snap

    def calc_bandwidth(self, interval=5):
        print(f"\n→ sampling traffic, waiting {interval}s …")
        first = self._snapshot()
        time.sleep(interval)
        second = self._snapshot()

        for side in ('src','dst'):
            dpid, port = self.link[side]
            a = first.get(dpid, {}).get(port)
            b = second.get(dpid, {}).get(port)

            if not a or not b:
                print(f"{side.upper()} {dpid}:{port} → Missing data, skipping")
                continue

            delta_bytes = (b['tx'] + b['rx']) - (a['tx'] + a['rx'])
            dt = b['time'] - a['time']

            if dt <= 0:
                print(f"{side.upper()} {dpid}:{port} → Invalid time gap ({dt:.3f}s), skipping")
                continue

            mbps = (delta_bytes * 8) / (dt * 1_000_000)
            print(f"{side.upper()} {dpid}:{port} → {mbps:.2f} Mbps")

    def run(self, interval=5, cycles=3):
        print("Starting monitor")
        for i in range(1, cycles+1):
            print(f"\n== Cycle {i}/{cycles} ==")
            self.calc_bandwidth(interval)


if __name__ == "__main__":
    monitor = SimpleLinkMonitor(controller_ip="127.0.0.1", rest_port=8080)
    monitor.run(interval=10, cycles=3)
