import os
import struct
import time
import sys

class RadarCore:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.candidates = {}
        self.locked_address = None
        self.mem_file = None
        self.steps_required_for_lock = 3  # Grau de confiança matemática para travar o alvo

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

    def initial_scan(self):
        print("\n[*] FASE 1: Calibração Espacial...")
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
            print(f"[+] Snapshot construído. Caminhe no jogo para calibrar o motor físico.")
        except Exception as e:
            print(f"[!] Erro no mapeamento inicial: {e}")

    def track_and_lock(self):
        if not self.mem_file:
            self.mem_file = open(f"/proc/{self.pid}/mem", "rb")
            
        survivors = {}
        
        for addr, data in self.candidates.items():
            try:
                self.mem_file.seek(addr)
                new_x, new_y, new_z = struct.unpack('<iii', self.mem_file.read(12))
                
                dx = abs(new_x - data['x'])
                dy = abs(new_y - data['y'])
                dz = abs(new_z - data['z'])
                
                # Permanece estático (Não ganha pontos, mas sobrevive no radar temporal)
                if dx == 0 and dy == 0 and dz == 0:
                    survivors[addr] = data
                    continue
                    
                # Física válida de caminhada (Delta)
                if dz == 0 and dx <= 2 and dy <= 2:
                    data['x'] = new_x
                    data['y'] = new_y
                    data['steps'] += 1
                    survivors[addr] = data
                    
                    # Condição de Trava (Target Lock)
                    if data['steps'] >= self.steps_required_for_lock:
                        self.locked_address = addr
                        return True # Trava ativada
            except Exception:
                pass
                
        self.candidates = survivors
        return False # Continua buscando

    def stream_locked_coordinates(self):
        """Leitura direta ultra-rápida sem varredura, ativada após o Target Lock."""
        try:
            self.mem_file.seek(self.locked_address)
            x, y, z = struct.unpack('<iii', self.mem_file.read(12))
            
            # Valida se o objeto não foi destruído (Ex: troca de andar / loading screen)
            if not (31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15):
                raise ValueError("Coordenada fora da geometria.")
                
            print(f"\r[TARGET LOCKED] -> X: {x} | Y: {y} | Z: {z}      ", end="")
            
        except Exception:
            # Se a memória morrer, limpa a trava e recomeça a calibração
            print("\n[!] Alvo perdido na RAM. Reiniciando calibração espacial...")
            self.locked_address = None
            self.candidates.clear()
            self.heap_regions.clear()
            self.map_heap()
            self.initial_scan()

    def run(self):
        print("="*60)
        print(" 🛰️ CORE DE NAVEGAÇÃO AUTÔNOMA ")
        print("="*60)
        
        self.initial_scan()
        
        while True:
            if not self.locked_address:
                # FASE DE BUSCA: Analisa o Delta de dezenas de milhares de entidades
                locked = self.track_and_lock()
                if not locked:
                    time.sleep(0.1)
                else:
                    print("\n\n" + "="*60)
                    print(f" [🔥] ASSINATURA FÍSICA TRAVADA EM: {hex(self.locked_address)}")
                    print(f" [🔥] VARREDURA DESLIGADA. INICIANDO TELEMETRIA 100Hz.")
                    print("="*60 + "\n")
            else:
                # FASE DE LEITURA: Lê apenas 12 bytes diretos no alvo confirmado
                self.stream_locked_coordinates()
                time.sleep(0.01) # Taxa de atualização extremamente alta para o Cavebot

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_radar_core.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    core = RadarCore(pid)
    
    if core.map_heap():
        try:
            core.run()
        except KeyboardInterrupt:
            print("\n\n[*] Motor de navegação desligado.")