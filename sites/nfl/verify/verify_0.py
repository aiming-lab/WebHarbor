"""Verify NFL--0: Bob wants annual billing for NFL+ Premium so he can keep watching NFL RedZone without monthly payments. Sign in as bob.c@test.com (TestPass123!), switch him to the annual plan, and pay with a valid test Visa in his name ending in 4242, using a future expiry and a three-digit code. Confirm the order reference, total including tax, and the plan and renewal date now shown in his account.

Expected facts below are from the captured site fixture."""
from verify_lib import Judge, check_only_tables_changed, check_precise_delta, check_trajectory_identity, contains_amount, contains_date, contains_phrase, contains_time, final_answer, navigated_to, navigated_to_path, orders_of, run_verifier, subscriptions_of, user_by_email
TASK_ID = 'NFL--0'
BOB_EMAIL = 'bob.c@test.com'
TOTAL = 108.94
AMOUNT = 99.99
TAX = 8.95
ORDER_REF = 'NFL-47C7FF'
NEW_PLAN_CODE = 'nfl_plus_premium_annual'
NEW_PLAN_TITLE = 'NFL+ Premium Annual'
RENEWAL = '2027-09-24'

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check('visited_signin', navigated_to_path(traj, '/account/signin/'), 'required: /account/signin/')
    judge.check('visited_plus_plans', navigated_to_path(traj, '/plus/'), 'required: /plus/ (compare plans, pick the annual RedZone plan)')
    judge.check('visited_premium_annual_checkout', navigated_to_path(traj, f'/plus/subscribe/{NEW_PLAN_CODE}/'), f'required: /plus/subscribe/{NEW_PLAN_CODE}/')
    judge.check('visited_confirmation', navigated_to(traj, '/plus/confirmation/'), 'required: /plus/confirmation/<ref>')
    judge.check('visited_account', navigated_to_path(traj, '/account/'), 'required: /account/ (plan + renewal date after the switch)')
    judge.check('answer_order_ref', contains_phrase(answer, ORDER_REF), f'expected order reference {ORDER_REF}')
    judge.check('answer_total_108_94', contains_amount(answer, TOTAL), f'expected total charged ${TOTAL:.2f} (99.99 + 8.95 tax)')
    judge.check('answer_plan_premium_annual', contains_phrase(answer, NEW_PLAN_TITLE), f'expected the account to show {NEW_PLAN_TITLE}')
    judge.check('answer_renewal_sept_24_2027', contains_date(answer, RENEWAL), 'expected renewal date September 24, 2027')
    bob = user_by_email(after_db, BOB_EMAIL)
    judge.check('bob_exists', bob is not None, f'bob={BOB_EMAIL}')
    if bob:
        subs = subscriptions_of(after_db, bob['id'])
        active = [s for s in subs if s['status'] == 'active']
        cancelled = [s for s in subs if s['status'] == 'cancelled']
        judge.check('one_active_premium_annual', len(active) == 1 and active[0]['plan_code'] == NEW_PLAN_CODE and (active[0]['plan_title'] == NEW_PLAN_TITLE) and (abs(active[0]['amount'] - AMOUNT) < 0.011) and str(active[0]['renews_at']).startswith(RENEWAL), f'active={active!r}')
        judge.check('old_monthly_cancelled', len(cancelled) == 1 and cancelled[0]['plan_code'] == 'nfl_plus_premium_monthly', f'cancelled={cancelled!r}')
        orders = orders_of(after_db, bob['id'])
        judge.check('one_new_order_row', len(orders) == 1 and orders[0]['order_ref'] == ORDER_REF and (abs(orders[0]['amount'] - AMOUNT) < 0.011) and (abs(orders[0]['tax'] - TAX) < 0.011) and (abs(orders[0]['total'] - TOTAL) < 0.011) and (orders[0]['card_last4'] == '4242') and ((orders[0]['cardholder'] or '').lower() == 'bob chen'), f'orders={orders!r}')
    check_only_tables_changed(judge, initial_db, after_db, ('users', 'plus_orders', 'subscriptions'))
    check_precise_delta(judge, initial_db, after_db, 'users', 'id')
    check_precise_delta(judge, initial_db, after_db, 'subscriptions', 'id', changed_keys=(1,), added_keys=(4,))
    check_precise_delta(judge, initial_db, after_db, 'plus_orders', 'id', added_keys=(3,))
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
