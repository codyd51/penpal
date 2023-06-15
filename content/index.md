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

{{listing1}}

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

{{listing2}}

```shell
$ cargo run dns_resolver
   Compiling dns_resolver v0.1.0 
    Finished dev [unoptimized + debuginfo] target(s) in 0.70s
     Running `target/debug/dns_resolver dns_resolver`
Bound to UdpSocket { addr: 0.0.0.0:57167, fd: 3 }
```

Great! Our server is running and ready to receive inbound packets. By binding to `0.0.0.0:0`, we're requesting that the OS bind our socket to any available address. In this case, the OS has bound my socket to `0.0.0.0:57167`. 








We're now ready to send a test packet to our server. Let's use `dig`, a standard command line utility that allows us to manually send DNS queries. Fixme


- Receiving packets
- Parsing a simple query
- Writing a simplne response
- Test bed
- Trying it on real traffic (crash)
- Parsing many query types
- Writing many response types
- Concurrency



