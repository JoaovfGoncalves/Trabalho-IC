import socket
import threading


class Server:
    def __init__(self, protocol, cumulative_ack, receive_window_size):
        self.server_host = "127.0.0.1"
        self.server_port = 63214
        self.protocol_type = protocol.upper()
        self.cumulative_ack = cumulative_ack
        self.receive_window_size = receive_window_size
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.server_host, self.server_port))
        self.server_socket.listen(5)

        self.expected_sequence = 1
        self.received_messages = {}
        self.out_of_order_packets = {}
        self.current_receive_window = list(range(1, self.receive_window_size + 1))

    @staticmethod
    def calculate_checksum(message: str) -> int:
        return sum(ord(c) for c in message) & 0xFFFF

    def send_message(self, connection, message_type, sequence_number):
        message = f"{message_type}|{sequence_number}"
        checksum = self.calculate_checksum(message)
        full_message = f"{message}|{checksum}\n"
        connection.sendall(full_message.encode())
        print(f"Sent: {full_message.strip()}")

    def handle_packet(self, connection, sequence_number, message_content, received_checksum):
        if not self.validate_checksum(message_content, received_checksum):
            self.process_corrupted_packet(connection, sequence_number, message_content)
        elif sequence_number == self.expected_sequence:
            self.process_in_order_packet(connection, sequence_number, message_content)
        elif sequence_number in self.current_receive_window:
            self.process_out_of_order_packet(connection, sequence_number, message_content)
        else:
            self.process_invalid_packet(connection, sequence_number, message_content)

    def validate_checksum(self, message_content, received_checksum) -> bool:
        return self.calculate_checksum(message_content) == received_checksum

    def process_in_order_packet(self, connection, sequence_number, message_content):
        print(f"Packet {sequence_number} confirmed: {message_content}")
        self.received_messages[sequence_number] = message_content
        self.send_message(connection, "ACK", sequence_number)
        self.update_receive_window()
        self.process_out_of_order_buffer(connection)

    def process_out_of_order_packet(self, connection, sequence_number, message_content):
        print(f"Packet {sequence_number} out-of-order: {message_content}. Window: {self.current_receive_window}")
        self.out_of_order_packets[sequence_number] = message_content
        self.send_message(connection, "NAK", self.expected_sequence)

    def process_corrupted_packet(self, connection, sequence_number, message_content):
        print(f"Checksum error in packet {sequence_number}: {message_content}")
        if sequence_number not in self.received_messages:
            self.send_message(connection, "NAK", sequence_number)

    def process_invalid_packet(self, connection, sequence_number, message_content):
        if sequence_number < self.expected_sequence:
            print(f"Packet {sequence_number} already processed: {message_content}")
            self.send_message(connection, "ACK", sequence_number)
        else:
            print(f"Packet {sequence_number} outside receive window: {message_content}. "
                  f"Expected: {self.current_receive_window}")
            self.send_message(connection, "NAK", sequence_number)

    def process_out_of_order_buffer(self, connection):
        while self.expected_sequence in self.out_of_order_packets:
            message_content = self.out_of_order_packets.pop(self.expected_sequence)
            print(f"Processing out-of-order packet: {self.expected_sequence}|{message_content}")
            self.received_messages[self.expected_sequence] = message_content
            self.send_message(connection, "ACK", self.expected_sequence)
            self.update_receive_window()

    def update_receive_window(self):
        while self.expected_sequence in self.received_messages:
            self.expected_sequence += 1
        self.current_receive_window = list(
            range(self.expected_sequence, self.expected_sequence + self.receive_window_size)
        )
        print(f"Receive window updated: {self.current_receive_window}")

    def handle_abort(self, sequence_number):
        print(f"Client aborted packet {sequence_number}. Skipping further processing.")
        self.out_of_order_packets.pop(sequence_number, None)
        if sequence_number in self.current_receive_window:
            self.current_receive_window.remove(sequence_number)

    def handle_client(self, connection):
        if not self.handle_handshake(connection):
            return

        buffer = ""
        while True:
            try:
                data = connection.recv(1024).decode()
                if not data:
                    print("Client disconnected.")
                    break

                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    parts = line.strip().split("|")
                    if len(parts) >= 4:
                        command, seq_num_str, content, checksum_str = parts
                        sequence_number = int(seq_num_str)
                        received_checksum = int(checksum_str)

                        print(f"Received {command}|{sequence_number}|{content} "
                              f"(Checksum received: {received_checksum})")

                        if command == "SEND":
                            self.handle_packet(connection, sequence_number, content, received_checksum)
                        elif command == "ERR":
                            print(f"Corrupted packet {sequence_number} received: {content}")
                            self.send_message(connection, "NAK", sequence_number)
                        elif command == "ABORT":
                            self.handle_abort(int(seq_num_str))
                            continue
                    else:
                        print(f"Unrecognized message format: {line.strip()}")
            except ConnectionResetError:
                print("Client unexpectedly closed the connection.")
                break
            except Exception as e:
                print(f"Communication error: {e}")
                break
        connection.close()
        print("Client connection closed.")

    def handle_handshake(self, connection):
        try:
            handshake_message = connection.recv(1024).decode().strip()
            if handshake_message.startswith("HANDSHAKE|"):
                print(f"Received: {handshake_message}")
                parts = handshake_message.split("|")
                protocol = parts[2]
                window_size = int(parts[4])

                if protocol == self.protocol_type and window_size == self.receive_window_size:
                    handshake_ack = f"ACK_HANDSHAKE|PROTOCOL|{self.protocol_type}|WINDOW|{self.receive_window_size}\n"
                    connection.sendall(handshake_ack.encode())
                    print(f"Sent: {handshake_ack.strip()}")
                    return True
                else:
                    print("Handshake validation failed. Closing connection.")
                    connection.close()
            else:
                print("Invalid handshake message. Closing connection.")
                connection.close()
        except Exception as e:
            print(f"Error during handshake: {e}")
            connection.close()
        return False

    def start(self):
        print("Server is running and waiting for connections...")
        while True:
            client_connection, client_address = self.server_socket.accept()
            print(f"Connection established with {client_address}.")
            threading.Thread(target=self.handle_client, args=(client_connection,), daemon=True).start()


if __name__ == "__main__":
    protocol = input("Choose protocol (SR for Selective Repeat, GBN for Go-Back-N): ").upper()
    cumulative_ack = input("Enable cumulative acknowledgments? (Y/N): ").lower() == "y"
    receive_window_size = int(input("Enter receive window size (e.g., 5): "))
    server = Server(protocol, cumulative_ack, receive_window_size)
    server.start()
