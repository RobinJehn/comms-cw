from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.ofproto import ofproto_v1_4
from os_ken.lib.packet import packet
from os_ken.lib.packet import ethernet
from os_ken.lib.packet import in_proto
from os_ken.lib.packet import arp
from os_ken.lib.packet import ipv4
from os_ken.lib.packet import tcp
from os_ken.lib.packet.tcp import TCP_SYN
from os_ken.lib.packet.tcp import TCP_FIN
from os_ken.lib.packet.tcp import TCP_RST
from os_ken.lib.packet.tcp import TCP_ACK
from os_ken.lib.packet.ether_types import ETH_TYPE_IP, ETH_TYPE_ARP
import datetime


class Nat(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_4.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Nat, self).__init__(*args, **kwargs)
        self.hostmacs = {
            "10.0.1.100": "00:00:00:00:00:01",
            "10.0.2.100": "00:00:00:00:00:02",
            "10.0.2.101": "00:00:00:00:00:03",
        }
        self.lmac = "00:00:00:00:00:10"  # Private network MAC
        self.emac = "00:00:00:00:00:20"  # Public network MAC
        # The public ports that aren't in use right now
        self.available_ports = set(range(1024, 65536))

        # The public ports that are currently being used
        self.used_ports = set()

        # (private_ip, private_port) -> (public_ip, public_port, timestamp)
        self.nat_table = {}

        # 122 recommended, but 10 for this coursework
        self.entry_timeout = 10

    def _remove_one_expired_entry(self):
        """Remove one expired entry from the NAT table"""
        now = datetime.datetime.now()
        for k, (_, public_port, timestamp) in self.nat_table.items():
            if (now - timestamp).seconds > self.entry_timeout:
                self.available_ports.add(public_port)
                self.used_ports.remove(public_port)
                del self.nat_table[k]
                break

    def _get_port(self) -> int | None:
        if len(self.available_ports) == 0:
            return None
        port = self.available_ports.pop()
        self.used_ports.add(port)
        return port

    def _send_packet(self, datapath, port, pkt):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt.serialize()
        data = pkt.data
        actions = [parser.OFPActionOutput(port=port)]
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=ofproto.OFPP_CONTROLLER,
            actions=actions,
            data=data,
        )
        return out

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features_handler(self, ev):
        dp = ev.msg.datapath
        ofp, psr = (dp.ofproto, dp.ofproto_parser)
        acts = [psr.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, psr.OFPMatch(), acts)

    def add_flow(
        self, datapath, prio: int, match, acts, buffer_id=None, delete: bool = False
    ):
        """
        Add a flow rule to the switch
        Parameters:
            - datapath: The switch to which the rule should be added
            - prio: The priority of the rule
            - match: The match fields of the rule
            - acts: The actions to be taken if the rule matches
            - buffer_id: The buffer ID of the packet to be sent to the switch
            - delete: If True, the rule will be deleted instead of added
        """
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        bid = buffer_id if buffer_id is not None else ofp.OFP_NO_BUFFER
        if delete:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                command=datapath.ofproto.OFPFC_DELETE,
                out_port=datapath.ofproto.OFPP_ANY,
                out_group=datapath.ofproto.OFPG_ANY,
                match=match,
            )
        else:
            ins = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, acts)]
            mod = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=bid,
                priority=prio,
                match=match,
                instructions=ins,
            )
        # Let the datapath know about the flow modification
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        in_port = msg.match["in_port"]
        pkt = packet.Packet(msg.data)
        dp = msg.datapath
        ofp, psr, did = (dp.ofproto, dp.ofproto_parser, format(dp.id, "016d"))
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Handle ARP
        if eth.ethertype == ETH_TYPE_ARP:
            ah = pkt.get_protocols(arp.arp)[0]
            if ah.opcode == arp.ARP_REQUEST:
                print("ARP", pkt)
                ar = packet.Packet()
                ar.add_protocol(
                    ethernet.ethernet(
                        ethertype=eth.ethertype,
                        dst=eth.src,
                        src=self.emac if in_port == 1 else self.lmac,
                    )
                )
                ar.add_protocol(
                    arp.arp(
                        opcode=arp.ARP_REPLY,
                        src_mac=self.emac if in_port == 1 else self.lmac,
                        dst_mac=ah.src_mac,
                        src_ip=ah.dst_ip,
                        dst_ip=ah.src_ip,
                    )
                )
                out = self._send_packet(dp, in_port, ar)
                print("ARP Rep", ar)
                dp.send_msg(out)
            return

        ip_packet = pkt.get_protocol(ipv4.ipv4)
        tcp_packet = pkt.get_protocol(tcp.tcp)
        if ip_packet is None or tcp_packet is None:
            print("Not an IP packet or not a TCP packet")
            return

        # Outgoing packets are expected to be from "10.0.2.0/24"
        outgoing = ip_packet.src.startswith("10.0.2.")
        if outgoing:
            # Create/update the NAT entry
            private_entry = (ip_packet.src, tcp_packet.src_port)
            public_entry = self.nat_table.get(private_entry)
            if public_entry is None:
                self._remove_one_expired_entry()
                public_port = self._get_port()
                if public_port is None:
                    print("No available ports")
                    return
                public_entry = (ip_packet.dst, public_port, datetime.datetime.now())
                self.nat_table[private_entry] = public_entry
            else:
                # Extend the lifetime of the entry
                self.nat_table[private_entry] = (
                    public_entry[0],
                    public_entry[1],
                    datetime.datetime.now(),
                )

            # Do the NAT translation
            ip_packet.src = public_entry[0]
            tcp_packet.src_port = public_entry[1]
            eth.src = self.emac
        else:  # Incoming packet
            for (private_ip, private_port), (
                public_ip,
                public_port,
                _,
            ) in self.nat_table.items():
                if public_ip == ip_packet.dst and public_port == tcp_packet.dst_port:
                    ip_packet.dst = private_ip
                    tcp_packet.dst_port = private_port
            eth.src = self.lmac

        # Update the destination MAC address
        if ip_packet.dst in self.hostmacs:
            eth.dst = self.hostmacs[ip_packet.dst]

        # Create a new packet with the updated IP and TCP headers
        p = packet.Packet()
        p.add_protocol(eth)
        p.add_protocol(ip_packet)
        p.add_protocol(tcp_packet)
        p.serialize()

        # Install a flow rule so that future packets in this flow are handled directly by the switch.
        match = psr.OFPMatch(
            in_port=in_port,
            eth_type=0x0800,  # ipv4
            ipv4_src=ip_packet.src,
            ipv4_dst=ip_packet.dst,
            ip_proto=ip_packet.proto,  # TCP
            tcp_src=tcp_packet.src_port,
            tcp_dst=tcp_packet.dst_port,
        )
        actions = [psr.OFPActionOutput(ofp.OFPP_NORMAL)]  # Send to normal processing
        self.add_flow(dp, 1, match, actions)

        # We ignore any buffered packets and send the new packet directly to the switch
        out = psr.OFPPacketOut(
            datapath=dp,
            buffer_id=ofp.OFP_NO_BUFFER,  # Force using the new packet
            in_port=in_port,
            actions=actions,
            data=p.data,
        )
        dp.send_msg(out)
