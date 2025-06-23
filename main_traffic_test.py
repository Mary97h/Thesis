import csv
import json
import statistics
import time
import os
import threading
from mininet.log import info, error
from wifi_test import run_concurrent_tests

class NetworkTester:
    def __init__(self, net):
        self.net = net
        self.host_ips = {
            'h0': '10.0.0.1', 'h1': '10.0.0.2', 'h2': '10.0.0.3', 'h3': '10.0.0.4',
            'h4': '10.0.0.8', 'h5': '10.0.0.5', 'h6': '10.0.0.6', 'h7': '10.0.0.7',
            'h8': '10.0.0.9', 'h9': '10.0.0.10', 'h10': '10.0.0.11',
            'sta1': '10.0.0.101', 'sta2': '10.0.0.102', 'sta3': '10.0.0.103'
        }
    
    def format_timestamp(self, timestamp):
        """Convert timestamp to readable format: YYYY-MM-DD HH:MM:SS.microseconds"""
        try:
            if isinstance(timestamp, str):
                if '_' in timestamp and len(timestamp) == 15:
                    dt = time.strptime(timestamp, "%Y%m%d_%H%M%S")
                    return time.strftime("%Y-%m-%d %H:%M:%S", dt)
                return timestamp
            else:
                ts = float(timestamp)
                return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts)) + f".{int((ts % 1)*1e6):06d}"
        except:
            return str(timestamp)
        
    def monitor_video_quality(self, duration=60):
        results = {'video_quality': [], 'start_time': time.time()}
        h0 = self.net.get('h0')
        
        def collect():
            prev_rx, prev_time = None, None
            arrival_times = []
            
            for _ in range(duration // 5):
                timestamp = time.time()
                output = h0.cmd('cat /proc/net/dev | grep h0-eth0')
                
                if output:
                    parts = output.strip().split()
                    if len(parts) >= 10:
                        rx_bytes, rx_packets = int(parts[1]), int(parts[2])
                        rx_errs, rx_drop = int(parts[3]), int(parts[4])
                        loss_rate = (rx_errs + rx_drop) / max(rx_packets, 1) * 100
                        
                        if rx_packets > 0 and not results.get('first_packet_time'):
                            results['first_packet_time'] = timestamp
                            
                        jitter = None
                        if prev_rx and prev_time and rx_packets > prev_rx:
                            arrival_times.append(timestamp)
                            if len(arrival_times) >= 3:
                                diffs = [arrival_times[i] - arrival_times[i-1] for i in range(1, len(arrival_times))]
                                jitter = statistics.stdev(diffs[-10:]) if len(diffs) > 1 else 0
                        
                        results['video_quality'].append({
                            'timestamp': self.format_timestamp(timestamp),
                            'rx_bytes': rx_bytes, 'rx_packets': rx_packets,
                            'rx_errors': rx_errs, 'rx_dropped': rx_drop,
                            'packet_loss_rate': loss_rate, 'jitter': jitter
                        })
                        
                        prev_rx, prev_time = rx_packets, timestamp
                time.sleep(5)
        
        thread = threading.Thread(target=collect, daemon=True)
        thread.start()
        return thread, results
    
    def analyze_video_quality(self, results):
        data = results['video_quality']
        if len(data) < 3:
            return None
        packet_times = []
        for entry in data:
            if entry['rx_packets'] > 0:
                try:
                    ts_str = entry['timestamp']
                    if '.' in ts_str:
                        dt_part, micro_part = ts_str.split('.')
                        dt = time.strptime(dt_part, "%Y-%m-%d %H:%M:%S")
                        ts = time.mktime(dt) + float('0.' + micro_part)
                    else:
                        dt = time.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                        ts = time.mktime(dt)
                    packet_times.append(ts)
                except:
                    continue
                    
        if len(packet_times) < 3:
            return None
            
        inter_times = [packet_times[i] - packet_times[i-1] for i in range(1, len(packet_times))]
        rfc3550_jitter = 0
        for i in range(1, len(inter_times)):
            d = abs(inter_times[i] - inter_times[i-1])
            rfc3550_jitter = rfc3550_jitter + (d - rfc3550_jitter) / 16
        
        quality = "Excellent" if rfc3550_jitter < 0.020 else "Good" if rfc3550_jitter < 0.050 else "Fair" if rfc3550_jitter < 0.100 else "Poor"
        
        return {'rfc3550_jitter': rfc3550_jitter, 'quality': quality}
    
    def setup_video_stream(self):
        sta1, h0 = self.net.get('sta1'), self.net.get('h0')
        if not (sta1 and h0):
            return False
            
        video_path = "/home/wifi/test-video/HD_fixed.mp4"
        if not os.path.exists(video_path):
            os.makedirs("/home/wifi/test-video", exist_ok=True)
            cmd = f"ffmpeg -f lavfi -i testsrc=duration=60:size=360x240:rate=30 -f lavfi -i sine=frequency=1000:duration=60 -c:v libx264 -preset ultrafast -c:a aac -shortest {video_path}"
            os.system(cmd)
            
        h0.cmd("pkill -f 'cvlc'")
        h0.cmd("sudo -u wifi cvlc udp://@:1234 --network-caching=1500 --sout file/ts:/tmp/sta1_to_h0_video.ts --run-time=180 --play-and-exit > /tmp/vlc_recv_sta1.log 2>&1 &")

        time.sleep(5)
        sta1.cmd("sudo -u wifi cvlc --intf dummy /home/wifi/test-video/HD_fixed.mp4 --sout '#udp{dst=10.0.0.1:1234}' --sout-ffmpeg-strict=-2 --play-and-exit > /tmp/vlc_send_sta1.log 2>&1 &")

        return True
    
    def start_servers(self, scenarios):
        server_map = {}
        for scenario in scenarios:
            server_ip, port = scenario['server_ip'], scenario.get('port', 5201)
            for host, ip in self.host_ips.items():
                if ip == server_ip and (host, port) not in server_map:
                    host_obj = self.net.get(host)
                    if host_obj:
                        host_obj.cmd(f"pkill -f 'iperf3 -s -p {port}'")
                        time.sleep(0.5)
                        result = host_obj.cmd(f"iperf3 -s -p {port} -D")
                        if "error" not in result.lower():
                            server_map[(host, port)] = True
                            
    def inject_background_traffic(self):
        flows = [("h8", "h4", "20M"),
                 ("h5", "h10", "20M")]
        
        for i, (src, dst, bw) in enumerate(flows, 4000):
            src_host, dst_host = self.net.get(src), self.net.get(dst)
            dst_ip = self.host_ips.get(dst)
            if src_host and dst_host and dst_ip:
                dst_host.cmd(f"pkill -f 'iperf3 -s -p {i}'; iperf3 -s -p {i} -D")
                time.sleep(1)
                src_host.cmd(f"iperf3 -c {dst_ip} -p {i} -b {bw} -t 9999 > /dev/null 2>&1 &")
                
    def create_test_scenarios(self):
        configs = [
            ('sta2', '10.0.0.2', 15, 30, 5202), ('sta3', '10.0.0.3', 40, 30, 5203),
            ('sta4', '10.0.0.4', 15, 60, 5204), ('sta5', '10.0.0.5', 15, 60, 5205),
            ('sta6', '10.0.0.6', 15, 30, 5206), ('sta7', '10.0.0.7', 15, 30, 5207),
            ('sta8', '10.0.0.8', 15, 30, 5208), ('sta9', '10.0.0.9', 15, 30, 5209),
            ('sta10', '10.0.0.10', 15, 30, 5210)
        ]
        
        scenarios = []
        for sta, server_ip, bw, duration, port in configs:
            station = self.net.get(sta)
            if station:
                scenarios.append({
                    'station': station, 'server_ip': server_ip,
                    'bandwidth_mbps': bw, 'duration_seconds': duration,
                    'protocol': 'tcp', 'port': port
                })
        return scenarios
    
    def cleanup_servers(self, scenarios):
        cleaned = set()
        for scenario in scenarios:
            server_ip, port = scenario['server_ip'], scenario.get('port', 5201)
            for host, ip in self.host_ips.items():
                if ip == server_ip and (host, port) not in cleaned:
                    host_obj = self.net.get(host)
                    if host_obj:
                        host_obj.cmd(f"pkill -f 'iperf3 -s -p {port}'")
                        cleaned.add((host, port))
    
    def save_results(self, results, video_results=None, output_dir="network_test_results"):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        os.makedirs(output_dir, exist_ok=True)
        
        if results:
            with open(f"{output_dir}/results_{timestamp}.json", "w") as f:
                json.dump(results, f, indent=2)
            all_keys = set()
            for res in results:
                all_keys.update(res.keys())
                    
            with open(f"{output_dir}/results_{timestamp}.csv", "w", newline='') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                writer.writeheader()
                for row in results:
                    formatted_row = row.copy()
                    for key in ['allocation_start_time', 'timestamp', 'start_time', 'end_time']:
                        if key in formatted_row:
                            formatted_row[key] = self.format_timestamp(formatted_row[key])
                    
                    writer.writerow(formatted_row)
        
        if video_results and video_results.get('video_quality'):
            with open(f"{output_dir}/video_kpis_{timestamp}.csv", "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "timestamp", "rx_bytes", "rx_packets", "rx_errors", 
                    "rx_dropped", "packet_loss_rate", "jitter"
                ])
                writer.writeheader()
                writer.writerows(video_results['video_quality']) 
    
    def print_summary(self, test_results, video_results):
        successful = [r for r in test_results if r.get('success', False)]
        print(f"\nTest Results: {len(successful)}/{len(test_results)} successful")
        
        for i, test in enumerate(successful):
            print(f"{i+1}. {test.get('station', 'Unknown')} -> {test.get('selected_ap', 'Unknown')}: {test.get('avg_mbps', 0):.1f} Mbps")
        
        data = video_results['video_quality']
        if len(data) >= 2:
            total_packets = data[-1]['rx_packets'] - data[0]['rx_packets']
            duration = time.time() - video_results['start_time']
            print(f"\n[VIDEO] Packets: {total_packets}, Duration: {duration:.1f}s")
            
            enhanced_metrics = self.analyze_video_quality(video_results)
            if enhanced_metrics:
                print(f"Video Quality: {enhanced_metrics['quality']} (Jitter: {enhanced_metrics['rfc3550_jitter']:.6f}s)")
    
    def run_test(self):
        scenarios = self.create_test_scenarios()
        aps = [self.net.get(f'ap{i}') for i in range(1, 9)]
        
        print("Starting network test - setting up servers")
        self.start_servers(scenarios)
        time.sleep(5)
        
        print("Injecting background traffic")
        self.inject_background_traffic()
        time.sleep(10)
        
        print("Starting video stream")
        self.setup_video_stream()
        monitor_thread, video_results = self.monitor_video_quality(60)
        
        try:
            print("Running concurrent tests")
            test_results = run_concurrent_tests(scenarios, aps, self.net)
            self.print_summary(test_results, video_results)
            self.save_results(test_results, video_results)
            
        finally:
            self.cleanup_servers(scenarios)
            

def main_traffic_test(net):
    tester = NetworkTester(net)
    return tester.run_test()

def run_network_tests(net):
    return main_traffic_test(net)