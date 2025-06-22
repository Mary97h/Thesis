# Thesis

in order to run this controller with the topology i follow this :

1- Install Python 3.9:

sudo apt install python3.9 python3.9-venv python3.9-dev

2- install pip for the same version :

curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.9

3-Do a vritual environment using python 3.9 and activate it :

python3.9 -m venv ~/py39_env

source ~/py39_env/bin/activate

4- install these spesific versions for RYU , add the path:

pip install eventlet==0.30.2

sudo pip3 install numpy==1.21.0

export PATH=$VIRTUAL_ENV/bin:$PATH

5- install ryu or clone to the github

git clone https://github.com/faucetsdn/ryu.git

cd ryu

sudo pip3 install -e .

6- run it normally ( without Rest ):

python3 -m ryu.cmd.manager ryu.app.simple_stp_switch_13

7- run the topology then wait until ryu fiish configration then test if everything is fine ( for example pingall)

---

for the second step to do like a matrix for getting info from the porst and links as much as we can , i use the rest Api folowing the documentaton of RYU with rest

1- i run the controller :
python3 -m --observe-links ryu.cmd.manager ryu.app.simple_switch_stp_13 ryu.app.ofctl_rest

2- then run the topology in onther terminal: sudo python ~/Topology.py

3- run the code of montoring :
sudo python3 Fullmonitor.py --controller 127.0.0.1 --port 8080 --interval 5 --cycles 3

---

UPDATES FOR WIFI PART

we have now the seperated topology file , and 4 other files :

1- network_saver :it is for save the topology as a matrix in csv and json
2- resource_ap : - Implements a system where access points have limited "resource blocks" (RBs) that represent available bandwidth/capacity - When a wireless device needs bandwidth, it requests specific resource blocks from access points - Creates and destroys network links dynamically based on resource availability - Tracks resource usage and automatically releases expired allocations
3- wifi_test: - Simulates wireless devices scanning for available access points - Measures signal strength (RSSI) and converts it to Channel Quality Indicator (CQI) - Automatically selects the best available access point based on signal quality and resource availability - Runs network performance tests using iperf3 to measure actual throughput - Works with the resource management system to reserve bandwidth before testing
4- main_traffic_test: - inject background traffic - Coordinates tests across multiple wireless devices simultaneously - Sets up video streams to test multimedia performance - Measures video quality metrics like jitter and packet loss - save results (csv- json )

---

1\_\_\_ run the topology :
sudo python ~/Topology.py

2\_\_\_ to save the matrix ( without traffic ) inside minint run :
py net.save_topology()

3\_\_\_ to run the traffic inside mininet run :
py net.main_traffic_test()

- the recived vedio is in tmp folder
