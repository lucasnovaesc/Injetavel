import os
import struct
import time
import sys
import threading
import subprocess

class TibiaCoreAPIV5:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.lock = threading.Lock()
        self.running = True
        
        self.api_state = {
            'x': 0, 'y': 0, 'z': 0,
            'is_moving': False,
            'tracker_votes': 0,
            'tracker_status': 'Aguardando Delta',
            'hp': 0, 'max_hp': 0,
            'mana': 0, 'max_mana': 0,
            'healer_status': 'Aguardando Calibração'
        }

        self.tracker_candidates = {}
        self.active_coord = None
        self.last_votes = 0
        
        self.vitals_address = None
        self.max_hp = None
        self.max_mana = None
        self.hp_cura = 200        
        self.tecla_cura = "F1"    
        self.mana_potion = 50     
        self.tecla_potion = "F2"  
        self.cooldown = 1.0       
        self.ultimo_heal = 0
        self.ultima_potion = 0

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
            with self.lock:
                self.heap_regions = regions
            return True
        except Exception:
            return False

    def press_key(self, key):
        try:
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            env["XAUTHORITY"] = "/home/lucasnovaesc/.Xauthority"
            subprocess.Popen(['xdotool', 'key', key], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            pass

    def fast_auto_calibrate(self):
        print("\n" + "="*65)
        print(" ⚡ CALIBRAÇÃO HEURÍSTICA DE ALTA VELOCIDADE ⚡")
        print("="*65)
        print("[*] Mapeando matriz (Garanta que VIDA e MANA estejam CHEIAS)...")
        
        candidates = {}
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                with self.lock:
                    current_regions = list(self.heap_regions)
                    
                for start, end in current_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue
                    
                    rem = len(dump) % 4
                    if rem: dump = dump[:-rem]
                    
                    try: ints = memoryview(dump).cast('i')
                    except Exception: continue
                        
                    for i in range(len(ints) - 3):
                        mhp = ints[i+1]
                        if 100 < mhp < 20000:
                            if ints[i] == mhp:
                                mmana = ints[i+3]
                                if 10 < mmana < 20000:
                                    if ints[i+2] == mmana:
                                        candidates[start + i*4] = (mhp, mmana)
        except Exception:
            return False
            
        if not candidates:
            print("[-] Falha: Atributos não estão cheios ou não foram localizados.")
            return False
            
        print(f"[+] {len(candidates)} candidatos na RAM. \033[1;33mUSE UMA MAGIA NO JOGO PARA ATIVAR O HEALER.\033[0m")
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                while self.running:
                    for addr, (mhp, mmana) in list(candidates.items()):
                        try:
                            mem.seek(addr)
                            chp, read_mhp, cmana, read_mmana = struct.unpack('<iiii', mem.read(16))
                            
                            if read_mhp == mhp and read_mmana == mmana:
                                if cmana < mmana or chp < mhp: 
                                    self.max_hp = mhp
                                    self.max_mana = mmana
                                    self.vitals_address = addr
                                    
                                    with self.lock:
                                        self.api_state['max_hp'] = mhp
                                        self.api_state['max_mana'] = mmana
                                        self.api_state['healer_status'] = 'Monitorando'
                                        
                                    print(f" [🔥] ASSINATURA TRAVADA: HP Máx {self.max_hp} | Mana Máx {self.max_mana}")
                                    return True
                            else:
                                del candidates[addr] 
                        except Exception:
                            del candidates[addr]
                            
                    if not candidates:
                        print("[-] Candidatos invalidados. A interface pode ter recriado a barra.")
                        return False
                    time.sleep(0.05)
        except Exception:
            return False

    def tracker_background_worker(self):
        while self.running:
            self.update_heap_map()
            snapshot = {}
            
            with self.lock:
                current_regions = list(self.heap_regions)
                
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    for start, end in current_regions:
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
                            
                            # FUNIL DE FÍSICA AMPLO: Permite saltos de até 5 tiles para não excluir chars que estão correndo
                            if (dx > 0 or dy > 0 or dz > 0) and dx <= 10 and dy <= 10 and dz <= 1:
                                movimentados[addr] = (nx, ny, nz)
                        except Exception:
                            pass
            except Exception:
                pass
                
            agora = time.time()
            with self.lock:
                for addr, (nx, ny, nz) in movimentados.items():
                    if addr not in self.tracker_candidates:
                        self.tracker_candidates[addr] = {'x': nx, 'y': ny, 'z': nz, 'last_move': agora, 'score': 1}
                        
                para_remover = []
                for a, d in self.tracker_candidates.items():
                    if agora - d['last_move'] > 10.0:
                        if self.active_coord and (d['x'], d['y'], d['z']) == self.active_coord:
                            continue
                        para_remover.append(a)
                        
                for a in para_remover:
                    del self.tracker_candidates[a]

    def tracker_fast_worker(self):
        while self.running:
            agora = time.time()
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    with self.lock:
                        for addr in list(self.tracker_candidates.keys()):
                            data = self.tracker_candidates[addr]
                            try:
                                mem.seek(addr)
                                nx, ny, nz = struct.unpack('<iii', mem.read(12))
                                
                                if not (31000 < nx < 34000 and 31000 < ny < 34000 and 0 <= nz <= 15):
                                    raise ValueError("Corrompido")
                                    
                                dx, dy, dz = abs(nx - data['x']), abs(ny - data['y']), abs(nz - data['z'])
                                
                                if dx > 0 or dy > 0 or dz > 0:
                                    # FUNIL DE FÍSICA ESTRITO: A 50Hz, qualquer salto > 1 é ruído
                                    if dx <= 1 and dy <= 1 and dz <= 1:
                                        data['score'] = 1 
                                        data['last_move'] = agora
                                    else:
                                        data['score'] = 0 
                                    data['x'], data['y'], data['z'] = nx, ny, nz
                            except Exception:
                                del self.tracker_candidates[addr]
                                    
                        vote_pool = {}
                        for addr, data in self.tracker_candidates.items():
                            if data['score'] > 0:
                                coord = (data['x'], data['y'], data['z'])
                                vote_pool[coord] = vote_pool.get(coord, 0) + 1
                                
                        if vote_pool:
                            best_coord = max(vote_pool.items(), key=lambda item: item[1])
                            self.active_coord = best_coord[0]
                            self.last_votes = best_coord[1]
                        else:
                            self.last_votes = 0

                        if self.active_coord and self.last_votes >= 4:
                            self.api_state['x'] = self.active_coord[0]
                            self.api_state['y'] = self.active_coord[1]
                            self.api_state['z'] = self.active_coord[2]
                            self.api_state['tracker_votes'] = self.last_votes
                            self.api_state['is_moving'] = True
                            self.api_state['tracker_status'] = 'RASTREANDO'
                        elif self.active_coord:
                            self.api_state['x'] = self.active_coord[0]
                            self.api_state['y'] = self.active_coord[1]
                            self.api_state['z'] = self.active_coord[2]
                            self.api_state['tracker_votes'] = self.last_votes
                            self.api_state['is_moving'] = False
                            self.api_state['tracker_status'] = 'PARADO'
                        else:
                            self.api_state['is_moving'] = False
                            self.api_state['tracker_status'] = 'BUSCANDO'
                            
            except Exception:
                pass
                
            time.sleep(0.02)

    def healer_worker(self):
        while self.running:
            if not self.max_hp or not self.max_mana:
                time.sleep(1)
                continue
                
            hp, mana = None, None
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    if self.vitals_address:
                        try:
                            mem.seek(self.vitals_address)
                            chp, mhp, cmana, mmana = struct.unpack('<iiii', mem.read(16))
                            
                            if (self.max_hp <= mhp <= self.max_hp + 50) and (self.max_mana <= mmana <= self.max_mana + 50):
                                if mhp > self.max_hp or mmana > self.max_mana:
                                    self.max_hp, self.max_mana = mhp, mmana
                                    with self.lock:
                                        self.api_state['max_hp'] = mhp
                                        self.api_state['max_mana'] = mmana
                                hp, mana = chp, cmana
                            else:
                                self.vitals_address = None
                        except Exception:
                            self.vitals_address = None
                    
                    if not self.vitals_address and self.max_hp and self.max_mana:
                        max_hp_bytes = struct.pack('<i', self.max_hp)
                        max_mana_bytes = struct.pack('<i', self.max_mana)
                        with self.lock:
                            current_regions = list(self.heap_regions)
                            
                        for start, end in current_regions:
                            mem.seek(start)
                            try: dump = mem.read(end - start)
                            except OSError: continue
                            
                            offset = 0
                            while True:
                                offset = dump.find(max_hp_bytes, offset)
                                if offset == -1: break
                                if offset >= 4 and offset + 12 <= len(dump):
                                    if dump[offset+8 : offset+12] == max_mana_bytes:
                                        curr_hp = struct.unpack('<i', dump[offset-4 : offset])[0]
                                        curr_mana = struct.unpack('<i', dump[offset+4 : offset+8])[0]
                                        if 0 <= curr_hp <= self.max_hp and 0 <= curr_mana <= self.max_mana:
                                            self.vitals_address = start + (offset - 4)
                                            hp, mana = curr_hp, curr_mana
                                            break
                                offset += 4
                            if self.vitals_address: break

            except Exception:
                pass

            agora = time.time()
            with self.lock:
                if hp is not None and mana is not None:
                    self.api_state['hp'] = hp
                    self.api_state['mana'] = mana
                    self.api_state['healer_status'] = 'Monitorando'
                    
                    if hp < self.hp_cura and (agora - self.ultimo_heal) > self.cooldown:
                        self.press_key(self.tecla_cura)
                        self.ultimo_heal = agora
                        self.api_state['healer_status'] = f'Curou (HP {hp})'
                        
                    elif mana < self.mana_potion and (agora - self.ultima_potion) > self.cooldown:
                        self.press_key(self.tecla_potion)
                        self.ultima_potion = agora
                        self.api_state['healer_status'] = f'Poção (MP {mana})'
                else:
                    self.api_state['healer_status'] = 'PERDA DE ASSINATURA'
                    
            time.sleep(0.05)

    def run(self):
        if not self.update_heap_map():
            print("[!] Execute como root (sudo).")
            return
            
        print("="*65)
        print(" 🧠 TIBIA CORE API V5 - CONSENSO ESPACIAL & HEALER ")
        print("="*65)
        
        while not self.fast_auto_calibrate():
            time.sleep(2)
            
        print("[*] Iniciando Threads Operacionais...")
        print("[*] Dê alguns passos contínuos pelo jogo para engatilhar o radar.\n")
        
        t1 = threading.Thread(target=self.tracker_background_worker)
        t2 = threading.Thread(target=self.tracker_fast_worker)
        t3 = threading.Thread(target=self.healer_worker)
        
        t1.daemon = t2.daemon = t3.daemon = True
        t1.start()
        t2.start()
        t3.start()
        
        try:
            while self.running:
                with self.lock:
                    st = self.api_state.copy()
                
                status_color = "\033[92m" if st['tracker_status'] == 'RASTREANDO' else "\033[93m"
                ui = (
                    f"\r\033[K{status_color}[{st['tracker_status']}]\033[0m "
                    f"X:{st['x']} Y:{st['y']} Z:{st['z']} (Votos: {st['tracker_votes']}) | "
                    f"HP: {st['hp']:>4}/{st['max_hp']} | "
                    f"MP: {st['mana']:>4}/{st['max_mana']} | "
                    f"Ação: {st['healer_status']}"
                )
                print(ui, end="")
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            self.running = False
            print("\n\n[*] Core da API finalizado.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 tibia_core_api_v5.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    bot = TibiaCoreAPIV5(pid)
    bot.run()