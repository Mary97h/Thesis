# General
This folder will contain all the util script. 

The goal is to have a script that load all the util in the mininet consol. 

# How to use

## link_sta_switch
"sta1" can be substitued with other Station, such as "s0" with other switches.

```bash
mininet-wifi> py exec(open('link_sta_switch.py').read())
mininet-wifi> py link_sta_switch(net, 'sta1', 's0')
```
