#!/usr/bin/env python3
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import json
import random
import re
from pathlib import Path


DEFAULT_WORD_LIST = "data/enable1_words.txt"
EXCLUDED_ANSWERS = {
    "solutions to anxiety",
    "just your mind",
    "lurking lemon",
    "subliminal message",
}
VERIFIED_SEED_ANSWERS = {
    5: ["baked", "wiped", "couch", "modem", "orcin", "spitz", "frets", "fakey", "agios", "ninja"],
    6: ["tapeta", "somata", "jordan", "limply", "walked", "robalo", "strand", "boxers", "waffed", "coseys"],
    7: ["vetoing", "fencing", "kismets", "hirsute", "sponged", "hurtled", "alkanes", "foulest", "vibrios", "crapper"],
    8: ["gillying", "tenpenny", "encyclic", "boxthorn", "harrumph", "frizzles", "conflict", "hexagram", "squadded", "acaulose"],
    9: ["epopoeias", "guitguits", "tubificid", "exscinded", "bollixing", "logogriph", "zarzuelas", "silicious", "thrumming", "commences"],
    10: ["exhibitive", "syndactyly", "silicified", "hasheeshes", "embankment", "donnybrook", "jambalayas", "unpuzzling", "ubiquities", "nonproblem"],
    11: ["equilibrium", "ovipositing", "gullibility", "bombardment", "exemplifies", "ichthyology", "titrimetric", "exclusively", "encampments", "bibliophile"],
    12: ["burgher pipe", "urial heehaw", "boughed heme", "lawn backlog", "hulky pikake", "wise execute", "waney cozily", "gobbing tomb", "gigue sextet", "yeuky pilaff"],
    13: ["wawls stanzas", "ataxy pajamas", "scamming quit", "kvass mysosts", "krater quokka", "mayday cruddy", "warship addax", "donzels ponds", "fibrin pinier", "hazzans blebs"],
    14: ["unbound unhurt", "backfit mikveh", "fitch iniquity", "hoopoo coinage", "stylists swags", "telexed nuzzle", "mink zany pink", "schlepps jiffs", "cyma injecting", "circlet coccyx"],
    15: ["mezzo coxcombry", "jackpot panchax", "divvy momi ditz", "hove flex phpht", "quern desk monk", "calx jouk xylyl", "fuji jibb kooky", "pubic kook bozo", "jobholder hafiz", "curve meze fizz"],
}
VARIANT_PRONE_PATTERNS = (
    "ized",
    "ize",
    "izer",
    "izers",
    "izes",
    "izing",
    "izable",
    "izability",
    "ization",
    "izations",
    "ised",
    "ising",
    "isation",
    "isations",
)

COMMON_PREFERRED_WORDS = """
about above actor acute admit adopt adult after again agent agree ahead alarm album alert alien
alike alive allow alone along alter amber angel anger angle apple apply arena argue arise armed
array aside asset audio audit avoid award aware awful baker basic beach began begin below bench
birth black blame blind block blood board boost bound brain brand bread break brick bride brief
bring broad brown brush build buyer cable candy carry cause chain chair charm chart chase cheap
check chest chief child civil claim clean clear clerk click climb clock close coach coast could
count court cover craft crash cream crime crowd crown cycle daily dance dated dealt death delay
depth doing doubt dozen draft drama drawn dream dress drink drive eager early earth eight elite
empty enemy enjoy enter equal error event every exact faith false fault fiber field fifth final
first flame flash fleet floor focus force forth found frame fresh front fruit fully ghost giant
given glass globe grace grade grain grand grant grass green greet group grown guard guest guide
habit happy heart heavy hence honey honor horse hotel house human ideal image imply index inner
input issue joint judge known label large laser later laugh layer learn lease least leave legal
level light limit local logic loose lucky lunch magic major maker march match maybe metal might
minor model money month moral motor mount mouse mouth movie music needs never night noble noise
north novel nurse occur ocean offer often order other paint panel paper party peace phase phone
photo piano piece pilot pitch place plain plane plant plate point pound power press price pride
prime print prior prize proof proud prove queen quick quiet radio raise range rapid ratio reach
ready realm reply right rival river rough round route royal scale scene scope score serve seven
shape share sharp sheet shelf shell shift shirt shock short shown skill sleep small smart smile
solid solve sound south space spare speak speed spend spent split sport staff stage stand start
state steam steel stick still stock stone stood store storm story strip stuck study style sugar
table taken taste teach thank theme thick thing think third those three threw throw tight title
today topic total touch tough tower track trade train trend trial trust truth twice under union
unity until upper upset urban usage usual valid value video visit vital voice waste watch water
wheel where which while white whole whose woman world worry worth would write wrong youth
ability absence academy account accused achieve acquire address advance adviser against airline
airport alcohol alleged already analyst ancient another anxiety anybody arrange arrival article
athlete attempt attract average balance banking battery because bedroom believe beneath benefit
between billion biology brother cabinet capital captain capture careful carrier central century
certain chamber channel chapter charity cheaper chicken citizen climate college combine comfort
command comment company compare complex concept concern conduct confirm connect consent consist
contact contain content contest context control convert correct council counsel counter country
crystal culture current declare decline default defense deliver density deposit desktop despite
destroy develop diagram diamond digital disease display distant diverse drawing eastern economy
edition elderly elegant element emotion employ enable evening exactly example excited expense
explain factory faculty failure fashion feature federal feeling fiction finance finding foreign
forever fortune forward founder freedom gallery general genuine gesture greater grocery habitat
healthy history holiday housing however hundred husband improve include initial insight install
instead intense involve journal journey justice kitchen landing largely lasting liberal library
license limited machine manager massive meaning measure medical meeting mention message million
mineral minimum mission mistake mixture monitor morning musical natural neither nervous network
nothing notable nuclear obvious officer opening opinion optical organic outcome outside overall
package painter partner passage pattern payment percent perfect perhaps physics picture plastic
popular portion poverty precise predict premium prepare present prevent primary printer private
problem proceed process produce product profile program project promise protect protein provide
purpose qualify quarter quickly radical railway reader reality recover reflect regular related
release remain remote remove repair repeat replace require reserve resolve respect respond restore
retired revenue reverse routine sample science section segment serious service session several
similar smaller speaker special station storage strange student subject succeed suggest summary
support surface surgery teacher theater therapy traffic trouble typical uniform unknown unusual
upgrade village virtual visible warning weather weekend welcome western whereas winning witness
working writing
absolute absorbed abstract academic accident accurate activity actually addition adjacent
adjustment admirable advantage adventure afternoon agreement allowance amazing analysis apparent
applicant approach approval argument assignment assistant athletic audience bathroom beautiful
beginning benchmark breakfast brilliant broadcast building business calendar campaign capacity
carefully ceremony chairman chemical classroom clinical clothing colorful commerce committee
community companion comparison complaint computer condition conference confident connection
conscious constant consumer continue contract contrast convention conversion copyright customer
database decision decrease delivery describe designer detailed determine developer diagnosis
direction director discovery discussion distance division document domestic downtown dramatic
education effective efficient election emergency emotional emphasis employer encourage enormous
estimate evaluate evidence excellent executive exercise familiar favorite festival financial
finished forecast foundation framework friendly function generous geography household identify
immediate important impossible incentive incident increase indicate industry informal innocent
inspection instance institute insurance interview introduce inventory knowledge landscape language
location magazine maintain majority marketing material meanwhile medicine migration military
minister minority mountain movement musician national negative neighborhood newspaper nominate
objection objective occasion official operator ordinary organize original otherwise overview
painting paragraph parallel passenger personal persuade physical pipeline platform pleasant
position positive powerful practice pregnancy pressure previous principal prisoner procedure
property proposal prospect province purchase reaction realistic reception recognize recommend
recording reduction regional relation remember reporter research resident resource response
schedule security sentence separate sequence shoulder software solution somewhat southern
specific standard statement strategy strength structure struggle suddenly suitable surprise
surround swimming technical telephone tendency thousand tomorrow transfer treatment ultimate
umbrella universe valuable variation variety vehicle vertical violence volunteer wonderful
workshop yesterday
administration architecture calculation communication consideration construction contribution
conversation demonstration determination distribution documentation education electricity
environment expectation explanation identification illustration implementation independence
information instruction investigation organization participation presentation professional
qualification recommendation relationship representation responsibility satisfaction
significant transportation understanding
""".split()


def normalize_answer(text):
    return re.sub(r"\s+", " ", text.strip().lower())


def answer_letters(text):
    return re.sub(r"[^a-z]", "", text.lower())


def signature(text):
    return "".join(sorted(answer_letters(text)))


@lru_cache(maxsize=None)
def subtract_signature(whole, part):
    remaining = Counter(whole)
    remaining.subtract(Counter(part))
    return "".join(sorted(letter * count for letter, count in remaining.items() if count > 0))


@lru_cache(maxsize=None)
def subset_signatures(sig):
    counts = sorted(Counter(sig).items())
    out = []

    def build(index, pieces):
        if index == len(counts):
            candidate = "".join(pieces)
            if candidate:
                out.append(candidate)
            return
        letter, count = counts[index]
        for amount in range(count + 1):
            pieces.append(letter * amount)
            build(index + 1, pieces)
            pieces.pop()

    build(0, [])
    return out


def load_words(path, max_letters, min_letters=2):
    words = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        word = raw.strip().lower()
        if re.fullmatch(r"[a-z]+", word) and min_letters <= len(word) <= max_letters:
            words.append(word)
    return sorted(set(words))


def decompositions_any_depth(target_sig, words_by_signature, cap=2):
    valid_signatures = set(words_by_signature)
    memo = {}

    def search(remaining, min_signature):
        key = (remaining, min_signature)
        if key in memo:
            return memo[key]

        found = set()
        if remaining in valid_signatures and remaining >= min_signature:
            for word in words_by_signature[remaining]:
                found.add((word,))
                if len(found) >= cap:
                    memo[key] = found
                    return found

        for part in subset_signatures(remaining):
            if (
                len(part) < 2
                or len(part) > len(remaining) - 2
                or part not in valid_signatures
                or part < min_signature
            ):
                continue

            rest = subtract_signature(remaining, part)
            for suffix in search(rest, part):
                for word in words_by_signature[part]:
                    found.add(tuple(sorted((word,) + suffix)))
                    if len(found) >= cap:
                        memo[key] = found
                        return found

        memo[key] = found
        return found

    return search(target_sig, "")


def intended_decomposition(answer):
    return tuple(sorted(answer_letters(part) for part in normalize_answer(answer).split()))


def has_unique_dictionary_decomposition(answer, words_by_signature):
    answer_sig = signature(answer)
    decompositions = decompositions_any_depth(answer_sig, words_by_signature, cap=2)
    return decompositions == {intended_decomposition(answer)}


def heuristic_score(word):
    common_bonus = 1000 if word in COMMON_PREFERRED_WORDS else 0
    suffix_penalty = sum(
        word.endswith(suffix)
        for suffix in ("s", "ed", "er", "est", "ing", "ly", "ness", "tion", "ions")
    )
    rare_penalty = sum(word.count(letter) for letter in "jqxz")
    repeat_penalty = len(word) - len(set(word))
    return common_bonus - 40 * suffix_penalty - 12 * rare_penalty - 4 * repeat_penalty


def spelling_is_stable(word):
    if any(word.endswith(pattern) for pattern in VARIANT_PRONE_PATTERNS):
        return False
    if "bousouki" in word or "leukaem" in word:
        return False
    if "colour" in word or "honour" in word or "favour" in word:
        return False
    if "center" in word or "theater" in word:
        return False
    return True


def scramble(answer, rng, dictionary):
    letters = list(answer_letters(answer)) + [" "] * answer.count(" ")
    for _ in range(500):
        rng.shuffle(letters)
        candidate = "".join(letters)
        if (
            candidate.strip() == candidate
            and "  " not in candidate
            and normalize_answer(candidate) != normalize_answer(answer)
            and candidate.replace(" ", "") not in dictionary
        ):
            return candidate
    return "".join(reversed(letters))


def generate(args):
    rng = random.Random(args.seed)
    raw_words = load_words(args.word_list, args.max_length, args.min_dictionary_word_length)
    words = [word for word in raw_words if spelling_is_stable(word)]
    dictionary = set(words)
    words_by_signature = defaultdict(list)
    for word in words:
        words_by_signature[signature(word)].append(word)

    for grouped_words in words_by_signature.values():
        grouped_words.sort()

    preferred = [word for word in dict.fromkeys(COMMON_PREFERRED_WORDS) if word in dictionary]
    random_pool = words[:]
    rng.shuffle(random_pool)
    simulated_words = preferred + random_pool[: args.simulations]
    words_by_length = defaultdict(list)
    for word in simulated_words:
        words_by_length[len(word)].append(word)

    phrase_pool = [
        word for word in simulated_words
        if spelling_is_stable(word) and 2 <= len(word) <= args.max_length - 3
    ]

    selected = defaultdict(list)
    rejected = Counter()
    seen = set()

    def consider(answer, target_length):
        if answer in seen:
            return
        seen.add(answer)
        if answer in EXCLUDED_ANSWERS:
            rejected["excluded"] += 1
            return
        if not spelling_is_stable(answer):
            rejected["variant_prone_spelling"] += 1
            return
        if not all(part in dictionary for part in normalize_answer(answer).split()):
            rejected["not_dictionary_words"] += 1
            return
        if not has_unique_dictionary_decomposition(answer, words_by_signature):
            rejected["non_unique_decomposition"] += 1
            return
        selected[target_length].append(answer)

    for target_length in range(args.min_length, args.max_length + 1):
        for answer in VERIFIED_SEED_ANSWERS.get(target_length, []):
            consider(answer, target_length)
            if len(selected[target_length]) >= args.per_length:
                break

        for word in words_by_length[target_length]:
            consider(word, target_length)
            if len(selected[target_length]) >= args.per_length:
                break

        attempts = 0
        while len(selected[target_length]) < args.per_length and attempts < args.simulations:
            attempts += 1
            left = rng.choice(phrase_pool)
            right_length = target_length - len(left) - 1
            if right_length < args.min_dictionary_word_length:
                continue
            right_candidates = words_by_length[right_length]
            if not right_candidates:
                continue
            right = rng.choice(right_candidates)
            if left == right:
                continue
            consider(f"{left} {right}", target_length)

        if len(selected[target_length]) < args.per_length:
            rejected[f"length_{target_length}_shortfall"] = args.per_length - len(selected[target_length])

    missing = {
        length: args.per_length - len(selected[length])
        for length in range(args.min_length, args.max_length + 1)
        if len(selected[length]) < args.per_length
    }
    if missing:
        raise SystemExit(f"Not enough candidates after {len(seen)} simulations: {missing}")

    answers = []
    for length in range(args.min_length, args.max_length + 1):
        candidates = sorted(
            selected[length],
            key=lambda word: (-sum(heuristic_score(part) for part in word.split()), word),
        )
        answers.extend(candidates[: args.per_length])

    questions = {
        scramble(answer, rng, dictionary): answer
        for answer in answers
    }

    output = {
        "metadata": {
            "source_word_list": args.word_list,
            "raw_source_word_count": len(raw_words),
            "source_word_count": len(words),
            "min_dictionary_word_length": args.min_dictionary_word_length,
            "seed": args.seed,
            "simulated_candidates": len(seen),
            "per_length": args.per_length,
            "lengths": [args.min_length, args.max_length],
            "total_answers": len(answers),
            "rejected": dict(rejected),
            "heuristic": (
                "Answers are valid ENABLE words, grouped by total character count, "
                "and accepted only when the intended answer is the sole dictionary "
                "decomposition under the filtered benchmark lexicon: ENABLE words of "
                "at least the configured minimum length, with spelling-variant-prone "
                "forms rejected."
            ),
        },
        "questions": questions,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    if args.questions_output:
        args.questions_output.parent.mkdir(parents=True, exist_ok=True)
        args.questions_output.write_text(json.dumps(questions, indent=2) + "\n", encoding="utf-8")

    return output


def parse_args():
    parser = argparse.ArgumentParser(description="Generate unambiguous unscramble benchmark questions.")
    parser.add_argument("--word-list", default=DEFAULT_WORD_LIST)
    parser.add_argument("--output", type=Path, default=Path("generated/unique-unscrambles-5-15.json"))
    parser.add_argument("--questions-output", type=Path, default=Path("questions/unique-unscrambles-5-15.json"))
    parser.add_argument("--min-length", type=int, default=5)
    parser.add_argument("--max-length", type=int, default=15)
    parser.add_argument("--per-length", type=int, default=10)
    parser.add_argument("--simulations", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=20260531)
    parser.add_argument("--min-dictionary-word-length", type=int, default=3)
    return parser.parse_args()


def scramble_simple(input: str) -> str:
    return "".join(random.sample(input, len(input)))

if __name__ == "__main__":
    print(scramble_simple("the meaning of life is difficult to put into words"))

