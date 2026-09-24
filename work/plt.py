#!/usr/bin/env python3
"""main.bin の PLT スタブを走査して {スタブアドレス: import 名} を plt.json に書く。
usage: plt.py [main.bin]"""
import json
import struct
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "main.bin"
img = open(path, "rb").read()
info = json.load(open(path + ".json"))
t = {int(k): v[0] for k, v in info["tags"].items()}
symtab, strtab, jmprel, pltsz = t[6], t[5], t[23], t[2]  # DT_SYMTAB/STRTAB/JMPREL/PLTRELSZ


def name(i):
    st = struct.unpack_from("<I", img, symtab + 24 * i)[0]
    return img[strtab + st:img.index(b"\0", strtab + st)].decode()


got = {}
for o in range(jmprel, jmprel + pltsz, 24):
    off, rinfo, _ = struct.unpack_from("<QQq", img, o)
    got[off] = name(rinfo >> 32)

# adrp x16, page ; ldr x17, [x16, #off] ; add x16, x16, #off ; br x17
stubs = {}
for a in range(0, info["segments"][0]["size"] - 16, 4):
    w = struct.unpack_from("<I", img, a)[0]
    if w & 0x9F00001F != 0x90000010:
        continue
    w2 = struct.unpack_from("<I", img, a + 4)[0]
    if w2 & 0xFFC003FF != 0xF9400211 or struct.unpack_from("<I", img, a + 12)[0] != 0xD61F0220:
        continue
    imm = (((w >> 5) & 0x7FFFF) << 2) | ((w >> 29) & 3)
    if imm & (1 << 20):
        imm -= 1 << 21
    tgt = (a & ~0xFFF) + (imm << 12) + ((w2 >> 10) & 0xFFF) * 8
    if tgt in got:
        stubs[hex(a)] = got[tgt]
json.dump(stubs, open("plt.json", "w"), indent=0)
print(len(stubs), "stubs")
