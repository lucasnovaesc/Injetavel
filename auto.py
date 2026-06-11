import os
import struct
import time
import sys

class TibiaAutoHook:
    def __init__(self, pid, max_hp, max_mana):
        self.pid = pid
        self.max_hp = max_hp
        self.max_mana = max_mana
        self.heap_regions = []
        self.target_address = 0
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

    def auto_scan(self):
        print(f"[*] Buscando estrutura com MaxHP={self.max_hp} e MaxMana={self.max_mana}...")
        
        # Empacotamos apenas as partes vitais. Int32 ocupa 4 bytes.
        # Estrutura: [HP Atual (4b)] [HP Máx (4b)] [Mana Atual (4b)] [Mana Máx (4b)]
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue 
                    
                    # Varre a região pulando de 4 em 4 bytes para manter o alinhamento de memória
                    for offset in range(0, len(dump) - 16, 4):
                        v1, v2, v3, v4 = struct.unpack('<iiii', dump[offset:offset+16])
                        
                        # Filtro de Validação Lógica
                        if v2 == self.max_hp and v4 == self.max_mana:
                            # Filtro de Sanidade (Os valores atuais não podem ser bizarros ou negativos)
                            if 0 <= v1 <= self.max_hp and 0 <= v3 <= self.max_mana:
                                self.target_address = start + offset
                                print(f"[+] Estrutura validada e fisgada no endereço: {hex(self.target_address)}")
                                return True
        except Exception as e:
            print(f"[!] Falha na varredura: {e}")
            
        print("[-] Nenhuma estrutura correspondente encontrada.")
        return False

    def monitor(self):
        if not self.mem_file:
            self.mem_file = open(f"/proc/{self.pid}/mem", "rb")
            
        try:
            self.mem_file.seek(self.target_address)
            hp, max_hp, mana, max_mana = struct.unpack('<iiii', self.mem_file.read(16))
            print(f"\r[STATUS] Vida: {hp:>4}/{max_hp:<4} | Mana: {mana:>4}/{max_mana:<4}    ", end="")
        except Exception:
            # Caso o endereço morra (jogo fechou ou objeto foi destruído)
            pass

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_auto.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    
    # === CONFIGURAÇÃO DO PERSONAGEM ===
    # Atualize estes valores sempre que passar de nível ou mudar itens que afetem HP/Mana totais
    MEU_MAX_HP = 260
    MEU_MAX_MANA = 115
    # ==================================
    
    bot = TibiaAutoHook(pid, MEU_MAX_HP, MEU_MAX_MANA)
    
    if bot.map_heap() and bot.auto_scan():
        print("[*] Hook estabelecido. Iniciando telemetria (Ctrl+C para sair):\n")
        try:
            while True:
                bot.monitor()
                time.sleep(0.1) # Taxa de atualização (100ms) - Leve e suficiente para curas
        except KeyboardInterrupt:
            print("\n\n[*] Operação encerrada.")