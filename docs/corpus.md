# The Jewel corpus: every kind of password and key, and where to get them

Plan for the training and test data behind a clipboard app's small local Jewel. Benchmark results: `benchmark.md`.

## How much data: types beat volume

Learning curve on the current Jewel model (`bench/curve.py`, 2026-10-05), judged on 300 fresh passwords from generators it never saw and on extra locks across the owner's real history:

| Fake passwords | Harmless lines | Fresh caught (of 300) | Extra locks on real history |
| - | - | - | - |
| 199 | 39,497 | 217 | 11 |
| 796 | 39,497 | 219 | 10 |
| 2,388 | 39,497 | 221 | 5 |
| 2,388 | 2,000 | 214 | 5 |
| 2,388 | 20,000 | 221 | 5 |

Twelve times more passwords of the same kinds moved the catch rate by 2%. The experiment loop (`bench/loop.py`, benchmark.md round 5) adds the mirror finding: seven feature configurations land within noise of each other, while everyday-shaped negatives move false alarms by 20-30 points. Data, not features. What it still misses (passphrases with spaces, CamelCase word passwords) are *kinds* it never saw. More harmless text mostly cuts false alarms. So the targets are:

- **Positives:** about 200-300 examples per kind, across every kind below (roughly 70-90 kinds, so 15,000-25,000 in all). Past that, returns are small.
- **Negatives:** 50,000-100,000 lines, as varied as possible (prose, code, links, ids, numbers, other languages), plus a hand-made set of look-alikes for every positive kind.
- **Tests:** whole kinds held out of training (a generator the model never saw), plus real history checked locally.

## The list

Status: **have** = in `bench/dataset.ts` today; **add** = still to generate. "Lock?" marks the cases that need a decision.

### A. Passwords people make up
| Kind | Example shape | Status |
| - | - | - |
| Word + year + symbol | `Summer2026!` | have |
| Word + symbol + word + digits | `maple#river42` | have |
| Two words + digits | `lanternpickle520` | have |
| CamelCase words + symbol | `MeadowRavenQuill?3` | add |
| Leetspeak | `P@ssw0rd!`, `Gl@c13r2024` | have (partly) |
| Name or pet + birth year | `Bella1998` | add |
| Keyboard walks | `qwerty123`, `1qaz2wsx`, `zaq12wsx` | add |
| Short and simple (6-8) | `monkey12`, `abc123` | add |
| Phrase without spaces | `ilovemydog2`, `letmein!` | add |
| Passphrase with spaces | `correct horse battery staple` | add (hard: looks like words) |
| Sentence-style | `MyCatIs7YearsOld!` | add |
| Non-English words | `contraseña2024`, `пароль123` | add |
| Repeated or patterned | `aaaa1111`, `123456789a` | add |

### B. Passwords from password managers and generators
| Kind | Format | Status |
| - | - | - |
| Apple Passwords / iCloud Keychain | 20 chars: 3 groups of 6 lowercase, hyphens, one capital, one digit | add (holdout uses it) |
| 1Password random | user-chosen length, letters/digits/symbols | have (random) |
| 1Password memorable | words, separator, optional capitals and digit | add |
| Bitwarden passphrase | `word-word-word`, optional capitalize and number | add |
| Bitwarden / LastPass / Dashlane random | length and sets vary | have (random) |
| Google Password Manager / Chrome | random, verify current format | add (check format) |
| KeePass / KeePassXC presets | random, hex, base64 | add |
| `pwgen` pronounceable | `ieGh5ahz` | add |
| Random alphanumeric, 8-64 | `k3Jd9QaZ...` | have |
| Random printable with symbols | `+9AA=A)9aaa...` | have |
| Hex, base64, URL-safe tokens | `9f2c...`, `aGVsbG8...`, `Xy-9_...` | have (partly) |

### C. Codes and numbers
| Kind | Format | Lock? | Status |
| - | - | - | - |
| One-time codes | 6 or 8 digits, `123 456` | yes | have |
| 2FA backup codes | lists of `xxxx-xxxx` or 8-10 digits | yes | add |
| Apple / account recovery keys | 28 chars in groups of 4 | yes | add |
| BitLocker / FileVault recovery keys | 48 digits in groups of 6 / groups of 4 | yes | add |
| PINs | 4 or 6 digits | decide (4 digits: too many false alarms) | have (6) |
| Wi-Fi passwords | `Network / password`, WPA keys | yes | add |
| Card number, expiry, CVV | Luhn-valid 13-19 digits | yes | have (rules) |
| Bank: IBAN, routing + account | mod-97 / ABA check | yes | have (IBAN) |
| SSN and other government ids | country formats | yes | have (US SSN) |
| Software license keys | `XXXXX-XXXXX-XXXXX-XXXXX` | decide | add |
| Gift card codes | 16 chars, retailer formats | decide (it's money) | add |
| Coupon and referral codes | `SAVE20`, `REF-AB12` | decide (usually public) | add as look-alike |

### D. Machine credentials
| Kind | Notes | Status |
| - | - | - |
| Provider API keys | ~180 formats in gitleaks, 900+ in TruffleHog; generate fakes from their regexes | have 8, add the rest |
| JWTs, OAuth access/refresh tokens, session cookies | | have (JWT) |
| `Authorization: Bearer` / `Basic` headers | | have (Bearer) |
| Connection strings with passwords | postgres, mysql, mongodb, redis, amqp | have (postgres) |
| Private keys | PEM, OpenSSH, PGP, age, PuTTY `.ppk` | have (most) |
| Crypto wallets | BIP39 seed phrases (12/24), `xprv`, WIF, raw hex | have |
| Webhook URLs | Slack, Discord, Teams webhooks (the URL is the key) | add |
| Signed and magic links | S3/GCS signatures, reset and sign-in links | have |
| Config files | `.env` blocks, AWS credentials, `.npmrc`, `.netrc`, kubeconfig, Docker `auth` | have (single lines), add blocks |
| Public keys | SSH, PEM, PGP | yes (owner) | have (rules) |

### E. Passwords inside other text
| Kind | Example | Status |
| - | - | - |
| Labeled | `Password: ...`, `pw: ...`, `pass = ...` | have |
| Login pairs | `jamie@example.com / Falcon50!`, `user: admin pass: ...` | have |
| In a message | "the wifi password is ...", "the door code is 4821" | have |
| Wi-Fi share text | `WIFI:S:Home;T:WPA;P:...;;` | add |
| In a table or CSV row | `site,username,password` exports | add |

### Look-alikes that must stay unlocked (negatives)
Prose that mentions passwords ("your password is incorrect"), code (identifiers, `password: string`, env lookups), git commit ids, UUIDs, version strings, file names and paths, links with long ids, emails, phone numbers, dates and times, order and tracking numbers, product codes, hex colors, math, usernames and @handles, hashtags, wallet addresses (decided: unlocked), coupon codes, short words, non-English text, plus the owner's real everyday copies (local testing only, never training data for a public model).

## Where to get it

| Source | What it gives | License / care |
| - | - | - |
| Our generators (`bench/dataset.ts`, `holdout.py`) | Every kind above, unlimited, nothing real | Ours |
| Password-manager docs (e.g. Apple's "Automatic strong passwords" page) | Exact generated formats | Read the formats; generate our own |
| EFF diceware word lists, BIP39 word list | Passphrases, seed phrases | EFF lists CC BY; BIP39 MIT |
| [gitleaks](https://github.com/gitleaks/gitleaks) rules (~180), [detect-secrets](https://github.com/Yelp/detect-secrets) (27 plugins) | Key formats to generate fakes from | MIT / Apache 2.0 |
| [TruffleHog](https://github.com/trufflesecurity/trufflehog) detectors (900+) | The widest list of key formats | AGPL: use as a reference list only, don't copy code |
| [CredData](https://github.com/Samsung/CredData) (Samsung) | 73,842 human-labeled code lines, 4,583 real credentials, by type | Real values from public repos: testing only, don't ship in a public model |
| [SecretBench](https://par.nsf.gov/servlets/purl/10505638) | 97,479 secrets from 818 repos, 15,084 hand-verified | Same care as CredData; access via BigQuery |
| Stack Exchange data dump, Wikipedia | Varied harmless text (questions, code snippets, prose) | CC BY-SA |
| The Stack v2 (Hugging Face) | Huge harmless code corpus | Per-repo licenses; terms apply |
| Our own repos' tracked files | Harmless code and docs (used today) | Private: fine for a private model, not for a public one |
| Leaked password lists (e.g. RockYou) | How real people choose passwords | Real people's passwords: don't train on or store them; at most learn structures from published research |
| Jev (gold standard), Laya, our rules | Labels for unlabeled harmless text; finding mistakes | Jev costs money; only send public or fake text |
| The owner's history | The real test of false alarms | Local only, counts and masked shapes, never sent or trained on for a public model |

## Is that all there is to it?

Data is most of the work, but not all:

1. **Decisions:** which ambiguous kinds to lock (PINs, license keys, gift cards, coupons).
2. **Features and model:** character patterns plus a few counts work for one-token passwords; passwords inside sentences need context, which the rules (or a small transformer) cover.
3. **Thresholds:** pick the trade-off between missed passwords and false alarms per layer.
4. **Honest testing:** hold out whole kinds, and check real history locally.
5. **Shipping:** prune the weights, export to JSON or ONNX, and run it in the app in under a millisecond.
6. **Keeping it current:** new key formats appear every month; every real miss becomes a new generator and the model is retrained and re-benchmarked.
