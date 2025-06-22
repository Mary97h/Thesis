from mininet.node import RemoteController, OVSKernelSwitch, Host
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from resource_ap import ResourceAP
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
from mn_wifi.cli import CLI
from code import InteractiveConsole
from network_saver import save_topology_to_file
from resource_ap import monitor_resource_blocks


try:
    from main_traffic_test import main_traffic_test
except ImportError as e:
    main_traffic_test = None
    info(f"*** WARNING: Could not import main_traffic_test: {e}\n")


def create_network_topology():
    """Create and configure the network topology"""
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
                dpid = dpid.replace(':', '') 
            OVSKernelSwitch.__init__(self, name, dpid=dpid, **kwargs)

    class DPIDAP(ResourceAP):
        def __init__(self, name, dpid=None, **kwargs):
            if dpid is not None:
                dpid = dpid.replace(':', '')
            ResourceAP.__init__(self, name, dpid=dpid, **kwargs)

    # Add switches
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

    # Add access points
    ap1 = net.addAccessPoint('ap1', cls=ResourceAP, ssid='ap1-ssid', 
                             channel='1', mode='g', position='337.0,699.0,0', **setup)
    ap2 = net.addAccessPoint('ap2', cls=ResourceAP, ssid='ap2-ssid',
                             channel='1', mode='g', position='679.0,697.0,0', **setup)
    ap3 = net.addAccessPoint('ap3', cls=ResourceAP, ssid='ap3-ssid',
                             channel='1', mode='g', position='1066.0,712.0,0', **setup)
    ap4 = net.addAccessPoint('ap4', cls=ResourceAP, ssid='ap4-ssid',
                             channel='1', mode='g', position='1464.0,712.0,0', **setup)
    ap5 = net.addAccessPoint('ap5', cls=ResourceAP, ssid='ap5-ssid',
                             channel='1', mode='g', position='220.0,831.0,0', **setup)
    ap6 = net.addAccessPoint('ap6', cls=ResourceAP, ssid='ap6-ssid',
                             channel='1', mode='g', position='573.0,859.0,0', **setup)
    ap7 = net.addAccessPoint('ap7', cls=ResourceAP, ssid='ap7-ssid',
                             channel='1', mode='g', position='985.0,880.0,0', **setup)
    ap8 = net.addAccessPoint('ap8', cls=ResourceAP, ssid='ap8-ssid',
                             channel='1', mode='g', position='1398.0,877.0,0', **setup)

    # Add stations
    info('*** Add hosts/stations\n')
    sta1 = net.addStation('sta1', ip='10.0.0.101', position='230.0,830.0,0')   
    sta2 = net.addStation('sta2', ip='10.0.0.102', position='380.0,820.0,0')   
    sta3 = net.addStation('sta3', ip='10.0.0.103', position='680.0,700.0,0')  
    sta4 = net.addStation('sta4', ip='10.0.0.104', position='750.0,730.0,0')   
    sta5 = net.addStation('sta5', ip='10.0.0.105', position='950.0,730.0,0')   
    sta6 = net.addStation('sta6', ip='10.0.0.106', position='1070.0,820.0,0')  
    sta7 = net.addStation('sta7', ip='10.0.0.107', position='1260.0,790.0,0') 
    sta8 = net.addStation('sta8', ip='10.0.0.108', position='500.0,950.0,0')  
    sta9 = net.addStation('sta9', ip='10.0.0.109', position='1450.0,730.0,0')
    sta10 = net.addStation('sta10', ip='10.0.0.110', position='250.0,800.0,0')

    # Add hosts
    h0 = net.addHost('h0', cls=Host, ip='10.0.0.1', defaultRoute=None)
    h1 = net.addHost('h1', cls=Host, ip='10.0.0.2', defaultRoute=None)
    h2 = net.addHost('h2', cls=Host, ip='10.0.0.3', defaultRoute=None)
    h3 = net.addHost('h3', cls=Host, ip='10.0.0.4', defaultRoute=None)
    h4 = net.addHost('h4', cls=Host, ip='10.0.0.8', defaultRoute=None)
    h5 = net.addHost('h5', cls=Host, ip='10.0.0.5', defaultRoute=None)
    h6 = net.addHost('h6', cls=Host, ip='10.0.0.6', defaultRoute=None)
    h7 = net.addHost('h7', cls=Host, ip='10.0.0.7', defaultRoute=None)
    h8 = net.addHost('h8', cls=Host, ip='10.0.0.9', defaultRoute=None)
    h9 = net.addHost('h9', cls=Host, ip='10.0.0.10', defaultRoute=None)
    h10 = net.addHost('h10', cls=Host, ip='10.0.0.11', defaultRoute=None)

    info("*** Configuring Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3)

    info("*** Configuring wifi nodes\n")
    net.configureWifiNodes()

    # Add links
    info('*** Add links\n')
    link_opts = dict(cls=TCLink, bw=100)

    # Switch-to-switch links
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
    
    # Switch-to-AP links
    net.addLink(s7, ap1, **link_opts)
    net.addLink(s8, ap2, **link_opts)
    net.addLink(s9, ap3, **link_opts)
    net.addLink(s10, ap4, **link_opts)
    net.addLink(ap5, s7, **link_opts)
    net.addLink(ap6, s8, **link_opts)
    net.addLink(ap7, s9, **link_opts)
    net.addLink(ap8, s10, **link_opts)
    
    # Core network links with hosts
    net.addLink(s0, h9, **link_opts)
    net.addLink(h9, s1, **link_opts)
    net.addLink(s0, s2, **link_opts)
    net.addLink(s2, h10, **link_opts)
    net.addLink(h10, s4, **link_opts)
    
    # Host connections
    net.addLink(s0, h0, **link_opts)
    net.addLink(h8, s3, **link_opts)
    net.addLink(h1, s7, **link_opts)
    net.addLink(h5, s4, **link_opts)
    net.addLink(h2, s8, **link_opts)
    net.addLink(h6, s5, **link_opts)
    net.addLink(h3, s9, **link_opts)
    net.addLink(s6, h7, **link_opts)
    net.addLink(s10, h4, **link_opts)

    try:
        net.plotGraph(max_x=1500, max_y=1000)
    except Exception as e:
        info(f"*** WARNING: Could not plot graph: {e}\n")

    return net, c0

def start_network_infrastructure(net, c0):
    """Start the network infrastructure (controllers, switches, APs)"""
    info('*** Starting network\n')
    net.build()
    aps = [net.get(f'ap{i}') for i in range(1, 9)]
    from threading import Thread
    Thread(target=monitor_resource_blocks, args=(aps, net), daemon=True).start()

    info('*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info('*** Starting switches/APs\n')
    all_switches = ['s0', 's1', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9', 's10',
                    'ap1', 'ap2', 'ap3', 'ap4', 'ap5', 'ap6', 'ap7', 'ap8']
    
    for sw in all_switches:
        try:
            net.get(sw).start([c0])
        except Exception as e:
            info(f"*** ERROR starting {sw}: {e}\n")

    # Configure switch DPIDs
    for sw in all_switches:
        try:
            device = net.get(sw)
            dpid = device.dpid
            info(f"*** {sw} has DPID: {dpid}\n")
            device.cmd(f"sudo ovs-vsctl set Bridge {sw} other_config:datapath-id={dpid}")
            device.cmd(f"sudo ovs-vsctl set Bridge {sw} other-config:dp-desc=\"{sw}\"")
        except Exception as e:
            info(f"*** ERROR configuring {sw}: {e}\n")

    if main_traffic_test is not None:
        net.main_traffic_test = lambda: main_traffic_test(net)
        info("*** Attached main_traffic_test to net\n")

    net.save_topology = lambda: save_topology_to_file(net)

    # Start CLI
    CLI(net)

    net.stop()

def launch():
    setLogLevel('info')
    net, c0 = create_network_topology()
    start_network_infrastructure(net, c0)

if __name__ == '__main__':
    launch()