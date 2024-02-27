"""
donation_match:  Match donors to recipients, keeping legal requirements and
fairness in mind.
"""

import argparse
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


def find_valid_pledge(data: dd.State, recipient: dd.Recipient) -> bool:
    best_donor = None
    best_store_count = 0
    for donor in data.donors.values():
        # Requirements:
        # Has pledges remaining
        # Has not given to this recipient.
        #   Of those: pick the one with the most cards from this store.
        if data.remaining_pledges(donor) > 0 and not data.has_given(recipient, donor):
            store_count = data.calculate_store_count(donor, recipient.store)
            if best_donor is None:
                best_donor = donor
                best_store_count = store_count
            elif store_count > best_store_count:
                best_donor = donor
                best_store_count = store_count
    if best_donor is not None:
        data.pledge(best_donor, recipient)
        return True
    return False


def donation_match(data: dd.State) -> None:
    for recipient in data.valid_recipients():
        while recipient_remaining_need(data, recipient):
            if not find_valid_pledge(data, recipient):
                data.remove_new_pledges(recipient)
                break
    optimize(data)


def optimize(data: dd.State) -> None:
    # Try swapping donor/recipient pairs until we can't find
    # one that improves our score
    iterations = 0
    while iterations < ITERATION_COUNT:
        if data.try_to_swap():
            print(iterations)
            iterations = 0
        else:
            iterations += 1


def write_donors_report(data: dd.State, filename: str) -> None:
    with open(filename, 'w') as report:
        for donor in data.donors.values():
            recipients = data._donations_from[donor.id]
            recipient_list = ''.join(
                [recipient_template.format(**data.recipients[recipient])
                 for recipient in recipients])
            report.write(
                donor_report_template.format(**donor,
                                             recipient_list=recipient_list))


def Main():
    parser = argparse.ArgumentParser(
        prog='donation_match',
        description="Match donors to recipients")
    parser.add_argument('donors')
    parser.add_argument('recipients')
    parser.add_argument('--memory', default='memory.csv')
    parser.add_argument('--recip-out')
    parser.add_argument('--donor-out')
    args = parser.parse_args()

    data = load_state(args.memory)
    data.update_donors(load_csv(args.donors))
    data.update_recipients(load_csv(args.recipients))
    data.donation_match()

    if args.recip_out:
        data.write_recipient_table(args.recip_out)

    if args.donor_out:
        data.write_donors_report(args.donor_out)

    data.write_memory()


if __name__ == '__main__':
    sys.exit(Main())
