import requests
import json
import time
import argparse
import csv
import os
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt

def load_topology_from_file(filepath="topology.json"):
    with open(filepath, "r") as f:
        topology = json.load(f)
    return topology

class MinimalRyuSwitchMonitor:
    def __init__(self, controller_ip='127.0.0.1', rest_port=8080, topology_file="topology.json"):
        self.controller_ip = controller_ip
        self.rest_port = rest_port
        self.base_url = f"http://{controller_ip}:{rest_port}"
        self.switches = []
        self.aps = []  
        self.switch_map = {} 
        self.port_stats = defaultdict(lambda: defaultdict(dict))
        self.previous_stats = defaultdict(lambda: defaultdict(dict))
        self.flow_stats = defaultdict(lambda: defaultdict(dict))
        self.previous_flow_stats = defaultdict(lambda: defaultdict(dict))
        
        try:
            self.topology = load_topology_from_file(topology_file)
            print(f"Loaded topology from {topology_file}")
            print(f"Nodes: {len(self.topology['nodes'])}")
            print(f"Links: {len(self.topology['links'])}")
            
            self.topology_switches = [node for node in self.topology['nodes'] if node.startswith('s')]
            self.topology_aps = [node for node in self.topology['nodes'] if node.startswith('ap')]
            print(f"Switches in topology: {self.topology_switches}")
            print(f"APs in topology: {self.topology_aps}")
        except Exception as e:
            print(f"Failed to load topology from {topology_file}: {e}")
            self.topology = {"nodes": [], "links": []}
            self.topology_switches = []
            self.topology_aps = []
        
        self.base_dir = "Results"
        self.viz_dir = os.path.join(self.base_dir, "bandwidth_viz")
        self.report_dir = os.path.join(self.base_dir, "reports")

        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.viz_dir, exist_ok=True)
        os.makedirs(self.report_dir, exist_ok=True)

        self.topology_file = os.path.join(self.base_dir, "topology.json")


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
                'Timestamp', 'Cycle', 'Switch DPID', 'Switch Name', 'Port',
                'TX Bytes', 'RX Bytes', 'TX Packets', 'RX Packets',
                'TX Errors', 'RX Errors', 'TX Dropped', 'RX Dropped',
                'TX Mbps', 'RX Mbps', 'Total Mbps', 'Free BW (Mbps)'
            ])
        
        with open(self.flow_csv, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Timestamp', 'Cycle', 'Switch DPID', 'Switch Name', 'Table ID', 'Priority',
                'Match', 'Actions', 'Packet Count', 'Byte Count', 'Duration (s)'
            ])
            
        with open(self.switch_csv, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Cycle', 'Switch DPID', 'Switch Name', 'Type'])
        
        self.current_cycle = 0

    def generate_port_connections_report(self):
        """Generate a report showing each port's connection details."""
        port_connections_file = os.path.join(self.report_dir, f"port_connections_cycle_{self.current_cycle}.txt")
    
        try:
            with open(port_connections_file, 'w') as f:
                f.write(f"=== Port Connection Report - Cycle {self.current_cycle} ===\n")
                f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
                all_devices = self.switches + self.aps
            
                for dpid in all_devices:
                    device_name = self.get_switch_name(dpid)
                    device_type = "AP" if device_name.startswith('ap') else "Switch"
                    f.write(f"\n{device_name} ({device_type}, DPID {dpid}):\n")
                    f.write("=" * 60 + "\n")
                    f.write(f"{'Port':<6} {'Connected To':<20} {'Remote Port':<12} {'Bandwidth':<10} {'Delay':<10}\n")
                    f.write("-" * 60 + "\n")
                
                    ports = list(self.port_stats[dpid].keys())
                
                    try:
                        ports.sort(key=lambda x: int(x) if isinstance(x, int) or x.isdigit() else float('inf'))
                    except:
                        ports.sort()
                
                    for port_no in ports:
                
                        link_info = self.find_link_info(device_name, port_no)
                    
                        if link_info:
                            if link_info["src"] == device_name and link_info["src_port"] == port_no:
                                remote_device = link_info["dst"]
                                remote_port = link_info["dst_port"]
                            else:
                                remote_device = link_info["src"]
                                remote_port = link_info["src_port"]
                        
                            bandwidth = link_info.get("bw", "Unknown")
                            delay = link_info.get("delay", "Unknown")
                        
                            f.write(f"{port_no:<6} {remote_device:<20} {remote_port:<12} {bandwidth:<10} {delay:<10}\n")
                        else:
                            f.write(f"{port_no:<6} {'Not connected':<20} {'N/A':<12} {'N/A':<10} {'N/A':<10}\n")
                f.write("\n\n=== Network Connection Summary ===\n")
                f.write("-" * 60 + "\n")
                f.write(f"{'Source':<15} {'Source Port':<12} {'Destination':<15} {'Dest Port':<12} {'Bandwidth':<10} {'Delay':<10}\n")
                f.write("-" * 60 + "\n")
            
                for link in self.topology["links"]:
                    src = link.get("src", "Unknown")
                    src_port = link.get("src_port", "Unknown")
                    dst = link.get("dst", "Unknown")
                    dst_port = link.get("dst_port", "Unknown")
                    bw = link.get("bw", "Unknown")
                    delay = link.get("delay", "Unknown")
                
                    f.write(f"{src:<15} {src_port:<12} {dst:<15} {dst_port:<12} {bw:<10} {delay:<10}\n")
            
            print(f"Port connections report generated: {port_connections_file}")
            return True
        except Exception as e:
            print(f"Error generating port connections report: {e}")
            return False
        
    def generate_bandwidth_matrix(self):
        """Generate and save adjacency matrix with bandwidth values."""
        node_port_stats = {}
        for dpid, port_data in self.port_stats.items():
            device_name = self.get_switch_name(dpid)
            node_port_stats[device_name] = {}
        
            for port_no, stats in port_data.items():
                if dpid in self.previous_stats and port_no in self.previous_stats[dpid]:
                    prev = self.previous_stats[dpid][port_no]
                    curr = stats
                    time_diff = curr['timestamp'] - prev['timestamp']
                
                    if time_diff > 0:
                        tx_diff = curr['tx_bytes'] - prev['tx_bytes']
                        rx_diff = curr['rx_bytes'] - prev['rx_bytes']
                    
                        tx_mbps = (tx_diff * 8) / (time_diff * 1_000_000)
                        rx_mbps = (rx_diff * 8) / (time_diff * 1_000_000)
                    
                        node_port_stats[device_name][port_no] = {
                            'tx_mbps': tx_mbps,
                            'rx_mbps': rx_mbps,
                            'total_mbps': tx_mbps + rx_mbps
                        }
        from sdn import save_adjacency_matrix 
        save_adjacency_matrix(self.topology, node_port_stats)


    def map_dpid_to_switch_name(self):
        """Map DPIDs to switch and AP names based on topology."""
        all_dpids = self.switches + self.aps
        for dpid in all_dpids:
            dpid_val = int(dpid, 16) if isinstance(dpid, str) else dpid
            if dpid_val > 1000000000000: 
                self.switch_map[dpid] = "s0"
                continue
            ap_name = f"ap{int(dpid, 16) - 10}" if isinstance(dpid, str) else f"ap{dpid - 10}"
            switch_name = f"s{int(dpid, 16)}" if isinstance(dpid, str) else f"s{dpid}"
            
            if ap_name in self.topology_aps:
                self.switch_map[dpid] = ap_name
                if dpid not in self.aps:
                    self.aps.append(dpid)
                if dpid in self.switches:
                    self.switches.remove(dpid)
            elif switch_name in self.topology_switches or dpid in self.switches:
                if dpid == 0 or dpid == "0000000000000000":
                    self.switch_map[dpid] = "s0"
                else:
                    self.switch_map[dpid] = switch_name
            else:
                print(f"[WARNING] Cannot determine if {dpid} is a switch or AP, assuming switch")
                self.switch_map[dpid] = f"s{dpid}"
        print("Switch/AP mapping created:")
        for dpid, name in self.switch_map.items():
            device_type = "AP" if name.startswith("ap") else "Switch"
            print(f"DPID {dpid} → {name} ({device_type})")

    def get_switch_name(self, dpid):
        """Get the logical switch or AP name for a DPID"""
        return self.switch_map.get(dpid, f"s{dpid}")

    def is_ap(self, dpid):
        """Check if the device with this DPID is an AP"""
        device_name = self.get_switch_name(dpid)
        return device_name.startswith('ap')

    def get_switches(self):
        try:
            url = f"{self.base_url}/stats/switches"
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                print(f"Error fetching switches: {response.status_code}")
                return False

            all_dpids = response.json()
            print("\n[DEBUG] Raw devices from Ryu controller:", all_dpids)
            
            self.switches = []
            self.aps = []
            
            for dpid in all_dpids:
                dpid_decimal = int(dpid) if isinstance(dpid, int) else int(dpid, 16)
                if dpid_decimal >= 11 and dpid_decimal <= 18:
                    self.aps.append(dpid)
                else:
                    self.switches.append(dpid)
            
            print(f"[INFO] Identified APs: {self.aps}")
            print(f"[INFO] Identified Switches: {self.switches}")

            self.map_dpid_to_switch_name()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.switch_csv, mode='a', newline='') as f:
                writer = csv.writer(f)
                for dpid in self.switches:
                    writer.writerow([timestamp, self.current_cycle, dpid, self.get_switch_name(dpid), "Switch"])
                for dpid in self.aps:
                    writer.writerow([timestamp, self.current_cycle, dpid, self.get_switch_name(dpid), "AP"])
            return True
        except Exception as e:
            print(f"Exception fetching switches: {e}")
            return False

    def get_ap_link_bandwidth(self, ap_name, port_no=None):
        """Get the bandwidth capacity for an AP link."""
        try:
            for link in self.topology["links"]:
                if link["src"] == ap_name:
                    if port_no is None or link.get("src_port") == port_no:
                        return link.get("bw", 100)
                elif link["dst"] == ap_name:
                    if port_no is None or link.get("dst_port") == port_no:
                        return link.get("bw", 100)
            return 100 #the defult
        except Exception as e:
            print(f"Error getting AP link bandwidth: {e}")
            return 100

    def collect_port_stats(self):
        """collect port statistics for both switches and aps."""
        success = False
        all_devices = self.switches + self.aps
    
        for dpid in all_devices:
            try:
                url = f"{self.base_url}/stats/port/{dpid}"
                response = requests.get(url, timeout=5)
                if response.status_code != 200:
                    print(f"failed to fetch port stats for device {dpid}: {response.status_code}")
                    continue
            
                stats = response.json().get(str(dpid))
                if not stats:
                    print(f"No port stats received for device {dpid}")
                    continue
            
                self.previous_stats[dpid] = self.port_stats[dpid].copy() if dpid in self.port_stats else {}
            
                for port_stat in stats:
                    port_no = port_stat.get('port_no')
                    if port_no is None:
                        continue
                
                    if isinstance(port_no, str) or port_no > 65000 or port_no < 0:
                        print(f"local port {port_no} detected on device {dpid} - collecting data")
                    self.port_stats[dpid][port_no] = {
                        'rx_bytes': port_stat.get('rx_bytes', 0),
                        'tx_bytes': port_stat.get('tx_bytes', 0),
                        'rx_packets': port_stat.get('rx_packets', 0),
                        'tx_packets': port_stat.get('tx_packets', 0),
                        'rx_errors': port_stat.get('rx_errors', 0),
                        'tx_errors': port_stat.get('tx_errors', 0),
                        'rx_dropped': port_stat.get('rx_dropped', 0),
                        'tx_dropped': port_stat.get('tx_dropped', 0),
                        'timestamp': time.time(),
                        'is_special': isinstance(port_no, str) or port_no > 65000 or port_no < 0
                    }
                success = True
            except Exception as e:
                print(f"exception collecting port stats for device {dpid}: {e}")

        return success

    def collect_flow_stats(self):
        """collect flow statistics for both switches and aps."""
        success = False
        all_devices = self.switches + self.aps
        
        for dpid in all_devices:
            try:
                url = f"{self.base_url}/stats/flow/{dpid}"
                response = requests.get(url, timeout=5)
                if response.status_code != 200:
                    print(f"Failed to fetch flow stats for device {dpid}: {response.status_code}")
                    continue
                
                stats = response.json().get(str(dpid))
                if not stats:
                    print(f"No flow stats received for device {dpid}")
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
                            timestamp, self.current_cycle, dpid, self.get_switch_name(dpid), 
                            table_id, priority, match, actions, packet_count, byte_count, duration_sec
                        ])
                success = True
            except Exception as e:
                print(f"xception collecting flow stats for device {dpid}: {e}")
        
        return success

    def find_link_info(self, device_id, port_no):
        """find link info for any device (switch or AP)."""
        try:
            if isinstance(port_no, str) or port_no > 65000 or port_no < 0:
                print(f"Finding link info for local port {port_no} on {device_id}")
                return {
                    "src": device_id,
                    "dst": "controller" if port_no == -1 else "special",
                    "src_port": port_no,
                    "dst_port": 0,
                    "bw": float('inf'),
                    "delay": "0ms"
                }
            for link in self.topology["links"]:
                if link["src"] == device_id and link["src_port"] == port_no:
                    return link
                elif link["dst"] == device_id and link["dst_port"] == port_no:
                    return link
            print(f"could't find link info for device {device_id} Port {port_no},it seems it is not connect to anything")
            return None
        
        except Exception as e:
            print(f"error finding link info: {e}")
            return None

    def calculate_port_bandwidth(self):
        """clculate and record bandwidth usage for all devices (switches and APs)."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            all_devices = self.switches + self.aps
        
            with open(self.port_csv, mode='a', newline='') as f:
                writer = csv.writer(f)
            
                for dpid in all_devices:
                    device_name = self.get_switch_name(dpid)
                    is_ap = device_name.startswith('ap')
                
                    for port_no, curr in self.port_stats[dpid].items():
                        prev = self.previous_stats.get(dpid, {}).get(port_no)
                        is_special = curr.get('is_special', False)
                    
                        if prev:
                            time_diff = curr['timestamp'] - prev['timestamp']
                            if time_diff > 0:
                                tx_diff = curr['tx_bytes'] - prev['tx_bytes']
                                rx_diff = curr['rx_bytes'] - prev['rx_bytes']
                            
                                tx_mbps = (tx_diff * 8) / (time_diff * 1_000_000)
                                rx_mbps = (rx_diff * 8) / (time_diff * 1_000_000)
                                total_mbps = tx_mbps + rx_mbps
                            
                                if is_special:
                                    bw_limit = float('inf')
                                    free_bw = float('inf')
                                    print(f"Special port {port_no} on {device_name} - TX: {tx_mbps:.2f} Mbps, RX: {rx_mbps:.2f} Mbps")
                                elif is_ap:
                                    bw_limit = self.get_ap_link_bandwidth(device_name, port_no)
                                    free_bw = bw_limit - total_mbps if bw_limit > 0 else 0
                                    free_bw = max(0, free_bw)
                                else:
                                    link_info = self.find_link_info(device_name, port_no)
                                    if link_info:
                                        bw_limit = link_info.get('bw', 100)
                                        free_bw = bw_limit - total_mbps if bw_limit > 0 else 0
                                        free_bw = max(0, free_bw)
                                    else:
                                        bw_limit = 100
                                        free_bw = bw_limit - total_mbps
                                        free_bw = max(0, free_bw)
                        
                                if not is_special and free_bw < 5:
                                    print(f"Port {port_no} on {device_name} is near capacity - only {free_bw:.2f} Mbps free")
                            else:
                                tx_mbps = rx_mbps = total_mbps = 0
                                free_bw = 100 if not is_special else float('inf')
                        else:
                            tx_mbps = rx_mbps = total_mbps = 0
                            free_bw = 100 if not is_special else float('inf')
                    
                        writer.writerow([
                            timestamp, self.current_cycle, dpid, device_name, port_no,
                            curr['tx_bytes'], curr['rx_bytes'],
                            curr['tx_packets'], curr['rx_packets'],
                            curr['tx_errors'], curr['rx_errors'],
                            curr['tx_dropped'], curr['rx_dropped'],
                            f"{tx_mbps:.6f}", f"{rx_mbps:.6f}", f"{total_mbps:.6f}",
                            f"{free_bw:.6f}" if not is_special else "N/A"
                        ])
        except Exception as e:
            print(f"Error calculating port bandwidth: {e}")

    def generate_report(self):
        """Generate a monitoring report for both switches and APs."""
        report_file = os.path.join(self.report_dir, f"report_cycle_{self.current_cycle}.txt")        
        try:
            with open(report_file, 'w') as f:
                f.write(f"=== Ryu Network Monitor Report - Cycle {self.current_cycle} ===\n")
                f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                f.write("=== Topology Summary ===\n")
                f.write(f"Nodes in topology: {len(self.topology['nodes'])}\n")
                f.write(f"Links in topology: {len(self.topology['links'])}\n\n")
                
                f.write(f"Active Switches: {len(self.switches)}\n")
                f.write("Switch Mapping:\n")
                for dpid in self.switches:
                    f.write(f"  DPID {dpid} → {self.get_switch_name(dpid)}\n")
                f.write("\n")
                
                f.write(f"Active APs: {len(self.aps)}\n")
                f.write("AP Mapping:\n")
                for dpid in self.aps:
                    f.write(f"  DPID {dpid} → {self.get_switch_name(dpid)}\n")
                f.write("\n")
                
                all_devices = self.switches + self.aps
                f.write("=== Port Statistics ===\n")
                
                for dpid in all_devices:
                    device_name = self.get_switch_name(dpid)
                    device_type = "AP" if device_name.startswith('ap') else "Switch"
                    f.write(f"\n{device_name} ({device_type}, DPID {dpid}):\n")
                    
                    if not self.port_stats[dpid]:
                        f.write("  No port statistics available\n")
                    else:
                        f.write(f"{'Port':<6} {'TX Mbps':>10} {'RX Mbps':>10} {'TX Packets':>12} {'RX Packets':>12} {'Free BW':>10}\n")
                        f.write("-" * 70 + "\n")
                        
                        def custom_sort_key(x):
                            try:
                                return int(x[0])
                            except ValueError:
                                return float('inf')

                        for port_no, curr in sorted(self.port_stats[dpid].items(), key=custom_sort_key):

                            prev = self.previous_stats.get(dpid, {}).get(port_no)
                            
                            if prev:
                                time_diff = curr['timestamp'] - prev['timestamp']
                                if time_diff > 0:
                                    tx_diff = curr['tx_bytes'] - prev['tx_bytes']
                                    rx_diff = curr['rx_bytes'] - prev['rx_bytes']
                                    tx_mbps = (tx_diff * 8) / (time_diff * 1_000_000)
                                    rx_mbps = (rx_diff * 8) / (time_diff * 1_000_000)
                                    total_mbps = tx_mbps + rx_mbps
                                    
                                    if device_name.startswith('ap'):
                                        bw_limit = self.get_ap_link_bandwidth(device_name, port_no)
                                    else:
                                        link_info = self.find_link_info(device_name, port_no)
                                        bw_limit = link_info.get('bw', 100) if link_info else 100
                                    
                                    free_bw = max(0, bw_limit - total_mbps)
                                else:
                                    tx_mbps = rx_mbps = 0
                                    free_bw = 100 
                            else:
                                tx_mbps = rx_mbps = 0
                                free_bw = 100
                            
                            f.write(f"{port_no:<6} {tx_mbps:>10.3f} {rx_mbps:>10.3f} {curr['tx_packets']:>12} {curr['rx_packets']:>12} {free_bw:>10.3f}\n")
                
                f.write("\n\n=== Flow Statistics ===\n")
                for dpid in all_devices:
                    device_name = self.get_switch_name(dpid)
                    device_type = "AP" if device_name.startswith('ap') else "Switch"
                    f.write(f"\n{device_name} ({device_type}, DPID {dpid}):\n")
                    
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
        """Generate bandwidth visualization plots for both switches and APs."""
        try:
            if self.current_cycle < 2:
                return
            
            all_devices = self.switches + self.aps
            
            for dpid in all_devices:
                device_name = self.get_switch_name(dpid)
                device_type = "AP" if device_name.startswith('ap') else "Switch"
                
                plt.figure(figsize=(12, 6))
                
                all_ports = list(self.port_stats[dpid].keys())
                tx_values = []
                rx_values = []
                free_bw_values = []
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
                            total_mbps = tx_mbps + rx_mbps
                            
                            if device_name.startswith('ap'):
                                bw_limit = self.get_ap_link_bandwidth(device_name, port)
                            else:
                                link_info = self.find_link_info(device_name, port)
                                bw_limit = link_info.get('bw', 100) if link_info else 100
                            
                            free_bw = max(0, bw_limit - total_mbps)
                            
                            tx_values.append(tx_mbps)
                            rx_values.append(rx_mbps)
                            free_bw_values.append(free_bw)
                            labels.append(f"{device_name}-p{port}")
                
                if labels:
                    x = range(len(labels))
                    width = 0.25
                    
                    plt.bar([i - width for i in x], tx_values, width, label='TX Mbps')
                    plt.bar(x, rx_values, width, label='RX Mbps')
                    plt.bar([i + width for i in x], free_bw_values, width, label='Free BW Mbps')
                    
                    plt.xlabel('Port')
                    plt.ylabel('Bandwidth (Mbps)')
                    plt.title(f'Port Bandwidth - {device_name} ({device_type}) - Cycle {self.current_cycle}')
                    plt.xticks(x, labels, rotation=45)
                    plt.legend()
                    plt.tight_layout()
                    
                    plt.savefig(os.path.join(self.viz_dir, f'bandwidth_{device_name}_cycle{self.current_cycle}.png'))
                    plt.close()
        
        except Exception as e:
            print(f"Error plotting bandwidth: {e}")

    def monitor_network(self, interval=5, cycles=3):
        print("===== Starting Ryu Network Monitor =====")
        print(f"Topology loaded with {len(self.topology['nodes'])} nodes and {len(self.topology['links'])} links")
        
        for cycle in range(1, cycles+1):
            self.current_cycle = cycle
            print(f"\n===== Monitoring Cycle {cycle}/{cycles} =====")
            
            if not self.get_switches():
                print("failed to fetch switches - will try again next cycle")
                time.sleep(2)
                continue
            
            if not self.switches and not self.aps:
                print("no network devices discovered. Waiting before retry")
                time.sleep(2)
                continue
            
            self.collect_port_stats()
            self.collect_flow_stats()
            
            print(f"\nWaiting {interval} seconds to calculate bandwidth")
            time.sleep(interval)
            
            self.collect_port_stats()
            self.collect_flow_stats()
            self.calculate_port_bandwidth()
            self.generate_bandwidth_matrix()
            
            self.generate_report()
            self.generate_port_connections_report()
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
    parser.add_argument('--topology', default='topology.json', help='Path to topology JSON file')
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