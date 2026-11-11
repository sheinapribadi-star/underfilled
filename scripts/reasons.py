"""Rule-based classifier for the free-text whyStopped field on ClinicalTrials.gov.

Buckets are checked in order and the first match wins, with one exception:
an explicit enrollment problem ("slow accrual", "poor recruitment") beats
safety and efficacy wording, because sponsors often add "no safety concerns"
to an accrual stop. Phrases that deny a reason ("not related to safety")
are stripped before matching. Rules were tuned on two hand-read samples and
checked on a third (see BRIEF.md).
"""
import re

R = lambda p: re.compile(p, re.I)
TERM = r"(safety|efficacy|adverse|tolerability|toxicity)"
DENIALS = R(r"\b(not|no|without|unrelated to|nothing to do with)\s+(\w+\s+){0,5}?" + TERM
            + r"(\s+(or|and|nor)\s+(\w+\s+)?" + TERM + r")?(\s+(\w+\s+)?(concerns?|issues?|reasons?|signals?|findings?|data|events?))?")
DSMB = R(r"(data (and )?)?safety monitoring (board|committee)")

COVID = R(r"covid|corona ?virus|pandemic|sars-?cov")
SAFETY = R(r"safety|adverse|\baes?\b|toxicit|side[- ]effect|\bsaes?\b|death|tolerab|hepatotox|clinical hold|benefit[/ -]risk|risk[/ -]benefit")
EFFICACY = R(r"efficac|futil|objective respons|no respons|antitumou?r activity|lack of (benefit|response|effect|activity)|no (clinical )?benefit|ineffective|interim (analys|assess)|endpoint|did not show|negative results?|not effective|insufficient (response|activity)|\bdsmb\b|\bdmc\b|\bidmc\b|data monitoring|primary objective")

NOUN = r"(accru\w*|enrol\w*|recruit\w*|inclusions?|inclusion rate)"
NEG = (r"(slow\w*|low|lower|poor\w*|insufficient\w*|inadequate|lack\w*|difficult\w*|delay\w*|fail\w*|unable|inability|impossib\w*|"
       r"limited|below|not|no|challeng\w*|issues?|problems?|barriers?|few|fewer|small|less|stall\w*|competing|shortage|"
       r"unsuccessful|scarc\w*|feasib\w*|couldn't|didn't|declin\w*|decreas\w*|futil\w*|halted|sluggish|unsatisfactory|default|"
       r"insufficiency|underenrol\w*|under-enrol\w*)")
NEAR = R(r"\b" + NEG + r"\b\W+(\w+\W+){0,4}?" + NOUN + r"|\b" + NOUN + r"\W+(\w+\W+){0,4}?" + NEG + r"\b")
BARE = R(r"^\W*(the\s+)?(patient\s+|subject\s+|participant\s+)?(accrual|enrollment|enrolment|recruitment)\W*$")
POOL = R(r"\b(lack|insufficient|not enough|shortage|limited number|few|unable to (find|identify|locate)|difficult\w* (in )?(identifying|finding|locating))\s+(of\s+)?(\w+\s+){0,2}?(patients?|participants?|subjects?|volunteers?|population|candidates?)\b")
DONE = R(r"(?<!not )(?<!never )\b(enrol|recruit|accru)\w*\s+(was\s+|is\s+|has been\s+)?(over|complete\w*|reached|achieved|finished)|statistical power|power was reached")
UNDERENROLL = R(r"underenrol|under-enrol")

BUSINESS = R(r"sponsor|grant|no longer available|could not be (supplied|delivered)|can be delivered|business|fund|company|commercial|strateg|portfolio|financ|budget|program|acquisi|merger|drug supply|supply|manufactur|priorit|resource|license|marketing|corporate|decision|bankrupt")
SITE = R(r"investigator|\bpi\b|left the (institution|university|hospital|organi)|relocat|retire|staff|site closed|personnel")
REGULATORY = R(r"\birb\b|ethic|regulator|\bfda\b|approval|protocol (amend|redesign)|redesign")


def accrual_hit(t):
    strong = (bool(NEAR.search(t)) and not DONE.search(t)) or bool(BARE.search(t)) or bool(UNDERENROLL.search(t))
    return strong, strong or bool(POOL.search(t))


def classify(text):
    if not text or not text.strip():
        return "not stated"
    t = DENIALS.sub(" ", DSMB.sub("dsmb", text))
    if COVID.search(t):
        return "covid-19"
    strong, acc = accrual_hit(t)
    if strong:
        return "low accrual"
    if SAFETY.search(t):
        return "safety"
    if EFFICACY.search(t):
        return "efficacy or futility"
    if acc:
        return "low accrual"
    if BUSINESS.search(t):
        return "business or funding"
    if SITE.search(t):
        return "investigator or site"
    if REGULATORY.search(t):
        return "regulatory or protocol"
    return "other or unclear"
