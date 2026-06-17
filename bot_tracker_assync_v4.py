import os
import struct
import time
import sys
import threading

class AsyncTrackerV5Fixed:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.candidates = {} 
        self.active_coord = None 
        self.last_votes = 0
        self.lock = threading.Lock()
        self.running = True
        
    def update_heap_map(self):
        regions = []
        try:
            with open(f"/proc/{self.pid}/maps", "r") as maps:
                for line in maps:
                    parts = line.split()
                    if len(parts) < 5: continue
                    if "rw-p" in parts[1] and "bin/client" not in line:
                        start, end = [int(x, 16) for x in parts[0].split('-')]
                        regions.append((start, end))
            self.heap_regions = regions
            return True
        except Exception:
            return False

    def background_delta_scanner(self):
        """Thread Secundária: Filtra o lixo estático e gerencia o ciclo de vida dos candidatos."""
        while self.running:
            self.update_heap_map()
            snapshot = {}
            
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    for start, end in self.heap_regions:
                        mem.seek(start)
                        try: dump = mem.read(end - start)
                        except OSError: continue
                        
                        for offset in range(0, len(dump) - 12, 4):
                            x, y, z = struct.unpack_from('<iii', dump, offset)
                            if 31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15:
                                snapshot[start + offset] = (x, y, z)
            except Exception:
                pass
                
            time.sleep(0.5) 
            
            movimentados = {}
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    for addr, (ox, oy, oz) in snapshot.items():
                        try:
                            mem.seek(addr)
                            nx, ny, nz = struct.unpack('<iii', mem.read(12))
                            dx, dy, dz = abs(nx - ox), abs(ny - oy), abs(nz - oz)
                            
                            if (dx > 0 or dy > 0 or dz > 0) and dx <= 1 and dy <= 1 and dz <= 1:
                                movimentados[addr] = (nx, ny, nz)
                        except Exception:
                            pass
            except Exception:
                pass
                
            agora = time.time()
            with self.lock:
                for addr, (nx, ny, nz) in movimentados.items():
                    if addr not in self.candidates:
                        self.candidates[addr] = {'x': nx, 'y': ny, 'z': nz, 'last_move': agora, 'score': 1}
                        
                # --- ÂNCORA DE INATIVIDADE PROTOCOLO V5 ---
                # Remove alvos antigos (como monstros que se moveram longe e pararam),
                # MAS protege os endereços que sustentam a posição atual do jogador.
                para_remover = []
                for a, d in self.candidates.items():
                    if agora - d['last_move'] > 10.0:
                        if self.active_coord and (d['x'], d['y'], d['z']) == self.active_coord:
                            continue # Proteção absoluta contra perda de calibragem
                        para_remover.append(a)
                        
                for a in para_remover:
                    del self.candidates[a]

    def run_fast_monitor(self):
        if not self.update_heap_map():
            print("[!] Execute como root (sudo).")
            return
            
        print("="*65)
        print(" 🎯 TRACKER V5 FIXED (PERSISTENT ANCHORAGE) ")
        print("="*65)
        print("[*] Monitoramento online. Dê alguns passos para calibrar o enxame.")
        
        bg_thread = threading.Thread(target=self.background_delta_scanner)
        bg_thread.daemon = True
        bg_thread.start()
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                while self.running:
                    agora = time.time()
                    
                    with self.lock:
                        for addr in list(self.candidates.keys()):
                            data = self.candidates[addr]
                            try:
                                mem.seek(addr)
                                nx, ny, nz = struct.unpack('<iii', mem.read(12))
                                
                                if not (31000 < nx < 34000 and 31000 < ny < 34000 and 0 <= nz <= 15):
                                    raise ValueError("Corrompido")
                                    
                                dx, dy, dz = abs(nx - data['x']), abs(ny - data['y']), abs(nz - data['z'])
                                
                                if dx > 0 or dy > 0 or dz > 0:
                                    if dx <= 1 and dy <= 1 and dz <= 1:
                                        data['score'] = 1 
                                        data['last_move'] = agora
                                    else:
                                        data['score'] = 0 # Invalidado por quebra de física
                                    data['x'], data['y'], data['z'] = nx, ny, nz
                                else:
                                    # Correção: O score permanece ativo enquanto o objeto for válido na RAM.
                                    # Eliminada a amnésia de 0.5s que zerava os votos prematuramente.
                                    pass
                            except Exception:
                                del self.candidates[addr]
                                    
                        # --- PROCESSAMENTO DO CONSENSO ESPACIAL ---
                        vote_pool = {}
                        for addr, data in self.candidates.items():
                            if data['score'] > 0:
                                coord = (data['x'], data['y'], data['z'])
                                vote_pool[coord] = vote_pool.get(coord, 0) + 1
                                
                        if vote_pool:
                            best_coord = max(vote_pool.items(), key=lambda item: item[1])
                            self.active_coord = best_coord[0]
                            self.last_votes = best_coord[1]

                    # Módulo de Exibição Estabilizado
                    if self.active_coord and self.last_votes >= 4:
                        x, y, z = self.active_coord
                        print(f"\r\033[K[RASTREANDO] X: {x} | Y: {y} | Z: {z}  (Votos Consolidados: {self.last_votes})", end="")
                    elif self.active_coord:
                        x, y, z = self.active_coord
                        print(f"\r\033[K[PARADO]     X: {x} | Y: {y} | Z: {z}  (Aguardando re-sincronização)", end="")
                    else:
                        print(f"\r\033[K[BUSCANDO]   Calibrando enxame... ande um tile.   ", end="")
                        
                    time.sleep(0.02) # 50Hz
                    
        except KeyboardInterrupt:
            self.running = False
            print("\n\n[*] Rastreamento encerrado.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_tracker_v5_fixed.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    tracker = AsyncTrackerV5Fixed(pid)
    tracker.run_fast_monitor()