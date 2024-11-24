import socket
from threading import Thread, Lock

def calculate_checksum(data):
    """
    Calcula o checksum como a soma dos valores ASCII dos caracteres na mensagem,
    reduzido por módulo 256.
    """
    return sum(ord(char) for char in data) % 256

def load_messages_from_file(file_path):
    """
    Carrega as mensagens de um arquivo de texto.
    Cada linha do arquivo é tratada como uma mensagem separada.
    """
    with open(file_path, "r") as file:
        content = file.read()
    return content.split(", ")  # Divide as mensagens separadas por vírgula e espaço

class SlidingWindowClient:
    def __init__(self, host='127.0.0.1', port=65432, window_size=4, timeout=3, max_retries=3):
        self.host = host
        self.port = port
        self.window_size = window_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.lock = Lock()
        self.acknowledged = set()

    def send_message(self, messages, mode="burst", num_packets=None):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.host, self.port))
        client_socket.settimeout(self.timeout)

        print(f"\nConfiguração inicial:")
        print(f"- Tamanho da janela deslizante: {self.window_size}")
        print(f"- Timeout: {self.timeout}s")
        print(f"- Número máximo de tentativas por pacote: {self.max_retries}\n")

        if mode == "single":
            print("Modo: Envio de um único pacote.")
            self._send_packet(client_socket, 1, messages[0])
        elif mode == "burst":
            print(f"Modo: Envio de {num_packets if num_packets else 'todos'} pacotes.")
            threads = []
            for seq_number, message in enumerate(messages[:num_packets] if num_packets else messages, start=1):
                t = Thread(target=self._send_packet, args=(client_socket, seq_number, message))
                threads.append(t)
                t.start()

                if seq_number % self.window_size == 0:
                    print(f"\n[LOG] Janela deslizante enviada: {seq_number - self.window_size + 1} - {seq_number}\n")
                    for thread in threads:
                        thread.join()
                    threads = []

            for thread in threads:
                thread.join()

        client_socket.close()

        print(f"\nConfiguração final da janela deslizante:")
        print(f"- Pacotes confirmados (ACK): {sorted(self.acknowledged)}")
        print(f"- Último pacote enviado: {max(self.acknowledged) if self.acknowledged else 'Nenhum'}")

    def _send_packet(self, client_socket, seq_number, message):
        retries = 0
        checksum = calculate_checksum(message)
        full_message = f"{seq_number}|{message}|{checksum}"

        while retries < self.max_retries:
            with self.lock:
                if seq_number in self.acknowledged:
                    print(f"Pacote {seq_number} já confirmado anteriormente. Ignorando envio.")
                    return

            try:
                print(f"Enviando pacote: Seq: {seq_number}, Mensagem: {message}, Checksum: {checksum}")
                client_socket.sendall(full_message.encode())

                response = client_socket.recv(1024).decode()
                print(f"Resposta recebida: {response}")

                if f"ACK|{seq_number}" in response or f"ACK_DUPLICATE|{seq_number}" in response:
                    with self.lock:
                        self.acknowledged.add(seq_number)
                    print(f"Pacote {seq_number} confirmado.")
                    return
                elif f"NACK|{seq_number}" in response:
                    print(f"Pacote {seq_number} corrompido, retransmitindo...")
            except socket.timeout:
                print(f"Timeout para o pacote {seq_number}, retransmitindo...")
                retries += 1

        print(f"Falha ao enviar o pacote {seq_number} após {self.max_retries} tentativas.")

if __name__ == "__main__":
    file_path = "bandas_forro_sanitized.txt"
    messages = load_messages_from_file(file_path)

    while True:
        try:
            window_size = int(input("Digite o tamanho inicial da janela deslizante (ex: 4): "))
            if window_size > 0:
                break
            else:
                print("O tamanho da janela deve ser maior que 0.")
        except ValueError:
            print("Entrada inválida! Digite um número inteiro.")

    print("\nEscolha o modo de envio:")
    print("1. Enviar um único pacote")
    print("2. Enviar uma rajada de pacotes")
    mode_choice = input("Digite o número da sua escolha: ")

    if mode_choice == "1":
        mode = "single"
        num_packets = 1
    elif mode_choice == "2":
        mode = "burst"
        num_packets = input("Quantos pacotes deseja enviar na rajada? (Digite 0 para enviar todos): ")
        try:
            num_packets = int(num_packets)
            if num_packets <= 0 or num_packets > len(messages):
                num_packets = None
        except ValueError:
            print("Entrada inválida. Enviando todos os pacotes.")
            num_packets = None
    else:
        print("Opção inválida! Usando o modo padrão: rajada de pacotes.")
        mode = "burst"
        num_packets = None

    client = SlidingWindowClient(window_size=window_size)
    client.send_message(messages, mode=mode, num_packets=num_packets)
