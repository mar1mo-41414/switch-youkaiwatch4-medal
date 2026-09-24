#!/usr/bin/env python3
"""main.bin を capstone で簡易逆アセンブル (Ghidra 解析待ちの間の下見用)。
usage: dis.py <start hex> <end hex>"""
import json
import sys

import capstone

img = open("main.bin", "rb").read()
plt = {int(k, 16): v for k, v in json.load(open("plt.json")).items()}
md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
s, e = int(sys.argv[1], 16), int(sys.argv[2], 16)
for i in md.disasm(img[s:e], s):
    c = ""
    if i.mnemonic in ("bl", "b") and i.op_str.startswith("#"):
        t = int(i.op_str[1:], 16)
        c = "  ; " + plt.get(t, "")
    print("%08x: %-8s %s%s" % (i.address, i.mnemonic, i.op_str, c))
