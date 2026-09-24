#!/usr/bin/env python3
"""アンロック済みの Flipper .nfc から、UID を差し替えたメダルの .nfc を作る。

元ダンプのページ 28-39 を元 UID の鍵で復号し、新 UID の鍵で暗号化し直す。
あわせて UID / BCC (ページ 0-2)、PWD (ページ 43)、PACK (ページ 44) を書き換える。
Signature (NXP の署名) は元のまま残す (ゲームは READ_SIG を送らないので確認されない)。

usage:
  make_nfc.py <src.nfc> <out.nfc> [UID hex]     # UID を省略すると 04 始まりの乱数
  make_nfc.py <src.nfc> <out.nfc> <UID hex> --plain <48 バイト hex>   # 平文を差し替える
  make_nfc.py <src.nfc> <out.nfc> [UID hex] --id M88                  # 種別 ID から平文を作る (YW4)

--id: 平文 = "<番号 4 桁><ID 3 文字>" + 0 埋め (チェックサムは自動)。番号 = 36 進 ID の数値 - 28652
      (シールの A 番号。ゲームは使っていないので、負になる ID では 0000 にする)。
"""
import os
import re
import sys

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from medal_pwd import _hex, decrypt, derive

DATA_FIRST, DATA_LAST = 28, 39
ID_NUM_BASE = 28652  # シールの番号 = int(ID, 36) - 28652 (MCN=315, MD2=330 で確認)


def read_nfc(path):
    lines = open(path).read().splitlines()
    pages = {}
    for ln in lines:
        m = re.match(r"Page (\d+): (.*)", ln)
        if m:
            pages[int(m.group(1))] = _hex(m.group(2))
    uid = _hex(next(ln for ln in lines if ln.startswith("UID:")).split(":", 1)[1])
    return lines, pages, uid


def fix_checksums(plain):
    b = bytearray(plain)
    for i in range(0, len(b), 16):
        b[i + 15] = sum(b[i:i + 15]) & 0xFF
    return bytes(b)


def encrypt(uid, plain):
    _, key, iv = derive(uid)
    enc = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()
    return enc.update(plain) + enc.finalize()


def main():
    args = sys.argv[1:]
    plain_override = None
    if "--id" in args:
        i = args.index("--id")
        mid = args[i + 1].upper()
        del args[i:i + 2]
        assert len(mid) == 3 and mid.isalnum(), "ID は 36 進 3 文字"
        num = max(int(mid, 36) - ID_NUM_BASE, 0)
        plain_override = ("%04d%s" % (num, mid)).encode() + bytes(41)
    if "--plain" in args:
        i = args.index("--plain")
        plain_override = _hex(args[i + 1])
        del args[i:i + 2]
    src, out = args[0], args[1]
    new_uid = _hex(args[2]) if len(args) > 2 else b"\x04" + os.urandom(6)
    assert len(new_uid) == 7 and new_uid[0] == 0x04, "UID は 04 で始まる 7 バイト"

    lines, pages, old_uid = read_nfc(src)
    assert all(p in pages for p in range(0, 45)), "ページ 0-44 がすべて読めているダンプが必要"
    data = b"".join(pages[p] for p in range(DATA_FIRST, DATA_LAST + 1))
    plain, ok = decrypt(old_uid, data)
    assert all(ok), "元ダンプの復号でチェックサムが合わない (UID かデータが違う)"
    if plain_override is not None:
        assert len(plain_override) == 48
        plain = fix_checksums(plain_override)

    enc = encrypt(new_uid, plain)
    pwd, _, _ = derive(new_uid)
    u = new_uid
    bcc0 = 0x88 ^ u[0] ^ u[1] ^ u[2]
    bcc1 = u[3] ^ u[4] ^ u[5] ^ u[6]
    new_pages = dict(pages)
    new_pages[0] = bytes([u[0], u[1], u[2], bcc0])
    new_pages[1] = u[3:7]
    new_pages[2] = bytes([bcc1]) + pages[2][1:]
    for i, p in enumerate(range(DATA_FIRST, DATA_LAST + 1)):
        new_pages[p] = enc[i * 4:i * 4 + 4]
    new_pages[43] = pwd
    new_pages[44] = b"\xBE\xEF" + pages[44][2:]

    fmt = lambda b: b.hex(" ").upper()
    res = []
    for ln in lines:
        m = re.match(r"Page (\d+): ", ln)
        if m:
            ln = "Page %d: %s" % (int(m.group(1)), fmt(new_pages[int(m.group(1))]))
        elif ln.startswith("UID:"):
            ln = "UID: " + fmt(new_uid)
        res.append(ln)
    open(out, "w").write("\n".join(res) + "\n")

    check, ok2 = decrypt(new_uid, enc)
    assert check == plain and all(ok2)
    print("UID  %s\nPWD  %s  PACK BE EF\nplain %s" % (fmt(new_uid), fmt(pwd), fmt(plain[:16])))


if __name__ == "__main__":
    main()
