# GOV.UK grading contract

Run through the repository entrypoint:

```bash
python agent_demo/eval_judge.py --run_dir /absolute/path/to/run --verifier True
```

The 20 `verify_N.py` scripts delegate to `verify_lib.py`. They return JSON
`{task_id, pass, reason, evidence[]}` and exit 0/1. `--no_llm` is accepted for
compatibility. Primary grading always runs offline and requires Pillow, already
provided by the image/evaluator. Use `eval_judge.py` without `--verifier` for the
separate secondary LLM grade. The optional anchored text helper accepts standard
OpenAI-compatible base URLs, adds `/chat/completions`, and explicitly reports
unconfigured, failed or malformed responses as skipped.

Requirements:

- Matching task ID, completed `agent_done` run, no explicit failed self-report.
- Exact on-site paths on the `start_url` origin, with a decodable screenshot.
  A URL in a query string or another host/port does not establish a visit.
- `agent_demo` step URLs pair with `screenshot_before`; the GUI review recorder's
  explicit `url_after` pairs with `screenshot_after`. Conflicting metadata fails.
  Screenshot names cannot escape their directory. A symlink to an evidence
  directory is allowed for isolated controls; a screenshot symlink outside it is not.
- Task 12 requires nonempty search before the passport page; task 18 requires
  the Childcare browse page before eligibility. Other checks require relevant
  guide parts, service pages or organisation profiles. Task 6 also requires
  allowance, rate and taxable-gain facts. There is no minimum click count.
- News tasks require the relevant permanent news article. A listing or homepage
  summary alone no longer demonstrates completion of the expanded questions.
- Requested answer facts must be affirmative and use the right units. Basic
  number words, scale notation and punctuation variants are accepted. All 20
  tasks require reading beyond a page title or publisher name. Rubrics and
  tasks specify these requirements.

| Task | Answer contract |
| --- | --- |
| 0 | Standard Personal Allowance, income taper and allowance calculation |
| 1 | Pension weekly amount, payment interval and payment day |
| 2 | Paper/online filing, payment deadlines and payment reference |
| 3 | Three VAT categories and zero-rated versus exempt supplies |
| 4 | Minimum/full pension qualifying years and personal forecast service |
| 5 | Initial and daily late-filing penalties, including no-tax-due case |
| 6 | CGT allowance, rate for the specified disposal date and taxable gain |
| 7 | HMRC minister and employment/savings records for Self Assessment |
| 8 | DWP headcount and pension online claim preparation |
| 9 | Treasury establishment and latest announcement date/measures |
| 10 | Latest announcement publisher/date and purposes of two measures |
| 11 | HMRC filing count/deadline, prompt filing and initial penalty |
| 12 | Passport renewal preparation, fees, photo dimensions and recency |
| 13 | England Blue Badge fee, validity, documents and PIP conditions |
| 14 | Skilled Worker publisher/duration, sponsorship and conditional evidence |
| 15 | Practical test fees, preparation and automatic-to-manual exception |
| 16 | Moving address, missing NI number, paper registration and voter ID |
| 17 | France passport validity, Schengen limit, GHIC limits and email updates |
| 18 | Child Benefit age/education eligibility, backdating and NI credits |
| 19 | NHS App users/capabilities, GP dependence and emergency limitation |

Tests:

```bash
python -m unittest discover -s sites/gov_uk/tests -v
```

These are deterministic, bounded language rules, not a universal semantic judge.
Unusual paraphrases, subtle contradictions or adversarial multi-sentence answers
may need reviewer judgment. Trajectory metadata and images cannot authenticate
an untrusted recorder or prove which text was read; synthetic tests are never
represented as browser attempts. The mirror is read-only, so completion is judged
from navigation and answers; GUI regression also checks initial/final DB identity.

Integration controls also cover swapped paper/online deadlines, an incorrect
daily-penalty threshold, either valid pair of growth measures, photo units,
reversed explicit width/height order and equivalent decimal fee notation.
Task 9 accepts any two of infrastructure, planning and skills; task 10
specifically requires infrastructure and planning as requested.
