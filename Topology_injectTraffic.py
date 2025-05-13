from mininet.node import RemoteController, OVSKernelSwitch, Host
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import Station, OVSKernelAP
from mn_wifi.cli import CLI
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
from subprocess import call
import os
import time
import json
import numpy as np
import csv
import re
from collections import defaultdict


def calculate_free_bandwidth(link_usage, max_bw=100):
    return max_bw - link_usage

def inject_custom_traffic(net):

    h0 = net.get('h0')
    h8 = net.get('h8')
    h1 = net.get('h1')

    for host in [h0, h1, h8]:
        host.cmd('pkill -9 iperf')
        host.cmd('pkill -9 ping')
    
    info("Starting Iperf UDP server on h0...\n")
    h0_server = h0.popen('iperf -s -u -p 5001')
    
    time.sleep(1)
    server_check = h0.cmd('ps aux | grep "iperf -s -u" | grep -v grep')
    if not server_check:
        info("*** ERROR: Failed to start iperf server on h0. Retrying...\n")
        h0_server = h0.popen('iperf -s -u -p 5001')
        time.sleep(1)

    info("Starting UDP client from h8 to h0...\n")
    h8_client = h8.popen(f'iperf -u -c {h0.IP()} -p 5001 -b 5M -t 9999')
    
    time.sleep(1)
    client_check = h8.cmd('ps aux | grep "iperf -u -c" | grep -v grep')
    if not client_check:
        info("*** ERROR: Failed to start iperf client on h8. Retrying...\n")
        h8_client = h8.popen(f'iperf -u -c {h0.IP()} -p 5001 -b 20M -l 1470 -t 9999')

    info("Starting background traffic (ping) between h1 and h8...\n")
    h1_ping = h1.popen(f'ping {h8.IP()} -i 0.2 -s 1000')
    
    info("Starting TCP background traffic between h1 and h8...\n")
    h1_server = h1.popen('iperf -s -p 5002')
    time.sleep(1)
    h8_tcp = h8.popen(f'iperf -c {h1.IP()} -p 5002 -b 5M -t 9999') 

    time.sleep(2)
    info("\n=== Traffic verification ===\n")
    iperf_check = h0.cmd('netstat -anp | grep 5001')
    info(f"UDP server status on h0: {'ESTABLISHED' in iperf_check}\n")
    info(f"Server netstat: {iperf_check}\n")
    
    tcp_check = h1.cmd('netstat -anp | grep 5002')
    info(f"TCP server status on h1: {'ESTABLISHED' in tcp_check}\n")
    info(f"TCP server netstat: {tcp_check}\n")
    
    ping_check = h1.cmd('ps aux | grep ping | grep -v grep')
    info(f"Ping active: {len(ping_check) > 0}\n")

def save_topology_to_file(net, filename="topology.json"):
    info("[*] Saving topology to JSON file...\n")
    
    all_nodes = []
    for name, obj in net.items():
        all_nodes.append(name)
    all_nodes.sort()
    
    links = []
    seen_links = set()

    for name, node in net.items():
        for intf_name, intf in node.intfs.items():
            if not intf.link: 
                continue
            link = intf.link
            intf1, intf2 = link.intf1, link.intf2

            if not intf1 or not intf2 or id(link) in seen_links:
                continue
            src_node = intf1.node.name

            if isinstance(intf2, str):
                dst_node = intf2 
            else:
                dst_node = intf2.node.name
            try:
                src_port = node.ports[intf1] if src_node == name else -1
                dst_port = -1 
                for other_name, other_node in net.items():
                    if other_name == dst_node:
                        for other_intf_name, other_intf in other_node.intfs.items():
                            if other_intf == intf2:
                                dst_port = other_node.ports[other_intf]
                                break
            except Exception as e:
                info(f"Error getting ports for link {src_node}-{dst_node}: {e}\n")
            
            links.append({
                "src": src_node,
                "dst": dst_node,
                "src_port": src_port,
                "dst_port": dst_port,
                "bw": getattr(link, 'bw', 100),
                "delay": getattr(link, 'delay', '5ms') 
            })
            seen_links.add(id(link))
            
    info(f"Found {len(all_nodes)} nodes and {len(links)} links\n")
    
    topology = {
        "nodes": all_nodes,
        "links": links
    }
    
    filepath = os.path.join(os.getcwd(), filename)
    with open(filepath, "w") as f:
        json.dump(topology, f, indent=2)
    
    info(f"[INFO] Topology saved to {filepath}\n")

    save_adjacency_matrix(topology)
    return topology

def save_adjacency_matrix(topology):
    info("[*] Generating adjacency matrix...\n")
    
    all_nodes = topology["nodes"]
    node_index = {node: idx for idx, node in enumerate(all_nodes)}
    matrix_size = len(all_nodes)
    adjacency_matrix = np.zeros((matrix_size, matrix_size), dtype=int)
    
    for link in topology["links"]:
        src = link["src"]
        dst = link["dst"]
        try:
            if src in node_index and dst in node_index:
                i = node_index[src]
                j = node_index[dst]
                adjacency_matrix[i][j] = 1
                adjacency_matrix[j][i] = 1  
        except KeyError as e:
            info(f"Error in adjacency matrix: {e} not found in node_index\n")
    
    info("\n[INFO] Adjacency Matrix:\n")
    header = "    " + "  ".join(n.ljust(4) for n in all_nodes)
    info(header + "\n")
    
    for i, node in enumerate(all_nodes):
        row = node.ljust(4) + " " + "  ".join(str(x).ljust(4) for x in adjacency_matrix[i])
        info(row + "\n")
    
    csv_filename = os.path.join(os.getcwd(), "adjacency_matrix.csv")
    with open(csv_filename, mode='w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([""] + all_nodes)
        for i, node in enumerate(all_nodes):
            writer.writerow([node] + list(adjacency_matrix[i]))
    
    info(f"\n[INFO] Adjacency matrix saved to {csv_filename}\n")

def myNetwork():
    setup = {'protocols': "OpenFlow13"}

    net = Mininet_wifi(topo=None,
                       build=False,
                       link=wmediumd,
                       wmediumd_mode=interference,
                       ipBase='10.0.0.0/8')

    info('*** Adding controller\n')
    c0 = net.addController(name='c0', controller=RemoteController)

    class DPIDSwitch(OVSKernelSwitch):
        def __init__(self, name, dpid=None, **kwargs):
            if dpid is not None:
                dpid = str(dpid)
            OVSKernelSwitch.__init__(self, name, dpid=dpid, **kwargs)

    class DPIDAP(OVSKernelAP):
        def __init__(self, name, dpid=None, **kwargs):
            dpid = str(dpid) if dpid is not None else None
            OVSKernelAP.__init__(self, name, dpid=dpid, **kwargs)

    info('*** Add switches/APs\n')
    s0 = net.addSwitch('s0', cls=DPIDSwitch, dpid='0000000000000000', **setup)
    s1 = net.addSwitch('s1', cls=DPIDSwitch, dpid='0000000000000001', **setup)
    s2 = net.addSwitch('s2', cls=DPIDSwitch, dpid='0000000000000002', **setup)
    s3 = net.addSwitch('s3', cls=DPIDSwitch, dpid='0000000000000003', **setup)
    s4 = net.addSwitch('s4', cls=DPIDSwitch, dpid='0000000000000004', **setup)
    s5 = net.addSwitch('s5', cls=DPIDSwitch, dpid='0000000000000005', **setup)
    s6 = net.addSwitch('s6', cls=DPIDSwitch, dpid='0000000000000006', **setup)
    s7 = net.addSwitch('s7', cls=DPIDSwitch, dpid='0000000000000007', **setup)
    s8 = net.addSwitch('s8', cls=DPIDSwitch, dpid='0000000000000008', **setup)
    s9 = net.addSwitch('s9', cls=DPIDSwitch, dpid='0000000000000009', **setup)
    s10 = net.addSwitch('s10', cls=DPIDSwitch, dpid='000000000000000a', **setup)

    ap1 = net.addAccessPoint('ap1', cls=DPIDAP, dpid='000000000000000b', ssid='ap1-ssid',
                             channel='1', mode='g', position='337.0,699.0,0', **setup)
    ap2 = net.addAccessPoint('ap2', cls=DPIDAP, dpid='000000000000000c', ssid='ap2-ssid',
                             channel='1', mode='g', position='679.0,697.0,0', **setup)
    ap3 = net.addAccessPoint('ap3', cls=DPIDAP, dpid='000000000000000d', ssid='ap3-ssid',
                             channel='1', mode='g', position='1066.0,712.0,0', **setup)
    ap4 = net.addAccessPoint('ap4', cls=DPIDAP, dpid='000000000000000e', ssid='ap4-ssid',
                             channel='1', mode='g', position='1464.0,712.0,0', **setup)
    ap5 = net.addAccessPoint('ap5', cls=DPIDAP, dpid='000000000000000f', ssid='ap5-ssid',
                             channel='1', mode='g', position='220.0,831.0,0', **setup)
    ap6 = net.addAccessPoint('ap6', cls=DPIDAP, dpid='0000000000000010', ssid='ap6-ssid',
                             channel='1', mode='g', position='573.0,859.0,0', **setup)
    ap7 = net.addAccessPoint('ap7', cls=DPIDAP, dpid='0000000000000011', ssid='ap7-ssid',
                             channel='1', mode='g', position='985.0,880.0,0', **setup)
    ap8 = net.addAccessPoint('ap8', cls=DPIDAP, dpid='0000000000000012', ssid='ap8-ssid',
                             channel='1', mode='g', position='1398.0,877.0,0', **setup)

    info('*** Add hosts/stations\n')
    sta1 = net.addStation('sta1', ip='10.0.0.101', position='441.0,872.0,0')
    sta2 = net.addStation('sta2', ip='10.0.0.102', position='835.0,891.0,0')
    sta3 = net.addStation('sta3', ip='10.0.0.103', position='1291.0,879.0,0')

    h0 = net.addHost('h0', cls=Host, ip='10.0.0.1', defaultRoute=None)
    h8 = net.addHost('h8', cls=Host, ip='10.0.0.9', defaultRoute=None)
    h1 = net.addHost('h1', cls=Host, ip='10.0.0.2', defaultRoute=None)
    h5 = net.addHost('h5', cls=Host, ip='10.0.0.5', defaultRoute=None)
    h2 = net.addHost('h2', cls=Host, ip='10.0.0.3', defaultRoute=None)
    h3 = net.addHost('h3', cls=Host, ip='10.0.0.4', defaultRoute=None)
    h6 = net.addHost('h6', cls=Host, ip='10.0.0.6', defaultRoute=None)
    h7 = net.addHost('h7', cls=Host, ip='10.0.0.7', defaultRoute=None)
    h4 = net.addHost('h4', cls=Host, ip='10.0.0.8', defaultRoute=None)

    info("*** Configuring Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3)

    info("*** Configuring wifi nodes\n")
    net.configureWifiNodes()

    info('*** Add links\n')
    link_opts = dict(cls=TCLink, bw=100)##max_queue_size=1000)
    
    net.addLink(s1, s5, **link_opts)
    net.addLink(s2, s4, **link_opts)
    net.addLink(s1, s3, **link_opts)
    net.addLink(s2, s6, **link_opts)
    net.addLink(s3, s8, **link_opts)
    net.addLink(s4, s7, **link_opts)
    net.addLink(s3, s7, **link_opts)
    net.addLink(s4, s8, **link_opts)
    net.addLink(s5, s9, **link_opts)
    net.addLink(s6, s10, **link_opts)
    net.addLink(s5, s10, **link_opts)
    net.addLink(s6, s9, **link_opts)
    net.addLink(s7, ap1, **link_opts)
    net.addLink(s8, ap2, **link_opts)
    net.addLink(s9, ap3, **link_opts)
    net.addLink(s10, ap4, **link_opts)
    net.addLink(s1, s0, **link_opts)
    net.addLink(s0, s2, **link_opts)
    net.addLink(s0, h0, **link_opts)
    net.addLink(ap5, s7, **link_opts)
    net.addLink(ap6, s8, **link_opts)
    net.addLink(ap7, s9, **link_opts)
    net.addLink(ap8, s10, **link_opts)
    net.addLink(h8, s3, **link_opts)
    net.addLink(h1, s7, **link_opts)
    net.addLink(h5, s4, **link_opts)
    net.addLink(h2, s8, **link_opts)
    net.addLink(h6, s5, **link_opts)
    net.addLink(h3, s9, **link_opts)
    net.addLink(s6, h7, **link_opts)
    net.addLink(s10, h4, **link_opts)

    net.plotGraph(max_x=1000, max_y=1000)

    info('*** Starting network\n')
    net.build()

    # Create a wondershaper for solve link error after setting it 100mbps
    with open('/tmp/wondershaper.py', 'w') as f:
        f.write('''#!/usr/bin/python
import os
import sys
import subprocess

def clear_tc(iface):
    """Clear all traffic control settings from interface"""
    commands = [
        f"tc qdisc del dev {iface} root 2>/dev/null",
        f"tc qdisc del dev {iface} ingress 2>/dev/null"
    ]
    for cmd in commands:
        subprocess.call(cmd, shell=True)

def apply_shaping(iface, download=None, upload=None):
    """Apply traffic shaping to interface using wondershaper approach"""
    # Clear any existing TC configuration
    clear_tc(iface)
    
    # Parameters
    quantum = 6000  # Same as wondershaper
    
    if upload:
        # Create root qdisc with proper r2q value
        subprocess.call(f"tc qdisc add dev {iface} root handle 1: htb default 20 r2q 1", shell=True)
        
        # Create main class with rate limit
        subprocess.call(f"tc class add dev {iface} parent 1: classid 1:1 htb rate {upload}Mbit", shell=True)
        
        # High priority class (20% of bandwidth, can borrow up to 95%)
        rate = max(1, int(20 * upload / 100))
        ceil = int(95 * upload / 100)
        subprocess.call(f"tc class add dev {iface} parent 1:1 classid 1:10 htb rate {rate}Mbit ceil {ceil}Mbit prio 1", shell=True)
        
        # Default class (40% of bandwidth, can borrow up to 95%)
        rate = max(1, int(40 * upload / 100))
        subprocess.call(f"tc class add dev {iface} parent 1:1 classid 1:20 htb rate {rate}Mbit ceil {ceil}Mbit prio 2", shell=True)
        
        # Low priority class (20% of bandwidth, can borrow up to 90%)
        rate = max(1, int(20 * upload / 100))
        ceil = int(90 * upload / 100)
        subprocess.call(f"tc class add dev {iface} parent 1:1 classid 1:30 htb rate {rate}Mbit ceil {ceil}Mbit prio 3", shell=True)
        
        # Add SFQ queuing to each class with proper quantum
        for handle in [10, 20, 30]:
            subprocess.call(f"tc qdisc add dev {iface} parent 1:{handle} handle {handle}: sfq perturb 10 quantum {quantum}", shell=True)
        
        # Add filters based on TOS
        subprocess.call(f"tc filter add dev {iface} parent 1: protocol ip prio 10 u32 match ip tos 0x10 0xff flowid 1:10", shell=True)
        
        # ICMP gets high priority
        subprocess.call(f"tc filter add dev {iface} parent 1: protocol ip prio 11 u32 match ip protocol 1 0xff flowid 1:10", shell=True)
        
        # Small packets get high priority
        subprocess.call(f"""tc filter add dev {iface} parent 1: protocol ip prio 12 u32 \\
            match ip protocol 6 0xff \\
            match u8 0x05 0x0f at 0 \\
            match u16 0x0000 0xffc0 at 2 \\
            flowid 1:10""", shell=True)
        
        # Default class for everything else
        subprocess.call(f"tc filter add dev {iface} parent 1: protocol ip prio 18 u32 match ip dst 0.0.0.0/0 flowid 1:20", shell=True)
    
    if download:
        # For download shaping, need to create IFB device and redirect ingress to it
        subprocess.call("modprobe ifb numifbs=1", shell=True)
        subprocess.call("ip link set dev ifb0 up", shell=True)
        
        # Redirect ingress to ifb0
        subprocess.call(f"tc qdisc add dev {iface} handle ffff: ingress", shell=True)
        subprocess.call(f"tc filter add dev {iface} parent ffff: protocol ip u32 match u32 0 0 action mirred egress redirect dev ifb0", shell=True)
        
        # Set up HTB on ifb0
        subprocess.call(f"tc qdisc add dev ifb0 root handle 2: htb r2q 1", shell=True)
        subprocess.call(f"tc class add dev ifb0 parent 2: classid 2:1 htb rate {download}Mbit", shell=True)
        
        # Add filter for all IP traffic
        subprocess.call(f"tc filter add dev ifb0 protocol ip parent 2: prio 1 u32 match ip src 0.0.0.0/0 flowid 2:1", shell=True)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: {sys.argv[0]} <interface> [clear|status|shape] [upload_mbps] [download_mbps]")
        sys.exit(1)
    
    iface = sys.argv[1]
    mode = sys.argv[2]
    
    if mode == "clear":
        clear_tc(iface)
    elif mode == "status":
        subprocess.call(f"tc -s qdisc ls dev {iface}", shell=True)
        subprocess.call(f"tc -s class ls dev {iface}", shell=True)
    elif mode == "shape":
        if len(sys.argv) < 4:
            print("For shape mode, provide at least one of upload or download limits")
            sys.exit(1)
        
        upload = float(sys.argv[3]) if len(sys.argv) > 3 else None
        download = float(sys.argv[4]) if len(sys.argv) > 4 else None
        apply_shaping(iface, download, upload)
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
''')
    os.chmod('/tmp/wondershaper.py', 0o755)

    info('*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info('*** Starting switches/APs\n')
    for sw in ['s0', 's1', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9', 's10',
               'ap1', 'ap2', 'ap3', 'ap4', 'ap5', 'ap6', 'ap7', 'ap8']:
        net.get(sw).start([c0])

    info("*** Injecting custom traffic...\n")
    inject_custom_traffic(net)

    for sw in ['s0', 's1', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9', 's10',
               'ap1', 'ap2', 'ap3', 'ap4', 'ap5', 'ap6', 'ap7', 'ap8']:
        device = net.get(sw)
        dpid = device.dpid
        info(f"*** {sw} has DPID: {dpid}\n")
        device.cmd(f"sudo ovs-vsctl set Bridge {sw} other_config:datapath-id={dpid}")
        device.cmd(f"sudo ovs-vsctl set Bridge {sw} other-config:dp-desc={sw}")
            
    info("*** Saving network topology files\n")
    topology = save_topology_to_file(net)

    info('*** Applying wondershaper traffic control to all interfaces\n')
    time.sleep(1)
    for node in net.switches + net.aps + net.stations + net.hosts:
        for intf in node.intfList():
            if intf.name != 'lo':
                node.cmd(f'/tmp/wondershaper.py {intf.name} shape 100 100')
                info(f" - Applied wondershaper to {intf.name}\n")

    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    myNetwork()