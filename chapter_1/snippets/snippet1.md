lang: rust
###
use std::net::UdpSocket;

const MAX_DNS_UDP_PACKET_SIZE: usize = 512;

fn main() {