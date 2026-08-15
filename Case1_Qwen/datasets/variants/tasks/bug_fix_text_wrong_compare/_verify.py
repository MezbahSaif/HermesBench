"""Ad-hoc verification: compare fixed work/main.py against pristine/main.py."""
import sys, os

# Get the project root (parent of 'work' and 'pristine')
project_root = os.path.dirname(os.path.abspath("work"))
sys.path.insert(0, os.path.join(project_root, "work"))
sys.path.insert(0, os.path.join(project_root, "pristine"))

from work.main import slugify as sf_work, word_frequency as wf_work, sentence_split as ss_work
from pristine.main import slugify as sf_pristine, word_frequency as wf_pristine, sentence_split as ss_pristine

passed = 0
failed = 0

def check(name, got, expected):
    global passed, failed
    if got == expected:
        passed += 1
    else:
        failed += 1
        print(f"FAIL [{name}]")
        print(f"  Expected: {expected!r}")
        print(f"  Got:      {got!r}")

# --- slugify tests (should be identical, no bug) ---
check("slugify basic",     sf_work("Hello World"),    "hello-world")
check("slugify spaces",    sf_work("  spaced out  "),   "spaced-out")
check("slugify punctuation", sf_work("foo!bar baz?"),  "foo-bar-baz")

# --- word_frequency tests (THE FIX: >= vs >) ---
text = "the cat sat on mat and ate the"
result_w = wf_work(text, min_len=3)
result_p = wf_pristine(text, min_len=3)
check("word_freq boundary match", result_w, result_p)

# Specific: 2-letter words excluded, 3+ included
assert "the" in result_p and "cat" in result_p
print(f"  word_frequency(min_len=3): {result_w}")

# min_len=2: 2-letter words included
text2 = "it is the cat sat on mat and ate it"
r2w = wf_work(text2, min_len=2)
r2p = wf_pristine(text2, min_len=2)
check("word_freq min_len=2 match", r2w, r2p)

# --- sentence_split tests (should be identical) ---
text3 = "Hello world. How are you? I'm fine!"
check("sentence_split basic", ss_work(text3), ss_pristine(text3))

# Edge cases: empty input
check("empty text slugify",     sf_work(""),    "")
check("empty text word_freq",   wf_work(""),    {})
check("empty text sentences",   ss_work(""),    [])

print(f"\nResult: {passed} passed, {failed} failed")
if failed > 0:
    sys.exit(1)
