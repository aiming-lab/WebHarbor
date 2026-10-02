"""Pages must be served from the seed even if source captures are absent."""
import builtins
from pathlib import Path
import pytest
import app as sec

@pytest.mark.parametrize('path', [
    '/', '/enforcement-litigation/whistleblower-program',
    '/resources-investors', '/submit-filings/forms-index',
    '/submit-tip-or-complaint',
    '/enforcement-litigation/litigation-releases/lr-26662',
])
def test_pages_do_not_read_source_captures(client, monkeypatch, path):
    real_open = builtins.open
    def guarded(file, *args, **kwargs):
        if isinstance(file, (str, Path)) and 'source_data' in str(file):
            raise AssertionError('Runtime attempted to open source capture')
        return real_open(file, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', guarded)
    monkeypatch.setattr(sec, '_PDF_CACHE', None)
    response = client.get(path)
    assert response.status_code == 200
