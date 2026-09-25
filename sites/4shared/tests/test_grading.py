from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'verify'))
from answer_checks import count_claims, runtime_claims, winner_claim

W, L = 'Open Data Mapping Basics', 'City Cycling Route Planning'

@pytest.mark.parametrize('answer,expected', [
 (f'{W} is longer: 27:03 versus 19:05 for {L}.', True),
 (f'{W} is longer: 19:05. {L} runs 27:03.', False),
 (f'{W} is not longer than {L}. Their runtimes are 27:03 and 19:05 respectively.', False),
 (f'Compared with {L} (19:05), {W} (27:03) is the longer video.', True),
 (f'At 27:03, longer than {L} at 19:05, is {W}.', True),
 (f'{L} runs 19 minutes 5 seconds; {W} lasts 27 minutes and 3 seconds. The latter is longer.', True),
 (f'{W} is longer.\n| Video | Runtime |\n| --- | --- |\n| {W} | 27:03 |\n| {L} | 19:05 |', True),
 (f'{W} and {L} run 27:03 and 19:05 respectively. The former is longer.', True),
 (f'{W} runs 27:03. {L} runs 19:05. {L} is longer.', False),
 (f'{W} runs 27:03. {L} runs 19:05. {W} is shorter.', False),
 (f'{W} runs 27:03. {L} runs 19:05. {W} is longer, but {W} is not longer.', False),
 (f'{W} runs 19:05. {L} runs 27:03. Reference 27:03 and 19:05.', False),
 (f'{W} runs 27:03. {L} runs 19:05. {L} is shorter.', True),
])
def test_runtime_binding_and_comparison(answer, expected):
    assert bool(runtime_claims(answer, [W,L], [1623,1145]) and winner_claim(answer,W,[L])) == expected

F = 'Rain Garden Planting Guide.pdf'
@pytest.mark.parametrize('answer,expected', [
 (f'{F}, 58 pages, uploader Community Library.', True),
 (f'{F} has 49 pages; reference number 58.', False),
 (f'{F} has fifty-eight pages.', True),
 (f'{F}. Page count: 58. The calendar is on page 49.', True),
 (f'{F} has 58 chapters and 49 pages.', False),
 (f'{F} has 58 pages. It has 49 pages.', False),
 (f'{F} has not 58 pages.', False),
 (f'{F} has 58 pages, not 49 pages.', True),
 (f'{F} does not have 49 pages.', False),
 (f'| Filename | Pages |\n| --- | --- |\n| {F} | 58 |', True),
])
def test_count_properties(answer,expected):
    assert count_claims(answer,F,[F],'page',58) == expected

B='Twenty Thousand Leagues Under the Seas.epub'
@pytest.mark.parametrize('answer,expected',[
 (f'{B} has the most pages: 512 pages and 47 chapters (Pride and Prejudice 432/61, Anne of Green Gables 412/38).',True),
 (f'{B} has the most pages: 47 pages and 512 chapters.',False),
 (f'{B} has five hundred and twelve pages and forty-seven chapters.',True),
 (f'| Book | Pages | Chapters |\n| --- | --- | --- |\n| {B} | 512 | 47 |',True),
 (f'{B} has 400 pages and 12 chapters. Pride and Prejudice has 512 pages and 47 chapters.',False),
])
def test_book_counts(answer,expected):
    names=[B,'Pride and Prejudice','Anne of Green Gables']
    assert (count_claims(answer,B,names,'page',512) and count_claims(answer,B,names,'chapter',47)) == expected
