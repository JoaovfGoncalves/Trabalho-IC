import socket
import threading
import time
import os
from collections import defaultdict

class Client:
    def __init__(self, packets_with_error, window_size, total_messages, protocol):
        self.server_host = "127.0.0.1"
        self.server_port = 63214
        self.packets_with_error = packets_with_error
        self.error_attempts_tracker = defaultdict(int)
        self.window_size = window_size
        self.total_messages = total_messages
        self.protocol_type = protocol.upper()
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.server_host, self.server_port))
        self.acknowledged_packets = set()
        self.sent_packets = {}
        self.message_timeout = 2
        self.active_timers = {}
        self.data_buffer = []

    def perform_handshake(self):
        handshake_message = f"HANDSHAKE|PROTOCOL|{self.protocol_type}|WINDOW|{self.window_size}"
        self.client_socket.sendall(f"{handshake_message}\n".encode())
        print(f"Sent: {handshake_message}")
        server_response = self.client_socket.recv(1024).decode().strip()

        if server_response.startswith(f"ACK_HANDSHAKE|PROTOCOL|{self.protocol_type}|WINDOW|{self.window_size}"):
            print(f"Handshake confirmed by server: {server_response}")
        else:
            print("Handshake failed. Closing connection.")
            self.client_socket.close()
            exit()

    def load_message_data(self):
        file_path = os.path.join(os.getcwd(), "bands.txt")
        try:
            with open(file_path, "r") as file:
                self.data_buffer = [line.strip() for line in file.read().split(",")]
        except FileNotFoundError:
            print("File 'bands.txt' not found. Using generic messages.")
            self.data_buffer = [f"Message {i + 1}" for i in range(self.total_messages)]

    def calculate_checksum(self, message):
        return sum(ord(c) for c in message) & 0xFFFF

    def send_message_packet(self, sequence_number, message_content):
        if sequence_number in self.packets_with_error and self.error_attempts_tracker[sequence_number] < 3:
            self.error_attempts_tracker[sequence_number] += 1
            checksum = self.calculate_checksum(message_content)
            message_content = f"ERR|{sequence_number}|{message_content[::-1]}|{checksum}"
            print(f"Simulating error in packet {sequence_number} (attempt {self.error_attempts_tracker[sequence_number]})")
        elif sequence_number in self.packets_with_error and self.error_attempts_tracker[sequence_number] >= 3:
            print(f"Packet {sequence_number} discarded after 3 failed attempts. Aborting batch.")
            self.client_socket.sendall(f"ABORT|{sequence_number}|FAILED\n".encode())
            return False
        else:
            checksum = self.calculate_checksum(message_content)
            message_content = f"SEND|{sequence_number}|{message_content}|{checksum}"

        try:
            self.client_socket.sendall(f"{message_content}\n".encode())
            self.sent_packets[sequence_number] = message_content
            print(f"Sent: {message_content}")
            return True
        except Exception as e:
            print(f"Error sending packet {sequence_number}: {e}")
            return False

    def start_message_timer(self, sequence_number):
        def timer_expired():
            if sequence_number not in self.acknowledged_packets:
                print(f"Timeout for packet {sequence_number}, retransmitting...")
                if not self.send_message_packet(sequence_number, self.data_buffer[sequence_number - 1]):
                    return
                self.start_message_timer(sequence_number)

        if sequence_number in self.active_timers:
            self.active_timers[sequence_number].cancel()

        timer = threading.Timer(self.message_timeout, timer_expired)
        timer.start()
        self.active_timers[sequence_number] = timer

    def cancel_message_timer(self, sequence_number):
        if sequence_number in self.active_timers:
            self.active_timers[sequence_number].cancel()
            del self.active_timers[sequence_number]

    def process_server_responses(self):
        response_buffer = ""
        while len(self.acknowledged_packets) < self.total_messages:
            try:
                server_data = self.client_socket.recv(1024).decode()
                if not server_data:
                    break
                response_buffer += server_data
                while "\n" in response_buffer:
                    line, response_buffer = response_buffer.split("\n", 1)
                    response_parts = line.split("|")
                    if len(response_parts) < 3:
                        continue
                    response_type, sequence_number_str, checksum_str = response_parts
                    sequence_number = int(sequence_number_str)
                    checksum = int(checksum_str)

                    expected_checksum = f"{response_type}|{sequence_number}"
                    if self.calculate_checksum(expected_checksum) == checksum:
                        if response_type == "ACK":
                            print(f"Received ACK|{sequence_number}")
                            self.acknowledged_packets.add(sequence_number)
                            self.cancel_message_timer(sequence_number)
                        elif response_type == "NAK":
                            print(f"Received NAK|{sequence_number}, retransmitting...")
                            if sequence_number not in self.acknowledged_packets:
                                self.send_message_packet(sequence_number, self.data_buffer[sequence_number - 1])
                                self.start_message_timer(sequence_number)
                        elif response_type == "ABORT":
                            print(f"Batch aborted by server due to packet {sequence_number} failure.")
                            return
                    else:
                        print(f"Corrupted response: {line}")
            except Exception as e:
                print(f"Error receiving server response: {e}")

    def start_sending_messages(self):
        self.load_message_data()
        threading.Thread(target=self.process_server_responses, daemon=True).start()

        for sequence_number in range(1, self.total_messages + 1):
            if sequence_number not in self.acknowledged_packets:
                if not self.send_message_packet(sequence_number, self.data_buffer[sequence_number - 1]):
                    return
                self.start_message_timer(sequence_number)

        while len(self.acknowledged_packets) < self.total_messages:
            time.sleep(1)

        print("All packets acknowledged. Closing connection.")

    def close_client_connection(self):
        print("Waiting for final ACK confirmations...")
        time.sleep(1)
        self.client_socket.close()
        print("Connection closed.")

def client_menu():
    window_size = int(input("Enter initial window size: "))
    total_messages = int(input("Enter total number of messages to send: "))
    protocol_type = input("Choose protocol (SR for Selective Repeat, GBN for Go-Back-N): ").upper()
    error_packets_input = input("Enter packet numbers to simulate errors (comma-separated): ")
    packets_with_error = list(map(int, error_packets_input.split(","))) if error_packets_input else []

    client = Client(packets_with_error, window_size, total_messages, protocol_type)
    client.perform_handshake()
    client.start_sending_messages()
    client.close_client_connection()

if __name__ == "__main__":
    client_menu()