import os
import struct

def get_base_address(pid, process_name):
    """Varre o arquivo maps do processo para encontrar o endereço base do ASLR."""
    try:
        with open(f"/proc/{pid}/maps", "r") as maps_file:
            for line in maps_file:
                # Procura pela primeira linha que contém o caminho do executável
                if process_name in line and "r-xp" in line:
                    base_addr_str = line.split("-")[0]
                    return int(base_addr_str, 16)
    except FileNotFoundError:
        print(f"[-] Processo {pid} não encontrado.")
    return None

def read_memory(pid, address, data_type="I", data_size=4):
    """Lê bytes diretamente do arquivo de memória do processo."""
    try:
        with open(f"/proc/{pid}/mem", "rb") as mem_file:
            mem_file.seek(address)
            data = mem_file.read(data_size)
            if len(data) == data_size:
                return struct.unpack(data_type, data)[0]
    except PermissionError:
        print("[-] Permissão negada. Execute como sudo.")
    except Exception as e:
        print(f"[-] Erro ao ler memória: {e}")
    return None

# Configurações do ambiente com base nos dados coletados
PID = 10512
BINARY_NAME = "Tibia/bin/client"

# ATENÇÃO: Estes offsets são exemplificativos. Devem ser mapeados via ferramenta de busca de ponteiros.
OFFSETS = {
    "vida_atual": 0x1A20,
    "mana_atual": 0x1A28,
    "coord_x": 0x2B00,
    "coord_y": 0x2B04,
    "coord_z": 0x2B08
}

base_address = get_base_address(PID, BINARY_NAME)

if base_address:
    print(f"[+] Endereço Base do Módulo (ASLR): {hex(base_address)}")
    
    # Cálculo dos endereços dinâmicos reais da sessão atual
    addr_hp = base_address + OFFSETS["vida_atual"]
    addr_mana = base_address + OFFSETS["mana_atual"]
    addr_x = base_address + OFFSETS["coord_x"]
    
    # Leitura dos dados (I = Unsigned Integer de 4 bytes)
    hp_atual = read_memory(PID, addr_hp, "I", 4)
    mana_atual = read_memory(PID, addr_mana, "I", 4)
    
    # Leitura de coordenadas contíguas (X, Y, Z sequenciais)
    pos_x = read_memory(PID, addr_x, "I", 4)
    pos_y = read_memory(PID, addr_x + 4, "I", 4)
    pos_z = read_memory(PID, addr_x + 8, "I", 4) # Geralmente Z é um inteiro menor, mas mapeado em 4 bytes por alinhamento
    
    print("\n--- Dados Obtidos Automaticamente ---")
    print(f"Vida Atual: {hp_atual}")
    print(f"Mana Atual: {mana_atual}")
    print(f"Coordenadas: X: {pos_x} | Y: {pos_y} | Z: {pos_z}")
else:
    print("[-] Não foi possível mapear o endereço base do cliente.")