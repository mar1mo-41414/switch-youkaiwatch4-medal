# 解析環境の再現

ゲームの ROM と鍵は自分の本体から吸い出したものを使う。このリポジトリには含まれていない。

## 1. ExeFS / RomFS の取り出し

[hactoolnet](https://github.com/Thealexbarney/LibHac) を使う。鍵は `~/.switch/prod.keys` と `~/.switch/title.keys` に置く。

```bash
# アップデート (NSP) を展開して Program NCA を探す
hactoolnet -t pfs0 Youkai-Watch4_v2.2.0.nsp --outdir upd
hactoolnet -t nca upd/<NCA>.nca          # Content Type: Program のものを探す

# ExeFS (main / sdk / rtld / main.npdm)。アップデートの NCA 単体で揃っている
hactoolnet -t nca upd/<Program NCA>.nca --exefsdir exefs

# RomFS はベース (XCI の secure パーティション) と重ねて取り出す
hactoolnet -t xci Youkai-Watch4.xci --securedir base
hactoolnet -t nca --basenca base/<Program NCA>.nca upd/<Program NCA>.nca --romfsdir romfs
```

解析に必要なのは ExeFS (約 18MB) と、RomFS の `data/common/gamedata*.cpk`、`data/common/text/text_jp.cpk`、
`data/common/script.cpk` だけ。

## 2. 実行コードの解析

```bash
cd work
python3 nso2bin.py exefs/main main.bin      # LZ4 を展開したフラットイメージ + main.bin.json (MOD0 / dynamic)
python3 nso2bin.py elf main.bin main.elf    # Ghidra などで開く用に PT_LOAD / PT_DYNAMIC だけの ELF に包む
python3 plt.py                              # PLT スタブ → import 名 (plt.json)
python3 disa.py 724550 724850               # capstone で逆アセンブル (import 名つき)
```

`nn::crypto::GenerateHmacSha256Mac` と `nn::nfc::SendCommandByPassThrough` の呼び出し元を追うと、
算出処理 (`0x724550`) と PWD_AUTH の送信 (`0x9597d8`) にすぐたどり着く。

## 3. ゲームデータの解析

```bash
cd work
python3 cpk.py extract romfs/gamedata.cpk gd
python3 cpk.py extract romfs/text_jp.cpk gd
python3 medal_table.py            # 種別 ID → 妖怪名
python3 medal_list.py > list.txt  # 全種別の報酬 (抽選テーブル・限定報酬・アイテム)
python3 cfgbin.py gd/data/common/gamedata/nfc/nfc_lottery_config.cfg.bin
```

## work/ のツール

| ファイル | 内容 |
|---|---|
| `medal_pwd.py` | パスワード・鍵の算出、保護データの復号 |
| `make_nfc.py` | UID / 種別 ID を変えた Flipper 用 `.nfc` の作成 |
| `nso2bin.py` | NSO → フラットイメージ / ELF |
| `plt.py` | PLT スタブと import 名の対応表 |
| `disa.py` | capstone による簡易逆アセンブラ (要 `pip install capstone`) |
| `cpk.py` | CRI CPK の一覧・展開 (CRILAYLA 対応) |
| `cfgbin.py` | Level-5 cfg.bin のダンプ |
| `medal_table.py` | 種別 ID → 妖怪名の一覧 |
| `medal_list.py` | 全種別の報酬の一覧 |
| `luadis.py` | Lua 5.2 バイトコード (`*.lua.bin`) の簡易逆アセンブラ |
