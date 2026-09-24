# switch-youkaiwatch4-medal

[日本語 README →](README.md)

Reverse-engineering notes and small tools for the NFC Yo-kai Arks (NTAG213) of *Yo-kai Watch 4* (Switch):
how the PWD_AUTH password and the data encryption key are derived from the tag UID.

- Compute the password and keys from the UID
- Decrypt the protected area (pages 28-39). The plaintext is "sticker number + 3-char type ID", e.g. `0315MCN`
- Build Flipper Zero `.nfc` files with another UID or another ark type (verified on the real game)

For reading/cloning on the Flipper itself, see the app [flipper-youkai-medal](https://github.com/mar1mo-41414/flipper-youkai-medal).

## Derivation

```
h1   = HMAC-SHA256(key = "DKtjn3JAZc", msg = 7-byte UID)
h1'  = substitute both nibbles of each byte of h1 via SBOX
       SBOX = [4, 9, 15, 0, 5, 10, 14, 1, 6, 11, 13, 2, 7, 12, 3, 8]
h2   = HMAC-SHA256(key = "5g9D63n8Mt", msg = h1')
PWD  = h2[28:32], PACK = BE EF
Data (pages 28-39): AES-128-CTR, key = h2[0:16], IV = (h2[24:32] || UID || 00) XOR (h2[0:15] || 00)
```

Same structure as the Yo-kai Watch 3 (3DS) medals; only the keys and the S-box differ.

## Usage

Requires Python 3 and `cryptography`.

```bash
python3 work/medal_pwd.py "04 70 BC C2 DB 64 81"
python3 work/medal_pwd.py --decrypt "<UID>" "<48 bytes of pages 28-39 in hex>"
python3 work/make_nfc.py unlocked.nfc new.nfc                 # same ark, new random UID
python3 work/make_nfc.py unlocked.nfc jibanyan.nfc --id M88   # another ark type
```

The game accepts each UID only once. Yo-kai type IDs: [docs/YOKAI_IDS.md](docs/YOKAI_IDS.md).
Details (Japanese): [docs/ANALYSIS.md](docs/ANALYSIS.md), [docs/REPRODUCE.md](docs/REPRODUCE.md).

## Notes

Intended for backing up and testing arks you own. Not affiliated with LEVEL-5 or Nintendo.
No ROMs, keys or game data are included.

## License

[MIT](LICENSE)
