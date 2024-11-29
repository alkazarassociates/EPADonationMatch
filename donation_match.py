"""
donation_match:  Match donors to recipients, keeping legal requirements and
fairness in mind.
"""

import argparse
from dataclasses import dataclass
import os
import random
import sys
import cProfile

import donation_data as dd


DONATIONS_PER_RECIPIENT: int = 10  # How many gift cards to be received
EPAAA_DONATIONS: int = 1  # How many slots does EPAA fill?  Set to zero for none.
ITERATION_COUNT = 10000  # How hard to try and optimize.

donor_report_template = """
------ Donor {Donor #} -----
{First} {Last}:
{Email}
{recipient_list}
"""

recipient_template = """
Store {Selected}
{Name} {Home Email}

"""


def recipient_remaining_need(data: dd.State, recipient: dd.Recipient) -> int:
    return DONATIONS_PER_RECIPIENT - data.donations_to(recipient) - EPAAA_DONATIONS


def donor_remaining_pledges(data: dd.State, donor: dd.Donor) -> int:
    return donor.pledges - data.donations_from(donor)


def find_valid_pledge(data: dd.State, donor: dd.Donor) -> bool:
    best_recipient = None
    best_store_count = 0
    for recipient in data.valid_recipients():
        # Requirements:
        #  Has not received the limit in dondations.
        #  Has not received from this donor.
        #  Of those: pick one that matches the stores we've already used.
        if recipient_remaining_need(data, recipient) > 0 and not data.has_given(recipient, donor):
            store_count = data.calculate_store_count(donor, recipient.store)
            if best_recipient is None:
                best_recipient = recipient
                best_store_count = store_count
            elif store_count > best_store_count:
                best_recipient = recipient
                best_store_count = store_count
    if best_recipient is not None:
        data.pledge(donor, best_recipient)
        return True
    return False


def try_to_swap(data: dd.State) -> bool:
    previous_score = data.score()
    new_index1 = random.randrange(len(data.new_this_session))
    donation1 = data.new_this_session[new_index1]
    if donation1.donor == dd.ASSOCIATION_ID:
        return False
    new_index2 = random.randrange(len(data.new_this_session))
    if new_index1 == new_index2:
        return False
    donation2 = data.new_this_session[new_index2]
    if donation1.recipient == donation2.recipient:
        return False
    if donation1.donor == donation2.donor:
        return False
    if donation2.donor == dd.ASSOCIATION_ID:
        return False
    if data.has_given_id(donation1.recipient, donation2.donor):
        return False
    if data.has_given_id(donation2.recipient, donation1.donor):
        return False
    index1 = data.donations.index(donation1)
    index2 = data.donations.index(donation2)
    data._swap_donation((index1, new_index1), (index2, new_index2))
    new_score = data.score()
    if new_score > previous_score:
        print(new_score, end='')
        return True
    # Swap back
    data._swap_donation((index2, new_index2), (index1, new_index1))
    return False


@dataclass
class MatchResult:
    success: bool
    new_donations: int


def add_final_pledges(data: dd.State) -> None:
    assert data.epaaa is not None  # double check that EPAAA is set up.
    for recipient in data.recipients.values():
        if recipient_remaining_need(data, recipient) == 0:
            while data.epaaa_donations_to(recipient) < EPAAA_DONATIONS:
                data.pledge(data.epaaa, recipient)


def donation_match(data: dd.State) -> MatchResult:
    result = MatchResult(success=True, new_donations=0)
    for donor in data.donors.values():
        while donor_remaining_pledges(data, donor) > 0:
            if not find_valid_pledge(data, donor):
                data.remove_new_pledges(donor)
                break
    optimize(data)
    add_final_pledges(data)  # EPAAA contributions
    data.validate()
    result.new_donations = len(data.new_this_session)
    return result


def optimize(data: dd.State) -> None:
    # Try swapping donor/recipient pairs until we can't find
    # one that improves our score
    if len(data.new_this_session) == 0:
        return
    iterations = 0
    while iterations < ITERATION_COUNT:
        if try_to_swap(data):
            print(f" after {iterations} iterations")
            iterations = 0
        else:
            iterations += 1


def report(result: MatchResult, data: dd.State) -> str:
    if result.success:
        return f"Success, {result.new_donations} donations assigned."
    else:
        return "Donation match failed."


def Main():
    parser = argparse.ArgumentParser(
        prog='donation_match',
        description="Match donors to recipients")
    dd.add_args(parser)
    args = parser.parse_args()

    data = dd.load_state(args)

    result = donation_match(data)

    if result.success:
        # Don't update the saved state unless all the reports
        # can be updated.
        dd.update_recipient_view(args, data)
        dd.update_donor_view(args, data)
        dd.update_epaaa_view(args, data)

        dd.save_state(args, data)

    print(report(result, data))


if __name__ == '__main__':
    sys.exit(Main())
