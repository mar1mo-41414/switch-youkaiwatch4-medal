#!/usr/bin/env python3
"""NSO (Switch 実行形式) を LZ4 展開してフラットなメモリイメージにする。

usage: nso2bin.py <in.nso> <out.bin>
  out.bin      : text/rodata/data を仮想アドレス通りに並べ、bss 分をゼロ埋めしたイメージ
  out.bin.json : 各セグメントのオフセット/サイズ、MOD0 から得た dynamic/dynsym/dynstr 情報
"""
import json
import struct
import sys

import lz4.block


def main(src, dst):
    d = open(src, "rb").read()
    assert d[:4] == b"NSO0"
    flags = struct.unpack_from("<I", d, 0xC)[0]
    segs = []
    for i, (hoff, szoff) in enumerate(((0x10, 0x60), (0x20, 0x64), (0x30, 0x68))):
        foff, moff, size = struct.unpack_from("<III", d, hoff)
        csize = struct.unpack_from("<I", d, szoff)[0]
        raw = d[foff:foff + csize]
        if flags & (1 << i):
            raw = lz4.block.decompress(raw, uncompressed_size=size)
        assert len(raw) == size
        segs.append((moff, size, raw))
    bss = struct.unpack_from("<I", d, 0x3C)[0]
    end = segs[2][0] + segs[2][1] + bss
    img = bytearray(end)
    for moff, size, raw in segs:
        img[moff:moff + size] = raw
    open(dst, "wb").write(img)

    # MOD0 -> dynamic
    mod0 = struct.unpack_from("<I", img, 4)[0]
    assert img[mod0:mod0 + 4] == b"MOD0"
    dyn = mod0 + struct.unpack_from("<i", img, mod0 + 4)[0]
    tags = {}
    off = dyn
    while True:
        tag, val = struct.unpack_from("<qQ", img, off)
        off += 16
        if tag == 0:
            break
        tags.setdefault(tag, []).append(val)
    info = {
        "segments": [{"vaddr": m, "size": s} for m, s, _ in segs],
        "bss": bss,
        "mod0": mod0,
        "dynamic": dyn,
        "tags": {str(k): v for k, v in tags.items()},
    }
    json.dump(info, open(dst + ".json", "w"), indent=1)
    print(json.dumps(info["segments"]), hex(dyn))




def to_elf(bin_path, elf_path):
    """フラットイメージを PT_LOAD/PT_DYNAMIC だけを持つ ELF64 (AArch64) に包む。
    Ghidra の ELF ローダが DT_SYMTAB/DT_JMPREL から import 名と再配置を解決してくれる。"""
    info = json.load(open(bin_path + ".json"))
    img = open(bin_path, "rb").read()
    segs = info["segments"]
    base = 0x1000  # ファイル上で image を置くオフセット
    phdrs = []
    flags = (5, 4, 6)  # R-X, R--, RW-
    for i, s in enumerate(segs):
        memsz = s["size"] + (info["bss"] if i == 2 else 0)
        phdrs.append(struct.pack("<IIQQQQQQ", 1, flags[i], base + s["vaddr"], s["vaddr"], s["vaddr"],
                                 s["size"], memsz, 0x1000))
    dyn = info["dynamic"]
    dsz = 0
    while struct.unpack_from("<q", img, dyn + dsz)[0] != 0:
        dsz += 16
    dsz += 16
    phdrs.append(struct.pack("<IIQQQQQQ", 2, 6, base + dyn, dyn, dyn, dsz, dsz, 8))
    eh = struct.pack("<4sBBBBB7sHHIQQQIHHHHHH", b"\x7fELF", 2, 1, 1, 0, 0, b"\0" * 7,
                     3, 183, 1, 0, 64, 0, 0, 64, 56, len(phdrs), 64, 0, 0)
    hdr = eh + b"".join(phdrs)
    out = hdr + b"\0" * (base - len(hdr))
    data_end = segs[2]["vaddr"] + segs[2]["size"]
    out += img[:data_end]
    open(elf_path, "wb").write(out)


if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[1] == "elf":
    to_elf(sys.argv[2], sys.argv[3])


if __name__ == "__main__" and len(sys.argv) == 3:
    main(sys.argv[1], sys.argv[2])
