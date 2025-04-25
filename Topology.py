#!/usr/bin/python

from mininet.node import RemoteController, OVSKernelSwitch, Host
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import Station, OVSKernelAP
from mn_wifi.cli import CLI
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
from subprocess import call


def myNetwork():
    setup={'protocols':"OpenFlow13"}

    net = Mininet_wifi(topo=None,
                       build=False,
                       link=wmediumd,
                       wmediumd_mode=interference,
                       ipBase='10.0.0.0/8')

    info( '*** Adding controller\n' )
    c0 = net.addController(name='c0',
                           controller=RemoteController,)
    
    info( '*** Add switches/APs\n')
    
    s0 = net.addSwitch('s0', cls=OVSKernelSwitch,**setup)
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch,**setup)
    s2 = net.addSwitch('s2', cls=OVSKernelSwitch,**setup)
    s3 = net.addSwitch('s3', cls=OVSKernelSwitch,**setup)
    s4 = net.addSwitch('s4', cls=OVSKernelSwitch,**setup)
    s5 = net.addSwitch('s5', cls=OVSKernelSwitch,**setup)
    s6 = net.addSwitch('s6', cls=OVSKernelSwitch,**setup)
    s7 = net.addSwitch('s7', cls=OVSKernelSwitch,**setup)
    s8 = net.addSwitch('s8', cls=OVSKernelSwitch,**setup)
    s9 = net.addSwitch('s9', cls=OVSKernelSwitch,**setup)
    s10 = net.addSwitch('s10', cls=OVSKernelSwitch,**setup)
    
    ap1 = net.addAccessPoint('ap1', cls=OVSKernelAP, ssid='ap1-ssid',
                             channel='1', mode='g', position='337.0,699.0,0',**setup)
    ap2 = net.addAccessPoint('ap2', cls=OVSKernelAP, ssid='ap2-ssid',
                             channel='1', mode='g', position='679.0,697.0,0',**setup)
    ap3 = net.addAccessPoint('ap3', cls=OVSKernelAP, ssid='ap3-ssid',
                             channel='1', mode='g', position='1066.0,712.0,0',**setup)
    ap4 = net.addAccessPoint('ap4', cls=OVSKernelAP, ssid='ap4-ssid',
                             channel='1', mode='g', position='1464.0,712.0,0',**setup)
   
    ap5 = net.addAccessPoint('ap5', cls=OVSKernelAP, ssid='ap5-ssid',
                             channel='1', mode='g', position='220.0,831.0,0',**setup)
    ap6 = net.addAccessPoint('ap6', cls=OVSKernelAP, ssid='ap6-ssid',
                             channel='1', mode='g', position='573.0,859.0,0',**setup)
    ap7 = net.addAccessPoint('ap7', cls=OVSKernelAP, ssid='ap7-ssid',
                             channel='1', mode='g', position='985.0,880.0,0',**setup)
    ap8 = net.addAccessPoint('ap8', cls=OVSKernelAP, ssid='ap8-ssid',
                             channel='1', mode='g', position='1398.0,877.0,0',**setup)

    info( '*** Add hosts/stations\n')
    sta1 = net.addStation('sta1', ip='10.0.0.101',
                           position='441.0,872.0,0')
    sta2 = net.addStation('sta2', ip='10.0.0.102',
                           position='835.0,891.0,0')
    sta3 = net.addStation('sta3', ip='10.0.0.103',
                           position='1291.0,879.0,0')
    h0 = net.addHost('h0', cls=Host, ip='10.0.0.100', defaultRoute=None)
    h8 = net.addHost('h8', cls=Host, ip='10.0.0.8', defaultRoute=None)
    h1 = net.addHost('h1', cls=Host, ip='10.0.0.1', defaultRoute=None)
    h5 = net.addHost('h5', cls=Host, ip='10.0.0.5', defaultRoute=None)
    h2 = net.addHost('h2', cls=Host, ip='10.0.0.2', defaultRoute=None)
    h3 = net.addHost('h3', cls=Host, ip='10.0.0.3', defaultRoute=None)
    h6 = net.addHost('h6', cls=Host, ip='10.0.0.6', defaultRoute=None)
    h7 = net.addHost('h7', cls=Host, ip='10.0.0.7', defaultRoute=None)
    h4 = net.addHost('h4', cls=Host, ip='10.0.0.4', defaultRoute=None)

    info("*** Configuring Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3)

    info("*** Configuring wifi nodes\n")
    net.configureWifiNodes()

    info( '*** Add links\n')
    net.addLink(s1, s5)
    net.addLink(s2, s4)
    net.addLink(s1, s3)
    net.addLink(s2, s6)
    net.addLink(s3, s8)
    net.addLink(s4, s7)
    net.addLink(s3, s7)
    net.addLink(s4, s8)
    net.addLink(s5, s9)
    net.addLink(s6, s10)
    net.addLink(s5, s10)
    net.addLink(s6, s9)
    net.addLink(s7, ap1)
    net.addLink(s8, ap2)
    net.addLink(s9, ap3)
    net.addLink(s10, ap4)
    net.addLink(s1, s0)
    net.addLink(s0, s2)
    net.addLink(s0, h0)
    net.addLink(ap5, s7)
    net.addLink(ap6, s8)
    net.addLink(ap7, s9)
    net.addLink(ap8, s10)
    net.addLink(h8, s3)
    net.addLink(h1, s7)
    net.addLink(h5, s4)
    net.addLink(h2, s8)
    net.addLink(h6, s5)
    net.addLink(h3, s9)
    net.addLink(s6, h7)
    net.addLink(s10, h4)

    net.plotGraph(max_x=1000, max_y=1000)

    info( '*** Starting network\n')
    net.build()

    info('*** Setting OpenFlow rules\n')
    for s in net.switches:
        s.cmd('ovs-ofctl add-flow {} "priority=0,actions=output:NORMAL"'.format(s.name))

    info( '*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info( '*** Starting switches/APs\n')
    net.get('s1').start([c0])
    net.get('s2').start([c0])
    net.get('s3').start([c0])
    net.get('s4').start([c0])
    net.get('s5').start([c0])
    net.get('s6').start([c0])
    net.get('s7').start([c0])
    net.get('s8').start([c0])
    net.get('s9').start([c0])
    net.get('s10').start([c0])
    net.get('ap1').start([c0])
    net.get('ap2').start([c0])
    net.get('ap3').start([c0])
    net.get('ap4').start([c0])
    net.get('s0').start([c0])
    net.get('ap5').start([c0])
    net.get('ap6').start([c0])
    net.get('ap7').start([c0])
    net.get('ap8').start([c0])

    info( '*** Post configure nodes\n')

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    myNetwork()