# /// script
# requires-python = ">=3.11"
# dependencies = ["scikit-learn", "numpy", "scipy"]
# ///
"""Jewel's trainer: the one file autoresearch edits. The baseline is Jewel 1's recipe.

    uv run research/train.py > research/run.log 2>&1 && grep "^fp94:" research/run.log

Everything here is fair game: the training data (which fake passwords and how many,
everyday-shaped negatives, class weights), the feature configuration (within what
runtime/jewel.ts supports: char_n, shape_n, boundary, dense, dim), the linear model
and its regularisation, the pruning threshold. prepare.py scores the pruned result
on the frozen exam and prints the summary; it is never edited here.
"""
from __future__ import annotations

import random
import string
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(ROOT / "research"))
import numpy as np
from sklearn.linear_model import LogisticRegression

import prepare
from jewel import DEFAULT_FEATURES, gated, matrix

t_start = time.time()

# ---- data -------------------------------------------------------------------
# 12 seeds of bench/dataset.ts (never the test seed): about 2,300 fake passwords, keys and
# codes plus 2,100 look-alikes; and about 39,000 harmless lines from our repos. prepare.py has
# already removed every text that is also in the exam.
cases = prepare.train_cases()
negatives = prepare.train_negatives()
texts = [c["text"] for c in cases] + negatives
labels = [int(c["locked"]) for c in cases] + [0] * len(negatives)

# ---- generated data ---------------------------------------------------------
# Run oct5 found the recipe one step at a time under a rule that let the threshold slide;
# under the recall floors every step on its own dips (everyday negatives alone pull the wild
# passwords down with the copies, human-shaped positives alone dilute the generated ones), so
# the whole contrast is taught in one step. The exam rewards whatever separates Thursday2026
# from thursday26!: everyday-shaped negatives show the tags, human-shaped positives the
# passwords, machine-shaped positives keep the generated passwords up (repo code had taught
# the model that + = % - mean "not a password": the weakest benchmark positive is an 8-char
# generated password with + and =, and the fresh tail is random_full and random_alnum).


def draw(n: int, seed: int, make) -> list[str]:
    """n distinct gated texts from make(rng)'s patterns; exact exam texts are dropped by prepare.clean."""
    rng = random.Random(seed)
    pats = make(rng)
    out: list[str] = []
    seen: set[str] = set()
    while len(out) < n:
        t = rng.choice(pats)()
        if t in seen or not gated(t):
            continue
        seen.add(t)
        out.append(t)
    return prepare.clean(out)


# Everyday-shaped negatives: ordinary copies the model must leave alone (word+year tags, report
# names, CamelCase phrases with and without digits, snake identifiers, version strings, order codes,
# product models such as Word+Letter+digits, platform versions such as Word+1.2). Own word list, disjoint
# from the exam, and no literal under four letters that is an exam token: the peek check cannot see those,
# and the gain of such a token is the token, not the shape (609b8d4). Pro (in four product copies), At (a
# lunch time), pm (a call time) and the INV/ORD/PO/CASE code prefixes (one copy each) sat in 3d517a6's
# generator and are gone; the short literals that stay were counted against the exam: Q and v are the
# report-tag and semver syntax (like the dots and dashes, not words) and am/th/st, the semver tags and the
# code prefixes match no copy. No lowercase-kebab-with-number pattern: it shadows dashed password-manager
# strings (fresh memorable_dash, safari), and repo text already teaches kebab-case.
EW = ["Tuesday", "Friday", "January", "March", "July", "Winter", "Spring", "Autumn", "Holiday", "Vacation", "Project", "Launch", "Memo",
      "Photos", "Trip", "Paris", "London", "Berlin", "Tokyo", "Austin", "Denver", "Seattle", "Boston", "Lisbon", "Surface", "Roomba", "Vespa",
      "Honda", "Toyota", "Lego", "Nikon", "Canon", "Garmin", "Peloton", "Dyson", "Nespresso", "Garden", "Kitchen", "Studio", "Family", "Reunion",
      "Concert", "Festival", "Recipe", "Workout", "Payroll", "Hiring", "Onboarding", "Pricing", "Design", "Backend", "Mobile", "Alpha"]
EL = [w.lower() for w in EW]


def everyday_pats(rng: random.Random) -> list:
    W, L = lambda: rng.choice(EW), lambda: rng.choice(EL)
    year = lambda: str(rng.randint(2019, 2031))
    return [
        lambda: W() + year(),
        lambda: W() + W() + year(),
        lambda: f"Q{rng.randint(1, 4)}{W()}{year()}",
        lambda: W() + W() + str(rng.randint(1, 99)),
        lambda: W() + str(rng.randint(2, 20)) + W(),
        lambda: W() + W() + W(),
        lambda: f"{L()}_{L()}_{L()}",
        lambda: f"{L().upper()}_{L().upper()}",
        lambda: f"{W()}{W()}{W()}{rng.randint(2, 17)}",
        lambda: f"v{rng.randint(0, 9)}.{rng.randint(0, 30)}.{rng.randint(0, 99)}-{rng.choice(['alpha', 'rc1', 'dev'])}",
        lambda: f"{rng.choice(['REF', 'TKT', 'REQ', 'DOC', 'JOB', 'RMA'])}-{rng.randint(2019, 2031)}-{rng.randint(10, 9999):04d}",
        lambda: f"{W()}{rng.randint(1, 31)}{rng.choice(['am', 'th', 'st'])}",
        lambda: f"{L()}{rng.randint(1, 12)}{L()}",
        # product models and platform versions: the two everyday kinds still locked most (9/20 and 7/16)
        lambda: f"{W()}{rng.choice(string.ascii_uppercase)}{rng.randint(1, 30)}",
        lambda: W() + ".".join(str(rng.randint(0, 30)) for _ in range(rng.choice([2, 3]))),
        lambda: f"{rng.randint(0, 12)}.{rng.randint(0, 30)}.{rng.randint(0, 99)}{rng.choice(['rc', 'b', 'a', '-dev', '-alpha'])}{rng.randint(1, 9)}",
    ]


# Human-shaped positives: two thirds of real passwords are a word or name plus digits
# (monkey12, jessica1990, iloveyou123, qwerty1234) and bench/dataset.ts makes almost none of
# that shape. Lowercase word + digits, name + birth year, digits first, keyboard walks,
# repeats and Capitalized word + digits + symbol: the contrast with the tags above.
NAMES = ["jessica", "michael", "ashley", "daniel", "andrew", "joshua", "matthew", "amanda", "nicole", "jennifer", "anthony", "brandon",
         "samantha", "justin", "robert", "william", "thomas", "stephanie", "elizabeth", "kevin", "jason", "tyler", "melissa", "brittany",
         "jonathan", "heather", "rachel", "lauren", "megan", "emily", "sarah", "hannah", "jacob", "nathan", "zachary", "kayla", "alexis",
         "christina", "rebecca", "danielle", "victoria", "natalie", "olivia", "sophia", "isabella", "chloe", "lucas", "ethan", "logan",
         "carlos", "miguel", "diego", "sofia", "lucia", "pedro", "pablo", "andrea", "marco", "giulia", "pierre", "louis", "marie",
         "camille", "felix", "jonas", "oliver", "harry", "george", "charlie", "oscar", "james", "amelia", "ahmed", "fatima", "priya", "rahul"]
PWORDS = ["iloveyou", "letmein", "monkey", "dragon", "hunter", "soccer", "football", "baseball", "basketball", "princess", "sunshine",
          "butterfly", "chocolate", "whatever", "superman", "batman", "pokemon", "starwars", "freedom", "jordan", "harley", "ranger",
          "cowboy", "mustang", "yankees", "cheese", "pepper", "ginger", "cookie", "banana", "chicken", "flower", "angel", "tigger",
          "buster", "jasmine", "lovely", "metallica", "nirvana", "trustno", "killer", "rockstar", "sweety", "peanut", "pumpkin", "scooby",
          "spider", "thunder", "scooter", "maggie", "bailey", "sparky"]
ALL = NAMES + PWORDS
SUFFIX = ["1", "12", "123", "1234", "12345", "123456", "11", "22", "69", "99", "007", "100", "2013", "2014", "2015", "01", "07", "13", "21", "77", "88"]
KEYS = ["qwerty", "qwertyuiop", "1qaz2wsx", "1q2w3e4r", "zaq12wsx", "asdfgh", "qazwsx", "1q2w3e4r5t", "asdfjkl", "zxcvbnm", "qweasd", "qweasdzxc"]
REPEATS = ["abcd1234", "a1b2c3d4", "aaaa1111", "123456789a", "abc123abc", "12345678a", "1234abcd", "aabbccdd", "abcabc123", "a123456",
           "abc12345", "123abc123", "aaaaaa1", "1234567a", "qwe123qwe"]


def human_pats(rng: random.Random) -> list:
    A, N = lambda: rng.choice(ALL), lambda: rng.choice(NAMES)
    year = lambda: str(rng.randint(1960, 2008))
    digits = lambda: rng.choice(SUFFIX)
    sym = lambda: rng.choice("!@#$*.")
    return [
        lambda: A() + digits(),
        lambda: A() + digits(),
        lambda: A() + str(rng.randint(0, 99)),
        lambda: N() + year(),
        lambda: N() + year(),
        lambda: A() + A() + str(rng.randint(1, 99)),
        lambda: "ilove" + N() + rng.choice(["", "1", "12", "123"]),
        lambda: digits() + A(),
        lambda: A() + f"{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}" + rng.choice(["", year()[2:]]),
        lambda: A().capitalize() + digits() + sym(),
        lambda: A().capitalize() + year() + sym(),
        lambda: A() + sym() + digits(),
        lambda: A() + digits() + sym(),
        lambda: rng.choice(KEYS) + rng.choice(["", "1", "12", "123", "1234", "12345"]),
        lambda: rng.choice(REPEATS) + rng.choice(["", "1", "a", "!", "123"]),
    ]


# Machine-shaped positives: random strings over letters, digits and all ASCII punctuation
# (mostly short, where every n-gram weighs a lot), plain alphanumerics and hex. They keep the
# generated passwords, tokens and hashes scoring high while the data above is about words.
def machine_pats(rng: random.Random) -> list:
    full = string.ascii_letters + string.digits + string.punctuation
    alnum = string.ascii_letters + string.digits
    s = lambda alphabet, n: "".join(rng.choice(alphabet) for _ in range(n))
    return [
        lambda: s(full, rng.randint(8, 20)),
        lambda: s(full, rng.randint(8, 20)),
        lambda: s(full, rng.randint(8, 12)),
        lambda: s(alnum, rng.randint(8, 24)),
        lambda: s("0123456789abcdef", rng.choice([16, 24, 32])),
    ]


# Case-run alnum positives: random letters whose case comes in runs of one to nine (xkQWERTyuiop4Asd)
# with a digit or three dropped between the runs. The random alnum passwords the fresh floor loses are
# the ones whose case runs happen to look like CamelCase words (99AaaaaaaAaA and a9aAAAAAAAAAaaaAaaaa
# at 0.53 and 0.65 with no capitals-inside positive) because the everyday negatives own that shape. The
# 300 CamelCase memorable positives (EW words + symbol + digit) that used to defend them did it with
# whole words, so they lifted the products and camel phrases too and cost the wild margin (dropping
# them: product 8 -> 6, wild 0.7433 -> 0.7814, fresh floor 0.7382 -> 0.5671). Random letters teach the
# shape without the words; uniform random case (the machine alnum pattern) makes runs of one or two.
def runs_pats(rng: random.Random) -> list:
    def one() -> str:
        n, out, upper = rng.randint(12, 20), [], rng.random() < 0.5
        while len(out) < n:
            if rng.random() < 0.4:
                out += [str(rng.randint(0, 9)) for _ in range(rng.randint(1, 3))]
            letters = string.ascii_uppercase if upper else string.ascii_lowercase
            out += [rng.choice(letters) for _ in range(rng.randint(1, 9))]
            upper = not upper
        return "".join(out[:n])
    return [one]


# Pronounceable positives: nonsense syllable bodies with digits (kalemo1987, Tovira123, 12sulemar,
# kaledo12ta). The wild sample is international and 84% lowercase+digits, so most of its words are
# in no list we have; the human-shaped positives above teach 128 bodies, and the everyday copies
# share their whole-word grams. Bodies of three or four syllables (six letters or more) spread the
# password weight over the digit tail and ordinary letter pairs instead of words, to lift the wild
# margin without lifting the plain words and place names among the copies.
CONS, VOW, CODA = "bcdfghjklmnprstvz", "aeiou", "nrstlm"
syllable = lambda rng: rng.choice(CONS) + rng.choice(VOW) + (rng.choice(CODA) if rng.random() < 0.3 else "")
body = lambda rng, k: "".join(syllable(rng) for _ in range(k))


def pron_pats(rng: random.Random) -> list:
    year = lambda: str(rng.randint(1960, 2008))
    digits = lambda: rng.choice(SUFFIX)
    return [
        lambda: body(rng, 3) + digits(),
        lambda: body(rng, 3) + str(rng.randint(10, 999)),
        lambda: body(rng, 4) + digits(),
        lambda: body(rng, 3) + year(),
        lambda: body(rng, 3).capitalize() + digits(),
        lambda: digits() + body(rng, 3),
        lambda: body(rng, 3) + str(rng.randint(1, 99)) + syllable(rng),
    ]


# Mixed positives: digits inside the letters (kal73mor, tes3ka9lom, ra7mor38). The wild passwords
# nearest the threshold are not word+digits (3 of the 64 within 0.03 of t, against 3,033 of 5,567
# overall) but short lowercase texts of 8-10 characters with a digit or two inside or between the
# letters (a+9a+ and a+9+a+ alone are 14 of those 64), a shape no positive above makes and the
# lower+digit+lower everyday tag denies. Letter runs of two or three (a syllable each), so the lesson
# is the digit-inside grams and not the lowercase bodies that carry the plain words among the copies.
def mixed_pats(rng: random.Random) -> list:
    cv = lambda: rng.choice(CONS) + rng.choice(VOW)
    cvc = lambda: cv() + rng.choice(CODA)
    d = lambda: str(rng.randint(0, 9))
    return [
        lambda: cvc() + d() + d() + cvc(),
        lambda: cvc() + d() + cvc() + d() + cv(),
        lambda: cvc() + d() + cvc() + d() + cvc(),
        lambda: cv() + d() + cvc() + d() + cvc(),
        lambda: cvc() + d() + cvc() + d() + d(),
        lambda: cv() + d() + d() + cvc() + d() + cv(),
    ]


# Dashed pronounceable positives: three syllable bodies joined by dashes with a digit tail
# (kalemo-tovira-sulem42), the password-manager memorable shape that repo kebab-case pushes down and
# that binds the fresh floor (memorable_dash 0.7382 and 0.7995 are the two lowest fresh items after the
# two random alnum misses). 500 lifted the cluster to 0.85-0.93 but every kebab token with it (a repo YAML
# key locked, kebab copies up to 0.69); 200 for the floor alone.
def dashed_pats(rng: random.Random) -> list:
    b = lambda: body(rng, 3)
    return [
        lambda: f"{b()}-{b()}-{b()}{rng.randint(10, 99)}",
        lambda: f"{b()}-{b()}-{b()}{rng.choice(SUFFIX)}",
        lambda: f"{b()}-{b()}{rng.randint(1, 9)}-{b()}",
    ]


# Ordinary copies with a symbol at an end: social handles (@ + CamelCase words, no digits: a digit
# tail on a negative makes the digit tail less informative and moves password weight onto lowercase
# bodies, which lifted the plain words) and code fragments (an increment statement). The look-alike
# generator makes the handle shape as one fixed text that is also in the exam, so once the given
# cases are cleaned nothing teaches it and the password symbols in the positives above carry it to 0.98.
def handle_pats(rng: random.Random) -> list:
    W = lambda: rng.choice(EW)
    return [
        lambda: f"@{W()}{W()}",
        lambda: f"@{W()}{W()}{W()}",
    ]


def code_pats(rng: random.Random) -> list:
    L = lambda: rng.choice(EL)
    return [
        lambda: f"{L()}++;",
        lambda: f"{L()}.{L()}++;",
    ]


# Numbered lowerCamel identifiers (userName2: lowercase word + Capitalised word + one digit), the look-alike
# shape the model locks most: 5 of the 6 in the exam at 0.82-0.90, and 54 of the 70 given ones even in-sample
# at x3. A lowercase start and a digit end are the human-password shape, so only the capital inside separates
# them; a dose of its own, one digit, so the lesson is the capital and not the tail.
def ident_pats(rng: random.Random) -> list:
    W, L = lambda: rng.choice(EW), lambda: rng.choice(EL)
    return [lambda: f"{L()}{W()}{rng.randint(0, 9)}"]


everyday = draw(3400, 7, everyday_pats)  # 16 patterns at the dose 14 had at 3000
handles = draw(500, 23, handle_pats)
code = draw(200, 29, code_pats)
idents = draw(400, 37, ident_pats)  # 800 held the look-alike cap (6/50) but slid the wild threshold 0.07 and locked 4 more copies; half the dose
human = draw(2000, 11, human_pats)
machine = draw(1200, 13, machine_pats)  # 1000 beside the camel positives; 600 new positives below would otherwise thin the hex pattern (hex_16 0.8019 is the fifth-lowest fresh item)
runs = draw(800, 41, runs_pats)  # 400 on the private repo text; on public text the fresh floor (two case-run alnum items) bound at 0.7265, 800 lifts it to 0.7659 (1200 and 2000 pull the bench floor down)
pron = draw(1000, 19, pron_pats)
mixed = draw(800, 31, mixed_pats)
dashed = draw(200, 43, dashed_pats)
texts += everyday + handles + code + idents + human + machine + runs + pron + mixed + dashed
labels += [0] * (len(everyday) + len(handles) + len(code) + len(idents)) + [1] * (len(human) + len(machine) + len(runs) + len(pron) + len(mixed) + len(dashed))

# ---- features ---------------------------------------------------------------
# Character 1-4 grams and shape 1-6 grams with ^ $ boundary markers, no dense features,
# 32,768 hash buckets (loop.py's boundary_nodense: the best configuration once everyday-shaped
# negatives are in the mix). Only these knobs exist in the runtime; the config ships inside the model JSON.
FEATURES = dict(DEFAULT_FEATURES, boundary=True, dense=False, runs=True)  # runs: the whole shape collapsed (Thursday2026 -> Aa9) as one more gram; by hand, 2026-10-06

# ---- model ------------------------------------------------------------------
C = 4.0
PRUNE = 0.2  # weights below this are dropped before shipping (Jewel 1: 5,080 of 32,768 survive)
GIVEN_WEIGHT = 2.0  # each given gated case counts twice (3 on the private repo text; on public text 1/1.5/2/2.5/3/4/6 lock 27/17/16/18/17/23/30 copies): the fresh and bench floors are generated passwords and the look-alike guard is generated ids, and 7,000 word-shaped generated texts would otherwise outvote them
X = matrix(texts, FEATURES)
sample_weight = np.ones(len(texts))
sample_weight[: len(cases)] = [GIVEN_WEIGHT if gated(c["text"]) else 1.0 for c in cases]
model = LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(X, labels, sample_weight=sample_weight)
w = model.coef_[0]
weights = {int(i): round(float(w[i]), 4) for i in np.nonzero(np.abs(w) >= PRUNE)[0]}
bias = round(float(model.intercept_[0]), 6)
train_seconds = time.time() - t_start

# ---- exam (do not change) ---------------------------------------------------
prepare.evaluate(weights, bias, FEATURES, texts, train_seconds=train_seconds, t_start=t_start)
