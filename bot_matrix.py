import os
import struct
import time
import sys

class TibiaMatrix:
    def __init__(self, pid, max_hp, max_mana):
        self.pid = pid
        self.max_hp = max_hp
        self.max_mana = max_mana
        self.heap_regions = []
        self.candidates = []
        self.mem_file = None

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

    def scan_matrix(self):
        print(f"[*] Varrendo a Heap procurando assinaturas MaxHP={self.max_hp} / MaxMana={self.max_mana}...")
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue

                    for offset in range(0, len(dump) - 16, 4):
                        v1, v2, v3, v4 = struct.unpack('<iiii', dump[offset:offset+16])
                        if v2 == self.max_hp and v4 == self.max_mana and v1 > 0 and v3 > 0 and v1 <= v2 and v3 <= v4:
                            self.candidates.append(start + offset)
            
            print(f"[+] {len(self.candidates)} blocos encontrados na memória.")
            return len(self.candidates) > 0
        except Exception as e:
            print(f"[!] Erro crítico de leitura: {e}")
            return False

    def poll_matrix(self):
        if not self.mem_file:
            self.mem_file = open(f"/proc/{self.pid}/mem", "rb")
        
        results = []
        for addr in self.candidates:
            try:
                self.mem_file.seek(addr)
                hp, _, mana, _ = struct.unpack('<iiii', self.mem_file.read(16))
                # Pegamos apenas os últimos 4 caracteres do endereço hexadecimal para caber na tela
                short_addr = hex(addr)[-4:]
                results.append(f"[{short_addr}] H:{hp:<3} M:{mana:<3}")
            except Exception:
                results.append(f"[{hex(addr)[-4:]}] MORT")
        
        # Imprime todos os resultados na mesma linha, atualizando constantemente
        print("\r" + " | ".join(results) + " "*10, end="")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_matrix.py [PID]")
        sys.exit(1)

    pid = int(sys.argv[1])
    
    # --- SUAS CONSTANTES ---
    MAX_HP = 260
    MAX_MANA = 115
    # -----------------------

    matrix = TibiaMatrix(pid, MAX_HP, MAX_MANA)

    if matrix.map_heap() and matrix.scan_matrix():
        print("\nMonitoramento em Matriz Ativo. (Ctrl+C para sair)")
        print("Vá para o jogo e ALTERE sua vida/mana. Apenas UM desses blocos continuará atualizando.")
        print("-" * 80)
        try:
            while True:
                matrix.poll_matrix()
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("\n\n[*] Script encerrado.")