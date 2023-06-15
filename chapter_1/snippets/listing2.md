executable: true
lang: rust
###
{{snippet1}}
{{highlight}}
    let socket = UdpSocket::bind("0.0.0.0:0").expect("Failed to bind to a local socket");
    println!("Bound to {socket:?}");
{{/highlight}}
{{snippet2}}
