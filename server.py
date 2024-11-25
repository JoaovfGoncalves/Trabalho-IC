import socket
import threading
from collections import defaultdict
from colorama import Fore, Style, init

# Inicializa o Colorama
init(autoreset=True)


class Server:
    def __init__(self, protocol, cumulative_acks, receive_window_size):
        self.server_host = "127.0.0.1"
        self.server_port = 63214
        self.protocol_type = protocol.upper()
        self.cumulative_acks = cumulative_acks
        self.receive_window_size = receive_window_size
        self.current_receive_window = []
        self.out_of_order_packets = {}
        self.received_messages = {}
        self.expected_sequence = 1
        self.lock = threading.Lock()

    def start_server(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.server_host, self.server_port))
        server_socket.listen(5)
        print(Fore.GREEN + f"Server is running and waiting for connections...")
        while True:
            client_socket, client_address = server_socket.accept()
            print(Fore.CYAN + f"Connection established with {client_address}.")
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def handle_client(self, client_socket):
        try:
            self.perform_handshake(client_socket)
            self.current_receive_window = list(
                range(self.expected_sequence, self.expected_sequence + self.receive_window_size)
            )
            while True:
                data = client_socket.recv(1024).decode().strip()
                if not data:
                    break
                for line in data.split("\n"):
                    if line.strip():
                        self.process_message(client_socket, line)
        except Exception as e:
            print(Fore.RED + f"[Error] {e}")
        finally:
            print(Fore.YELLOW + "Client connection closed.")
            client_socket.close()

    def perform_handshake(self, connection):
        handshake_data = connection.recv(1024).decode().strip()
        print(Fore.BLUE + f"Received: {handshake_data}")
        if handshake_data.startswith("HANDSHAKE"):
            _, _, protocol, _, window_size = handshake_data.split("|")
            if protocol == self.protocol_type and int(window_size) == self.receive_window_size:
                response = f"ACK_HANDSHAKE|PROTOCOL|{protocol}|WINDOW|{window_size}"
                connection.sendall(f"{response}\n".encode())
                print(Fore.GREEN + f"Sent: {response}")
            else:
                print(Fore.RED + "[Handshake Error] Protocol or window size mismatch.")
                connection.close()
                exit()

    def process_message(self, connection, message):
        message_parts = message.split("|")
        if len(message_parts) < 3:
            print(Fore.RED + f"[Invalid Message] {message}")
            return

        message_type, sequence_number_str, content = message_parts[:3]
        sequence_number = int(sequence_number_str)
        checksum_received = int(message_parts[3]) if len(message_parts) > 3 else None

        print(Fore.CYAN + f"[Message Received] Packet {sequence_number}: Type={message_type}, Content='{content}', Checksum={checksum_received}")
        if message_type == "SEND":
            self.handle_send(connection, sequence_number, content, checksum_received)
        elif message_type == "ERR":
            print(Fore.RED + f"[Corrupted Packet] Packet {sequence_number} received with errors.")
            self.send_message(connection, "NAK", sequence_number)
        elif message_type == "ABORT":
            print(Fore.RED + f"[Abort Received] Packet {sequence_number} failed. Client aborted.")
        else:
            print(Fore.YELLOW + f"[Unknown Message Type] {message}")

    def handle_send(self, connection, sequence_number, content, checksum_received):
        calculated_checksum = sum(ord(c) for c in content) & 0xFFFF
        print(Fore.BLUE + f"[Checksum Validation] Packet {sequence_number}: Received checksum={checksum_received}, Calculated checksum={calculated_checksum}")
        if checksum_received != calculated_checksum:
            print(Fore.RED + f"[Checksum Error] Packet {sequence_number} has invalid checksum. Sending NAK.")
            print(Fore.YELLOW + f"[Flow Control] Before NAK: Receive Window={self.current_receive_window}, Expected Sequence={self.expected_sequence}")
            self.send_message(connection, "NAK", sequence_number)
            print(Fore.YELLOW + f"[Flow Control] After NAK: Receive Window remains unchanged as packet needs retransmission.")
            return

        with self.lock:
            if sequence_number == self.expected_sequence:
                self.process_in_order_packet(connection, sequence_number, content)
            else:
                self.process_invalid_packet(connection, sequence_number, content)

    def process_in_order_packet(self, connection, sequence_number, message_content):
        print(Fore.GREEN + f"[Packet Received] Packet {sequence_number} received in order: {message_content}")
        self.received_messages[sequence_number] = message_content
        self.send_message(connection, "ACK", sequence_number)
        print(Fore.YELLOW + f"[Flow Control] Packet {sequence_number} acknowledged. Updating receive window.")
        self.update_receive_window()
        self.process_out_of_order_buffer(connection)

    def process_invalid_packet(self, connection, sequence_number, message_content):
        if sequence_number < self.expected_sequence:
            print(Fore.MAGENTA + f"[Duplicate Packet] Packet {sequence_number} already processed.")
            self.send_message(connection, "ACK", sequence_number)
        elif sequence_number in self.current_receive_window:
            print(Fore.YELLOW + f"[Out-of-Order Packet] Packet {sequence_number} buffered: {message_content}")
            self.out_of_order_packets[sequence_number] = message_content
        else:
            print(Fore.RED + f"[Out-of-Bounds Packet] Packet {sequence_number} outside of receive window: {self.current_receive_window}.")
            self.send_message(connection, "NAK", sequence_number)

    def update_receive_window(self):
        self.expected_sequence += 1
        self.current_receive_window = list(
            range(self.expected_sequence, self.expected_sequence + self.receive_window_size)
        )
        print(Fore.CYAN + f"[Flow Control] Updated receive window: {self.current_receive_window}")

    def process_out_of_order_buffer(self, connection):
        while self.expected_sequence in self.out_of_order_packets:
            content = self.out_of_order_packets.pop(self.expected_sequence)
            print(Fore.GREEN + f"[Processing Buffered Packet] Packet {self.expected_sequence} processed: {content}")
            self.process_in_order_packet(connection, self.expected_sequence, content)

    def send_message(self, connection, response_type, sequence_number):
        if response_type == "ACK":
            print(Fore.GREEN + f"[Flow Control] Sending ACK for Packet {sequence_number}.")
        elif response_type == "NAK":
            print(Fore.RED + f"[Flow Control] Sending NAK for Packet {sequence_number}.")
        connection.sendall(f"{response_type}|{sequence_number}|CONFIRM\n".encode())


def server_menu():
    protocol = input("Choose protocol (SR for Selective Repeat, GBN for Go-Back-N): ").upper()
    cumulative_acks = input("Enable cumulative acknowledgments? (Y/N): ").upper() == "Y"
    receive_window_size = int(input("Enter receive window size (e.g., 5): "))
    server = Server(protocol, cumulative_acks, receive_window_size)
    server.start_server()


if __name__ == "__main__":
    server_menu()
