+++
title = "DNS Resolver: Receiving Packets"
date = "2023-06-14T22:20:08+01:00"

tags = []
+++

Let's get started.

```text
$ cargo new dns_resolver --bin
$ cd dns_resolver
```

If you strip away our DNS resolver to the bare bones, its core runloop will be composed of a _request_ and a _response_. Our general approach will be:

1. _Wait_ for a DNS request to arrive.
2. _Parse_ the request.
3. _Perform_ the lookup.
4. _Send_ the response.

To get us started, let's _wait_ for DNS queries to come in.






Top-level show, _src/main.rs_
{{<highlight rust "linenos=inline,linenostart=25">}}
use std::net::UdpSocket;
const MAX_DNS_UDP_PACKET_SIZE: usize = 512;

fn main() {
    let socket = UdpSocket::bind("127.0.0.1:53")
        .expect("Failed to bind to our local DNS port");
    let mut receive_packet_buf = [0; MAX_DNS_UDP_PACKET_SIZE];
    println!("Awaiting incoming packets...");
    loop {
        let (byte_count_received, sender_addr) = socket
            .recv_from(&mut receive_packet_buf)
            .expect("Failed to read from the socket");

        println!("We've received a DNS query of {byte_count_received} bytes from {sender_addr:?}");    }
}
{{</highlight>}}

When we try to run this, the operating system rejects our request:

```text
$ cargo run dns_resolver
   Compiling dns_resolver v0.1.0 
    Finished dev [unoptimized + debuginfo] target(s) in 0.70s
     Running `target/debug/dns_resolver dns_resolver`
thread 'main' panicked at 'Failed to bind to our local DNS port: Os { code: 13, kind: PermissionDenied, message: "Permission denied" }', src/main.rs:6:50
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
```

This is a good call by the operating system! DNS traffic is important, as well as sensitive, and the OS shouldn't let any program that comes by handle these requests.

We're also not quite ready to handle all of our system's "real" DNS traffic, anyway. If we did try to route all our traffic through our nascent DNS resolver, it'd be difficult to even look up troubleshooting help!

Instead, while we're building things out, let's leave our system's DNS configuration alone, and build our server off to the side. We'll send ourselves controlled test packets to ensure everything is working as expected, without needing to worry about all the complexities of real-world traffic upfront.

Update, _src/main.rs_
{{<highlight rust "linenos=inline,hl_lines=4-6,linenostart=25">}}
const MAX_DNS_UDP_PACKET_SIZE: usize = 512;

fn main() {
    let socket = UdpSocket::bind("0.0.0.0:0")
        .expect("Failed to bind to a local socket");
    println!("Bound to {socket:?}");
    let mut receive_packet_buf = [0; MAX_DNS_UDP_PACKET_SIZE];
    println!("Awaiting incoming packets...");
{{</highlight>}}

```text
$ cargo run dns_resolver
   Compiling dns_resolver v0.1.0 
    Finished dev [unoptimized + debuginfo] target(s) in 0.70s
     Running `target/debug/dns_resolver dns_resolver`
Bound to UdpSocket { addr: 0.0.0.0:57167, fd: 3 }
```

Great! Our server is running and is ready to receive inbound packets. By specifying an address of `0.0.0.0:0`, we're implicitly requesting that the OS bind a socket to any available address. In this case, the OS has bound our socket to `0.0.0.0:57167`, but we can expect this address to change from run to run.

Our server is currently _awaiting_ a packet, and will remain in that state until we send it something. Let's give it a try!

##### PT: Could go on a big digression here about the framed data format of OSI packets

To send a DNS packet to our server, we'll use `dig`, a standard command line utility that allows manually sending DNS queries. `dig` will also automatically process the response that the DNS server sends back, which will come in handy further down the road.

For now, let's just send a request and see what happens. Since we haven't reconfigured our system's DNS, this request will be sent to whatever DNS resolver is already set up.

```text
$ dig google.com A

; <<>> DiG 9.10.6 <<>> google.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 15748
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 1232
;; QUESTION SECTION:
;google.com.			IN	A

;; ANSWER SECTION:
google.com.		128	IN	A	142.250.200.14

;; Query time: 47 msec
;; SERVER: 1.1.1.1#53(1.1.1.1)
;; WHEN: Fri Jun 16 08:11:59 BST 2023
;; MSG SIZE  rcvd: 55
```

Cool! `dig` sent a query for `google.com` to the resolver, and the resolver responded with the `A` records where this resource can be found. Down at the bottom of the output, we can see information about which resolver `dig` spoke to: in my case, a resolver hosted at `1.1.1.1`. Let's configure `dig` to talk to our nascent DNS resolver instead.

```text
$ dig @0.0.0.0 -p 53846 google.com

; <<>> DiG 9.10.6 <<>> @0.0.0.0 -p 53846 google.com
; (1 server found)
;; global options: +cmd
;; connection timed out; no servers could be reached
```

Switching back to our resolver, we can see we're receiving the packets sent by `dig`!

```text
$ cargo run dns_resolver
   Compiling dns_resolver v0.1.0 
    Finished dev [unoptimized + debuginfo] target(s) in 0.34s
     Running `target/debug/dns_resolver`
Bound to UdpSocket { addr: 0.0.0.0:53846, fd: 3 }
Awaiting incoming packets...
We've received a DNS query of 39 bytes from 127.0.0.1:61575
We've received a DNS query of 39 bytes from 127.0.0.1:61575
We've received a DNS query of 39 bytes from 127.0.0.1:61575
```

`dig` sent us a DNS query to resolve `google.com`, and since we didn't send any response back, it send a few more requests after a few seconds of waiting. After three attempts, it gave up and timed out. Eventually, our DNS resolver will happily respond back to `dig`, but first, we'll need to _parse_ and understand what the incoming packet contains.

* Note that `dig` bound to `61575`.

### Parsing an incoming DNS query

Every DNS packet will have the same general structure, which was initially defined by the IETF's RFC #1034. Let's check out Section #4.1, `Message Format`.

```text
+---------------------+
|        Header       |
+---------------------+
|       Question      | the question for the name server
+---------------------+
|        Answer       | RRs answering the question
+---------------------+
|      Authority      | RRs pointing toward an authority
+---------------------+
|      Additional     | RRs holding additional information
+---------------------+

The header section is always present.  The header includes fields that
specify which of the remaining sections are present, and also specify
whether the message is a query or a response, a standard query or some
other opcode, etc.
```

Cool! We'll start off parsing the header section, since the specification guarantees that it'll be around in every packet, and it contains useful info to boot. We'll find the header format in `Section 4.1.1. Header Section Format`.

```text
  0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                      ID                       |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|QR|   Opcode  |AA|TC|RD|RA|   Z    |   RCODE   |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    QDCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ANCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    NSCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ARCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
```

We can see that the header is composed of five fields, each of which is 16 bits in size and encodes some details some important metadata about the packet. The second field is somewhat special: whereas all the other fields use their 16 bits to encode a single value, the second field encodes a series of flags, each of which takes just one or a few bits to store.

If we were to define this structure in C code, it'd look a bit like this:

```c
struct dns_packet_header {
    uint16_t id;
    
	uint16_t is_packet_a_response:1;
	uint16_t opcode:4;
	uint16_t is_response_an_authoritative_answer:1;
	uint16_t is_response_truncated:1;
	uint16_t is_recursion_desired:1;
	uint16_t is_recursion_available:1;
	uint16_t reserved:3;
	uint16_t response_code:4;

	uint16_t question_record_count;
	uint16_t answer_record_count;
	uint16_t authority_record_count;
	uint16_t additional_record_count;
} __attribute__((packed));
```

For all C's warts, this _is_ quite a nice and tidy way to describe a bit-field. Unfortunately, Rust doesn't natively provide the same facilities for terse bitfield descriptions. Our approach will use `bitvec::BitArray` to store the header as a whole, and we'll use `bitvec`'s bit-level access to build up our resolver's model of a DNS header.

To get started, let's add `bitvec` to our crate's dependencies.



Child contextual show, `cargo_toml_dependencies`

{{<highlight toml "linenos=inline,hl_lines=4-5,linenostart=25">}}
version = "0.1.0"
edition = "2021"

[dependencies]
bitvec = "1"
{{</highlight>}}

Now, let's start modeling the DNS header format! Make a new file, `packet_header_layout.rs`.

Update, _src/main.rs_
{{<highlight rust "linenos=inline,hl_lines=1-2,linenostart=25">}}
use std::net::UdpSocket;
mod packet_header_layout;
const MAX_DNS_UDP_PACKET_SIZE: usize = 512;

{{</highlight>}}



Top-level show, _src/packet_header_layout.rs_
{{<highlight rust "linenos=inline,linenostart=25">}}
use std::mem;
use std::ops::Range;

use bitvec::prelude::*;

#[derive(Debug)]
pub(crate) struct DnsPacketHeaderRaw(pub(crate) BitArray<[u16; 6], Lsb0>);

{{</highlight>}}

We'll define a 'raw' buffer type that allows bit-level access atop the over-the-wire DNS packet. Let's define some groundwork for interacting with the different fields encoded within this buffer.

Update, _src/packet_header_layout.rs_
{{<highlight rust "linenos=inline,hl_lines=3-67,linenostart=25">}}
#[derive(Debug)]
pub(crate) struct DnsPacketHeaderRaw(pub(crate) BitArray<[u16; 6], Lsb0>);
impl DnsPacketHeaderRaw {
    pub(crate) const HEADER_SIZE: usize = mem::size_of::<Self>();

    fn read_u16_at_index(&self, idx: usize) -> u16 {
        let bits_in_u16 = 16;
        let start_bit_idx = idx * bits_in_u16;
        let end_bit_idx = (idx + 1) * bits_in_u16;
        self.0[start_bit_idx..end_bit_idx].load::<u16>().to_be()
    }

    pub(crate) fn identifier(&self) -> u16 {
        self.read_u16_at_index(0)
    }

    pub(crate) fn question_record_count(&self) -> u16 {
        self.read_u16_at_index(2)
    }

    pub(crate) fn answer_record_count(&self) -> u16 {
        self.read_u16_at_index(3)
    }

    pub(crate) fn authority_record_count(&self) -> u16 {
        self.read_u16_at_index(4)
    }

    pub(crate) fn additional_record_count(&self) -> u16 {
        self.read_u16_at_index(5)
    }

    fn read_bit_range_from_flags(&self, range: Range<usize>) -> u16 {
        let flags = self.read_u16_at_index(1);
        let flags_bits = flags.view_bits::<Msb0>();
        let bits_in_range = flags_bits.get(range).unwrap();
        bits_in_range.load::<u16>()
    }

    pub(crate) fn is_packet_a_response(&self) -> bool {
        self.read_bit_range_from_flags(0..1) == 1
    }

    pub(crate) fn opcode(&self) -> u16 {
        self.read_bit_range_from_flags(1..5)
    }

    pub(crate) fn is_packet_an_authoritative_answer(&self) -> bool {
        self.read_bit_range_from_flags(5..6) == 1
    }

    pub(crate) fn is_packet_a_truncated_response(&self) -> bool {
        self.read_bit_range_from_flags(6..7) == 1
    }

    pub(crate) fn is_recursion_desired(&self) -> bool {
        self.read_bit_range_from_flags(7..8) == 1
    }

    pub(crate) fn is_recursion_available(&self) -> bool {
        self.read_bit_range_from_flags(8..9) == 1
    }

    pub(crate) fn response_code(&self) -> u16 {
        self.read_bit_range_from_flags(12..16)
    }
}
{{</highlight>}}

Let's try it out with the packets `dig` sends us!

Update, _src/main.rs_
{{<highlight rust "linenos=inline,linenostart=25">}}
use std::net::UdpSocket;

use packet_header_layout::DnsPacketHeaderRaw;
mod packet_header_layout;
const MAX_DNS_UDP_PACKET_SIZE: usize = 512;
{{</highlight>}}

Update, _src/main.rs_
{{<highlight rust "linenos=inline,hl_lines=4-13,linenostart=25">}}
            .recv_from(&mut receive_packet_buf)
            .expect("Failed to read from the socket");

        println!("We've received a DNS query of {byte_count_received} bytes from {sender_addr:?}");
        let (header_bytes, _body_bytes) = receive_packet_buf.split_at(DnsPacketHeaderRaw::HEADER_SIZE);
        let header_raw = unsafe { &*(header_bytes.as_ptr() as *const DnsPacketHeaderRaw) };
        println!("\tPacket ID:                {:04x}", header_raw.identifier());
        println!("\tPacket opcode:            {:04x}", header_raw.opcode());
        println!("\tIs the packet a response? {}", header_raw.is_packet_a_response());
        println!("\tQuestion record count:    {:04}", header_raw.question_record_count());
        println!("\tAnswer record count:      {:04}", header_raw.answer_record_count());
        println!("\tAuthority record count:   {:04}", header_raw.authority_record_count());
        println!("\tAdditional record count:  {:04}", header_raw.additional_record_count());
{{</highlight>}}

```text
$ dig @0.0.0.0 -p 51456 google.com A
```

```text
$ cargo run dns_resolver
    Finished dev [unoptimized + debuginfo] target(s) in 0.05s
     Running `target/debug/dns_resolver dns_resolver`
Bound to UdpSocket { addr: 0.0.0.0:51456, fd: 3 }
Awaiting incoming packets...
We've received a DNS query of 39 bytes from 127.0.0.1:50084
        Packet ID:                00d0
        Packet opcode:            0000
        Is the packet a response? false
        Question record count:    0001
        Answer record count:      0000
        Authority record count:   0000
        Additional record count:  0001
```

Now that we can make some sense of the on-the-wire packet header, it'll be nice to have a corresponding higher-level representation of the packet header. For example, the _raw_ header format encodes the _type_ of query in a 4-bit integer. We _could_ have code that looks like this:

```rust
match header.opcode {
    0 => // Handle a Query packet
    2 => // Handle a Status packet
    4 => // Handle a Notify packet
}
```

... but this isn't very expressive or clear. One very useful technique for keeping code readable and easy to reason with, is to encode domain logic into the type system. Let's do this by defining higher-level representations to store information about the packet header fields.


Top-level show, _src/packet_header.rs_
{{<highlight rust "linenos=inline,linenostart=25">}}
#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub(crate) enum DnsOpcode {
    Query = 0,
    Status = 2,
    Notify = 4,
}

{{</highlight>}}

Let's define conversions from the 'raw' bit-fields stored in the on-the-wire packet to our strongly typed higher-level representations.

Child contextual show, `dns_opcode_try_from`

{{<highlight rust "linenos=inline,hl_lines=3-16,linenostart=25">}}
    Notify = 4,
}

impl TryFrom<usize> for DnsOpcode {
    type Error = usize;

    fn try_from(value: usize) -> Result<Self, Self::Error> {
        match value {
            0 => Ok(Self::Query),
            2 => Ok(Self::Status),
            4 => Ok(Self::Notify),
            _ => Err(value),
        }
    }
}

{{</highlight>}}

Let's flesh out this same concept for the rest of the header fields, by introducing a layer in between the 'raw' header and another representation which isn't constrained by the bitwise representation. 

Child contextual show, `packet_header_fields`

{{<highlight rust "linenos=inline,hl_lines=3-29,linenostart=25">}}
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub(crate) struct ResponseFields {
    is_packet_an_authoritative_answer: bool,
    is_recursion_available: bool,
    pub(crate) response_code: DnsPacketResponseCode,
}

impl ResponseFields {
    pub(crate) fn new(
        is_packet_an_authoritative_answer: bool,
        is_recursion_available: bool,
        response_code: DnsPacketResponseCode,
    ) -> Self {
        Self {
            is_packet_an_authoritative_answer,
            is_recursion_available,
            response_code,
        }
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub(crate) enum PacketDirection {
    Query,
    Response(ResponseFields),
}
{{</highlight>}}

Certain fields are always present in the packet header on-the-wire, such as the `is_packet_an_authoritative_answer` flag. However, these fields are _only valid_ when the packet is a response! Queries still need to send the storage to contain them, but their value will be ignored. We're forced to model these fields even when dealing with a query in the _raw_ representation, but we can leverage the power of the type system by using a sum type to express that these fields are _only present_ when we're dealing with a `PacketDirection::Response()`. 

Let's define the header itself.

Child contextual show, `define_packet_header`

{{<highlight rust "linenos=inline,hl_lines=2-17,linenostart=25">}}
    Response(ResponseFields),
}
#[derive(Debug, Clone)]
pub(crate) struct DnsPacketHeader {
    pub(crate) identifier: usize,
    pub(crate) direction: PacketDirection,
    pub(crate) opcode: DnsOpcode,
    pub(crate) response_code: DnsPacketResponseCode,
    pub(crate) is_packet_a_truncated_response: bool,
    pub(crate) is_packet_an_authoritative_answer: bool,
    pub(crate) is_recursion_desired: bool,
    pub(crate) is_recursion_available: bool,
    pub(crate) question_record_count: usize,
    pub(crate) answer_record_count: usize,
    pub(crate) authority_record_count: usize,
    pub(crate) additional_record_count: usize,
}
{{</highlight>}}

Finally, let's build a utility to convert the bitwise representation into the convenient representation.

Child contextual show, `packet_header_from_raw`

{{<highlight rust "linenos=inline,hl_lines=2-30,linenostart=25">}}
    pub(crate) additional_record_count: usize,
}
impl From<&DnsPacketHeaderRaw> for DnsPacketHeader {
    fn from(raw: &DnsPacketHeaderRaw) -> Self {
        Self {
            identifier: raw.identifier(),
            direction: match raw.is_response() {
                true => PacketDirection::Response(
                    ResponseFields::new(
                        raw.is_authoritative_answer(),
                        raw.is_recursion_available(),
                        raw.response_code().try_into().unwrap(),
                    )
                ),
                false => PacketDirection::Query,
            },
            opcode: DnsOpcode::try_from(raw.opcode())
                        .unwrap_or_else(|op| panic!("Unexpected DNS opcode: {}", op)),
            response_code: DnsPacketResponseCode::try_from(raw.response_code())
                        .unwrap_or_else(|val| panic!("Unexpected response code: {}", val)),
            is_truncated: raw.is_truncated(),
            is_recursion_desired: raw.is_recursion_desired(),
            is_recursion_available: raw.is_recursion_available(),
            question_count: raw.question_record_count(),
            answer_count: raw.answer_record_count(),
            authority_count: raw.authority_record_count(),
            additional_record_count: raw.additional_record_count(),
        }
    }
}
{{</highlight>}}

//We're now going to need some way to interpret the bytes we're receiving over-the-wire 

