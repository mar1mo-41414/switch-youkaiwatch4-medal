#!/usr/bin/env python3
"""nfc_lottery_config の NFC_INFO (メダル種別) を妖怪名つきで一覧にする。

前提: cpk.py で gamedata.cpk / text_jp.cpk を gd/ に展開済み。
usage: medal_table.py [ID(3文字, 例 MCN)...]
列: ID(36進) 数値 フラグ(+0x44: 0=永久に1回, 非0=1日単位?) 抽選テーブル キャラ名 図鑑連番
"""
import struct
import sys

from cfgbin import parse

G = "gd/data/common/gamedata/"
B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def b36(n):
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = B36[r] + s
    return s


def load():
    info = [v for k, v in parse(open(G + "nfc/nfc_lottery_config.cfg.bin", "rb").read()) if k == "NFC_INFO"]
    names = {}
    for k, v in parse(open("gd/data/common/text/ja/chara_text.cfg.bin", "rb").read()):
        if k == "NOUN_INFO" and isinstance(v[5], str):
            names[v[0]] = v[5]
    chara = {}
    for k, v in parse(open(G + "character/chara_base_0.00.00.cfg.bin", "rb").read()):
        if k == "CHARA_BASE_INFO":
            chara[v[0]] = names.get(v[3], v[1])
    # dictionary_config (RDBN 形式): ffff... の後に [u16 idx, u16 2, hash, ?, ?, u32 1, u16 0, u16 連番]
    d = open(G + "dictionary/dictionary_config_5.00.20.cfg.bin", "rb").read()
    dic = {}
    p = 0
    while True:
        p = d.find(b"\xff" * 16, p)
        if p < 0:
            break
        q = p
        while q < len(d) and d[q] == 0xFF:
            q += 1
        if q + 24 <= len(d) and d[q + 2:q + 4] == b"\x02\x00":
            h = struct.unpack_from("<i", d, q + 4)[0]
            dic.setdefault(h, struct.unpack_from("<H", d, q + 22)[0])
        p = q
    return info, chara, dic


def main():
    info, chara, dic = load()
    want = set(sys.argv[1:])
    for v in sorted(info, key=lambda r: r[0]):
        i = b36(v[0])
        if want and i not in want:
            continue
        c = v[4]
        print("%s %6d flag=%-2d lot=%08x %s %s" % (
            i, v[0], v[17], v[2] & 0xFFFFFFFF,
            chara.get(c, "-" if c == 0 else "?%08x" % (c & 0xFFFFFFFF)),
            dic.get(c, "")))


if __name__ == "__main__":
    main()
