import time

def link_sta_switch(net, sta_name, sw_name, ip_cidr='10.0.0.51/8', ping_target='10.0.0.1'):
    """
    Connects a station to a switch in Mininet-WiFi at runtime, using wired channel.
    Usage:
    mininet-wifi> py exec(open('link_sta_switch.py').read())
    mininet-wifi> py link_sta_switch(net, 'sta1', 's0')
    """

    # Retrieve nodes
    sta = net.get(sta_name)
    sw = net.get(sw_name)

    # Turn off Wi-Fi
    sta.cmd(f'ip link set {sta_name}-wlan0 down 2>/dev/null || true')

    # Save interface list before the link
    old_sta_intfs = set(sta.intfNames())
    old_sw_intfs = set(sw.intfNames())

    # Create link
    net.addLink(sta, sw)
    time.sleep(0.5)

    # Find the new interface on the station side and on the switch side
    new_sta_intf = (set(sta.intfNames()) - old_sta_intfs).pop()
    new_sw_intf = (set(sw.intfNames()) - old_sw_intfs).pop()

    # Attach the port on the switch
    sw.attach(new_sw_intf)

    # Configure IP on the station
    sta.cmd(f'ip addr flush dev {new_sta_intf}')
    sta.cmd(f'ip addr add {ip_cidr} dev {new_sta_intf}')
    sta.cmd(f'ip link set {new_sta_intf} up')

    # Print interface status
    print(sta.cmd(f'ip addr show {new_sta_intf}'))
    print(sw.cmd(f'ip link show {new_sw_intf}'))

    # Test ping
    print(sta.cmd(f'ping -c 3 {ping_target}'))

    return new_sta_intf, new_sw_intf



