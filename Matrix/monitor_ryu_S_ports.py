#!/usr/bin/env python3

import requests
import json
import time
import argparse
from collections import defaultdict
from tabulate import tabulate

class RyuNetworkMonitor:
    def __init__(self, controller_ip='127.0.0.1', rest_port=8080):
        self.controller_ip = controller_ip
        self.rest_port = rest_port
        self.base_url = f"http://{controller_ip}:{rest_port}"
        self.switches = []
        self.links = []
        self.port_stats = defaultdict(lambda: defaultdict(dict))
        self.previous_stats = defaultdict(lambda: defaultdict(dict))

    def get_switches(self):
        try:
            url = f"{self.base_url}/stats/switches"
            response = requests.get(url)
            if response.status_code != 200:
                print(f"Error fetching switches: {response.status_code} {response.text}")
                return False

            self.switches = response.json()
            print(f"Discovered {len(self.switches)} switches: {self.switches}")
            return True
        except Exception as e:
            print(f"Exception fetching switches: {e}")
            return False
    
    def get_links(self):
        try:
            url = f"{self.base_url}/v1/topology/links"
            response = requests.get(url)
            if response.status_code != 200:
                print(f"Error fetching links: {response.status_code} {response.text}")
                return False
            
            self.links = response.json()
            print(f"Discovered {len(self.links)} links between switches")
            return True
        except Exception as e:
            print(f"Exception fetching links: {e}")
            return False
    
    def collect_port_stats(self):
        try:
            for dpid in self.switches:
                url = f"{self.base_url}/stats/port/{dpid}"
                response = requests.get(url)
                if response.status_code != 200:
                    print(f"Failed to fetch stats for switch {dpid}: {response.status_code}")
                    continue

                stats = response.json().get(str(dpid))
                if not stats:
                    print(f"No stats found for switch {dpid}.")
                    continue

                self.previous_stats[dpid] = self.port_stats[dpid].copy()

                for port_stat in stats:
                    port_no = port_stat['port_no']
                    if isinstance(port_no, str):
                        try:
                            port_no = int(port_no)
                        except ValueError:
                            continue
                            
                    if port_no > 65530:  
                        continue
                        
                    self.port_stats[dpid][port_no] = {
                        'rx_bytes': port_stat['rx_bytes'],
                        'tx_bytes': port_stat['tx_bytes'],
                        'rx_packets': port_stat['rx_packets'],
                        'tx_packets': port_stat['tx_packets'],
                        'timestamp': time.time()
                    }
            return True
        except Exception as e:
            print(f"Exception collecting port stats: {e}")
            print(f"Error details: {type(e).__name__}: {str(e)}")
            return False

    def calculate_bandwidth(self, interval=5):
        print(f"\nWaiting {interval} calculate bandwidth")
        time.sleep(interval)
        self.collect_port_stats()

        bandwidth_data = {}
        for dpid in self.switches:
            bandwidth_data[dpid] = {}
            for port_no, curr in self.port_stats[dpid].items():
                prev = self.previous_stats[dpid].get(port_no)
                if not prev:
                    continue
                    
                time_diff = curr['timestamp'] - prev['timestamp']
                if time_diff <= 0:
                    continue
                    
                tx_diff = curr['tx_bytes'] - prev['tx_bytes']
                rx_diff = curr['rx_bytes'] - prev['rx_bytes']
                
                tx_mbps = (tx_diff * 8) / (time_diff * 1_000_000)
                rx_mbps = (rx_diff * 8) / (time_diff * 1_000_000)
                
                bandwidth_data[dpid][port_no] = {
                    'tx_mbps': tx_mbps,
                    'rx_mbps': rx_mbps,
                    'total_mbps': tx_mbps + rx_mbps
                }

        return bandwidth_data
    
    def display_port_stats(self, bandwidth_data):
        for dpid, ports in bandwidth_data.items():
            if not ports:
                continue
                
            table_data = []
            for port_no, data in ports.items():
                table_data.append([
                    port_no,
                    f"{data['tx_mbps']:.6f}",
                    f"{data['rx_mbps']:.6f}",
                    f"{data['total_mbps']:.6f}"
                ])
            
            print(f"\nSwitch {dpid} Bandwidth Statistics:")
            print(tabulate(table_data, headers=["Port", "TX (Mbps)", "RX (Mbps)", "Total (Mbps)"], tablefmt="grid"))
    
    def monitor_network(self, interval=5, cycles=1):
        print("Starting monitoring")
        
        for cycle in range(cycles):
            self.get_switches()
            self.get_links()
        
            if not self.collect_port_stats():
                print("Failed to collect port statistics")
                time.sleep(1)
                continue
            try:
                bandwidth_data = self.calculate_bandwidth(interval)
                self.display_port_stats(bandwidth_data)
            except Exception as e:
                print(f"Error calculating bandwidth: {e}")
            
            if cycle < cycles - 1:
                time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="Ryu Network Monitor")
    parser.add_argument('--controller', default='127.0.0.1', help='Controller IP address')
    parser.add_argument('--port', type=int, default=8080, help='Controller REST API port')
    parser.add_argument('--interval', type=int, default=5, help='Statistics collection interval in seconds')
    parser.add_argument('--cycles', type=int, default=1, help='Number of monitoring cycles')
    args = parser.parse_args()

    monitor = RyuNetworkMonitor(controller_ip=args.controller, rest_port=args.port)
    monitor.monitor_network(interval=args.interval, cycles=args.cycles)


if __name__ == "__main__":
    main()