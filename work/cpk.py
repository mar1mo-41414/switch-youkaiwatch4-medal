#!/usr/bin/env python3
"""CRI CPK アーカイブの一覧表示と展開 (@UTF テーブル + CRILAYLA 圧縮対応)。

usage:
  cpk.py list <in.cpk>
  cpk.py extract <in.cpk> <outdir> [部分一致フィルタ...]
"""
import os
import struct
import sys


def read_utf(buf, off):
    """@UTF テーブルを [ {列名: 値} ] として返す。"""
    if buf[off:off + 4] != b"@UTF":
        raise ValueError("no @UTF at %#x" % off)
    size = struct.unpack_from(">I", buf, off + 4)[0]
    base = off + 8
    t = buf[base:base + size]
    rows_off, str_off, data_off, _name, ncol, rowlen, nrows = struct.unpack_from(">IIIIHHI", t, 0)

    def cstr(o):
        o += str_off
        return t[o:t.index(b"\0", o)].decode("utf-8", "replace")

    fmts = {0: ">B", 1: ">b", 2: ">H", 3: ">h", 4: ">I", 5: ">i", 6: ">Q", 7: ">q", 8: ">f", 9: ">d"}

    def val(typ, p):
        if typ in fmts:
            v = struct.unpack_from(fmts[typ], t, p)[0]
            return v, struct.calcsize(fmts[typ])
        if typ == 0xA:
            return cstr(struct.unpack_from(">I", t, p)[0]), 4
        if typ == 0xB:
            o, n = struct.unpack_from(">II", t, p)
            return t[data_off + o:data_off + o + n], 8
        raise ValueError("type %x" % typ)

    cols = []
    p = 24
    for _ in range(ncol):
        flag = t[p]
        name = cstr(struct.unpack_from(">I", t, p + 1)[0])
        p += 5
        const = None
        if flag & 0xF0 == 0x30:
            const, n = val(flag & 0xF, p)
            p += n
        cols.append((flag, name, const))
    rows = []
    for r in range(nrows):
        p = rows_off + r * rowlen
        row = {}
        for flag, name, const in cols:
            st = flag & 0xF0
            if st == 0x50:
                row[name], n = val(flag & 0xF, p)
                p += n
            elif st == 0x30:
                row[name] = const
            else:
                row[name] = None
        rows.append(row)
    return rows


def crilayla(src):
    """CRILAYLA 展開 (後ろから読むビットストリーム + 先頭 0x100 バイトの非圧縮ヘッダ)。"""
    usize, hoff = struct.unpack_from("<II", src, 8)
    prefix = src[hoff + 0x10:hoff + 0x110]
    out = bytearray(usize)
    pos_bits = [len(src) - hoff - 0x10 - 1 + 0x10 - 0x10, 0]  # 読み取り位置 (バイト), 残りビット
    data = src[:hoff + 0x10]
    byte_pos = len(data) - 1
    bits_left = 0
    cur = 0

    def get(n):
        nonlocal byte_pos, bits_left, cur
        v = 0
        while n:
            if bits_left == 0:
                cur = data[byte_pos]
                byte_pos -= 1
                bits_left = 8
            take = min(bits_left, n)
            v = (v << take) | ((cur >> (bits_left - take)) & ((1 << take) - 1))
            bits_left -= take
            n -= take
        return v

    w = usize - 1
    end = 0
    while w >= end:
        if get(1):
            back = get(13) + 3
            length = 3
            for lvl in (2, 3, 5, 8):
                a = get(lvl)
                length += a
                if a != (1 << lvl) - 1:
                    break
            else:
                while True:
                    a = get(8)
                    length += a
                    if a != 0xFF:
                        break
            for _ in range(length):
                out[w] = out[w + back]
                w -= 1
        else:
            out[w] = get(8)
            w -= 1
    del pos_bits
    return bytes(prefix) + bytes(out)


def entries(path):
    buf = open(path, "rb").read()
    hdr = read_utf(buf, 0x10)[0]
    toc = hdr.get("TocOffset")
    content = hdr.get("ContentOffset")
    rows = read_utf(buf, toc + 0x10)
    base = min(toc, content) if content else toc
    res = []
    for r in rows:
        name = (r.get("DirName") or "") + "/" + r["FileName"]
        res.append((name.lstrip("/"), base + r["FileOffset"], r["FileSize"], r.get("ExtractSize") or r["FileSize"]))
    return buf, res


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    buf, ents = entries(path)
    if cmd == "list":
        for n, o, s, e in ents:
            print("%10d %10d %s" % (s, e, n))
        return
    outdir, filt = sys.argv[3], sys.argv[4:]
    for n, o, s, e in ents:
        if filt and not any(f in n for f in filt):
            continue
        d = buf[o:o + s]
        if d[:8] == b"CRILAYLA":
            d = crilayla(d)
        dst = os.path.join(outdir, n)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(d)
        print(n, len(d))


if __name__ == "__main__":
    main()
