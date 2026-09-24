"""A claimed signup must match the user data entered in the trajectory."""
import pytest
from test_verifiers import HONEST, COMPLIANT_AFTER_SQL, SEED
from _support import build_run, mutate_db, run_verifier

@pytest.mark.parametrize('assignment', [
    "email='bad-email'",
    "email='someone.else@test.com'",
    "username='different_user'",
    "display_name='Different Name'",
    "password_hash='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'",
])
def test_signup_rejects_mismatched_identity(tmp_path, assignment):
    run = tmp_path / 'run'
    steps, answer = HONEST[25]
    build_run(run, 'League of Legends--25', steps, answer)
    after = mutate_db(SEED, tmp_path / 'after.db', COMPLIANT_AFTER_SQL[25] + [
        'UPDATE users SET ' + assignment + ' WHERE id=(SELECT MAX(id) FROM users)'])
    assert run_verifier(25, run, SEED, after)['pass'] is False
