# Thesis

## HOW TO RUN
In order to run this controller with the topology i follow this :

1. Install Python 3.9:
```bash
sudo apt install python3.9 python3.9-venv python3.9-dev
```
2. Install pip for the same version:
```bash
curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.9
```
3. Do a vritual environment using python 3.9 and activate it :
```bash
python3.9 -m venv ~/py39_env
source ~/py39_env/bin/activate
```
4. Install these spesific versions for RYU , add the path:
```bash
pip install eventlet==0.30.2
sudo pip3 install numpy==1.21.0
export PATH=$VIRTUAL_ENV/bin:$PATH
```
5. Install ryu or clone to the github
```bash
git clone https://github.com/faucetsdn/ryu.git
cd ryu
sudo pip3 install -e .
```
6. Run it normally ( without Rest ):
```bash
python3 -m ryu.cmd.manager ryu.app.simple_stp_switch_13
```
7. Run the topology then wait until ryu fiish configration then test if everything is fine ( for example pingall)

---
### SECOND STEP
For the second step to do like a matrix for getting info from the porst and links as much as we can, I use the rest Api folowing the documentaton of RYU with rest

1. I run the controller :
```bash
python3 -m --observe-links ryu.cmd.manager ryu.app.simple_switch_stp_13 ryu.app.ofctl_rest
```

2. Then run the topology in onther terminal:
```bash
sudo python ~/Topology.py
```
3. Run the code of montoring.
```bash
sudo python3 Fullmonitor.py --controller 127.0.0.1 --port 8080 --interval 5 --cycles 3
```
---

## UPDATES FOR WIFI PART
We have now the seperated topology file , and 4 other files :

1. `network_saver`: it is for save the topology as a matrix in csv and json
2. `resource_ap` :
    - Implements a system where access points have limited "resource blocks" (RBs) that represent available bandwidth/capacity
    - When a wireless device needs bandwidth, it requests specific resource blocks from access points
    - Creates and destroys network links dynamically based on resource availability
    - Tracks resource usage and automatically releases expired allocations
4. `wifi_test`:
    - Simulates wireless devices scanning for available access points
    - Measures signal strength (RSSI) and converts it to Channel Quality Indicator (CQI)
    - Automatically selects the best available access point based on signal quality and resource availability
    - Runs network performance tests using iperf3 to measure actual throughput
    - Works with the resource management system to reserve bandwidth before testing
5. `main_traffic_test`:
    - inject background traffic
    - Coordinates tests across multiple wireless devices simultaneously
    - Sets up video streams to test multimedia performance
    - Measures video quality metrics like jitter and packet loss
    - save results (csv- json )
---

## HOW TO
1. Run the topology:
```bash
sudo python ~/Topology.py
```
2. Save the matrix ( without traffic ) inside minint run:
```bash
py net.save_topology()
```

3. Run the traffic inside mininet run:
```bash
py net.main_traffic_test()
```

The recived video will be in tmp folder, also you will see the logs of the reciver there
