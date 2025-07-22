# Switching from Wi-Fi to Ethernet in Mininet-WiFi

In **Mininet-WiFi**, **stations (`sta`) cannot be directly connected via cable to Access Points (`ap`)** as you would do with a switch. This is because APs are not designed to handle wired links directly with hosts or stations.

---

## Correct Strategy

To switch from a **Wi-Fi** connection to an **Ethernet** one dynamically during a simulation, follow these steps:

---

## 1. Stations cannot connect via cable to Access Points

```bash
py net.addLink(sta1, ap1)
```

This command does not work correctly.  
An AP is not a switch and does not properly handle forwarding on direct wired links.

---

## 2. Disconnect the Wi-Fi connection

Before activating the wired connection, the wireless one must be disabled.

```bash
sta1.cmd('ip link set sta1-wlan0 down')
```

or (for more control):

```bash
sta1.setAssoc(ap1, intf='sta1-wlan0', assoc=False)
```

---

## 3. Create the wired link to the switch

Instead of connecting directly to the AP, connect `sta1` to a switch (`s0`):

```bash
py net.addLink(sta1, s0)
```

This command creates a new interface for `sta1` (`sta1-ethX`) and one for `s0` (`s0-ethX`).
Choose the switch relative to the AP (none should connect to s0, the network topology must be preserved).

---

## 4. Attach the switch port

After creating the link, Mininet-WiFi might not automatically activate the switch port. You need to force it using the command:

```bash
py s0.attach('s0-ethX')
```

### Explanation
The `s0.attach(...)` command tells the OVS switch to "take control" of the new port, meaning:
- include it in the datapath,
- activate it for forwarding.

You can find the exact name of the new port with:

```bash
s0.intfNames()
```

Or by checking the network with:

```bash
net
```

---

## 5. Assign an IP address to the new interface

After creating the link and attaching the port on the switch, assign an IP address to the new station interface:

```bash
sta1 ip addr add 10.0.0.110/24 dev sta1-ethX
sta1 ip link set sta1-ethX up
```

Replace `sta1-ethX` with the correct name of the newly created interface.

---

## Check connectivity

Run a ping to a known host (e.g., `h0`) to verify that the new wired connection is active:

```bash
sta1 ping -c 3 10.0.0.2
```

---

## Summary

| Step                          | Command                                                   |
|------------------------------|------------------------------------------------------------|
| Disable Wi-Fi                | `sta1.cmd('ip link set sta1-wlan0 down')`                 |
| Create wired link            | `py net.addLink(sta1, s0)`                                |
| Attach switch port           | `py s0.attach('s0-ethX')`                                 |
| Assign IP to sta1            | `sta1 ip addr add ... dev sta1-ethX`                      |
| Enable sta1 interface        | `sta1 ip link set sta1-ethX up`                           |
| Ping test                    | `sta1 ping -c 3 10.0.0.2`                                 |

---
