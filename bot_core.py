import os
import struct
import time

class TibiaMemoryReader:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.candidates = []
        
    def find_heap_regions(self):
        try:
            with open(f"/proc/{self.pid}/maps", "r") as maps:
                for line in maps:
                    if "rw-p" in line:
                        parts = line.split()[0].split('-')
                        self.heap_regions.append((int(parts[0], 16), int(parts[1], 16)))
            return True
        except PermissionError:
            print("[!] Execute como root.")
            return False

    def scan_neighborhood(self, hp_atual, mana_atual):
        mana_bytes = struct.pack('<i', mana_atual)
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue 
                    
                    offset = 0
                    while True:
                        offset = dump.find(mana_bytes, offset)
                        if offset == -1: break 
                        
                        # Define a janela: 16 bytes ANTES da mana e 16 bytes DEPOIS
                        start_read = offset - 16
                        if start_read >= 0 and offset + 16 <= len(dump):
                            chunk = dump[start_read : offset + 16]
                            ints = struct.unpack('<iiiiiiii', chunk)
                            
                            # Se a Vida que você digitou estiver em qualquer lugar dessa vizinhança, fisgamos o bloco!
                            if hp_atual in ints:
                                self.candidates.append(start + start_read)
                        offset += 4 
            return len(self.candidates) > 0
        except Exception as e:
            print(f"[!] Erro no scanner: {e}")
        return False

    def poll_neighborhood(self):
        results = []
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for addr in self.candidates:
                    mem.seek(addr)
                    # Lê as 8 variáveis da vizinhança
                    ints = struct.unpack('<iiiiiiii', mem.read(32))
                    results.append(ints)
        except Exception:
            pass
        return results

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_core.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    reader = TibiaMemoryReader(pid)
    
    print("="*60)
    print(" SCANNER DE VIZINHANÇA (Isolamento de HP Dinâmico)")
    print("="*60)
    
    try:
        hp = int(input("Digite seu HP ATUAL (não pode estar cheio!): "))
        mana = int(input("Digite sua MANA ATUAL: "))
    except ValueError:
        sys.exit(1)
        
    if reader.find_heap_regions():
        if reader.scan_neighborhood(hp, mana):
            print(f"\n[+] {len(reader.candidates)} blocos encontrados!")
            print("Tome dano no jogo e veja qual 'V' muda. (Ctrl+C para sair)")
            print("-" * 75)
            try:
                while True:
                    stats = reader.poll_neighborhood()
                    if stats:
                        # Pega o primeiro candidato válido e imprime as 8 variáveis
                        v = stats[0] 
                        out = f"\r[V1]:{v[0]:<4} [V2]:{v[1]:<4} [V3]:{v[2]:<4} [V4]:{v[3]:<4} | [V5]:{v[4]:<4} [V6]:{v[5]:<4} [V7]:{v[6]:<4} [V8]:{v[7]:<4}"
                        print(out + " "*5, end="")
                    time.sleep(0.05)
            except KeyboardInterrupt:
                print("\nEncerrando.")
        else:
            print("\n[-] Nada encontrado. Tente de novo (cuidado com a regeneração da mana!).")