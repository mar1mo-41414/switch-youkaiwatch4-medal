#!/usr/bin/env python3
"""nfc_lottery_config の全メダル種別 (NFC_INFO) を、抽選テーブル・アイテム名・フラグまで解決してテキストにする。

前提: cpk.py で gamedata.cpk / text_jp.cpk を gd/ に展開済み。
usage: medal_list.py > out/medal_list.txt

NFC_INFO の 18 フィールド (0x48 バイト) の解釈 (実機で確認したのは [0][1][4][17] と種別の仕組みだけ):
  [0] [1]  ID (36 進 3 文字を数値にしたもの)。min == max
  [2]      抽選テーブル ID。NFC_LOTTERY_INFO (カテゴリ 1〜7) ごとに同じ ID で別の中身がある。
           1 回の読み込みでどのカテゴリを引くかはゲーム本体 (funcLuaMenuNfcCommand) 側で、未解析
  [3]      0/1 (不明)
  [4]      妖怪 (chara_base のハッシュ)
  [5][8][9] 抽選テーブル (追加)
  [6]      特別抽選テーブル (カテゴリ 5 = アーク・装備などの限定アイテムにだけある)
  [10]     アイテム (装備品・大事なもの)
  [11]     0/1 (不明)
  [12][16] ゲームフラグ (flag_config の FLAG_INFO_PARAM。名前は無いので番号で出す)
  [17]     使用済み UID リストの選択 (0 = 永久に 1 回、それ以外 = 別リスト)
"""
import re

from cfgbin import parse

G = "gd/data/common/gamedata/"
T = "gd/data/common/text/ja/"
B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
NUM_BASE = 28652


def b36(n):
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = B36[r] + s
    return s


def clean(s):
    return re.sub(r"\[([^/\]]+)/[^\]]+\]", r"\1", s)


def cfg(path):
    return parse(open(path, "rb").read())


def nouns(path):
    return {v[0]: clean(v[5]) for k, v in cfg(path) if k == "NOUN_INFO" and isinstance(v[5], str)}


def main():
    nfc = cfg(G + "nfc/nfc_lottery_config.cfg.bin")
    info = [v for k, v in nfc if k == "NFC_INFO"]

    # 名前の解決用
    chara_names = nouns(T + "chara_text.cfg.bin")
    chara = {v[0]: chara_names.get(v[3], v[1]) for k, v in cfg(G + "character/chara_base_0.00.00.cfg.bin")
             if k == "CHARA_BASE_INFO"}
    item_names = nouns(T + "item_text.cfg.bin")
    item = {}
    item_kind = {}
    kinds = {"ITEM_CONSUME_INFO": "消費", "ITEM_EQUIP_INFO": "装備", "ITEM_SOUL_INFO": "魂",
             "ITEM_IMPORTANT_INFO": "大事"}
    for k, v in cfg(G + "item/item_config_0.13.66.cfg.bin"):
        if k in kinds:
            item[v[0]] = item_names.get(v[2], "?%08x" % (v[2] & 0xFFFFFFFF))
            item_kind[v[0]] = kinds[k]
    flags = {}
    for k, v in cfg(G + "system/flag_config_0.10.68.cfg.bin"):
        if k == "FLAG_INFO_PARAM":
            flags[v[1]] = v[0]

    def name(h):
        if h in item:
            return "%s[%s]" % (item[h], item_kind[h])
        if h in chara:
            return "妖怪:" + chara[h]
        return "?%08x" % (h & 0xFFFFFFFF)

    # 抽選テーブル
    tables = {}  # (カテゴリ, テーブル ID) -> [(アイテム, 値, 重み)]
    cat = cur = None
    for k, v in nfc:
        if k == "NFC_LOTTERY_INFO":
            cat = v[0]
        elif k == "NFC_LOTTERY_INFO_TABLE":
            cur = v[0]
            tables[(cat, cur)] = []
        elif k == "NFC_LOTTERY_INFO_TABLE_ITEM" and cur is not None:
            tables[(cat, cur)].append((v[0], v[1], v[2]))
    # 登場順に T01.. の名前を付ける
    tnames = {}
    for r in info:
        for fi in (2, 5, 8, 9):
            h = r[fi]
            if h and h not in tnames:
                tnames[h] = "T%02d" % (len(tnames) + 1)

    def tname(h):
        if not h:
            return None
        return tnames.get(h, "?%08x" % (h & 0xFFFFFFFF))

    def line(r):
        i = b36(r[0])
        n = r[0] - NUM_BASE
        parts = ["%s No.%s" % (i, "%04d" % n if n >= 0 else "----")]
        if r[4]:
            parts.append("妖怪:" + chara.get(r[4], "?%08x" % (r[4] & 0xFFFFFFFF)))
        parts.append("抽選:" + tname(r[2]))
        extra = [tname(r[fi]) for fi in (5, 8, 9) if r[fi]]
        if extra:
            parts.append("追加抽選:" + ",".join(extra))
        if r[6]:
            its = tables.get((5, r[6]), [])
            parts.append("特別:" + (" / ".join(name(h) for h, _, _ in its) or "?%08x" % (r[6] & 0xFFFFFFFF)))
        if r[10]:
            parts.append("アイテム:" + name(r[10]))
        fl = ["#%s" % flags.get(r[fi], "?%08x" % (r[fi] & 0xFFFFFFFF)) for fi in (12, 16) if r[fi]]
        if fl:
            parts.append("フラグ:" + ",".join(fl))
        if r[3] or r[11]:
            parts.append("[3]=%d [11]=%d" % (r[3], r[11]))
        parts.append("使用制限:" + ("永久1回" if r[17] == 0 else "別枠(%d)" % r[17]))
        return "  ".join(parts)

    rows = sorted(info, key=lambda r: r[0])
    print("# 妖怪ウォッチ4 妖怪アーク 種別一覧 (v2.2.0 RomFS: gamedata/nfc/nfc_lottery_config.cfg.bin)")
    print("# ID = 平文 5〜7 バイト目の 36 進 3 文字 / No. = シールの番号 (ID の数値 - 28652、負は ----)")
    print("# 使用制限: 永久1回 = 同じ UID は二度と使えない。別枠(n) = 別の使用済みリスト (n の意味は未確認)")
    print("# フィールドの解釈は medal_list.py の先頭を参照 (実機で確認したのは ID・妖怪・使用制限の仕組みだけ)")
    print()
    no = [r for r in rows if not r[4]]
    yes = [r for r in rows if r[4]]
    print("## 妖怪なし (%d 件)" % len(no))
    for r in no:
        print(line(r))
    print()
    print("## 妖怪つき (%d 件)" % len(yes))
    for r in yes:
        print(line(r))
    print()
    print("## 抽選テーブルの中身")
    print("# カテゴリ: 1/6 = けいけんちだま・こけし等、2 = 封魔のアーク、3 = コイン、4 = 数値のみ (個数か回数?)、")
    print("#           5 = 限定アイテム (アーク・装備。メダル行の「特別」)、7 = 食べ物")
    print("# 行: アイテム名[種類]  値 (カテゴリ 7 は個数らしい)  重み (テーブル内の確率)")
    cats = sorted({c for c, _ in tables})
    for h, t in sorted(tnames.items(), key=lambda x: x[1]):
        users = sum(1 for r in info if h in (r[2], r[5], r[8], r[9]))
        if not users:
            continue
        print()
        print("%s (%08x, 抽選/追加抽選で %d 件が使用)" % (t, h & 0xFFFFFFFF, users))
        for c in cats:
            items = tables.get((c, h))
            if not items:
                continue
            total = sum(w for _, _, w in items) or 1
            print("  [カテゴリ %d]" % c)
            for ih, val, w in items:
                nm = name(ih) if ih else "(なし)"
                print("    %-26s 値%-3d 重み %3d (%.1f%%)" % (nm, val, w, 100.0 * w / total))


if __name__ == "__main__":
    main()
