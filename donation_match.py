"""
donation_match:  Match donors to recipients, keeping legal requirements and fairness in mind.
"""

import argparse
import csv
import random
import sys

DONOR_SLOTS = ['Donor 1', 'Donor 2', 'Donor 3', 'Donor 4', 'Donor 5', 'Donor 6', 'Donor 7', 'Donor 8', 'Donor 9', 'Donor 10']

def donation_match(donors_list, recipients_list):
    donors = {}
    pledges = 0
    for donor in donors_list:
        donor['Donor #'] = int(donor['Donor #'])
        donor['remaining'] = int(donor['Pledge units'])
        pledges += donor['remaining']
        donors[donor['Donor #']] = donor

    recipients = {}
    for recipient in recipients_list:
        recipient['Recipient #'] = int(recipient['Recipient #'])
        recipient['received'] = 0
        recipient['Full'] = False
        recipients[recipient['Recipient #']] = recipient
        for d in DONOR_SLOTS:
            if recipient[d]:
                recipient[d] = int(recipient[d])
                recipient['received'] += 1
                donors[recipient[d]].remaining -= 1
                assert donors[recipient[d]].remaining >= 0

    # If we can possibly fill up all recipients, we aren't set up
    # to stop at the right time.  This will need to be fixed if this
    # ever fires.
    assert pledges < 10 * len(donors_list)

    while pledges:
        make_pledge(donors, recipients)
        pledges -= 1

    print(recipients)
                
def make_pledge(donors, recipients):
    while True:  # Keep trying until find a recipient who we can give to.
        # Of the recipients who have received the least, pick one at random.
        # This is make sure things spread evenly without a benefit to order
        # listed or alphabetical order etc.
        least_donations = min([x['received'] for x in recipients.values() if x['Full'] == False])
        lottery = [x for x in recipients.values() if x['received'] == least_donations and x['Full'] == False]
        if not lottery:
            # Everybody is full???
            assert False
        recipient = random.choice(lottery)
        # For the "first draft" match, just pick a donor at random who
        # 1) has the most number of pledges remaining
        # 2) Hasn't given to this recipient before.
        #
        # We will later try and cluster stores with particular donors.

        # If 1) and 2) don't have anybody in them, look at donors with fewer
        # pledges remaining.

        # If no donors can be found, this recipient is done--remove them.
        max_remaining = max([x['remaining'] for x in donors.values()])
        for remaining_value in range(max_remaining, -1, -1):
            possible_donors = [x for x in donors.values() if x['remaining'] == max_remaining]
            while possible_donors:
                donor = random.choice(possible_donors)
                nope = False
                for d in DONOR_SLOTS:
                    if recipient[d] == donor['Donor #']:
                        nope = True
                        break
                if nope:
                    possible_donors.remove(donor)
                    continue
                # SUCCESS.  We have a match.
                pledge(donor, recipient)
                return
            # Ok, nobody with the most remaining  can give.
            # Loop around with a lower remaining_value.
        # Ok, nobody at all can give!
        # Take this guy out of the list, as this won't change.
        recipient['Full'] = True


def pledge(donor, recipient):
    for d in DONOR_SLOTS:
        if recipient[d] == '':
            recipient[d] = donor['Donor #']
            recipient['received'] += 1
            donor['remaining'] -= 1
            assert donor['remaining'] >= 0
            return
        assert recipient[d] != donor['Donor #']
    else:
        assert False
        
def load_csv(filename):
    with open(filename, 'r', newline='') as csvfile:
        r = csv.DictReader(csvfile)

        return list(r)
        
def Main():
    parser = argparse.ArgumentParser(
        prog='donation_match',
        description="Match donors to recipients")
    parser.add_argument('donors')
    parser.add_argument('recipients')
    args = parser.parse_args()
    donation_match(load_csv(args.donors), load_csv(args.recipients))
    

if __name__ == '__main__':
    sys.exit(Main())
