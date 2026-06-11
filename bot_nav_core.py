import os
import struct
import time
import sys

class NavigationCore:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.candidates = {}
        self.locked_address = None
        self.mem_file = None
        self.steps_to_lock = 5  # Quantos passos para confirmar a identidade

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

    def hunt_phase(self):
        """Mapeia a matriz e usa a física de movimento para isolar o jogador."""
        if not self.candidates:
            print("\n[*] FASE DE CAÇA: Levantando matriz espacial...")
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    for start, end in self.heap_regions:
                        mem.seek(start)
                        try: dump = mem.read(end - start)
                        except OSError: continue
                        
                        for offset in range(0, len(dump) - 12, 4):
                            x, y, z = struct.unpack_from('<iii', dump, offset)
                            if 31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15:
                                self.candidates[start + offset] = {'x': x, 'y': y, 'z': z, 'steps': 0}
            except Exception:
                pass
            print("[+] Matriz capturada. DÊ ALGUNS PASSOS para travar o alvo.")
            return

        # Filtro de Movimento (Delta)
        if not self.mem_file:
            self.mem_file = open(f"/proc/{self.pid}/mem", "rb")
            
        survivors = {}
        for addr, data in self.candidates.items():
            try:
                self.mem_file.seek(addr)
                nx, ny, nz = struct.unpack('<iii', self.mem_file.read(12))
                
                dx, dy, dz = abs(nx - data['x']), abs(ny - data['y']), abs(nz - data['z'])
                
                if dx == 0 and dy == 0 and dz == 0:
                    survivors[addr] = data
                    continue
                    
                if dz == 0 and dx <= 2 and dy <= 2:
                    data['x'], data['y'] = nx, ny
                    data['steps'] += 1
                    survivors[addr] = data
                    
                    # SE CONFIRMAR IDENTIDADE, TRAVA O ALVO E ABORTA A CAÇA
                    if data['steps'] >= self.steps_to_lock:
                        self.locked_address = addr
                        self.candidates.clear()
                        print("\n" + "="*60)
                        print(f" [🔥] TARGET LOCKED: {hex(addr)}")
                        print(f" [🔥] MOTOR FÍSICO DESLIGADO. INICIANDO TELEMETRIA BLINDADA.")
                        print("="*60 + "\n")
                        return
            except Exception:
                pass
        self.candidates = survivors

    def lock_phase(self):
        """Lê o endereço absoluto sem checar distâncias. Imune a teleportes."""
        try:
            self.mem_file.seek(self.locked_address)
            x, y, z = struct.unpack('<iii', self.mem_file.read(12))
            
            # Sanity Check: O objeto ainda é uma coordenada válida do Tibia?
            if 31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15:
                print(f"\r[TELEMETRIA] X: {x} | Y: {y} | Z: {z}    \033[K", end="")
            else:
                raise ValueError("Out of bounds")
        except Exception:
            # Se o endereço for liberado pela RAM (Logout/Crash), a trava quebra.
            print("\n[!] Conexão com objeto perdida. Reiniciando matriz de caça...")
            self.locked_address = None

    def run(self):
        print("="*60)
        print(" 🧭 MOTOR DE NAVEGAÇÃO HÍBRIDO (CAÇA E TRAVA) ")
        print("="*60)
        
        while True:
            if not self.locked_address:
                self.hunt_phase()
                time.sleep(0.05)
            else:
                self.lock_phase()
                time.sleep(0.02) # Leitura de 50Hz (ultrarrápida)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_nav_core.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    nav = NavigationCore(pid)
    
    if nav.map_heap():
        try:
            nav.run()
        except KeyboardInterrupt:
            print("\n\n[*] Sistema encerrado.")