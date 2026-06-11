import os
import struct
import sys

class MemoryDumper:
    def __init__(self, pid):
        self.pid = pid
        
    def dump_region(self, address, before=16, after=32):
        """Lê os arredores de um endereço e formata como Int32."""
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                # Volta 'before' bytes para ler o cabeçalho da estrutura
                start_addr = address - before
                mem.seek(start_addr)
                
                total_bytes = before + 12 + after # 12 bytes = X, Y, Z
                dump = mem.read(total_bytes)
                
                print(f"\n[*] Autópsia do bloco: {hex(address)}")
                print("-" * 65)
                
                for offset in range(0, len(dump) - 3, 4):
                    real_addr = start_addr + offset
                    val = struct.unpack('<i', dump[offset:offset+4])[0]
                    
                    # Marcadores visuais para sabermos o que é o quê
                    marker = "   "
                    if real_addr == address: marker = "[X]"
                    elif real_addr == address + 4: marker = "[Y]"
                    elif real_addr == address + 8: marker = "[Z]"
                    
                    # Formata o offset em relação ao X (ex: -0x10, +0x0C)
                    rel_offset = real_addr - address
                    sign = "+" if rel_offset >= 0 else "-"
                    offset_str = f"{sign}0x{abs(rel_offset):02X}"
                    
                    print(f" {marker} Offset {offset_str} | Endereço: {hex(real_addr)} | Valor Int32: {val}")
                print("-" * 65)
                
        except Exception as e:
            print(f"[!] Falha na leitura do bloco {hex(address)}: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_coord_dumper.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    dumper = MemoryDumper(pid)
    
    # Os dois endereços persistentes isolados no seu último teste
    alvos = [0x56453bd4aa60, 0x564541fdad40]
    
    print("="*65)
    print(" EXTRATOR DE ASSINATURA ESTRUTURAL (STATELESS ANCHOR)")
    print("="*65)
    
    for alvo in alvos:
        dumper.dump_region(alvo)