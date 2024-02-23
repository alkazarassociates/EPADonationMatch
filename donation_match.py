"""
donation_match:  Match donors to recipients, keeping legal requirements and
fairness in mind.
"""

import argparse
import os
import random
import sys
import cProfile

DONATIONS_PER_RECIPIENT: int = 10  # How many gift cards to be received
EPAAA_DONATIONS: int = 1  # How many slots does EPAA fill?  Set to zero for none.
ITERATION_COUNT = 10000  # How hard to try and optimize.

NO_DATE_SUPPLIED = datetime.date(1980, 1, 1)

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
