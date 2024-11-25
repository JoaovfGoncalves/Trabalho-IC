import socket
import threading
import time
from collections import defaultdict, deque
from colorama import Fore, Style, init

# Inicializa o Colorama
init(autoreset=True)


class Client:
    def __init__(self, packets_with_error, window_size, total_messages, protocol):
        self.server_host = "127.0.0.1"
        self.server_port = 63214
        self.packets_with_error = packets_with_error
        self.error_attempts_tracker = defaultdict(int)
        self.max_window = window_size  # Janela máxima de envio
        self.total_messages = total_messages
        self.protocol_type = protocol.upper()
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.server_host, self.server_port))
        self.acknowledged_packets = set()
        self.sent_packets = {}
        self.message_timeout = 2
        self.active_timers = {}
        self.data_buffer = []
        self.stop_event = threading.Event()

        # Controle de congestionamento
        self.cwnd = 1  # Janela de congestionamento inicial
        self.ssthresh = 16  # Threshold inicial para Slow Start
        self.pending_packets = deque(range(1, total_messages + 1))  # Pacotes pendentes

        # Monitoramento de timeouts
        self.global_timeouts = 0  # Contador de timeouts consecutivos
        self.global_timeout_limit = 5  # Limite antes de abortar

    def perform_handshake(self):
        handshake_message = f"HANDSHAKE|PROTOCOL|{self.protocol_type}|WINDOW|{self.max_window}"
        self.client_socket.sendall(f"{handshake_message}\n".encode())
        print(Fore.CYAN + f"Sent: {handshake_message}")
        server_response = self.client_socket.recv(1024).decode().strip()

        if server_response.startswith(f"ACK_HANDSHAKE|PROTOCOL|{self.protocol_type}|WINDOW|{self.max_window}"):
            print(Fore.GREEN + f"Handshake confirmed by server: {server_response}")
        else:
            print(Fore.RED + "Handshake failed. Closing connection.")
            self.client_socket.close()
            exit()

    def load_message_data(self):
        try:
            with open("bandas_forro.txt", "r") as file:
                bandas = file.read().strip().split(", ")
                if len(bandas) < self.total_messages:
                    raise ValueError("O arquivo não contém mensagens suficientes para o total de mensagens especificado.")
                self.data_buffer = bandas[:self.total_messages]
                print(Fore.GREEN + f"[Data Loaded] Carregadas {len(self.data_buffer)} mensagens do arquivo.")
        except Exception as e:
            print(Fore.RED + f"[Error] Falha ao carregar mensagens do arquivo: {e}")
            exit()

    def calculate_checksum(self, message):
        checksum = sum(ord(c) for c in message) & 0xFFFF
        print(Fore.BLUE + f"[Checksum Calculation] Message content: '{message}', Calculated checksum: {checksum}")
        return checksum

    def send_message_packet(self, sequence_number):
        if self.stop_event.is_set():
            return False

        if sequence_number > self.cwnd:
            print(Fore.YELLOW + f"[Congestion Control] Packet {sequence_number} is waiting for congestion window (cwnd={self.cwnd}).")
            return False

        message_content = self.data_buffer[sequence_number - 1]
        checksum = self.calculate_checksum(message_content)

        # Introduzir erro de integridade intencional
        if sequence_number in self.packets_with_error:
            checksum = (checksum + 1) & 0xFFFF  # Alterar o checksum para criar um erro
            print(Fore.RED + f"[Checksum Injection] Intentionally altering checksum for Packet {sequence_number}. New checksum: {checksum}")

        message_content = f"SEND|{sequence_number}|{message_content}|{checksum}"
        print(Fore.CYAN + f"[Packet Preparation] Packet {sequence_number}: Content='{self.data_buffer[sequence_number - 1]}', Checksum={checksum}")
        try:
            self.client_socket.sendall(f"{message_content}\n".encode())
            self.sent_packets[sequence_number] = message_content
            print(Fore.GREEN + f"[Packet Sent] Packet {sequence_number} sent with checksum {checksum}. cwnd={self.cwnd}, pending_packets={list(self.pending_packets)}")
            return True
        except Exception as e:
            print(Fore.RED + f"[Error] Error sending packet {sequence_number}: {e}")
            return False

    def process_server_responses(self):
        while not self.stop_event.is_set():
            try:
                server_data = self.client_socket.recv(1024).decode()
                if not server_data:
                    break

                for line in server_data.split("\n"):
                    if not line.strip():
                        continue
                    response_parts = line.split("|")
                    if len(response_parts) < 3:
                        continue

                    response_type, sequence_number_str, _ = response_parts
                    sequence_number = int(sequence_number_str)

                    if response_type == "ACK":
                        print(Fore.GREEN + f"[ACK Received] ACK for Packet {sequence_number} received.")
                        self.acknowledged_packets.add(sequence_number)
                        self.global_timeouts = 0  # Resetar timeouts após ACK

                        # Crescimento da janela de congestionamento (Slow Start)
                        if self.cwnd < self.ssthresh:
                            self.cwnd += 1  # Crescimento exponencial
                            print(Fore.YELLOW + f"[Congestion Control] cwnd increased to {self.cwnd} (Slow Start).")
                        else:
                            self.cwnd = min(self.cwnd + 1, self.max_window)  # Crescimento linear após o limiar
                            print(Fore.YELLOW + f"[Congestion Control] cwnd increased to {self.cwnd} (Congestion Avoidance).")

                        print(Fore.CYAN + f"[Congestion State] cwnd={self.cwnd}, ssthresh={self.ssthresh}")
                        self.send_pending_packets()

                    elif response_type == "NAK":
                        print(Fore.RED + f"[NAK Received] NAK for Packet {sequence_number} received. Retransmitting...")
                        print(Fore.YELLOW + f"[Congestion Control] Before NAK: cwnd={self.cwnd}, ssthresh={self.ssthresh}")
                        
                        # Reinício do Slow Start
                        self.ssthresh = max(1, self.cwnd // 2)
                        self.cwnd = 1
                        print(Fore.YELLOW + f"[Congestion Control] After NAK: cwnd={self.cwnd}, ssthresh={self.ssthresh}")

                        # Retransmissão do pacote com checksum correto
                        self.send_message_packet(sequence_number)

            except Exception as e:
                if not self.stop_event.is_set():
                    print(Fore.RED + f"[Error] Error receiving server response: {e}")

    def send_pending_packets(self):
        while self.pending_packets and len(self.sent_packets) < self.cwnd:
            next_packet = self.pending_packets.popleft()
            if next_packet not in self.acknowledged_packets:
                self.send_message_packet(next_packet)

    def start_sending_messages(self):
        self.load_message_data()
        threading.Thread(target=self.process_server_responses, daemon=True).start()

        # Enviar pacotes iniciais dentro da janela de congestionamento
        self.send_pending_packets()

        # Esperar pelo reconhecimento de todos os pacotes
        while len(self.acknowledged_packets) < self.total_messages and not self.stop_event.is_set():
            self.send_pending_packets()

            # Monitore timeouts globais
            self.global_timeouts += 1
            if self.global_timeouts > self.global_timeout_limit:
                print(Fore.RED + f"Global timeout limit reached ({self.global_timeouts} consecutive timeouts). Aborting.")
                self.stop_client()

            time.sleep(1)

        print(Fore.GREEN + "All packets acknowledged. Closing connection.")

    def close_client_connection(self):
        self.stop_event.set()  # Sinaliza interrupção
        for timer in self.active_timers.values():
            timer.cancel()
        self.client_socket.close()
        print(Fore.YELLOW + "Connection closed.")

    def stop_client(self):
        print(Fore.RED + "Stopping client abruptly.")
        self.close_client_connection()
        exit()


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
