"""Verify NFL--2: Carol wants to stop paying for NFL+ while keeping up with football through the free newsletter. Sign in as carol.d@test.com (TestPass123!), cancel her subscription and enable the newsletter. Confirm her former plan and billing price, the reference and total of her original purchase, and that her account now shows the cancellation and newsletter subscription.

Expected facts below are from the captured site fixture."""
from verify_lib import Judge, check_only_tables_changed, check_precise_delta, check_trajectory_identity, contains_amount, contains_phrase, contains_time, entered_identity, final_answer, navigated_to, navigated_to_path, orders_of, run_verifier, subscriptions_of, user_by_email
TASK_ID = 'NFL--2'
CAROL_EMAIL = 'carol.d@test.com'
PLAN_TITLE = 'NFL+ Annual'
CYCLE_AMOUNT = 49.99
ORDER_REF = 'NFL-03NUAL'
ORDER_TOTAL = 54.46
NEW_PASSWORD = 'CarolFan2026!'

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check('visited_signin', navigated_to_path(traj, '/account/signin/'), 'required: /account/signin/')
    judge.check('visited_account', navigated_to_path(traj, '/account/'), 'required: /account/')
    judge.check('visited_profile_edit', navigated_to_path(traj, '/account/edit/'), 'required: /account/edit/ (newsletter + new password)')
    signin_visits = sum((1 for u in [s.get('url', '') for s in traj.get('steps', [])] if '/account/signin/' in str(u)))
    judge.check('answer_plan_annual', contains_phrase(answer, PLAN_TITLE), f'expected plan {PLAN_TITLE}')
    judge.check('answer_cycle_amount', contains_amount(answer, CYCLE_AMOUNT), f'expected per-cycle price ${CYCLE_AMOUNT:.2f}')
    judge.check('answer_order_ref', contains_phrase(answer, ORDER_REF), f'expected original order reference {ORDER_REF}')
    judge.check('answer_order_total', contains_amount(answer, ORDER_TOTAL), f'expected original order total ${ORDER_TOTAL:.2f}')
    judge.check('answer_cancelled_status', any((p in answer.lower() for p in ('cancel', 'no active', "don't have an active", 'inactive', 'ended'))), 'answer must state the post-cancellation status')
    judge.check('answer_newsletter_on', any((p in answer.lower() for p in ('newsletter on', 'newsletter is on', 'subscribed to the newsletter', 'newsletter now on', 'newsletter: on'))), 'answer must state the newsletter setting is on')
    carol = user_by_email(after_db, CAROL_EMAIL)
    judge.check('carol_exists', carol is not None, f'carol={CAROL_EMAIL}')
    if carol:
        judge.check('carol_newsletter_on', bool(carol['newsletter']), f'newsletter={carol['newsletter']!r}')
        seed_carol = user_by_email(initial_db, CAROL_EMAIL)
        subs = subscriptions_of(after_db, carol['id'])
        judge.check('subscription_cancelled_in_db', len(subs) == 1 and subs[0]['status'] == 'cancelled' and (subs[0]['plan_code'] == 'nfl_plus_annual'), f'subscriptions={subs!r}')
        orders = orders_of(after_db, carol['id'])
        judge.check('order_history_untouched', len(orders) == 1 and orders[0]['order_ref'] == ORDER_REF, f'orders={orders!r}')
    check_only_tables_changed(judge, initial_db, after_db, ('users', 'subscriptions'))
    check_precise_delta(judge, initial_db, after_db, 'users', 'id', changed_keys=(3,))
    check_precise_delta(judge, initial_db, after_db, 'subscriptions', 'id', changed_keys=(2,))
    check_precise_delta(judge, initial_db, after_db, 'plus_orders', 'id')
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
