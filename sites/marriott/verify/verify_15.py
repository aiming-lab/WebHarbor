"""Verify the four-person Chicago spa weekend research."""
from verify_lib import (check_trajectory_identity, check_read_only, final_answer,
                        contains_phrase, contains_amount, contains_count,
                        navigated_find_hotels, navigated_hotel_overview, navigated_hotel_tab, run_verifier)
from reviewed_contract import stated_capacity
TASK_ID = 'Marriott--15'


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    a = final_answer(traj)
    judge.check('destination_research', navigated_find_hotels(traj, 'Chicago'), 'Chicago search')
    judge.check('amenity_research', navigated_hotel_overview(traj, 'jw-marriott-chicago'), 'hotel amenities')
    judge.check('room_research', navigated_hotel_tab(traj, 'rooms', 'jw-marriott-chicago'), 'room capacities and rates')
    judge.check('hotel_and_brand', contains_phrase(a, 'JW Marriott Chicago'), 'JW Marriott Chicago, brand JW Marriott')
    judge.check('room', contains_phrase(a, 'Guest Room, 2 Double Beds'), 'cheapest four-person room')
    judge.check('capacity', stated_capacity(a, 4), 'sleeps four')
    judge.check('rate', contains_amount(a, 335), '$335 per night')
    judge.check('total', contains_amount(a, 670), '$670 for two nights')
    check_read_only(judge, initial_db, after_db)


if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
