import os
import struct
import time
import sys

class TrackerDNA:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.candidates = {}
        self.mem_file = None
        
        self.target_addr = None
        self.target_dna = None # A assinatura VTable de 8 bytes

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

    def calibração_cinetica(self):
        """Usa a física apenas para a primeira descoberta."""
        print("\n\033[K[*] FASE 1: Calibração Cinética (Ande no jogo para extrair o DNA)...")
        self.candidates.clear()
        
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

    def extrair_dna(self):
        if not self.mem_file:
            self.mem_file = open(f"/proc/{self.pid}/mem", "rb")
            
        for addr, data in list(self.candidates.items()):
            try:
                self.mem_file.seek(addr)
                new_x, new_y, new_z = struct.unpack('<iii', self.mem_file.read(12))
                
                dx = abs(new_x - data['x'])
                dy = abs(new_y - data['y'])
                dz = abs(new_z - data['z'])
                
                if dz == 0 and dx <= 2 and dy <= 2 and (dx > 0 or dy > 0):
                    data['x'], data['y'] = new_x, new_y
                    data['steps'] += 1
                    
                    # Trava confirmada no 3º passo
                    if data['steps'] >= 3:
                        # Extrai os 8 bytes anteriores ao X (O VTable da Classe)
                        self.mem_file.seek(addr - 8)
                        dna_bytes = self.mem_file.read(8)
                        
                        self.target_addr = addr
                        self.target_dna = dna_bytes
                        return True
            except Exception:
                pass
                
        return False

    def busca_por_dna(self):
        """Se o endereço morrer, acha o novo endereço usando a assinatura em 0.1s."""
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue
                    
                    offset = 0
                    while True:
                        offset = dump.find(self.target_dna, offset)
                        if offset == -1: break
                        
                        coord_start = offset + 8
                        if coord_start + 12 <= len(dump):
                            x, y, z = struct.unpack('<iii', dump[coord_start:coord_start+12])
                            if 31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15:
                                self.target_addr = start + coord_start
                                return True
                        offset += 8
        except Exception:
            pass
        return False

    def monitor_continuo(self):
        """Monitoramento leve e direto."""
        try:
            self.mem_file.seek(self.target_addr)
            x, y, z = struct.unpack('<iii', self.mem_file.read(12))
            
            if not (31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15):
                raise ValueError("Corrupção")
                
            print(f"\r\033[K[Rastreio DNA] X: {x} | Y: {y} | Z: {z}  (Trava: {hex(self.target_addr)})", end="")
            
        except Exception:
            # Objeto destruído (Teleporte, Loading ou Garbage Collector)
            print(f"\r\033[K[!] Objeto perdido. Reconectando via DNA da Classe... ", end="")
            self.target_addr = None
            if not self.busca_por_dna():
                # Se o DNA sumiu completamente (muito raro), refazemos a matriz
                self.calibração_cinetica()

    def run(self):
        print("="*60)
        print(" 🧬 TRACKER DE DNA (VTABLE EXTRACTION) ")
        print("="*60)
        
        self.calibração_cinetica()
        
        while True:
            if not self.target_dna:
                if self.extrair_dna():
                    print("\n\n" + "="*60)
                    print(f" [🔥] DNA EXTRAÍDO! Assinatura: {self.target_dna.hex()}")
                    print(f" [🔥] FÍSICA DESLIGADA. MUDANDO PARA MONITORAMENTO ABSOLUTO.")
                    print("="*60 + "\n")
                else:
                    print(f"\r\033[K[AGUARDANDO] Calibrando... dê 3 passos no jogo.", end="")
                    time.sleep(0.1)
            else:
                self.monitor_continuo()
                time.sleep(0.01)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_tracker_dna.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    tracker = TrackerDNA(pid)
    
    if tracker.map_heap():
        try:
            tracker.run()
        except KeyboardInterrupt:
            print("\n\n[*] Tracker desligado.")