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

_______________________________________________________________________________________________________________________________________________

for the second step to do like a matrix for getting info from the porst and links as much as we can  , i use the rest Api folowing the documentaton of RYU with rest 

1- i run the controller :
python3 -m --observe-links ryu.cmd.manager ryu.app.simple_switch_stp_13 ryu.app.ofctl_rest

2- then run the topology in onther terminal 

3- run the code of montoring 

i did untill now a code which is get all the info of the switches ports it give results while feaching links still unreachable 

also i did a code to check the links between 2 switches but it gives so small gaps for timestp ( may it never take the right switches of the topology  i am checking)

the last code i did is to feach links between switch and host ( still cant get the hosts )

NOTE : it is still for testing , i will store them in csv after everything is done 
