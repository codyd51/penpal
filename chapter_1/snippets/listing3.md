executable: true
lang: rust
depends-on: ["listing2"]
file: src/packet_header_layout.rs
###
#[derive(Debug)]
pub(crate) struct DnsPacketHeaderRaw(pub(crate) BitArray<[u16; 6], Lsb0>);



