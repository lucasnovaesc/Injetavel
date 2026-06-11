import os
import struct
import sys

class DeepPointerScanner:
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
                    if len(parts) < 5: continue
                    
                    start, end = [int(x, 16) for x in parts[0].split('-')]
                    perms = parts[1]
                    
                    if "bin/client" in line:
                        if self.client_base == 0 or start < self.client_base:
                            self.client_base = start
                        if "rw-p" in perms:
                            self.client_data_regions.append((start, end))
                    elif "heap" in line or ("rw-p" in perms and "bin/client" not in line):
                        self.heap_regions.append((start, end))
            return self.client_base != 0
        except PermissionError:
            print("[!] Execute como root.")
            return False

    def scan_for_value(self, target_value, regions):
        """Varre regiões específicas buscando por um endereço de 64-bits."""
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
        except Exception:
            pass
        return results

    def recursive_scan(self, target_addr, current_path, current_depth, max_depth):
        """Busca recursivamente até atingir a seção estática (.data) do jogo."""
        # Se acharmos o ponteiro na seção estática (.data), NÓS VENCEMOS!
        static_matches = self.scan_for_value(target_addr, self.client_data_regions)
        for static_ptr in static_matches:
            offset = static_ptr - self.client_base
            print("\n" + "🔥"*25)
            print(" CADEIA DE PONTEIROS ABSOLUTA ENCONTRADA!")
            print("🔥"*25)
            print(f"[*] Base do bin/client (client_base)")
            print(f" [+] Offset Global : 0x{offset:X}")
            
            # Imprime o caminho reverso
            for i, step_offset in enumerate(reversed(current_path)):
                print(f"  [+] Nível {i+1} Offset: 0x{step_offset:X}")
            print(f"   [+] Offset Final: 0x78 (HP Atual)")
            print("-" * 50 + "\n")
            sys.exit(0) # Encerra ao achar a primeira rota válida

        # Limite de segurança para não explodir a memória
        if current_depth >= max_depth:
            return

        # Se não achou na estática, busca na Heap e entra mais fundo no buraco do coelho
        heap_matches = self.scan_for_value(target_addr, self.heap_regions)
        for heap_ptr in heap_matches:
            # Assumimos que o ponteiro estava no início de uma estrutura (Offset 0x0)
            # ou calculamos o offset se soubermos (no nosso caso, o primeiro foi 0x3A8)
            offset_usado = 0x3A8 if current_depth == 0 else 0x0 
            
            base_of_this_struct = heap_ptr - offset_usado
            new_path = current_path + [offset_usado]
            
            print(f"  [Profundidade {current_depth+1}] Rastreado até Heap: {hex(base_of_this_struct)}...")
            self.recursive_scan(base_of_this_struct, new_path, current_depth + 1, max_depth)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: sudo python3 bot_deep_pointer.py [PID] [ENDERECO_DA_VIDA_HEX]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    target_hud = int(sys.argv[2], 16)
    
    scanner = DeepPointerScanner(pid)
    if not scanner.map_memory():
        sys.exit(1)
        
    print(f"[*] Escaneamento de Profundidade Iniciado.")
    print(f"[*] Alvo Inicial (HUD Base): {hex(target_hud)}")
    print(f"[*] Base do Cliente: {hex(scanner.client_base)}\n")
    
    # Inicia a recursão limitando a 3 níveis de profundidade (Padrão para Qt)
    scanner.recursive_scan(target_hud, [], 0, max_depth=3)
    
    print("\n[-] Varredura concluída. Se nenhuma cadeia foi impressa, o nível de profundidade é maior que 3.")