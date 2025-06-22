import time
import json
import csv
import os
from datetime import datetime
from mn_wifi.node import OVSKernelAP
from mininet.link import TCLink
from mininet.log import info, error

active_links = []
test_results_log = []

class ResourceAP(OVSKernelAP):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_rbs = 52
        self.available_rbs = 52
        self.allocations = {}
        self.allocation_history = []

    def _log_allocation(self, sta_name, action, rbs, **kwargs):
        entry = {
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'station': sta_name,
            'action': action,
            'rbs': rbs,
            'remaining_rbs': self.available_rbs,
            **kwargs
        }
        self.allocation_history.append(entry)
        return entry['timestamp']

    def _find_link(self, sta, net):
        for net_link in net.links:
            try:
                nodes = [getattr(net_link.intf1, 'node', None), getattr(net_link.intf2, 'node', None)]
                if sta in nodes and self in nodes:
                    return net_link
            except AttributeError:
                continue
    
        for intf in sta.intfList():
            try:
                link = getattr(intf, 'link', None)
                if link and hasattr(link, 'intf1') and hasattr(link, 'intf2'):
                    nodes = [getattr(link.intf1, 'node', None), getattr(link.intf2, 'node', None)]
                    if self in nodes:
                        return link
            except AttributeError:
                continue
        return None

    def allocate_rbs(self, sta, num_rbs, duration=10, net=None):
        timestamp = self._log_info_header(sta, num_rbs, duration)
        
        if self.available_rbs < num_rbs:
            self._log_denial(sta, num_rbs, timestamp)
            return False
        
        return self._process_allocation(sta, num_rbs, duration, net, timestamp)

    def _log_info_header(self, sta, num_rbs, duration):
        """Log allocation request details"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        info(f"[{timestamp}] [AP {self.name}] Processing RB allocation request...\n"
             f"   Station: {sta.name}, Requested: {num_rbs} RBs, Duration: {duration}s\n"
             f"   Available: {self.available_rbs}/{self.total_rbs} RBs\n")
        return timestamp

    def _log_denial(self, sta, num_rbs, timestamp):
        info(f"[{timestamp}] [AP {self.name}] RB allocation DENIED!\n"
             f"   Requested: {num_rbs}, Available: {self.available_rbs}, Shortage: {num_rbs - self.available_rbs}\n")
        self._log_allocation(sta.name, 'DENIED', num_rbs, reason='Insufficient resources', available_rbs=self.available_rbs)

    def _process_allocation(self, sta, num_rbs, duration, net, timestamp):
        """Process the actual allocation"""
        try:
            self.available_rbs -= num_rbs
            end_time = time.time() + duration
            
            info(f"[{timestamp}] [AP {self.name}] RB allocation approved! Allocated: {num_rbs}, Remaining: {self.available_rbs}\n")
            
            link = net.addLink(sta, self, cls=TCLink, bw=num_rbs) or self._find_link(sta, net)
            
            if not link:
                error(f"[{timestamp}] [AP {self.name}] Could not find/create link to {sta.name}\n")
                self.available_rbs += num_rbs 
                return False
            
            self.allocations[sta.name] = {
                'rb': num_rbs, 'end_time': end_time, 'link': link, 'bandwidth': num_rbs,
                'start_time': time.time(), 'duration': duration
            }
            
            active_links.append({
                'sta': sta, 'ap': self, 'link': link, 'end_time': end_time,
                'start_time': time.time(), 'bandwidth': num_rbs, 'rb_count': num_rbs
            })
            
            self._log_allocation(sta.name, 'ALLOCATED', num_rbs, bandwidth=num_rbs, duration=duration)
            self._log_link_details(sta, num_rbs, end_time, duration, timestamp)
            
            return True
            
        except Exception as e:
            error(f"[{timestamp}] [AP {self.name}] Failed to create link: {type(e).__name__}: {e}\n")
            self.available_rbs += num_rbs
            return False

    def _log_link_details(self, sta, bandwidth, end_time, duration, timestamp):
        """Log link creation details"""
        info(f"[{timestamp}] [AP {self.name}] Link created successfully!\n"
             f"   Link: {sta.name} <-> {self.name}, Bandwidth: {bandwidth} Mbps\n"
             f"   Expires: {datetime.fromtimestamp(end_time).strftime('%H:%M:%S')}, Duration: {duration}s\n"
             f"**DEBUGG {sta.name} - IP: {sta.IP()}, Interfaces: {sta.intfNames()}\n")

    def release_rbs(self, sta_name, net=None):
        if sta_name not in self.allocations:
            return False
        
        allocation = self.allocations.pop(sta_name)
        self.available_rbs += allocation['rb']
        
        timestamp = self._log_allocation(sta_name, 'MANUAL_RELEASE', allocation['rb'])
        info(f"[{timestamp}] [AP {self.name}] Manual release - Station: {sta_name}, "
             f"Released: {allocation['rb']} RBs, Available: {self.available_rbs}/{self.total_rbs}\n")
        return True

    def check_expired_allocations(self):
        now = time.time()
        expired = [(name, alloc) for name, alloc in self.allocations.items() if alloc['end_time'] <= now]
        
        for sta_name, allocation in expired:
            self.available_rbs += allocation['rb']
            actual_duration = now - allocation['start_time']
            
            timestamp = self._log_allocation(
                sta_name, 'EXPIRED', allocation['rb'],
                planned_duration=allocation['duration'],
                actual_duration=actual_duration,
                bandwidth=allocation['bandwidth']
            )
            
            info(f"[{timestamp}] [AP {self.name}] RB allocation EXPIRED!\n"
                 f"   Station: {sta_name}, Released: {allocation['rb']} RBs\n"
                 f"   Duration: {actual_duration:.1f}s (planned: {allocation['duration']}s)\n"
                 f"   Available: {self.available_rbs}/{self.total_rbs} RBs\n")
            
            del self.allocations[sta_name]

    def get_allocation_history(self):
        return self.allocation_history

    def save_allocation_log(self, filename=None):
        """Save allocation history to file"""
        filename = filename or f"ap_{self.name}_allocations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        return self._save_json(self.allocation_history, filename, f"[AP {self.name}] Allocation history")

    def estimate_required_rbs(self, bandwidth_mbps, cqi_level=10):
        """Estimate required RBs based on bandwidth and CQI"""
        cqi_capacity = {5: 0.3, 7: 0.6, 9: 0.9, 10: 1.0, 12: 1.2, 15: 1.4}
        rb_capacity = cqi_capacity.get(cqi_level, 1.0)
        return int((bandwidth_mbps / rb_capacity) + 0.5)

    def _save_json(self, data, filename, description):
        """Helper method to save JSON data"""
        filepath = os.path.join(os.getcwd(), filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            info(f"{description} saved to {filepath}\n")
            return filepath
        except Exception as e:
            error(f"Error saving {description.lower()}: {e}\n")
            return None


def monitor_resource_blocks(aps, net, interval=1):
    global active_links
    info("Resource block monitor started...\n")
    
    while True:
        now = time.time()
        timestamp = datetime.now().strftime("%H:%M:%S")
    
        for ap in aps:
            ap.check_expired_allocations()
        
        active_links = [entry for entry in active_links if not _cleanup_expired_link(entry, now, timestamp, net)]
        time.sleep(interval)


def _cleanup_expired_link(entry, now, timestamp, net):
    """Helper function to cleanup expired links"""
    if now < entry['end_time']:
        return False 
    
    duration = now - entry['start_time']
    info(f"[{timestamp}] Cleaning up expired link: {entry['sta'].name} <-> {entry['ap'].name} "
         f"(Duration: {duration:.1f}s)\n")
    
    try:
        if entry['link'] in net.links:
            net.delLink(entry['link'])
            info(f"[{timestamp}] Link deleted successfully!\n")
        else:
            info(f"[{timestamp}] Link already cleaned up\n")
    except Exception as e:
        info(f"[{timestamp}] Link cleanup note: {e}\n")
    
    return True


def save_test_results(results, filename=None):
    """Save test results to JSON and CSV files"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_name = filename or "test_results"
    
    json_file = _save_results_json(results, f"{base_name}_{timestamp}.json")
    
    csv_file = _save_results_csv(results, f"{base_name}_{timestamp}.csv")
    
    return json_file, csv_file


def _save_results_json(results, filename):
    """Save results as JSON"""
    filepath = os.path.join(os.getcwd(), filename)
    try:
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
        info(f"Test results saved to {filepath}\n")
        return filepath
    except Exception as e:
        error(f"Error saving JSON results: {e}\n")
        return None


def _save_results_csv(results, filename):
    """Save results as CSV"""
    if not results:
        return None
    
    filepath = os.path.join(os.getcwd(), filename)
    fieldnames = [
        'success', 'selected_ap', 'bandwidth_mbps', 'duration_seconds', 'error', 'station',
        'attempt_ap', 'attempt_rssi', 'attempt_cqi', 'required_rbs',
        'available_rbs_before', 'total_rbs', 'attempt_success'
    ]
    
    try:
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                attempts = result.get('allocation_attempts', [])
                base_row = {
                    'success': result.get('success', False),
                    'selected_ap': result.get('selected_ap', 'N/A'),
                    'bandwidth_mbps': result.get('bandwidth_mbps', 0),
                    'duration_seconds': result.get('duration_seconds', 0),
                    'error': result.get('error', ''),
                    'station': result.get('station', 'N/A')
                }
                
                if attempts:
                    for attempt in attempts:
                        row = {**base_row, **{
                            'attempt_ap': attempt.get('ap_name', ''),
                            'attempt_rssi': attempt.get('rssi', ''),
                            'attempt_cqi': attempt.get('cqi', ''),
                            'required_rbs': attempt.get('required_rbs', ''),
                            'available_rbs_before': attempt.get('available_rbs_before', ''),
                            'total_rbs': attempt.get('total_rbs', ''),
                            'attempt_success': attempt.get('success', False)
                        }}
                        writer.writerow(row)
                else:
                    writer.writerow({**base_row, **{k: '' for k in fieldnames[6:]}})
        
        info(f"Test results saved to {filepath}\n")
        return filepath
    except Exception as e:
        error(f"Error saving CSV results: {e}\n")
        return None


def save_all_ap_logs(aps):
    """Save allocation logs for all APs"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    all_logs = {ap.name: ap.get_allocation_history() for ap in aps if hasattr(ap, 'get_allocation_history')}
    
    filename = f"all_ap_allocations_{timestamp}.json"
    filepath = os.path.join(os.getcwd(), filename)
    
    try:
        with open(filepath, 'w') as f:
            json.dump(all_logs, f, indent=2)
        info(f"All AP allocation logs saved to {filepath}\n")
        return filepath
    except Exception as e:
        error(f"Error saving AP logs: {e}\n")
        return None