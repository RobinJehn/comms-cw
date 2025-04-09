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
        # The timestamp says when the entry was last used
        self.nat_table = {}

        # 122 recommended, but 10 for this coursework
        self.entry_timeout = 10

        # The public IP address of the NAT device
        self.public_ip = "10.0.1.2"

    def add_flows(
        self,
        datapath,
        private_ip,
        private_port,
        private_mac,
        public_ip,
        public_port,
        target_mac,
    ):
        """
        This should only be called when we add a new entry to the NAT table.
        src will be in the private network and target will be in the public network.
        We add a flow for both directions. The flow needs to update the ip and port to reflect the NAT translation
        and forward the packet.
        Parameters:
            - datapath: The switch to which the rule should be added
            - private_ip: The private IP address of the source
            - private_port: The private port of the source
            - private_mac: The private MAC address of the source
            - public_ip: The public IP address of the source
            - public_port: The public port of the source
            - target_mac: The public MAC address of the switch
        """
        ofp = datapath.ofproto
        psr = datapath.ofproto_parser

        # Outgoing flow
        match_out = psr.OFPMatch(
            ip_proto=in_proto.IPPROTO_TCP,  # TCP protocol
            ipv4_src=private_ip,
            tcp_src=private_port,
        )

        actions_out = [
            psr.OFPActionSetField(ipv4_src=public_ip),
            psr.OFPActionSetField(tcp_src=public_port),
            psr.OFPActionSetField(eth_src=self.emac),
            psr.OFPActionSetField(eth_dst=target_mac),
            psr.OFPActionOutput(ofp.OFPP_NORMAL),
        ]
        self.add_flow(datapath, 1, match_out, actions_out)

        # Incoming flow
        match_in = psr.OFPMatch(
            ip_proto=in_proto.IPPROTO_TCP,  # TCP protocol
            ipv4_dst=public_ip,
            tcp_dst=public_port,
        )

        actions_in = [
            psr.OFPActionSetField(ipv4_dst=private_ip),
            psr.OFPActionSetField(tcp_dst=private_port),
            psr.OFPActionSetField(eth_src=self.lmac),
            psr.OFPActionSetField(eth_dst=private_mac),
            psr.OFPActionOutput(ofp.OFPP_NORMAL),
        ]
        self.add_flow(datapath, 1, match_in, actions_in)

    def add_entry(self, private_ip, private_port) -> bool:
        """
        Add a new entry to the NAT table.

        Parameters:
            - private_ip: The private IP address
            - private_port: The private port
        Returns:
            - True if the entry was added successfully, False otherwise
        """
        if len(self.available_ports) == 0:
            # No available ports
            return False
        if (private_ip, private_port) in self.nat_table:
            # Entry already exists
            return False

        public_port = self.available_ports.pop()
        self.used_ports.add(public_port)

        self.nat_table[(private_ip, private_port)] = (
            self.public_ip,
            public_port,
            datetime.datetime.now(),
        )
        self.used_ports.add(public_port)
        self.available_ports.remove(public_port)

        return True

    def get_public(self, private_ip, private_port) -> tuple[str, int] | None:
        """
        Get the public IP and port for a given private IP and port. If no entry exists, create a new one.
        If we cannot add a new entry, return None.
        Updates the timestamp of the entry if it exists.
        Parameters:
            - private_ip: The private IP address
            - private_port: The private port
        Returns:
            - A tuple (public_ip, public_port) if the entry exists, None otherwise
        """
        # If we already have an entry return it
        if (private_ip, private_port) in self.nat_table:
            (public_ip, public_port, _) = self.nat_table[(private_ip, private_port)]
            # Update the timestamp
            self.nat_table[(private_ip, private_port)] = (
                public_ip,
                public_port,
                datetime.datetime.now(),
            )
            return public_ip, public_port

        # If the entry doesn't exist, create a new one
        self._remove_one_expired_entry()
        success = self.add_entry(private_ip, private_port)
        if not success:
            return None

        # Return the public IP and port.
        assert (private_ip, private_port) in self.nat_table
        public_ip, public_port, _ = self.nat_table[(private_ip, private_port)]
        return public_ip, public_port

    def get_private(self, public_ip, public_port) -> tuple[str, int] | None:
        """
        Get the private IP and port for a given public IP and port.
        If no entry exists, return None.
        Updates the timestamp of the entry if it exists.
        Parameters:
            - public_ip: The public IP address
            - public_port: The public port
        Returns:
            - A tuple (private_ip, private_port) if the entry exists, None otherwise
        """

        for public_ip_, public_port_, _ in self.nat_table.items():
            if public_ip == public_ip_ and public_port == public_port_:
                private_ip, private_port, _ = self.nat_table[(public_ip, public_port)]
                # Update the timestamp
                self.nat_table[(private_ip, private_port)] = (
                    public_ip,
                    public_port,
                    datetime.datetime.now(),
                )
                return private_ip, private_port

        return None

    def _remove_one_expired_entry(self):
        """
        Remove one expired entry from the NAT table.

        Flow is automatically removed by the idle_timeout
        """
        now = datetime.datetime.now()
        for k, (public_ip, public_port, timestamp) in self.nat_table.items():
            if (now - timestamp).seconds > self.entry_timeout:
                self.available_ports.add(public_port)
                self.used_ports.remove(public_port)
                del self.nat_table[k]
                break

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
                idle_timeout=self.entry_timeout,
            )
        # Let the datapath know about the flow modification
        datapath.send_msg(mod)

    def _send_rst(self, datapath, in_port, pkt, ip_packet, tcp_packet):
        """
        Send a TCP RST packet to the client when no port is available.
        """
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        # Build a new TCP segment with the RST flag set.
        # Using the original packet's values for ports and sequence numbers.
        rst_tcp = tcp.tcp(
            src_port=tcp_packet.src_port,
            dst_port=tcp_packet.dst_port,
            seq=tcp_packet.ack,  # Use the ACK as the sequence number
            ack=tcp_packet.seq + 1,  # Acknowledge the sequenc
            bits=ofp.TCP_FLAG_RST,  # Set the RST flag
            window_size=0,
        )

        # Build a new IPv4 packet.
        # Swap source and destination so that the RST is sent back to the sender.
        rst_ip = ipv4.ipv4(src=ip_packet.dst, dst=ip_packet.src, proto=ip_packet.proto)

        # Build a new Ethernet frame.
        # Swap source and destination MAC addresses.
        eth = pkt.get_protocol(ethernet.ethernet)
        rst_eth = ethernet.ethernet(src=eth.dst, dst=eth.src, ethertype=eth.ethertype)

        # Assemble the packet.
        p = packet.Packet()
        p.add_protocol(rst_eth)
        p.add_protocol(rst_ip)
        p.add_protocol(rst_tcp)
        p.serialize()

        # Create PacketOut message: send the RST back through the input port.
        actions = [parser.OFPActionOutput(in_port)]
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofp.OFP_NO_BUFFER,
            in_port=ofp.OFPP_CONTROLLER,
            actions=actions,
            data=p.data,
        )
        datapath.send_msg(out)

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

        # We only add new rules on outgoing packets, incoming ones should be handled by a flow
        if not ip_packet.src.startswith("10.0.2."):
            print("Incoming packets should be handled by flows!")
            self._send_rst(dp, in_port, pkt, ip_packet, tcp_packet)
            return

        # Automatically adds the entry to the NAT table if it doesn't exist
        public_entry = self.get_public(ip_packet.src, tcp_packet.src_port)
        if public_entry is None:
            print("No available ports")
            self._send_rst(dp, in_port, pkt, ip_packet, tcp_packet)
            return

        # Do the NAT translation
        ip_packet.src = public_entry[0]
        tcp_packet.src_port = public_entry[1]
        eth.src = self.emac
        target_mac = self.hostmacs[ip_packet.dst]
        eth.dst = target_mac

        # Create a new packet with the updated IP and TCP headers
        p = packet.Packet()
        p.add_protocol(eth)
        p.add_protocol(ip_packet)
        p.add_protocol(tcp_packet)
        p.serialize()

        # Install a flow rule so that future packets in this flow are handled directly by the switch.
        self.add_flows(dp, ip_packet.src, tcp_packet.src_port, eth.src, ip_packet.dst, tcp_packet.dst_port, target_mac)

        out = self._send_packet(dp, in_port, p)
        dp.send_msg(out)
