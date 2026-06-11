import os
import struct
import sys

class TibiaIdentityScanner:
    def __init__(self, pid, char_name, max_hp, max_mana):
        self.pid = pid
        self.char_name = char_name.encode('utf-8')
        self.max_hp = max_hp
        self.max_mana = max_mana
        self.heap_regions = []
        
    def map_heap(self):
        try:
            with open(f"/proc/{self.pid}/maps", "r") as maps:
                for line in maps:
                    parts = line.split()
                    if len(parts) < 5: continue
                    if "rw-p" in parts[1] and "bin/client" not in line:
                        start, end = [int(x, 16) for x in parts[0].split('-')]
                        self.heap_regions.append((start, end))
            return True
        except PermissionError:
            print("[!] Execute como root (sudo).")
            return False

    def scan_and_map_structure(self):
        print(f"[*] Varrendo a Heap buscando a assinatura: '{self.char_name.decode()}'...")
        found_count = 0
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue

                    offset = 0
                    while True:
                        offset = dump.find(self.char_name, offset)
                        if offset == -1: break
                        
                        found_count += 1
                        name_addr = start + offset
                        
                        # Capturamos uma janela larga: 500 bytes antes e 500 bytes depois do nome
                        window_start = max(0, offset - 500)
                        window_end = min(len(dump), offset + 500)
                        window_data = dump[window_start:window_end]
                        
                        # Empacota os valores que estamos buscando (Max HP e Max Mana)
                        hp_bytes = struct.pack('<i', self.max_hp)
                        mana_bytes = struct.pack('<i', self.max_mana)
                        
                        hp_local = window_data.find(hp_bytes)
                        mana_local = window_data.find(mana_bytes)
                        
                        print(f"\n[+] Nome encontrado no endereço: {hex(name_addr)}")
                        
                        if hp_local != -1 and mana_local != -1:
                            real_hp_addr = start + window_start + hp_local
                            real_mana_addr = start + window_start + mana_local
                            
                            dist_hp = real_hp_addr - name_addr
                            dist_mana = real_mana_addr - name_addr
                            
                            print("    [!] Atributos vitais localizados na vizinhança do nome!")
                            print(f"    -> Endereço do Max HP: {hex(real_hp_addr)} (Offset do Nome: {dist_hp:+d} bytes)")
                            print(f"    -> Endereço da Max Mana: {hex(real_mana_addr)} (Offset do Nome: {dist_mana:+d} bytes)")
                        else:
                            print("    [-] Atributos vitais (260/115) não encontrados próximos a este espelho.")
                            
                        offset += len(self.char_name)
                        
            print(f"\n[*] Total de espelhos do nome encontrados: {found_count}")
        except Exception as e:
            print(f"[!] Erro no scanner: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_identity.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    
    # Constantes já definidas
    NOME = "Vegano chines"
    VIDA_MAX = 260
    MANA_MAX = 115
    
    scanner = TibiaIdentityScanner(pid, NOME, VIDA_MAX, MANA_MAX)
    if scanner.map_heap():
        scanner.scan_and_map_structure()