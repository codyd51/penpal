use std::net::UdpSocket;

const MAX_DNS_UDP_PACKET_SIZE: usize = 512;

fn main() {
    let socket = UdpSocket::bind("0.0.0.0:0").expect("Failed to bind to our local DNS port");
    println!("Bound to {socket:?}");

    let mut receive_packet_buf = [0; MAX_DNS_UDP_PACKET_SIZE];
    println!("Awaiting incoming packets...");
    loop {
        let (byte_count_received, sender_addr) = socket.recv_from(&mut receive_packet_buf).expect("Failed to read from the socket");
        println!("We've received a DNS query of {byte_count_received} bytes from {sender_addr:?}");
    }
}
