"""
donation_match:  Match donors to recipients, keeping legal requirements and fairness in mind.
"""

import argparse
from collections import Counter
import csv
import random
import sys

DONOR_SLOTS = ['Donor 1', 'Donor 2', 'Donor 3', 'Donor 4', 'Donor 5', 'Donor 6', 'Donor 7', 'Donor 8', 'Donor 9', 'Donor 10']
ITERATION_COUNT = 10000

def donation_match(donors_list, recipients_list):
    donors = {}
    pledges = 0
    for donor in donors_list:
        if donor['Email'] == '':
            continue
        donor['Donor #'] = int(donor['Donor #'])
        donor['remaining'] = int(donor['Pledge units'])
        pledges += donor['remaining']
        donors[donor['Donor #']] = donor

    recipients = {}
    for recipient in recipients_list:
        if recipient['EPA Email'] == '':
            continue
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

    optimize(donors, recipients)
    
    return donors, recipients

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

def optimize(donors, recipients):
    # Try swapping donor/recipient pairs until we can't find one that improves our score.
    iterations = 0
    while iterations < ITERATION_COUNT:
        if maybe_swap(donors, recipients):
            iterations = 0
        else:
            iterations += 1

def maybe_swap(donors, recipients):
    previous_score = score(donors, recipients)
    recipient1 = random.choice(list(recipients.values()))
    donor_slot1 = random.choice([d for d in DONOR_SLOTS if recipient1[d]])
    recipient2 = random.choice(list(recipients.values()))
    donor_slot2 = random.choice([d for d in DONOR_SLOTS if recipient2[d]])
    if recipient1 == recipient2:
        return False
    if recipient1[donor_slot1] == recipient2[donor_slot2]:
        return False
    recipient1[donor_slot1], recipient2[donor_slot2] = recipient2[donor_slot2], recipient1[donor_slot1]
    new_score = score(donors, recipients)
    if new_score > previous_score:
        print(new_score)
        return True
    # Swap back
    recipient1[donor_slot1], recipient2[donor_slot2] = recipient2[donor_slot2], recipient1[donor_slot1]
    return False

def score(donors, recipients):
    # Basics that are most important, but actually probably already maximized.
    total = 0
    for r in recipients.values():
        these_donors = set()
        for d in DONOR_SLOTS:
            if r[d]:
                total += 100  # The most help we give everyone the better.
                if r[d] in these_donors:
                    return 0   # Violation of rule!
                these_donors.add(r[d])
    for d in donors.values():
        stores = Counter()
        these_recipients = [r for r in recipients.values() if has_donor(r, d)]
        for r in these_recipients:
            stores[r['Selected']] += 1
        # Add points for every time we are the most popular store, plus
        # less for second.  No points for third.
        stz = stores.most_common(2)
        total += stz[0][1] * 10
        if len(stz) > 1:
            total += stz[1][1]
    return total
        

def has_donor(recipient, donor):
    for d in DONOR_SLOTS:
        if recipient[d] == donor['Donor #']:
            return True
    return False

def write_recipient_table(filename, recipients):
    with open(filename, 'w', newline='') as csvfile:
        fields = ['Recipient #','Status','EPA Email','Name','Home Email','Phone #','Selected','Donor 1','Donor 2','Donor 3','Donor 4','Donor 5','Donor 6','Donor 7','Donor 8','Donor 9','Donor 10']
        w = csv.DictWriter(csvfile, fields, extrasaction='ignore')
        for r in recipients.values():
            w.writerow(r)

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
def write_donors_report(filename, donors, recipients):
    with open(filename, 'w') as report:
        for donor in donors.values():
            these_recipients = [r for r in recipients.values() if has_donor(r, donor)]
            recipient_list = ''.join([recipient_template.format(**recipient) for recipient in these_recipients])
            report.write(donor_report_template.format(**donor, recipient_list=recipient_list))

def Main():
    parser = argparse.ArgumentParser(
        prog='donation_match',
        description="Match donors to recipients")
    parser.add_argument('donors')
    parser.add_argument('recipients')
    parser.add_argument('--recip-out')
    parser.add_argument('--donor-out')
    args = parser.parse_args()
    d, r = donation_match(load_csv(args.donors), load_csv(args.recipients))

    if args.recip_out:
        write_recipient_table(args.recip_out, r)

    if args.donor_out:
        write_donors_report(args.donor_out, d, r)


if __name__ == '__main__':
    sys.exit(Main())
