import math
import time
import threading
from mininet.log import info, error
from threading import Lock, Thread
import json
import re

def get_visible_aps(station):
    result = station.cmd(f'iw dev {station.name}-wlan0 scan')
    print(f"\n--- Raw Scan Output for {station.name} ---\n{result}\n")
    aps = {}
    current_ssid = None
    rssi = None

    for line in result.splitlines():
        line = line.strip()
        if line.startswith("BSS"):
            current_ssid = None
            rssi = None
        elif line.startswith("signal:"):
            rssi_match = re.search(r'signal:\s*(-?\d+(?:\.\d+)?)\s*dBm', line)
            if rssi_match:
                rssi = float(rssi_match.group(1))
        elif line.startswith("SSID:"):
            current_ssid = line.split("SSID:")[1].strip()
            if current_ssid and rssi is not None:
                aps[current_ssid] = rssi

    return aps

def get_rssi(station, ap):
    rssi_output = station.cmd(f'iw dev {station.name}-wlan0 link')
    match = re.search(r'signal:\s*(-\d+)\s*dBm', rssi_output)
    if match:
        rssi = int(match.group(1))
        info(f"RSSI for {station.name} is {rssi} dBm\n")
        return rssi
    else:
        info(f"No RSSI info found for {station.name}\n")
        return None

def rssi_to_cqi(rssi):
    thresholds = [(-100, 1), (-90, 3), (-80, 5), (-70, 7), (-60, 10), (-50, 12)]
    for threshold, cqi in thresholds:
        if rssi < threshold:
            return cqi
    return 15

def scan_and_select_ap(station, ap_list, min_rssi_threshold=-90):
    info(f"{station.name} scanning for visible APs...\n")
    
    scan_results = get_visible_aps(station)
    best_ap = None
    best_rssi = -999
    best_cqi = 1
    available_aps = []

    for ap in ap_list:
        ssid = ap.params.get('ssid') or f"{ap.name}-ssid"
        if ssid in scan_results:
            rssi = scan_results[ssid]
            cqi = rssi_to_cqi(rssi)
            info(f"{station.name} sees {ap.name} (SSID {ssid}): RSSI={rssi}, CQI={cqi}\n")
            available_aps.append((ap, rssi))
            if rssi > best_rssi:
                best_rssi = rssi
                best_ap = ap
                best_cqi = cqi
        if not ssid:
            error(f"[WARN] {ap.name} has no SSID defined in .params!\n")
            continue
        if not scan_results:
            info(f"No APs detected at all by {station.name}\n")

    if best_ap:
        info(f"{station.name} selected {best_ap.name} with RSSI {best_rssi} dBm\n")
    else:
        info(f"No suitable AP found for {station.name}\n")

    return best_ap, available_aps, best_cqi

def request_and_reserve_rbs(station, ap, required_rbs, duration_seconds, net):
    info(f" {station.name} requesting {required_rbs} RBs from {ap.name} for {duration_seconds}s...\n")

    try:
        required_rbs = int(required_rbs)
        duration_seconds = int(duration_seconds)

        if hasattr(ap, 'allocate_rbs'):
            success = ap.allocate_rbs(station, required_rbs, duration=duration_seconds, net=net)
            if success:
                info(f"{station.name} reserved {required_rbs} RBs from {ap.name}\n")
                return True
            else:
                info(f"Failed to allocate RBs for {station.name} from {ap.name}\n")
                return False
        else:
            info(f"AP {ap.name} is standard AP, simulating RB allocation\n")
            return True

    except Exception as e:
        error(f"Error reserving RBs: {e}\n")
        return False

def is_iperf3_server_alive(station, server_ip, port=5201):
    result = station.cmd(f'nc -zvw2 {server_ip} {port} 2>&1')
    return "succeeded" in result or "open" in result

def run_iperf_test(station, server_ip, bandwidth_mbps, duration_seconds, protocol='tcp', port=5201):
    info(f"Starting iperf test: {station.name} -> {server_ip} at {bandwidth_mbps} Mbps for {duration_seconds}s (port {port})\n")

    try:
        ping_result = station.cmd(f'ping -c 1 {server_ip}')
        if 'unreachable' in ping_result or '100% packet loss' in ping_result:
            error(f" {station.name} cannot reach {server_ip}\n")
            return None

        for attempt in range(5):
            if is_iperf3_server_alive(station, server_ip, port):
                break
            info(f"[{station.name}] Waiting for iperf3 server on port {port} (attempt {attempt+1}/5)\n")
            time.sleep(2)
        else:
            error(f"[!] iperf3 server at {server_ip}:{port} not reachable from {station.name}\n")
            return None

        if protocol.lower() == 'tcp':
            cmd = f"iperf3 -c {server_ip} -p {port} -t {duration_seconds} -J"
        else:
            cmd = f"iperf3 -c {server_ip} -u -b {bandwidth_mbps}M -p {port} -t {duration_seconds} -J"

        info(f" Executing: {cmd}\n")
        result = station.cmd(cmd)

        info(f"iperf test completed for {station.name} on port {port}\n")
        return result

    except Exception as e:
        error(f"Error running iperf test: {e}\n")
        return None

def release_resources(station, ap, net):
    info(f"Releasing resources for {station.name} from {ap.name}...\n")

    try:
        if hasattr(ap, 'release_rbs'):
            ap.release_rbs(station.name, net)
            info(f"RBs released for {station.name}\n")

        if hasattr(ap, 'allocations') and station.name in ap.allocations:
            allocation = ap.allocations[station.name]
            if 'link' in allocation:
                link = allocation['link']
                try:
                    if link in net.links:
                        net.delLink(link)
                        info(f"Dynamic link deleted: {station.name} <-> {ap.name}\n")
                    else:
                        info(f"Link {station.name} <-> {ap.name} already removed\n")
                except Exception as e:
                    error(f"Error deleting link {station.name}<->{ap.name}: {e}\n")
        else:
            for intf in station.intfList():
                try:
                    if (intf.link and 
                        hasattr(intf.link, 'intf1') and hasattr(intf.link, 'intf2')):
                        other_node = None
                        if hasattr(intf.link.intf1, 'node') and intf.link.intf1.node == station:
                            other_node = getattr(intf.link.intf2, 'node', None)
                        elif hasattr(intf.link.intf2, 'node') and intf.link.intf2.node == station:
                            other_node = getattr(intf.link.intf1, 'node', None)
                        
                        if other_node == ap:
                            if intf.link in net.links:
                                net.delLink(intf.link)
                                info(f"Found and deleted link: {station.name} <-> {ap.name}\n")
                            break
                except AttributeError:
                    continue

    except Exception as e:
        error(f"Error in resource cleanup: {e}\n")

def parse_iperf_result(iperf_result, protocol):
    if not iperf_result:
        return {}, 0
    
    try:
        iperf_data = json.loads(iperf_result)
        iperf_end = iperf_data.get('end', {})

        if protocol == 'tcp':
            sum_stats = iperf_end.get('sum_received') or iperf_end.get('sum', {})
            result_summary = {
                'tx_bytes': iperf_end.get('sum_sent', {}).get('bytes', 0),
                'tx_mbps': iperf_end.get('sum_sent', {}).get('bits_per_second', 0) / 1e6,
                'rx_bytes': sum_stats.get('bytes', 0),
                'rx_mbps': sum_stats.get('bits_per_second', 0) / 1e6
            }
            avg_mbps = result_summary['rx_mbps']
        else:
            sum_stats = iperf_end.get('sum', {})
            result_summary = {
                'tx_bytes': iperf_data.get('start', {}).get('connected', [{}])[0].get('bytes', 0),
                'rx_bytes': sum_stats.get('bytes', 0),
                'rx_mbps': sum_stats.get('bits_per_second', 0) / 1e6,
                'jitter_ms': sum_stats.get('jitter_ms', 0),
                'lost_packets': sum_stats.get('lost_packets', 0),
                'total_packets': sum_stats.get('packets', 0),
                'loss_percent': sum_stats.get('lost_percent', 0),
            }
            avg_mbps = result_summary['rx_mbps']
        return result_summary, avg_mbps
    except Exception as e:
        print(f"[!] iperf3 RAW output: {iperf_result[:300]}")
        error(f"[!] Failed to parse iperf3 JSON: {e}\n")
        return {}, 0

def wifi_resource_manager(station, server_ip, bandwidth_mbps, ap_list, net,
                          duration_seconds=60, protocol='tcp', port=5201):
    info(f"Starting WiFi resource management for {station.name}\n")
    info(f"   Target: {server_ip}, Bandwidth: {bandwidth_mbps} Mbps, Duration: {duration_seconds}s, Port: {port}\n")

    allocation_attempts = []

    if not all([station, net, ap_list]):
        return {'success': False, 'error': 'Invalid inputs'}

    selected_ap, available_aps, _ = scan_and_select_ap(station, ap_list)

    if not available_aps:
        return {'success': False, 'error': 'No suitable AP found'}

    available_aps.sort(key=lambda x: x[1], reverse=True)

    for ap, rssi in available_aps:
        cqi = rssi_to_cqi(rssi)
        required_rbs = ap.estimate_required_rbs(bandwidth_mbps, cqi_level=cqi)
        initial_available_rbs = ap.available_rbs
        initial_total_rbs = ap.total_rbs

        info(f"Trying AP {ap.name} (RSSI: {rssi}, CQI: {cqi}) with {required_rbs} required RBs\n")

        success = request_and_reserve_rbs(station, ap, required_rbs, duration_seconds, net)

        allocation_attempts.append({
            'ap_name': ap.name,
            'rssi': rssi,
            'cqi': cqi,
            'required_rbs': required_rbs,
            'available_rbs_before': initial_available_rbs,
            'total_rbs': initial_total_rbs,
            'success': success
        })

        if success:
            selected_ap = ap
            estimated_cqi = cqi
            remaining_rbs = ap.available_rbs
            break
        else:
            selected_ap = None

    if not selected_ap:
        return {
            'success': False,
            'error': 'RB reservation failed on all available APs',
            'available_aps': [(ap.name, rssi) for ap, rssi in available_aps],
            'bandwidth_mbps': bandwidth_mbps,
            'duration_seconds': duration_seconds,
            'required_rbs': required_rbs,
            'station': station.name,
            'allocation_attempts': allocation_attempts
        }

    try:
        time.sleep(1)
        iperf_result = run_iperf_test(station, server_ip, bandwidth_mbps, duration_seconds, protocol, port)
        time.sleep(1)

        result_summary, avg_mbps = parse_iperf_result(iperf_result, protocol)

        result = {
            'success': True,
            'selected_ap': selected_ap.name,
            'available_aps': [(ap.name, rssi) for ap, rssi in available_aps],
            'bandwidth_mbps': bandwidth_mbps,
            'duration_seconds': duration_seconds,
            'required_rbs': required_rbs,
            'protocol': protocol,
            'avg_mbps': avg_mbps,
            'timestamp': time.strftime("%Y%m%d_%H%M%S"),
            'selected_ap_available_rbs_after_alloc': remaining_rbs,
            'selected_ap_available_rbs_before_alloc': initial_available_rbs,
            'selected_ap_total_rbs': initial_total_rbs,
            'allocation_start_time': time.time(),
            'error': '',
            'port_used': port,
            'station': station.name,
            'estimated_cqi': estimated_cqi,
            'allocation_attempts': allocation_attempts
        }

        result.update(result_summary)
        return result

    finally:
        release_resources(station, selected_ap, net)

def setup_iperf_servers(test_scenarios):
    unique_servers = {}
    
    for idx, scenario in enumerate(test_scenarios):
        server_ip = scenario['server_ip']
        port = scenario.get('port', 5201 + idx)
        
        if server_ip not in unique_servers:
            unique_servers[server_ip] = []
        unique_servers[server_ip].append(port)
    
    info(f"[SETUP] Need iperf3 servers: {unique_servers}\n")
    return unique_servers

def run_concurrent_tests(test_scenarios, aps, net):
    threads = []
    results = [None] * len(test_scenarios)  
    
    setup_iperf_servers(test_scenarios)

    def run_test(scenario, index):
        station = scenario['station']
        server_ip = scenario['server_ip']
        bandwidth_mbps = scenario['bandwidth_mbps']
        duration_seconds = scenario['duration_seconds']
        protocol = scenario['protocol']

        port = scenario.get('port', 5201 + index)  
        
        info(f"[CONCURRENT] Starting test {index}: {station.name} -> {server_ip}:{port}\n")

        result = wifi_resource_manager(
            station, server_ip, bandwidth_mbps, aps, net,
            duration_seconds=duration_seconds,
            protocol=protocol,
            port=port
        )
        
        results[index] = result
        info(f"[CONCURRENT] Completed test {index}: {station.name} (success: {result.get('success', False)})\n")

    for idx, scenario in enumerate(test_scenarios):
        t = Thread(target=run_test, args=(scenario, idx))
        threads.append(t)
        t.start()
        time.sleep(0.5)

    for t in threads:
        t.join()

    return [r for r in results if r is not None] 

def run_sequential_tests_with_sharing(test_scenarios, aps, net):
    results = []
    
    for idx, scenario in enumerate(test_scenarios):
        info(f"[SEQUENTIAL] Starting test {idx+1}/{len(test_scenarios)}: {scenario['station'].name}\n")
        
        result = wifi_resource_manager(
            scenario['station'], 
            scenario['server_ip'], 
            scenario['bandwidth_mbps'], 
            aps, 
            net,
            duration_seconds=scenario['duration_seconds'],
            protocol=scenario['protocol'],
            port=scenario.get('port', 5201)
        )
        
        results.append(result)
        time.sleep(2)
        
        info(f"[SEQUENTIAL] Completed test {idx+1}: success={result.get('success', False)}\n")
    
    return results