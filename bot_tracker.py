import os
import struct
import time

class TibiaAutoTracker:
    def __init__(self, pid, max_hp, max_mana):
        self.pid = pid
        self.max_hp = max_hp
        self.max_mana = max_mana
        self.heap_regions = []
        self.candidates = {}  # Guarda no formato: {endereco: (ultimo_hp, ultima_mana)}
        self.real_address = 0
        self.mem_file = None

    def map_heap(self):
        """Mapeia apenas as áreas dinâmicas onde o jogo aloca instâncias."""
        try:
            with open(f"/proc/{self.pid}/maps", "r") as maps:
                for line in maps:
                    parts = line.split()
                    if len(parts) < 5: continue
                    
                    # Filtra apenas regiões legíveis/graváveis (Heap e mmap anon)
                    if "rw-p" in parts[1] and "bin/client" not in line:
                        start, end = [int(x, 16) for x in parts[0].split('-')]
                        self.heap_regions.append((start, end))
            return True
        except PermissionError:
            print("[!] Execute como root (sudo).")
            return False

    def find_candidates(self):
        """Busca todas as estruturas que batem com a Vida Máxima e Mana Máxima."""
        print(f"[*] Varrendo a memória por blocos com MaxHP={self.max_hp} e MaxMana={self.max_mana}...")
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue

                    for offset in range(0, len(dump) - 16, 4):
                        v1, v2, v3, v4 = struct.unpack('<iiii', dump[offset:offset+16])
                        
                        # Filtro de Sanidade: Os máximos devem bater, e os atuais não podem ser maiores que os máximos
                        if v2 == self.max_hp and v4 == self.max_mana and v1 > 0 and v3 > 0 and v1 <= v2 and v3 <= v4:
                            addr = start + offset
                            self.candidates[addr] = (v1, v3) # Salva o estado atual (HP, Mana)
            
            print(f"[+] {len(self.candidates)} blocos encontrados (Objeto Vivo + Fantasmas).")
            return len(self.candidates) > 0
        except Exception as e:
            print(f"[!] Erro no scanner: {e}")
            return False

    def calibrate_and_lock(self):
        """Monitora todos os candidatos e aguarda uma mudança de estado (Delta)."""
        if not self.mem_file:
            self.mem_file = open(f"/proc/{self.pid}/mem", "rb")

        print("\n" + "="*60)
        print(" 🎯 CALIBRAÇÃO ATIVA: VÁ PARA O JOGO E MUDE SUA VIDA OU MANA 🎯")
        print(" O script detectará matematicamente qual objeto está vivo...")
        print("="*60)

        # Loop de polling ultrarrápido
        while not self.real_address:
            for addr, (last_hp, last_mana) in list(self.candidates.items()):
                try:
                    self.mem_file.seek(addr)
                    hp, max_hp, mana, max_mana = struct.unpack('<iiii', self.mem_file.read(16))

                    # A mágica: Se o HP ou a Mana desse endereço for diferente do que lemos há 2 segundos atrás...
                    if hp != last_hp or mana != last_mana:
                        self.real_address = addr
                        print(f"\n[🚀] ALVO CONFIRMADO! Objeto real isolado em: {hex(addr)}")
                        return True
                except Exception:
                    pass
            time.sleep(0.05) # Previne uso excessivo de CPU

    def stream_vitals(self):
        """Imprime os atributos do objeto real travado."""
        try:
            self.mem_file.seek(self.real_address)
            hp, max_hp, mana, max_mana = struct.unpack('<iiii', self.mem_file.read(16))
            print(f"\r[STATUS] HP: {hp}/{max_hp} | Mana: {mana}/{max_mana}        ", end="")
        except Exception:
            pass

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_tracker.py [PID]")
        sys.exit(1)

    pid = int(sys.argv[1])
    
    # --- INSIRA SUAS CONSTANTES ESTÁTICAS AQUI ---
    MAX_HP = 260
    MAX_MANA = 115
    # ---------------------------------------------

    tracker = TibiaAutoTracker(pid, MAX_HP, MAX_MANA)

    if tracker.map_heap() and tracker.find_candidates():
        if tracker.calibrate_and_lock():
            print("\n[*] Iniciando streaming contínuo. Imune a fantasmas e ASLR. (Ctrl+C para sair)")
            try:
                while True:
                    tracker.stream_vitals()
                    time.sleep(0.1) # Lê 10 vezes por segundo
            except KeyboardInterrupt:
                print("\n[*] Script encerrado com sucesso.")