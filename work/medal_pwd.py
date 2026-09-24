#!/usr/bin/env python3
"""妖怪ウォッチ4 (Switch) の NFC 妖怪メダル (NTAG213) の PWD_AUTH パスワード / データ鍵の算出。

main NSO (v2.2.0) の 0x724550 を Python に移植したもの (3DS 版と同じ構造で鍵と置換表だけ違う):
  h1  = HMAC-SHA256(key=b"DKtjn3JAZc", msg=UID(7 bytes))
  h1' = h1 の各バイトの上位/下位ニブルを SBOX で置換
  h2  = HMAC-SHA256(key=b"5g9D63n8Mt", msg=h1')
  PWD  = h2[28:32]          (PWD_AUTH 0x1B の後ろにこの順で送る)
  PACK = BE EF              (ゲームが期待する応答, 0x959858 で比較)
  AES-128-CTR key = h2[0:16]
  AES-128-CTR IV  = (h2[24:32] || UID || 00) XOR (h2[0:15] || 00)
保護データ = ページ 28-39 の 48 バイト (FAST_READ 0x3A で 28-42 を読む) (16 バイト x 3 ブロック)。
各ブロックの最終バイトは先頭 15 バイトの和 (mod 256) のチェックサム。

usage:
  python3 medal_pwd.py "04 70 BC C2 DB 64 81" [...]
  python3 medal_pwd.py --decrypt <UID hex> <pages28-39 hex (48 bytes)>
"""
import hashlib
import hmac
import sys

KEY1 = b"DKtjn3JAZc"   # v2.2.0 main: 0x1299977
KEY2 = b"5g9D63n8Mt"   # v2.2.0 main: 0x1299982
# v2.2.0 main: 0x1257c20 の (nibble, 置換後) ペア表
SBOX = [4, 9, 15, 0, 5, 10, 14, 1, 6, 11, 13, 2, 7, 12, 3, 8]


def derive(uid: bytes):
    assert len(uid) == 7, "UID must be 7 bytes"
    h1 = hmac.new(KEY1, uid, hashlib.sha256).digest()
    h1s = bytes(SBOX[b & 0xF] | (SBOX[b >> 4] << 4) for b in h1)
    h2 = hmac.new(KEY2, h1s, hashlib.sha256).digest()
    pwd = h2[28:32]
    key = h2[0:16]
    iv = bytes(a ^ b for a, b in zip(h2[24:32] + uid + b"\0", h2[0:15] + b"\0"))
    return pwd, key, iv


def decrypt(uid: bytes, data: bytes):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    _, key, iv = derive(uid)
    dec = Cipher(algorithms.AES(key), modes.CTR(iv)).decryptor()
    plain = dec.update(data) + dec.finalize()
    ok = [sum(plain[i:i + 15]) & 0xFF == plain[i + 15] for i in range(0, len(plain), 16)]
    return plain, ok


def _hex(s):
    return bytes.fromhex(s.replace(" ", "").replace(":", ""))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--decrypt"]:
        plain, ok = decrypt(_hex(args[1]), _hex(args[2]))
        print(plain.hex(" ").upper())
        print("checksum per block:", ok)
        sys.exit(0)
    for arg in args:
        uid = _hex(arg)
        pwd, key, iv = derive(uid)
        print("UID %s  PWD %s  PACK BE EF  key %s  iv %s"
              % (uid.hex(" ").upper(), pwd.hex(" ").upper(), key.hex(), iv.hex()))
