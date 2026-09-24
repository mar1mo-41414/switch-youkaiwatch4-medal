#!/usr/bin/env python3
"""Lua 5.2 バイトコード (.lua.bin, "\\x1bLuaR") の簡易逆アセンブラ。
usage: luadis.py <file.lua.bin> [関数名の部分一致...]
"""
import struct
import sys

OPS = ["MOVE", "LOADK", "LOADKX", "LOADBOOL", "LOADNIL", "GETUPVAL", "GETTABUP", "GETTABLE", "SETTABUP",
       "SETUPVAL", "SETTABLE", "NEWTABLE", "SELF", "ADD", "SUB", "MUL", "DIV", "MOD", "POW", "UNM", "NOT", "LEN",
       "CONCAT", "JMP", "EQ", "LT", "LE", "TEST", "TESTSET", "CALL", "TAILCALL", "RETURN", "FORLOOP", "FORPREP",
       "TFORCALL", "TFORLOOP", "SETLIST", "CLOSURE", "VARARG", "EXTRAARG"]


class R:
    def __init__(self, d):
        self.d = d
        self.p = 0

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def u64(self):
        v = struct.unpack_from("<Q", self.d, self.p)[0]
        self.p += 8
        return v

    def dbl(self):
        v = struct.unpack_from("<d", self.d, self.p)[0]
        self.p += 8
        return v

    def string(self, sz_t):
        n = self.u64() if sz_t == 8 else self.i32()
        if n == 0:
            return None
        s = self.d[self.p:self.p + n - 1]
        self.p += n
        return s.decode("utf-8", "replace")


def func(r, sz_t, depth=0):
    f = {}
    f["line"] = r.i32()
    r.i32()
    r.u8(), r.u8(), r.u8()
    n = r.i32()
    f["code"] = [struct.unpack_from("<I", r.d, r.p + 4 * i)[0] for i in range(n)]
    r.p += 4 * n
    n = r.i32()
    ks = []
    for _ in range(n):
        t = r.u8()
        if t == 0:
            ks.append(None)
        elif t == 1:
            ks.append(bool(r.u8()))
        elif t == 3:
            v = r.dbl()
            ks.append(int(v) if v == int(v) else v)
        elif t == 4:
            ks.append(r.string(sz_t))
        else:
            raise ValueError("const type %d" % t)
    f["k"] = ks
    n = r.i32()
    f["protos"] = [func(r, sz_t, depth + 1) for _ in range(n)]
    n = r.i32()
    r.p += 2 * n  # upvalues (instack, idx)
    f["source"] = r.string(sz_t)
    n = r.i32()
    r.p += 4 * n  # lineinfo
    n = r.i32()
    f["locals"] = []
    for _ in range(n):
        f["locals"].append(r.string(sz_t))
        r.i32(), r.i32()
    n = r.i32()
    f["upvals"] = [r.string(sz_t) for _ in range(n)]
    return f


def rk(f, x):
    if x & 0x100:
        k = f["k"][x & 0xFF]
        return repr(k)
    return "R%d" % x


def dump(f, name="main", ind=""):
    print("%sfunction %s (line %d)" % (ind, name, f["line"]))
    for pc, ins in enumerate(f["code"]):
        op = ins & 0x3F
        a = (ins >> 6) & 0xFF
        c = (ins >> 14) & 0x1FF
        b = (ins >> 23) & 0x1FF
        bx = ins >> 14
        sbx = bx - 131071
        o = OPS[op] if op < len(OPS) else "OP%d" % op
        if o == "LOADK":
            s = "R%d = %r" % (a, f["k"][bx])
        elif o in ("GETTABUP",):
            up = f["upvals"][b] if b < len(f["upvals"]) else b
            s = "R%d = %s[%s]" % (a, up, rk(f, c))
        elif o == "SETTABUP":
            up = f["upvals"][a] if a < len(f["upvals"]) else a
            s = "%s[%s] = %s" % (up, rk(f, b), rk(f, c))
        elif o == "GETTABLE":
            s = "R%d = R%d[%s]" % (a, b, rk(f, c))
        elif o == "SETTABLE":
            s = "R%d[%s] = %s" % (a, rk(f, b), rk(f, c))
        elif o == "SELF":
            s = "R%d = R%d; R%d = R%d[%s]" % (a + 1, b, a, b, rk(f, c))
        elif o in ("EQ", "LT", "LE"):
            s = "if (%s %s %s) != %d then pc++" % (rk(f, b), {"EQ": "==", "LT": "<", "LE": "<="}[o], rk(f, c), a)
        elif o == "JMP":
            s = "-> %d" % (pc + 1 + sbx)
        elif o in ("FORLOOP", "FORPREP"):
            s = "R%d -> %d" % (a, pc + 1 + sbx)
        elif o == "CALL":
            s = "R%d(%d args) -> %d rets" % (a, b - 1, c - 1)
        elif o == "GETUPVAL":
            s = "R%d = up:%s" % (a, f["upvals"][b] if b < len(f["upvals"]) else b)
        elif o == "CLOSURE":
            s = "R%d = closure #%d" % (a, bx)
        elif o in ("ADD", "SUB", "MUL", "DIV", "MOD"):
            s = "R%d = %s %s %s" % (a, rk(f, b), {"ADD": "+", "SUB": "-", "MUL": "*", "DIV": "/", "MOD": "%"}[o],
                                     rk(f, c))
        else:
            s = "A=%d B=%d C=%d" % (a, b, c)
        print("%s  %4d %-9s %s" % (ind, pc, o, s))
    for i, p in enumerate(f["protos"]):
        dump(p, "%s/#%d" % (name, i), ind + "  ")


def names(f):
    """closure を代入している名前 (SETTABUP _ENV["Name"]) を集める"""
    res = {}
    code = f["code"]
    for pc, ins in enumerate(code):
        if ins & 0x3F == 37 and pc + 1 < len(code):  # CLOSURE
            a = (ins >> 6) & 0xFF
            bx = ins >> 14
            nxt = code[pc + 1]
            if nxt & 0x3F == 8 and (nxt >> 14) & 0x1FF == a:
                b = (nxt >> 23) & 0x1FF
                if b & 0x100:
                    res[bx] = f["k"][b & 0xFF]
    return res


def main():
    d = open(sys.argv[1], "rb").read()
    assert d[:5] == b"\x1bLuaR", "not Lua 5.2"
    sz_t = d[8]  # ヘッダ: sig(4) ver fmt endian sizeof(int) sizeof(size_t) ... + LUAC_TAIL(6) = 18 バイト
    r = R(d)
    r.p = 18
    top = func(r, sz_t)
    nm = names(top)
    want = sys.argv[2:]
    if not want:
        dump(top)
        return
    for i, p in enumerate(top["protos"]):
        n = nm.get(i, "#%d" % i)
        if any(w in str(n) for w in want):
            dump(p, n)


if __name__ == "__main__":
    main()
