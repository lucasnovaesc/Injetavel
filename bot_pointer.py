import struct
import sys

class PointerScanner:
    def __init__(self, pid):
        self.pid = pid
        self.client_base = 0
        self.client_data_regions = []
        self.heap_regions = []
        
    def map_memory(self):
        try:
            with open(f"/proc/{self.pid}/maps", "r") as maps:
                for line in maps:
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    
                    start, end = [int(x, 16) for x in parts[0].split('-')]
                    perms = parts[1]
                    
                    # Verificação robusta: olha a linha inteira, não a string fragmentada
                    if "bin/client" in line:
                        # Captura o menor endereço possível como Base do Cliente (Cabeçalho ELF)
                        if self.client_base == 0 or start < self.client_base:
                            self.client_base = start
                            
                        # Regiões estáticas globais (.data / .bss)
                        if "rw-p" in perms:
                            self.client_data_regions.append((start, end))
                            
                    # Regiões de Heap e anônimas dinâmicas
                    elif "heap" in line or ("rw-p" in perms and "bin/client" not in line):
                        self.heap_regions.append((start, end))
            
            if self.client_base == 0:
                print("[-] Falha crítica: O binário bin/client não foi encontrado no mapa de memória.")
                return False
                
            return True
        except PermissionError:
            print("[!] Execute como root (sudo).")
            return False

    def scan_for_pointer(self, target_value, regions):
        """Procura na memória por um ponteiro de 64-bits (8 bytes) que aponte para target_value."""
        target_bytes = struct.pack('<Q', target_value)
        results = []
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue
                    
                    offset = 0
                    while True:
                        offset = dump.find(target_bytes, offset)
                        if offset == -1: break
                        results.append(start + offset)
                        offset += 8
        except Exception as e:
            print(f"Erro: {e}")
        return results

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: sudo python3 bot_pointer.py [PID] [HUD_BASE_ADDRESS_EM_HEX]")
        print("Exemplo: sudo python3 bot_pointer.py 41199 0x559a65371800")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    hud_base = int(sys.argv[2], 16) # O Endereço Base que descobrimos nos testes anteriores
    
    scanner = PointerScanner(pid)
    if not scanner.map_memory():
        sys.exit(1)
        
    print(f"[*] Base do Cliente: {hex(scanner.client_base)}")
    print(f"[*] HUD Base Alvo: {hex(hud_base)}")
    print("-" * 50)
    
    print("[1] Varrendo a Heap buscando a estrutura GameClient...")
    # O Ghidra diz que [GameClient + 0x3A8] = HUD_Base
    game_client_pointers = scanner.scan_for_pointer(hud_base, scanner.heap_regions)
    
    if not game_client_pointers:
        print("[-] Não encontramos quem aponta para o HUD. O endereço HUD Base mudou? (Você relogou?)")
        sys.exit(1)
        
    for ptr in game_client_pointers:
        # Se ptr é GameClient + 0x3A8, então:
        game_client_addr = ptr - 0x3a8
        print(f"    [+] Possível GameClient instanciado em: {hex(game_client_addr)}")
        
        print("[2] Varrendo a seção de dados do binário (.data/.bss) em busca do Ponteiro Global...")
        # Agora buscamos quem na área estática do jogo aponta para o GameClient
        global_pointers = scanner.scan_for_pointer(game_client_addr, scanner.client_data_regions)
        
        for g_ptr in global_pointers:
            # Subtraímos a base para ter o offset imutável (O nosso DAT_ !)
            static_offset = g_ptr - scanner.client_base
            print("\n" + "=" * 50)
            print("🎉 CADEIA DE PONTEIROS DEFINITIVA ENCONTRADA 🎉")
            print("=" * 50)
            print("Para ler a Vida Atual no nível 1 ou no nível 1000, o caminho é:")
            print(f"Base do Jogo (`client`)")
            print(f"  + 0x{static_offset:X} (Ponteiro Estático Global)")
            print(f"    + 0x3A8 (Offset da interface do Jogador)")
            print(f"      + 0x78 (Vida Atual)")
            print("=" * 50 + "\n")
            sys.exit(0)
            
    print("\n[-] Nenhum ponteiro estático conectou à base. A estrutura pode estar dentro de um Singleton aninhado.")