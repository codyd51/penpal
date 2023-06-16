executable: true
lang: rust
file: src/main.rs
###
{{main_imports}}

{{snippet1}}
    let socket = UdpSocket::bind("127.0.0.1:53")
        .expect("Failed to bind to our local DNS port, blah");
{{snippet2}}
