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


# How many gift cards to be received
DONATIONS_PER_RECIPIENT: int = 10
# How many recipients each donor can have per wave.
# This is a limitation of the mail merge step.
MAX_DONATIONS_PER_WAVE: int = 10

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
    return DONATIONS_PER_RECIPIENT - data.donations_to(recipient)


def donor_remaining_pledges(data: dd.State, donor: dd.Donor) -> int:
    return donor.pledges - data.donations_from(donor)


def find_valid_pledge(data: dd.State, donor: dd.Donor) -> bool:
    best_recipient = None
    best_store_count = 0
    assert data.epaaa
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
        # Deal with EPAAA pledges.
        # We do it here, because we only want to add EPAAA pledges to recipients
        # already getting donations.
        if data.epaaa_donations_to(best_recipient) == 0:
            if donor_remaining_pledges(data, data.epaaa) > 0:
                data.pledge(data.epaaa, best_recipient)
        return True
    return False


def try_to_swap(data: dd.State) -> bool:
    previous_score = data.score()
    new_index1 = random.randrange(len(data.new_this_session))
    donation1 = data.new_this_session[new_index1]
    assert data.epaaa
    if donation1.donor == data.epaaa.id:
        return False
    new_index2 = random.randrange(len(data.new_this_session))
    if new_index1 == new_index2:
        return False
    donation2 = data.new_this_session[new_index2]
    if donation1.recipient == donation2.recipient:
        return False
    if donation1.donor == donation2.donor:
        return False
    if donation2.donor == data.epaaa.id:
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


def donation_match(args, data: dd.State) -> MatchResult:
    assert data.epaaa
    result = MatchResult(success=True, new_donations=0)
    for donor in data.donors.values():
        if donor.id == data.epaaa.id:
            continue  # Don't assign all 500 now.
        session_donation_count = 0
        while donor_remaining_pledges(data, donor) > 0 and session_donation_count < MAX_DONATIONS_PER_WAVE:
            if not find_valid_pledge(data, donor):
                # Normally don't assign any donations to a donor who won't
                # be getting all of their pledges.  '--mop-up' can be
                # specified to assign any remaining pledges if this isn't
                # desired.
                if not args.mop_up:
                    data.remove_new_pledges(donor)
                break
            session_donation_count += 1
    optimize(data)
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
    print(f"{iterations} with no improvements found.  Optimization complete.")


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
    parser.add_argument('--mop-up', action='store_true')
    args = parser.parse_args()

    data = dd.load_state(args)

    result = donation_match(args, data)

    if result.success:
        # Don't update the saved state unless all the reports
        # can be updated.
        dd.update_recipient_view(args, data)
        dd.update_donor_view(args, data)
        dd.update_epaaa_view(args, data)

        dd.save_state(args, data)

    print(report(result, data))

    return 0 if result.success else 1


if __name__ == '__main__':
    sys.exit(Main())
