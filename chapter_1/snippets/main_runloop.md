executable: true
lang: rust
file: src/main.rs
###
{{main_imports}}

const MAX_DNS_UDP_PACKET_SIZE: usize = 512;

fn main() {
{{main_runloop_bind_to_socket}}
    let mut receive_packet_buf = [0; MAX_DNS_UDP_PACKET_SIZE];
    println!("Awaiting incoming packets...");
    loop {
        let (byte_count_received, sender_addr) = socket
            .recv_from(&mut receive_packet_buf)
            .expect("Failed to read from the socket");

            println!("We've received a DNS query of {byte_count_received} bytes from {sender_addr:?}");
    }
}