+++
title = "DNS Resolver: Receiving Packets"
date = "2023-06-14T22:20:08+01:00"

tags = []
+++

Let's get started.

```shell
$ cargo new dns_resolver --bin
$ cd dns_resolver
```

If you strip away our DNS resolver to the bare bones, its core runloop will be composed of a _request_ and a response_. Our general approach will be:

1. _Wait_ for a DNS request to arrive.
2. _Parse_ the request.
3. _Perform_ the lookup.
4. _Send_ the response.

To get us started, let's _wait_ for DNS queries to come in.









_src/main.rs_
```rust
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

        println!("We've received a DNS query of {byte_count_received} bytes from {sender_addr:?}");
    }
}
```


When we try to run this, the operating system rejects our request:

```shell
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

_src/main.rs_
```rust

fn main() {
{{< rawhtml >}}<div style="background-color: #4a4a00">    let socket = UdpSocket::bind("0.0.0.0:0")
        .expect("Failed to bind to a local socket");
    println!("Bound to {socket:?}");
</div>{{< /rawhtml >}}
    let mut receive_packet_buf = [0; MAX_DNS_UDP_PACKET_SIZE];
    println!("Awaiting incoming packets...");
```


```shell
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

```shell
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

```shell
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





_Cargo.toml_
```toml
[dependencies]
bitvec = "1"
```


Now, let's start modeling the DNS header format! Make a new file, `packet_header_layout.rs`.

_src/main.rs_
```rust
use std::net::UdpSocket;

{{< rawhtml >}}<div style="background-color: #4a4a00">use packet_header_layout;
</div>{{< /rawhtml >}}

const MAX_DNS_UDP_PACKET_SIZE: usize = 512;
```




_packet_header_layout.rs_
```rust
#[derive(Debug)]
pub(crate) struct DnsPacketHeaderRaw(pub(crate) BitArray<[u16; 6], Lsb0>);
```

