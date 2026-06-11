import os
import struct
import time
import sys

class TibiaNeighborhoodScanner:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.candidates = []
        
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

    def scan_for_mana_neighborhood(self, mana_atual, hp_esperado):
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
                        
                        # Isolamos um bloco de 32 bytes (16 antes e 16 depois da Mana)
                        start_read = offset - 16
                        if start_read >= 0 and offset + 16 <= len(dump):
                            chunk = dump[start_read : offset + 16]
                            ints = struct.unpack('<iiiiiiii', chunk)
                            
                            # Se a Vida que você digitou estiver rondando essa Mana, fisgamos o bloco!
                            if hp_esperado in ints:
                                self.candidates.append(start + start_read)
                        offset += 4 
            return len(self.candidates) > 0
        except Exception as e:
            print(f"[!] Erro no scanner: {e}")
        return False

    def poll_matrix(self):
        results = []
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for addr in self.candidates:
                    mem.seek(addr)
                    ints = struct.unpack('<iiiiiiii', mem.read(32))
                    results.append(ints)
        except Exception:
            pass
        return results

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_neighborhood.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    scanner = TibiaNeighborhoodScanner(pid)
    
    print("="*65)
    print(" MOTOR DE VIZINHANÇA (ANCORADO NA MANA)")
    print("="*65)
    
    try:
        hp = int(input("Digite seu HP ATUAL (Quebrado, não cheio): "))
        mana = int(input("Digite sua MANA ATUAL (Quebrada, não cheia): "))
    except ValueError:
        sys.exit(1)
        
    if scanner.map_heap():
        if scanner.scan_for_mana_neighborhood(mana, hp):
            print(f"\n[+] {len(scanner.candidates)} candidatos encontrados.")
            print("Vá ao jogo e TOME DANO. Olhe a matriz abaixo e veja qual coluna (V1 a V8) cai junto com seu hit.")
            print("-" * 80)
            try:
                while True:
                    stats = scanner.poll_matrix()
                    if stats:
                        # Pega o primeiro candidato e exibe as 8 variáveis em linha
                        v = stats[0] 
                        out = f"\r[V1]:{v[0]:<4} [V2]:{v[1]:<4} [V3]:{v[2]:<4} [V4]:{v[3]:<4} | [V5]:{v[4]:<4} [V6]:{v[5]:<4} [V7]:{v[6]:<4} [V8]:{v[7]:<4}"
                        print(out + " "*5, end="")
                    time.sleep(0.05)
            except KeyboardInterrupt:
                print("\nEncerrando.")
        else:
            print("\n[-] Estrutura não encontrada. A mana pode ter regenerado enquanto você digitava. Tente novamente.")