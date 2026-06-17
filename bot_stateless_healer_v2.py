import os
import struct
import time
import sys
import subprocess

class AutoHealerV4:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        
        self.max_hp = None
        self.max_mana = None
        self.vitals_address = None
        
        self.hp_cura = 200        
        self.tecla_cura = "F1"    
        self.mana_potion = 50     
        self.tecla_potion = "F2"  
        self.cooldown = 1.0       
        
        self.ultimo_heal = 0
        self.ultima_potion = 0

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
            print("[!] Erro de permissão. Execute como root.")
            return False

    def fast_auto_calibrate(self):
        print("\n" + "="*60)
        print(" ⚡ CALIBRAÇÃO HEURÍSTICA (REQUER HP/MP 100%) ⚡")
        print("="*60)
        print("[*] Mapeando matriz (Garanta que a vida e mana estejam cheias)...")
        
        candidates = {}
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
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
            print("[-] Falha: Atributos não estão cheios ou estruturas não localizadas.")
            return False
            
        print(f"[+] {len(candidates)} candidatos na RAM. \033[1;33mUSE UMA MAGIA NO JOGO PARA ATIVAR.\033[0m")
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                while True:
                    for addr, (mhp, mmana) in list(candidates.items()):
                        try:
                            mem.seek(addr)
                            chp, read_mhp, cmana, read_mmana = struct.unpack('<iiii', mem.read(16))
                            
                            if read_mhp == mhp and read_mmana == mmana:
                                if cmana < mmana or chp < mhp: 
                                    self.max_hp = mhp
                                    self.max_mana = mmana
                                    self.vitals_address = addr
                                    
                                    print("\n" + "="*60)
                                    print(f" [🔥] ASSINATURA TRAVADA: HP Máx {self.max_hp} | Mana Máx {self.max_mana}")
                                    print("="*60 + "\n")
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

    def scan_and_read(self):
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                # 1. Tenta a leitura via Cache e detecta Mutações (Level Up)
                if self.vitals_address:
                    try:
                        mem.seek(self.vitals_address)
                        chp, mhp, cmana, mmana = struct.unpack('<iiii', mem.read(16))
                        
                        # Valida se os máximos são iguais ou sofreram mutação de Level Up (Tolerância: até +50 por nível)
                        if (self.max_hp <= mhp <= self.max_hp + 50) and (self.max_mana <= mmana <= self.max_mana + 50):
                            if mhp > self.max_hp or mmana > self.max_mana:
                                print(f"\n[!] Mutação de Level Up detectada! Atualizando limites...")
                                self.max_hp = mhp
                                self.max_mana = mmana
                            return chp, cmana
                        else:
                            self.vitals_address = None # Corrompido
                    except Exception:
                        self.vitals_address = None
                
                # 2. Varredura Stateless de emergência (Caso o Qt tenha recriado o objeto sem Level Up)
                if not self.vitals_address and self.max_hp and self.max_mana:
                    max_hp_bytes = struct.pack('<i', self.max_hp)
                    max_mana_bytes = struct.pack('<i', self.max_mana)
                    
                    for start, end in self.heap_regions:
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
                                        return curr_hp, curr_mana
                            offset += 4
        except Exception:
            pass
        return None, None

    def press_key(self, key):
        try:
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            env["XAUTHORITY"] = "/home/lucasnovaesc/.Xauthority"
            subprocess.Popen(['xdotool', 'key', key], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            pass

    def run(self):
        while True:
            hp, mana = self.scan_and_read()
            agora = time.time()
            
            if hp is not None and mana is not None:
                print(f"\r\033[K[STATUS] HP: {hp:>4}/{self.max_hp} | Mana: {mana:>4}/{self.max_mana}   ", end="")
                
                if hp < self.hp_cura and (agora - self.ultimo_heal) > self.cooldown:
                    print(f"\n[+] Ação: Cura. Tecla {self.tecla_cura}")
                    self.press_key(self.tecla_cura)
                    self.ultimo_heal = agora
                    
                if mana < self.mana_potion and (agora - self.ultima_potion) > self.cooldown:
                    print(f"\n[+] Ação: Poção. Tecla {self.tecla_potion}")
                    self.press_key(self.tecla_potion)
                    self.ultima_potion = agora
            else:
                # Perda absoluta de assinatura (Level Up que destruiu o cache antes de lermos a mutação)
                print(f"\n[!] Assinatura permanentemente perdida. Iniciando recuperação pesada...")
                self.max_hp = None
                self.max_mana = None
                
                # Aguarda o jogador ficar com vida cheia para calibrar novamente (Falha crítica de design para AFK)
                while not self.fast_auto_calibrate():
                    time.sleep(2)
                
            time.sleep(0.05)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_stateless_v4.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    bot = AutoHealerV4(pid)
    
    if bot.map_heap():
        if bot.fast_auto_calibrate():
            bot.run()