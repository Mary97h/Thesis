import requests
import json
import time
import argparse
import csv
import os
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt

def load_topology_from_file(filepath="/tmp/topology.json"):
    with open(filepath, "r") as f:
        topology = json.load(f)
    return topology

class MinimalRyuSwitchMonitor:
    def __init__(self, controller_ip='127.0.0.1', rest_port=8080, topology_file="/tmp/topology.json"):
        self.controller_ip = controller_ip
        self.rest_port = rest_port
        self.base_url = f"http://{controller_ip}:{rest_port}"
        self.switches = []
        self.port_stats = defaultdict(lambda: defaultdict(dict))
        self.previous_stats = defaultdict(lambda: defaultdict(dict))
        self.flow_stats = defaultdict(lambda: defaultdict(dict))
        self.previous_flow_stats = defaultdict(lambda: defaultdict(dict))
        
        try:
            self.topology = load_topology_from_file(topology_file)
            print(f"Loaded topology from {topology_file}")
            print(f"Nodes: {len(self.topology['nodes'])}")
            print(f"Links: {len(self.topology['links'])}")
        except Exception as e:
            print(f"Failed to load topology from {topology_file}: {e}")
            self.topology = {"nodes": [], "links": []}
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_dir = f"switch_stats_{timestamp}"
        
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
            
        self.viz_dir = os.path.join(self.base_dir, "bandwidth_viz")
        if not os.path.exists(self.viz_dir):
            os.makedirs(self.viz_dir)
        
        self.port_csv = os.path.join(self.base_dir, "port_stats.csv")
        self.flow_csv = os.path.join(self.base_dir, "flow_stats.csv")
        self.switch_csv = os.path.join(self.base_dir, "switches.csv")
        
        with open(self.port_csv, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Timestamp', 'Cycle', 'Switch', 'Port',
                'TX Bytes', 'RX Bytes', 'TX Packets', 'RX Packets',
                'TX Errors', 'RX Errors', 'TX Dropped', 'RX Dropped',
                'TX Mbps', 'RX Mbps', 'Total Mbps'
            ])
        
        with open(self.flow_csv, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Timestamp', 'Cycle', 'Switch', 'Table ID', 'Priority',
                'Match', 'Actions', 'Packet Count', 'Byte Count', 'Duration (s)'
            ])
            
        with open(self.switch_csv, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Cycle', 'Switch ID'])
        
        self.current_cycle = 0

    def get_switches(self):
        try:
            url = f"{self.base_url}/stats/switches"
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                print(f"Error fetching switches: {response.status_code}")
                return False
            
            self.switches = response.json()
            print(f"Discovered {len(self.switches)} switches: {self.switches}")
            
            topology_switches = [node for node in self.topology['nodes'] if node.startswith('s')]
            discovered_switches = [f"s{s}" for s in self.switches]
            
            missing_switches = set(topology_switches) - set(discovered_switches)
            extra_switches = set(discovered_switches) - set(topology_switches)
            
            if missing_switches:
                print(f"Warning: The following switches from topology are not discovered: {missing_switches}")
            if extra_switches:
                print(f"Warning: Discovered switches not in topology: {extra_switches}")
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.switch_csv, mode='a', newline='') as f:
                writer = csv.writer(f)
                for switch in self.switches:
                    writer.writerow([timestamp, self.current_cycle, switch])
            
            return True
        except Exception as e:
            print(f"Exception fetching switches: {e}")
            return False

    def collect_port_stats(self):
        success = False
        for dpid in self.switches:
            try:
                url = f"{self.base_url}/stats/port/{dpid}"
                response = requests.get(url, timeout=5)
                if response.status_code != 200:
                    print(f"Failed to fetch port stats for switch {dpid}: {response.status_code}")
                    continue
                
                stats = response.json().get(str(dpid))
                if not stats:
                    print(f"No port stats received for switch {dpid}")
                    continue
                
                self.previous_stats[dpid] = self.port_stats[dpid].copy() if dpid in self.port_stats else {}
                
                for port_stat in stats:
                    port_no = port_stat.get('port_no')
                    if port_no is None:
                        continue
                    
                    if isinstance(port_no, str) or port_no > 65000:
                        continue
                    
                    self.port_stats[dpid][port_no] = {
                        'rx_bytes': port_stat.get('rx_bytes', 0),
                        'tx_bytes': port_stat.get('tx_bytes', 0),
                        'rx_packets': port_stat.get('rx_packets', 0),
                        'tx_packets': port_stat.get('tx_packets', 0),
                        'rx_errors': port_stat.get('rx_errors', 0),
                        'tx_errors': port_stat.get('tx_errors', 0),
                        'rx_dropped': port_stat.get('rx_dropped', 0),
                        'tx_dropped': port_stat.get('tx_dropped', 0),
                        'timestamp': time.time()
                    }
                success = True
            except Exception as e:
                print(f"Exception collecting port stats for switch {dpid}: {e}")
        
        return success

    def collect_flow_stats(self):
        success = False
        for dpid in self.switches:
            try:
                url = f"{self.base_url}/stats/flow/{dpid}"
                response = requests.get(url, timeout=5)
                if response.status_code != 200:
                    print(f"Failed to fetch flow stats for switch {dpid}: {response.status_code}")
                    continue
                
                stats = response.json().get(str(dpid))
                if not stats:
                    print(f"No flow stats received for switch {dpid}")
                    continue
                
                self.previous_flow_stats[dpid] = self.flow_stats[dpid].copy() if dpid in self.flow_stats else {}
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(self.flow_csv, mode='a', newline='') as f:
                    writer = csv.writer(f)
                    
                    for flow in stats:
                        table_id = flow.get('table_id', 0)
                        priority = flow.get('priority', 0)
                        match = str(flow.get('match', {}))
                        actions = str(flow.get('actions', []))
                        packet_count = flow.get('packet_count', 0)
                        byte_count = flow.get('byte_count', 0)
                        duration_sec = flow.get('duration_sec', 0)
                        
                        flow_id = f"{table_id}_{priority}_{hash(match)}"
                        
                        self.flow_stats[dpid][flow_id] = {
                            'table_id': table_id,
                            'priority': priority,
                            'match': match,
                            'actions': actions,
                            'packet_count': packet_count,
                            'byte_count': byte_count,
                            'duration_sec': duration_sec,
                            'timestamp': time.time()
                        }
                        
                        writer.writerow([
                            timestamp, self.current_cycle, dpid, table_id, priority,
                            match, actions, packet_count, byte_count, duration_sec
                        ])
                success = True
            except Exception as e:
                print(f"Exception collecting flow stats for switch {dpid}: {e}")
        
        return success

    def calculate_port_bandwidth(self):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(self.port_csv, mode='a', newline='') as f:
                writer = csv.writer(f)
                
                for dpid in self.switches:
                    for port_no, curr in self.port_stats[dpid].items():
                        prev = self.previous_stats.get(dpid, {}).get(port_no)
                        
                        if prev:
                            time_diff = curr['timestamp'] - prev['timestamp']
                            if time_diff > 0:
                                tx_diff = curr['tx_bytes'] - prev['tx_bytes']
                                rx_diff = curr['rx_bytes'] - prev['rx_bytes']
                                
                                tx_mbps = (tx_diff * 8) / (time_diff * 1_000_000)
                                rx_mbps = (rx_diff * 8) / (time_diff * 1_000_000)
                                total_mbps = tx_mbps + rx_mbps
                                
                                switch_id = f"s{dpid}"
                                link_info = self.find_link_info(switch_id, port_no)
                                if link_info:
                                    bw_limit = link_info.get('bw', 0)
                                    if bw_limit > 0 and total_mbps > bw_limit:
                                        print(f"Warning: Port {port_no} on switch {dpid} exceeds defined bandwidth limit "
                                              f"({total_mbps:.2f} Mbps > {bw_limit} Mbps)")
                            else:
                                tx_mbps = rx_mbps = total_mbps = 0
                        else:
                            tx_mbps = rx_mbps = total_mbps = 0
                        
                        writer.writerow([
                            timestamp, self.current_cycle, dpid, port_no,
                            curr['tx_bytes'], curr['rx_bytes'],
                            curr['tx_packets'], curr['rx_packets'],
                            curr['tx_errors'], curr['rx_errors'],
                            curr['tx_dropped'], curr['rx_dropped'],
                            f"{tx_mbps:.6f}", f"{rx_mbps:.6f}", f"{total_mbps:.6f}"
                        ])
        except Exception as e:
            print(f"Error calculating port bandwidth: {e}")
    
    def find_link_info(self, switch_id, port_no):
        try:
            for link in self.topology['links']:
                if link['src'] == switch_id or link['dst'] == switch_id:
                    return link
        except Exception as e:
            print(f"Error finding link info: {e}")
        return None

    def generate_report(self):
        report_file = os.path.join(self.base_dir, f"report_cycle_{self.current_cycle}.txt")
        
        try:
            with open(report_file, 'w') as f:
                f.write(f"=== Ryu Network Monitor Report - Cycle {self.current_cycle} ===\n")
                f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                f.write("=== Topology Summary ===\n")
                f.write(f"Nodes in topology: {len(self.topology['nodes'])}\n")
                f.write(f"Links in topology: {len(self.topology['links'])}\n\n")
                
                f.write(f"Active Switches: {len(self.switches)}\n")
                f.write(f"Switch IDs: {', '.join(str(s) for s in self.switches)}\n\n")
                
                f.write("=== Port Statistics ===\n")
                for dpid in self.switches:
                    f.write(f"\nSwitch {dpid}:\n")
                    if not self.port_stats[dpid]:
                        f.write("  No port statistics available\n")
                    else:
                        f.write(f"{'Port':<6} {'TX Mbps':>10} {'RX Mbps':>10} {'TX Packets':>12} {'RX Packets':>12}\n")
                        f.write("-" * 60 + "\n")
                        
                        for port_no, curr in sorted(self.port_stats[dpid].items()):
                            prev = self.previous_stats.get(dpid, {}).get(port_no)
                            
                            if prev:
                                time_diff = curr['timestamp'] - prev['timestamp']
                                if time_diff > 0:
                                    tx_diff = curr['tx_bytes'] - prev['tx_bytes']
                                    rx_diff = curr['rx_bytes'] - prev['rx_bytes']
                                    tx_mbps = (tx_diff * 8) / (time_diff * 1_000_000)
                                    rx_mbps = (rx_diff * 8) / (time_diff * 1_000_000)
                                else:
                                    tx_mbps = rx_mbps = 0
                            else:
                                tx_mbps = rx_mbps = 0
                            
                            f.write(f"{port_no:<6} {tx_mbps:>10.3f} {rx_mbps:>10.3f} {curr['tx_packets']:>12} {curr['rx_packets']:>12}\n")
                
                f.write("\n\n=== Flow Statistics ===\n")
                for dpid in self.switches:
                    f.write(f"\nSwitch {dpid}:\n")
                    if not self.flow_stats[dpid]:
                        f.write("  No flow statistics available\n")
                    else:
                        f.write(f"Active flows: {len(self.flow_stats[dpid])}\n")
                        f.write(f"{'Table':^5} {'Priority':^8} {'Packets':^10} {'Bytes':^12} {'Duration(s)':^10}\n")
                        f.write("-" * 50 + "\n")
                        
                        for flow_id, flow in sorted(self.flow_stats[dpid].items(), 
                                                   key=lambda x: (x[1]['table_id'], -x[1]['priority'])):
                            f.write(f"{flow['table_id']:^5} {flow['priority']:^8} {flow['packet_count']:^10} "
                                   f"{flow['byte_count']:^12} {flow['duration_sec']:^10.1f}\n")
            
            print(f"Report generated: {report_file}")
            return True
        except Exception as e:
            print(f"Error generating report: {e}")
            return False

    def plot_port_bandwidth(self):
        try:
            if self.current_cycle < 2:
                return
            
            plt.figure(figsize=(12, 6))
            
            for dpid in self.switches:
                all_ports = list(self.port_stats[dpid].keys())
                tx_values = []
                rx_values = []
                labels = []
                
                for port in all_ports:
                    curr = self.port_stats[dpid][port]
                    prev = self.previous_stats.get(dpid, {}).get(port)
                    
                    if prev:
                        time_diff = curr['timestamp'] - prev['timestamp']
                        if time_diff > 0:
                            tx_diff = curr['tx_bytes'] - prev['tx_bytes']
                            rx_diff = curr['rx_bytes'] - prev['rx_bytes']
                            
                            tx_mbps = (tx_diff * 8) / (time_diff * 1_000_000)
                            rx_mbps = (rx_diff * 8) / (time_diff * 1_000_000)
                            
                            tx_values.append(tx_mbps)
                            rx_values.append(rx_mbps)
                            labels.append(f"s{dpid}-p{port}")
            
                if labels:
                    x = range(len(labels))
                    width = 0.35
                    
                    plt.bar([i - width/2 for i in x], tx_values, width, label='TX Mbps')
                    plt.bar([i + width/2 for i in x], rx_values, width, label='RX Mbps')
                    
                    plt.xlabel('Port')
                    plt.ylabel('Bandwidth (Mbps)')
                    plt.title(f'Port Bandwidth - Switch {dpid} (Cycle {self.current_cycle})')
                    plt.xticks(x, labels, rotation=45)
                    plt.legend()
                    plt.tight_layout()
                    
                    plt.savefig(os.path.join(self.viz_dir, f'bandwidth_s{dpid}_cycle{self.current_cycle}.png'))
                    plt.close()
        
        except Exception as e:
            print(f"Error plotting bandwidth: {e}")

    def monitor_network(self, interval=5, cycles=3):
        print("===== Starting Minimal Ryu Switch Monitor =====")
        print(f"Topology loaded with {len(self.topology['nodes'])} nodes and {len(self.topology['links'])} links")
        
        for cycle in range(1, cycles+1):
            self.current_cycle = cycle
            print(f"\n===== Monitoring Cycle {cycle}/{cycles} =====")
            
            if not self.get_switches():
                print("Failed to fetch switches - will try again next cycle")
                time.sleep(2)
                continue
            
            if not self.switches:
                print("No switches discovered. Waiting before retry...")
                time.sleep(2)
                continue
            
            self.collect_port_stats()
            self.collect_flow_stats()
            
            print(f"\nWaiting {interval} seconds to calculate bandwidth...")
            time.sleep(interval)
            
            self.collect_port_stats()
            self.collect_flow_stats()
            self.calculate_port_bandwidth()
            
            self.generate_report()
            if cycle >= 2:
                self.plot_port_bandwidth()
            
            if cycle < cycles:
                time.sleep(1)
        
        print(f"\n===== Monitoring Complete =====")
        print(f"Data saved to directory: {self.base_dir}")
        print(f"Bandwidth visualizations saved to: {self.viz_dir}")


def main():
    parser = argparse.ArgumentParser(description="Minimal Ryu Switch Monitor")
    parser.add_argument('--controller', default='127.0.0.1', help='Controller IP address')
    parser.add_argument('--port', type=int, default=8080, help='Controller REST API port')
    parser.add_argument('--interval', type=int, default=5, help='Statistics collection interval in seconds')
    parser.add_argument('--cycles', type=int, default=3, help='Number of monitoring cycles')
    parser.add_argument('--topology', default='/tmp/topology.json', help='Path to topology JSON file')
    args = parser.parse_args()

    monitor = MinimalRyuSwitchMonitor(controller_ip=args.controller, rest_port=args.port, 
                                     topology_file=args.topology)
    monitor.monitor_network(interval=args.interval, cycles=args.cycles)

if __name__ == "__main__":
    if len(os.sys.argv) == 1:
        topology = load_topology_from_file()
        print("Loaded topology:", topology)
        print("Nodes:", topology['nodes'])
        print("Sample link:", topology['links'][0] if topology['links'] else "No links found")
        print("Use --help for monitoring options")
    else:
        main()