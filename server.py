import socket

def calculate_checksum(data):
    """
    Calcula o checksum como a soma dos valores ASCII dos caracteres na mensagem,
    reduzido por módulo 256.
    """
    return sum(ord(char) for char in data) % 256

def start_server(host='127.0.0.1', port=65432):
    """
    Inicializa o servidor para receber pacotes e responder com ACK ou NACK.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Servidor ouvindo em {host}:{port}")

    expected_seq = 1
    while True:
        conn, addr = server_socket.accept()
        print(f"Conexão estabelecida com {addr}")

        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break

                # Processa o pacote recebido
                parts = data.decode().split('|')
                if len(parts) != 3:
                    print("Pacote malformado recebido e ignorado.")
                    continue

                seq_number, message, received_checksum = parts
                seq_number = int(seq_number)
                received_checksum = int(received_checksum)

                print(f"Pacote recebido - Seq: {seq_number}, Mensagem: {message}, Checksum: {received_checksum}")

                # Valida o checksum e a ordem do pacote
                calculated_checksum = calculate_checksum(message)
                if seq_number < expected_seq:
                    print(f"Pacote duplicado ignorado - Seq: {seq_number}")
                    conn.sendall(f"ACK_DUPLICATE|{seq_number}".encode())
                elif calculated_checksum == received_checksum and seq_number == expected_seq:
                    print("Checksum válido! Dados íntegros.")
                    expected_seq += 1
                    conn.sendall(f"ACK|{seq_number}".encode())
                else:
                    print("Checksum inválido ou fora de ordem.")
                    conn.sendall(f"NACK|{seq_number}".encode())
            except ValueError:
                print("Erro ao processar pacote. Pacote ignorado.")
            except ConnectionResetError:
                print("Conexão perdida.")
                break

        print(f"Conexão encerrada com {addr}")
        conn.close()

if __name__ == "__main__":
    start_server()
