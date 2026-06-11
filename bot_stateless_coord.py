import os
import struct
import time
import sys

class AutoRadar:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.candidates = {}
        self.mem_file = None

    def map_heap(self):
        try:
            with open(f"/proc/{self.pid}/maps", "r") as maps:
                for line in maps:
                    parts = line.split()
                    if len(parts) < 5: continue
                    # Varremos apenas regiões onde o motor de física aloca entidades dinâmicas
                    if "rw-p" in parts[1] and "bin/client" not in line:
                        start, end = [int(x, 16) for x in parts[0].split('-')]
                        self.heap_regions.append((start, end))
            return True
        except PermissionError:
            print("[!] Execute como root (sudo).")
            return False

    def snapshot(self):
        print("[*] Mapeando universo espacial do jogo (Pode levar alguns segundos)...")
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue
                    
                    # Leitura bruta em lote
                    for offset in range(0, len(dump) - 12, 4):
                        x, y, z = struct.unpack_from('<iii', dump, offset)
                        
                        # Filtro de Sanidade: Seleciona apenas coordenadas que cabem no mapa
                        if 31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15:
                            self.candidates[start + offset] = {'x': x, 'y': y, 'z': z, 'steps': 0}
            print(f"[+] {len(self.candidates)} coordenadas estáticas capturadas.")
        except Exception as e:
            print(f"[!] Erro no Snapshot: {e}")

    def track_movement(self):
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
                
                # Se não se moveu, continua no radar, mas não pontua
                if dx == 0 and dy == 0 and dz == 0:
                    survivors[addr] = data
                    continue
                    
                # Física do Jogo: O personagem só anda 1 tile por vez (máximo 2 na diagonal). O Z (andar) não muda no passo plano.
                if dz == 0 and dx <= 2 and dy <= 2:
                    data['x'] = new_x
                    data['y'] = new_y
                    data['steps'] += 1 # Pontua a entidade por ter se movido de forma natural
                    survivors[addr] = data
                else:
                    # Movimento impossível (Lixo de memória realocado ou erro do Qt). Destruímos o candidato.
                    pass 
            except Exception:
                pass
                
        self.candidates = survivors
        
    def display(self):
        # Filtra apenas quem já se moveu e ordena pelo número de passos (Leaderboard)
        ativos = {k: v for k, v in self.candidates.items() if v['steps'] > 0}
        top_ativos = sorted(ativos.items(), key=lambda item: item[1]['steps'], reverse=True)[:5]
        
        print("\033[H\033[J")
        print("="*65)
        print(" 📡 RADAR AUTOCALIBRÁVEL (ZERO INPUT MANUAL)")
        print("="*65)
        print("-> Vá para o jogo e ANDE EM LINHA RETA. O script rastreará sozinho.\n")
        
        if not top_ativos:
            print("[!] O radar está aguardando você dar o primeiro passo...")
        else:
            print(" ALVOS ISOLADOS PELA FÍSICA DE MOVIMENTO:")
            for addr, data in top_ativos:
                short_addr = hex(addr)
                print(f" -> [{short_addr}] X: {data['x']} | Y: {data['y']} | Z: {data['z']} | Passos: {data['steps']}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_radar_auto.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    radar = AutoRadar(pid)
    
    if radar.map_heap():
        radar.snapshot()
        try:
            while True:
                radar.track_movement()
                radar.display()
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n[*] Radar desligado.")