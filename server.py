import socket
import hashlib

def calcular_checksum(mensagem_original):
    """Calcula a soma de verificação (checksum) MD5 para uma mensagem."""
    return hashlib.md5(mensagem_original.encode('utf-8')).hexdigest()

def servidor():
    servidor_host = '127.0.0.1'  # Endereço localhost
    servidor_porta = 12345       # Porta para comunicação

    # Criar socket do servidor
    socket_servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_servidor.bind((servidor_host, servidor_porta))
    socket_servidor.listen(1)

    numero_sequencia_esperado = 1  # Primeiro número de sequência esperado

    print(f"Servidor aguardando conexões em {servidor_host}:{servidor_porta}...\n")
    conexao_cliente, endereco_cliente = socket_servidor.accept()
    print(f"Conexão estabelecida com {endereco_cliente}\n")

    while True:
        mensagem_recebida = conexao_cliente.recv(1024).decode('utf-8')
        if not mensagem_recebida:
            print("\nNenhuma mensagem recebida ou conexão encerrada.\n")
            break

        if mensagem_recebida == "SAIR":
            print("\nCliente solicitou encerramento.\n")
            break

        # Processar mensagens
        if "|CHECKSUM=" in mensagem_recebida:
            mensagem_original, checksum_recebido = mensagem_recebida.rsplit("|CHECKSUM=", 1)
            checksum_calculado = calcular_checksum(mensagem_original)
            
            # Verificar integridade
            if checksum_recebido != checksum_calculado:
                print(f"\nErro de integridade detectado: {mensagem_original}\n")
                resposta_ao_cliente = f"NACK - Erro de integridade no pacote: {mensagem_original}"
                conexao_cliente.send(resposta_ao_cliente.encode('utf-8'))
                continue
            
            # Verificar ordem do número de sequência
            try:
                numero_sequencia_atual = int(mensagem_original.split("Seq#")[1].split(":")[0])
            except (IndexError, ValueError):
                print(f"\nMensagem malformada: {mensagem_original}\n")
                resposta_ao_cliente = "NACK - Mensagem malformada"
                conexao_cliente.send(resposta_ao_cliente.encode('utf-8'))
                continue

            if numero_sequencia_atual != numero_sequencia_esperado:
                print(f"\nNúmero de sequência fora da ordem: Esperado {numero_sequencia_esperado}, Recebido {numero_sequencia_atual}\n")
                resposta_ao_cliente = f"NACK - Número de sequência incorreto: {numero_sequencia_atual}"
                conexao_cliente.send(resposta_ao_cliente.encode('utf-8'))
                continue
            
            # Mensagem válida
            print(f"\nMensagem válida recebida: {mensagem_original}")
            print(f"-> Número de sequência: {numero_sequencia_atual}")
            print(f"-> Checksum: {checksum_recebido}\n")
            resposta_ao_cliente = f"ACK - Mensagem confirmada: {mensagem_original}"
            numero_sequencia_esperado += 1  # Atualizar número de sequência esperado

        else:
            print(f"\nMensagem recebida sem checksum: {mensagem_recebida}\n")
            resposta_ao_cliente = "NACK - Mensagem sem checksum!"

        conexao_cliente.send(resposta_ao_cliente.encode('utf-8'))

    conexao_cliente.close()
    socket_servidor.close()

if __name__ == "__main__":
    servidor()
