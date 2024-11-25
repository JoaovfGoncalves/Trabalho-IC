# Sistema Cliente-Servidor com Transporte Confiável

## Descrição do Projeto
Este trabalho implementa um sistema cliente-servidor que garante o transporte confiável de dados na camada de aplicação, simulando perdas de pacotes e erros de integridade em um canal de comunicação. Ele implementa:
- *Controle de fluxo*
- *Controle de congestionamento*
- *Mecanismos de transporte confiável*, como:
  - Retransmissão
  - Soma de verificação (checksum)
  - Suporte aos protocolos Go-Back-N (GBN) e Selective Repeat (SR)

## Características Implementadas

### Conexão
- Comunicação entre cliente e servidor utilizando *sockets*.
- Conexão via localhost.

### Protocolo de Aplicação
- Regras definidas para troca de mensagens:
  - *Pacotes de dados*
  - *Confirmações (ACK/NACK)*
  - *Configuração inicial*

### Transporte Confiável
- *Soma de verificação*: Garante a integridade das mensagens.
- *Temporizador*: Retransmissão de pacotes após timeout.
- *Número de sequência*: Gerencia pacotes enviados e recebidos.
- *ACK/NACK*: Confirmações positivas e negativas.
- *Janela deslizante*: Controle de fluxo e paralelismo no envio e recebimento.

### Simulação de Falhas
- Inserção de *erros em pacotes* enviados pelo cliente.
- *Perda simulada de pacotes*, onde o servidor ignora certos ACKs.

### Envio de Pacotes
- *Envio individual* ou em *rajada*.
- Configuração de lote pelo cliente.

### Controle Dinâmico
- Atualização da *janela de recepção* e do *congestionamento* com base em:
  - Perdas de pacotes
  - Duplicações
- Negociação do protocolo de retransmissão (*GBN* ou *SR*) entre cliente e servidor.

## Arquitetura

### Cliente
- Envia pacotes *individuais ou em lote*.
- Simula *erros de integridade* em pacotes específicos.
- Implementa *janela deslizante* para envio de mensagens.
- Gerencia *congestionamento* com algoritmos de controle.

### Servidor
- Recebe e processa pacotes:
  - Reconhecendo ou solicitando retransmissões.
  - Simulando perdas de pacotes e erros de ACK.
- Atualiza dinamicamente a *janela de recepção*.
- Gera *NACKs* para mensagens com erros detectados.

## Instruções para Uso

### Requisitos
- *Python* 3.8+
- Dependências: 
  - socket
  - threading
  - colorama

Para instalar as dependências:
bash
pip install colorama

## Execução

### Iniciar o Servidor
1. Para iniciar o servidor, execute o seguinte comando no terminal:
   ```bash
   python server.py

### Iniciar o Cliente
2. Para iniciar o cliente, execute o seguinte comando no terminal:
  ```bash
   python client.py
