import socket
import hashlib

def calcular_checksum(mensagem_original):
    """Calcula a soma de verificação (checksum) MD5 para uma mensagem."""
    return hashlib.md5(mensagem_original.encode('utf-8')).hexdigest()

def cliente():
    servidor_host = '127.0.0.1'  # Endereço do servidor (localhost)
    servidor_porta = 12345       # Porta para comunicação

    # Criar socket do cliente
    socket_cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_cliente.connect((servidor_host, servidor_porta))

    numero_sequencia = 1  # Número de sequência inicial
    mensagem_base = "Mensagem padrão do cliente"  # Mensagem padrão inicial

    print("=== Cliente Ativo ===\n")
    while True:
        print("\nMenu de Opções:")
        print("1. Enviar um único pacote (com ou sem erro de integridade)")
        print("2. Enviar vários pacotes (rajada)")
        print("3. Alterar mensagem base")
        print("4. Encerrar cliente\n")
        
        opcao_menu = input("Escolha uma opção: ")

        if opcao_menu == '1':
            incluir_erro = input("\nDeseja incluir erro de integridade neste pacote? (s/n): ").strip().lower() == 's'
            mensagem_com_sequencia = f"Seq#{numero_sequencia}: {mensagem_base}"
            checksum_calculado = calcular_checksum(mensagem_com_sequencia)

            if incluir_erro:
                checksum_calculado = "ERRO_INTENCIONAL"

            mensagem_completa = f"{mensagem_com_sequencia}|CHECKSUM={checksum_calculado}"
            print(f"\nEnviando: {mensagem_completa}\n")
            socket_cliente.send(mensagem_completa.encode('utf-8'))

            resposta_servidor = socket_cliente.recv(1024).decode('utf-8')
            print(f"\nResposta do servidor: {resposta_servidor}\n")
            numero_sequencia += 1

        elif opcao_menu == '2':
            quantidade_pacotes = int(input("\nDigite a quantidade de pacotes a enviar: "))
            for i in range(numero_sequencia, numero_sequencia + quantidade_pacotes):
                mensagem_com_sequencia = f"Seq#{i}: {mensagem_base}"
                checksum_calculado = calcular_checksum(mensagem_com_sequencia)
                mensagem_completa = f"{mensagem_com_sequencia}|CHECKSUM={checksum_calculado}"
                print(f"\nEnviando: {mensagem_completa}\n")
                socket_cliente.send(mensagem_completa.encode('utf-8'))

            resposta_servidor = socket_cliente.recv(1024).decode('utf-8')
            print(f"\nResposta do servidor para o lote: {resposta_servidor}\n")
            numero_sequencia += quantidade_pacotes

        elif opcao_menu == '3':
            nova_mensagem_base = input("\nDigite a nova mensagem base: ")
            mensagem_base = nova_mensagem_base
            print(f"\nMensagem base atualizada para: {mensagem_base}\n")

        elif opcao_menu == '4':
            print("\nEncerrando cliente...\n")
            socket_cliente.send("SAIR".encode('utf-8'))
            break

        else:
            print("\nOpção inválida. Por favor, escolha novamente.\n")

    socket_cliente.close()

if __name__ == "__main__":
    cliente()
