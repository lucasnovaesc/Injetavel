import os
import struct
import time
import sys

class DynamicTrackerV2:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.candidates = {}
        self.mem_file = None
        self.champion_addr = None

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
        print("\n\033[K[*] Recalibrando matriz espacial (Snapshot)... ", end="")
        self.candidates.clear()
        self.champion_addr = None
        
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
            print(f"[{len(self.candidates)} vetores]")
        except Exception:
            print("[Falha]")

    def track_and_elect(self):
        if not self.mem_file:
            self.mem_file = open(f"/proc/{self.pid}/mem", "rb")
            
        survivors = {}
        campeao_morto = False
        
        for addr, data in self.candidates.items():
            try:
                self.mem_file.seek(addr)
                new_x, new_y, new_z = struct.unpack('<iii', self.mem_file.read(12))
                
                # Validação de corrupção de memória (Objeto destruído pelo Garbage Collector)
                if not (31000 < new_x < 34000 and 31000 < new_y < 34000 and 0 <= new_z <= 15):
                    if addr == self.champion_addr:
                        campeao_morto = True
                    continue # Descarta o endereço corrompido

                dx = abs(new_x - data['x'])
                dy = abs(new_y - data['y'])
                dz = abs(new_z - data['z'])
                
                if dx == 0 and dy == 0 and dz == 0:
                    survivors[addr] = data
                    continue
                    
                # Movimento contínuo válido
                if dz == 0 and dx <= 2 and dy <= 2:
                    data['x'] = new_x
                    data['y'] = new_y
                    data['steps'] += 1
                    survivors[addr] = data
                # Tratamento de Teleporte para o Campeão
                elif addr == self.champion_addr and (dx > 2 or dy > 2 or dz != 0):
                    data['x'] = new_x
                    data['y'] = new_y
                    data['z'] = new_z
                    # Penalizamos os passos para que ele prove que ainda é válido, mas não o descartamos
                    data['steps'] = max(1, data['steps'] // 2) 
                    survivors[addr] = data
                else:
                    pass # Movimento bizarro em objeto não-campeão é descartado
            except Exception:
                if addr == self.champion_addr:
                    campeao_morto = True
                
        self.candidates = survivors
        
        # Se o campeão sofreu Wipe na memória (entrou em teleporte e o Qt destruiu a classe)
        if campeao_morto:
            return "REBOOT", None

        # Eleição protegida (Trava Geográfica)
        ativos = {k: v for k, v in self.candidates.items() if v['steps'] > 0}
        if ativos:
            novo_campeao = max(ativos, key=lambda k: ativos[k]['steps'])
            
            # Só aceita a troca de campeão se o novo estiver encostado fisicamente no antigo
            # Isso impede que a Câmera ou o Minimapa roubem a coroa
            if self.champion_addr and self.champion_addr in ativos and novo_campeao != self.champion_addr:
                c_atual = ativos[self.champion_addr]
                c_novo = ativos[novo_campeao]
                dist_x = abs(c_novo['x'] - c_atual['x'])
                dist_y = abs(c_novo['y'] - c_atual['y'])
                
                if dist_x > 2 or dist_y > 2:
                    novo_campeao = self.champion_addr # Veto: Usurpador muito distante
            
            self.champion_addr = novo_campeao
            return novo_campeao, ativos[novo_campeao]
            
        return None, None

    def run(self):
        print("="*60)
        print(" 🛰️ TRACKER DINÂMICO V2 (ANTI-GHOST & TELEPORT AWARE) ")
        print("="*60)
        
        self.initial_scan()
        
        while True:
            addr, data = self.track_and_elect()
            
            if addr == "REBOOT":
                print(f"\r\033[K[!] Teleporte drástico ou Loading Screen detectado. Rebootando matriz...")
                self.map_heap()
                self.initial_scan()
                continue
                
            if addr and data['steps'] >= 2:
                print(f"\r\033[K[LOCALPLAYER] X: {data['x']} | Y: {data['y']} | Z: {data['z']} (Confiança: {data['steps']})", end="")
            else:
                print(f"\r\033[K[AGUARDANDO] Calibrando... dê alguns passos no jogo.", end="")
                
            time.sleep(0.05)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_tracker_dyn.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    tracker = DynamicTrackerV2(pid)
    
    if tracker.map_heap():
        try:
            tracker.run()
        except KeyboardInterrupt:
            print("\n\n[*] Tracker desligado.")