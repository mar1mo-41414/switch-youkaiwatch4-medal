# switch-youkaiwatch4-medal

[English README →](README-EN.md)

『妖怪ウォッチ4』(Switch) の妖怪アーク (NFC、NTAG213) のパスワード保護と暗号化を、ゲーム本体のコードから解析した結果と、
それを使うための小さなツール集。

- タグの UID からパスワード (PWD_AUTH) と暗号鍵を計算できる
- 保護領域 (ページ 28〜39) を復号できる。中身は `0315MCN` のような「シールの番号 + 3 文字の種別 ID」
- UID や種別 ID を変えたアークの `.nfc` (Flipper Zero 形式) を作れる。ゲーム実機で読み込めることを確認済み

Flipper Zero 単体で読み取り・複製をしたい場合は、アプリ版 [flipper-youkai-medal](https://github.com/mar1mo-41414/flipper-youkai-medal) を使う。

## 算出式

```
h1   = HMAC-SHA256(key = "DKtjn3JAZc", msg = UID 7 バイト)
h1'  = h1 の各バイトの上位/下位ニブルを SBOX で置換
       SBOX = [4, 9, 15, 0, 5, 10, 14, 1, 6, 11, 13, 2, 7, 12, 3, 8]
h2   = HMAC-SHA256(key = "5g9D63n8Mt", msg = h1')
PWD  = h2[28:32]   (PWD_AUTH: 1B PWD0 PWD1 PWD2 PWD3)
PACK = BE EF
保護データ (ページ 28〜39): AES-128-CTR、key = h2[0:16]、IV = (h2[24:32] || UID || 00) XOR (h2[0:15] || 00)
```

妖怪ウォッチ3 (3DS) の妖怪メダルと同じ構造で、鍵と置換表だけが違う。

## 使い方

Python 3 と `cryptography` パッケージが必要 (`pip install cryptography`)。

```bash
# パスワードを計算する
python3 work/medal_pwd.py "04 70 BC C2 DB 64 81"

# 読み出した保護データ (ページ 28〜39 の 48 バイト) を復号する
python3 work/medal_pwd.py --decrypt "04 70 BC C2 DB 64 81" "<48 バイトの hex>"

# アンロック済みのダンプ (Flipper の .nfc) から、UID を変えたアークを作る (UID 省略時は乱数)
python3 work/make_nfc.py unlocked.nfc new.nfc ["04 xx xx xx xx xx xx"]

# 別の種類のアークを作る (例: M88 = ジバニャン)
python3 work/make_nfc.py unlocked.nfc jibanyan.nfc --id M88
```

- 妖怪の ID 一覧: [docs/YOKAI_IDS.md](docs/YOKAI_IDS.md)
- ゲームは同じ UID のアークを 1 回しか読み込まない。使うたびに新しい UID で作る

## ドキュメント

- [docs/ANALYSIS.md](docs/ANALYSIS.md): ゲーム内部の処理 (該当アドレス、チェック内容、エラー、種別表、抽選)
- [docs/REPRODUCE.md](docs/REPRODUCE.md): 解析環境の再現手順と、`work/` のツールの説明
- [HISTORY.md](HISTORY.md): 調査の経緯

## 注意

- 自分が持っているアークのバックアップや動作確認を目的としたものです。
- 株式会社レベルファイブ・任天堂とは関係ありません。
- ゲームの ROM・鍵・データは含んでいません。解析を再現する場合は自分で吸い出したものを使ってください。

## ライセンス

[MIT](LICENSE)
