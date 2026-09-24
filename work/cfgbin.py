#!/usr/bin/env python3
"""Level-5 cfg.bin のダンプ。

構造: [ヘッダ 16B: エントリ数, 文字列領域オフセット, 長さ, 個数]
      エントリ = crc32(名前) u32, 引数の数 u8, 型 (2bit ずつ, 0=文字列 1=int 2=float), 4 バイト境界まで 0xFF, 値 u32 x n
      文字列領域 (0xFF で 16 境界) の後ろにキー表 (crc32 → 名前)。
usage: cfgbin.py <file.cfg.bin>
"""
import struct
import sys


def parse(buf):
    n, soff, slen, _ = struct.unpack_from("<IIII", buf, 0)
    strings = buf[soff:soff + slen]

    def s_at(o):
        if o >= len(strings):
            return "<str@%#x>" % o
        e = strings.find(b"\0", o)
        return strings[o:e if e >= 0 else len(strings)].decode("utf-8", "replace")

    # キー表
    names = {}
    k = soff + slen
    k = (k + 15) & ~15
    if k + 16 <= len(buf):
        ksize, kcnt, kstr, kslen = struct.unpack_from("<IIII", buf, k)
        kst = buf[k + kstr:k + kstr + kslen]
        for i in range(kcnt):
            crc, so = struct.unpack_from("<II", buf, k + 16 + 8 * i)
            names[crc] = kst[so:kst.index(b"\0", so)].decode("utf-8", "replace")

    ents = []
    p = 16
    for _ in range(n):
        crc = struct.unpack_from("<I", buf, p)[0]
        cnt = buf[p + 4]
        tb = (cnt + 3) // 4
        types = [(buf[p + 5 + i // 4] >> (2 * (i % 4))) & 3 for i in range(cnt)]
        p += 5 + tb
        p = (p + 3) & ~3
        vals = []
        for t in types:
            raw = struct.unpack_from("<I", buf, p)[0]
            if t == 0:
                vals.append(s_at(raw) if raw != 0xFFFFFFFF else None)
            elif t == 2:
                vals.append(struct.unpack_from("<f", buf, p)[0])
            else:
                vals.append(struct.unpack_from("<i", buf, p)[0])
            p += 4
        ents.append((names.get(crc, "%08x" % crc), vals))
    return ents


if __name__ == "__main__":
    for name, vals in parse(open(sys.argv[1], "rb").read()):
        print(name, vals)
