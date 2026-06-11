import os
import struct
import time
import sys

class SurvivorInspector:
    def __init__(self, pid, addresses):
        self.pid = pid
        self.addresses = addresses
        self.mem_file = None

    def inspect(self):
        if not self.mem_file:
            try:
                self.mem_file = open(f"/proc/{self.pid}/mem", "rb")
            except PermissionError:
                print("[!] Execute como root (sudo).")
                sys.exit(1)

        print("\033[H\033[J") # Limpa o terminal
        print("="*65)
        print(" INSPETOR DE ESTRUTURAS VITAIS (TEMPO REAL)")
        print("="*65)
        print("Vá para o jogo, gaste mana e veja qual bloco possui a Mana Atual.\n")

        for addr in self.addresses:
            try:
                self.mem_file.seek(addr)
                # Lemos 16 bytes a partir do endereço do HP (4 inteiros de 32 bits)
                v1, v2, v3, v4 = struct.unpack('<iiii', self.mem_file.read(16))
                
                prefix = hex(addr)[:4]
                suffix = hex(addr)[-6:]
                short_addr = f"{prefix}..{suffix}"
                
                print(f"[{short_addr}] -> [+0x0]: {v1:<4} | [+0x4]: {v2:<4} | [+0x8]: {v3:<4} | [+0xC]: {v4:<4}")
            except Exception:
                print(f"[{hex(addr)}] -> [ BLOCO INACESSÍVEL OU DESTRUÍDO ]")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_inspector.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    
    # Os 5 endereços persistentes que isolamos
    TARGETS = [
        0x7f6b7c67e400,
        0x56453c1906a8,
        0x7f6c00fbf170,
        0x7f6b7c693378,
        0x564541051c78
    ]
    
    inspector = SurvivorInspector(pid, TARGETS)
    
    try:
        while True:
            inspector.inspect()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[*] Inspeção encerrada.")