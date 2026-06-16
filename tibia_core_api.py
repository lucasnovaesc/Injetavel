import os
import struct
import time
import sys
import threading
import subprocess
import json

class TibiaCoreAPI:
    def __init__(self, pid, max_hp, max_mana):
        self.pid = pid
        self.max_hp = max_hp
        self.max_mana = max_mana
        
        # Compartilhamento de Memória
        self.heap_regions = []
        self.lock = threading.Lock()
        self.running = True
        
        # Estado Global (Pronto para exportação via API)
        self.state = {
            'x': 0, 'y': 0, 'z': 0,
            'hp': 0, 'max_hp': max_hp,
            'mana': 0, 'max_mana': max_mana,
            'is_moving': False
        }
        
        # --- Variáveis do Tracker de Coordenadas ---
        self.coord_candidates = {}
        self.active_coord_target = None
        
        # --- Variáveis do Healer ---
        self.healer_locked_addr = None
        self.hp_cura = 200        
        self.tecla_cura = "F1"    
        self.mana_potion = 50     
        self.tecla_potion = "F2"  
        self.cooldown = 1.0       
        self.ultimo_heal = 0
        self.ultima_potion = 0

    def update_heap_map(self):
        """Atualiza as regiões de memória uma única vez para todos os módulos."""
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

    # =====================================================================
    # MÓDULO 1: TRACKER DE COORDENADAS (FÍSICA DELTA)
    # =====================================================================
    def coord_background_scanner(self):
        """Busca entidades que se moveram exatamente 1 tile."""
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
            except Exception: pass
                
            time.sleep(0.5) 
            
            movimentados = {}
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    for addr, (ox, oy, oz) in snapshot.items():
                        try:
                            mem.seek(addr)
                            nx, ny, nz = struct.unpack('<iii', mem.read(12))
                            dx, dy = abs(nx - ox), abs(ny - oy)
                            
                            if nz == oz and (dx > 0 or dy > 0) and dx <= 1 and dy <= 1:
                                movimentados[addr] = (nx, ny, nz)
                        except Exception: pass
            except Exception: pass
                
            agora = time.time()
            with self.lock:
                for addr, (nx, ny, nz) in movimentados.items():
                    if addr not in self.coord_candidates:
                        self.coord_candidates[addr] = {'x': nx, 'y': ny, 'z': nz, 'last_move': agora, 'score': 1}
                        
                para_remover = [a for a, d in self.coord_candidates.items() if agora - d['last_move'] > 5.0]
                for a in para_remover:
                    del self.coord_candidates[a]
                    if self.active_coord_target == a:
                        self.active_coord_target = None

    def coord_fast_monitor(self):
        """Lê os vetores isolados a 50Hz e atualiza o estado global."""
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                while self.running:
                    agora = time.time()
                    with self.lock:
                        for addr in list(self.coord_candidates.keys()):
                            data = self.coord_candidates[addr]
                            try:
                                mem.seek(addr)
                                nx, ny, nz = struct.unpack('<iii', mem.read(12))
                                
                                if not (31000 < nx < 34000 and 31000 < ny < 34000 and 0 <= nz <= 15):
                                    raise ValueError("Corrompido")
                                    
                                dx, dy, dz = abs(nx - data['x']), abs(ny - data['y']), abs(nz - data['z'])
                                
                                if dx > 0 or dy > 0 or dz > 0:
                                    if dz == 0 and dx <= 1 and dy <= 1:
                                        data['score'] += 1
                                        data['last_move'] = agora
                                    elif dx > 1 or dy > 1 or dz != 0:
                                        data['score'] = 0
                                        data['last_move'] = agora
                                    data['x'], data['y'], data['z'] = nx, ny, nz
                                else:
                                    if agora - data['last_move'] > 0.5:
                                        data['score'] = 0
                            except Exception:
                                del self.coord_candidates[addr]
                                if self.active_coord_target == addr:
                                    self.active_coord_target = None
                                    
                        ativos = [(a, d) for a, d in self.coord_candidates.items() if d['score'] > 0]
                        if ativos:
                            ativos.sort(key=lambda item: item[1]['score'], reverse=True)
                            self.active_coord_target = ativos[0][0]

                        # Atualiza a API Global
                        if self.active_coord_target and self.active_coord_target in self.coord_candidates:
                            t_data = self.coord_candidates[self.active_coord_target]
                            self.state['x'] = t_data['x']
                            self.state['y'] = t_data['y']
                            self.state['z'] = t_data['z']
                            self.state['is_moving'] = (t_data['score'] > 0)

                    time.sleep(0.02) 
        except Exception: pass

    # =====================================================================
    # MÓDULO 2: HEALER DE ALTA PERFORMANCE (COM CACHE DE PONTEIRO)
    # =====================================================================
    def press_key(self, key):
        try:
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            env["XAUTHORITY"] = "/home/lucasnovaesc/.Xauthority"
            subprocess.Popen(['xdotool', 'key', key], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception: pass

    def find_vitals_signature(self):
        """Executa a busca pesada (O(n)) apenas quando o alvo é perdido."""
        max_hp_bytes = struct.pack('<i', self.max_hp)
        max_mana_bytes = struct.pack('<i', self.max_mana)
        
        with self.lock:
            current_regions = list(self.heap_regions)
            
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
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
                                    # Calcula o endereço absoluto do HP Atual (4 bytes antes do MaxHP)
                                    self.healer_locked_addr = start + offset - 4
                                    return True
                        offset += 4
        except Exception: pass
        return False

    def healer_fast_monitor(self):
        """Lê os vitais em O(1) usando o endereço em cache."""
        while self.running:
            if not self.healer_locked_addr:
                self.find_vitals_signature()
                time.sleep(0.5) # Penalidade de CPU se não encontrar
                continue
                
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    mem.seek(self.healer_locked_addr)
                    hp, max_hp, mana, max_mana = struct.unpack('<iiii', mem.read(16))
                    
                    # Validação de corrupção do ponteiro
                    if max_hp != self.max_hp or max_mana != self.max_mana or hp < 0 or hp > max_hp:
                        raise ValueError("Ponteiro do Healer corrompido.")
                        
                    agora = time.time()
                    
                    # Atualiza o Estado Global
                    with self.lock:
                        self.state['hp'] = hp
                        self.state['mana'] = mana

                    # Lógica de Ação
                    if hp < self.hp_cura and (agora - self.ultimo_heal) > self.cooldown:
                        self.press_key(self.tecla_cura)
                        self.ultimo_heal = agora
                        
                    if mana < self.mana_potion and (agora - self.ultima_potion) > self.cooldown:
                        self.press_key(self.tecla_potion)
                        self.ultima_potion = agora
                        
            except Exception:
                # Se a estrutura morrer na RAM, solta o lock para forçar nova varredura
                self.healer_locked_addr = None
                
            time.sleep(0.05) # 20Hz para cura é o ideal humano

    # =====================================================================
    # MOTOR PRINCIPAL (OUTPUT & DISPATCHER)
    # =====================================================================
    def run(self):
        if not self.update_heap_map():
            print("[!] Execute como root (sudo).")
            return
            
        print("="*70)
        print(" 🧠 TIBIA CORE API (TRACKER ASSÍNCRONO + CACHED HEALER) ")
        print("="*70)
        
        # Despacha as Threads Secundárias
        threading.Thread(target=self.coord_background_scanner, daemon=True).start()
        threading.Thread(target=self.coord_fast_monitor, daemon=True).start()
        threading.Thread(target=self.healer_fast_monitor, daemon=True).start()
        
        try:
            while self.running:
                with self.lock:
                    estado_atual = self.state.copy()
                    
                movimento = "[ANDANDO]" if estado_atual['is_moving'] else "[PARADO] "
                hp_str = f"{estado_atual['hp']:>4}/{estado_atual['max_hp']}"
                mp_str = f"{estado_atual['mana']:>4}/{estado_atual['max_mana']}"
                
                # Interface do Terminal (Simulando o output da futura API)
                print(f"\r\033[K{movimento} Pos: ({estado_atual['x']}, {estado_atual['y']}, {estado_atual['z']}) | HP: {hp_str} | MP: {mp_str}", end="")
                
                time.sleep(0.1) # Taxa de refresh do terminal
                
        except KeyboardInterrupt:
            self.running = False
            print("\n\n[*] Core API finalizada com segurança.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 tibia_core_api.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    
    # Configure os máximos de acordo com o personagem
    core = TibiaCoreAPI(pid, max_hp=290, max_mana=125)
    core.run()