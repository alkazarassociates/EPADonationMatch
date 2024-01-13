"""
donation_match:  Match donors to recipients, keeping legal requirements and
fairness in mind.
"""

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import datetime
import os
import random
import re
import sys

NO_DATE_SUPPLIED = datetime.date(1980, 1, 1)

def object_from_dict(cls, field_mapping, type_mapping, values):
    """Make some object of type cls, mapping fields from values into parameter names."""
    # First check that our object is ok and produce a good error message if not.
    for source_field in field_mapping.values():
        if source_field not in values:
            raise KeyError(f"Could not find {source_field} in column names: {values.keys()}")
    parameters = {k: type_mapping.get(k, lambda x: x)(values[field_mapping[k]]) for k in field_mapping}
    return cls(**parameters)

def text_to_bool(text: str) -> bool:
    if text.lower() == 'true':
        return True
    if text.lower() == 'false':
        return False
    raise ValueError(f"Expected a TRUE or FALSE value, but got '{text}'")

def mark_to_bool(text: str) -> bool:
    if text == '':
        return False
    if text.lower() == 'x':
        return True
    raise ValueError(f"Expected blank or 'x', but got '{text}'")

def normalize_name(text: str) -> str:
    """try and make the name as generic as possible."""
    # Split into words, remove whitespace.
    # lowercase everything.  Remove non letters.
    # Remove titles and suffixes ('mr', 'junior' etc)
    # Only look at first and last names of remainder.
    words = [x.strip() for x in text.split()]
    words = [x.lower() for x in words]
    words = [re.sub('[^a-z]', '', x) for x in words]
    if words[0] in ['mr', 'mr.', 'mrs', 'mrs.', 'miss', 'ms.', 'mz.']:
        words = words[1:]
    if words[-1] in ['junior', 'iii', 'iv']:
        words = words[:-1]
    return words[0] + ' ' + words[-1]

@dataclass(frozen=True)
class Donor:
    first: str
    last: str
    email: str
    pledges: int
    comments: str
    id: int

    
    @staticmethod
    def from_dict(values):
        """Convert a dict of values into a donor object"""
        field_mapping = {'first': 'First', 'last': 'Last', 'email': 'Email', 'pledges': 'Pledge units',
                         'comments': 'Comments', 'id': 'Donor #'}
        return object_from_dict(Donor, field_mapping, {'pledges': int, 'id': int}, values)

@dataclass(frozen=True)
class Recipient:
    id: int
    valid: str
    status: str
    epa_email: str
    name: str
    address: str
    home_email: str
    store: str
    phone: str
    no_e_card: bool
    comments: str

    @staticmethod
    def from_dict(values):
        """Convert a dict of values into a recipient object"""
        field_mapping = {'id': 'Recipient #', 'valid': 'Valid?', 'status': 'Status', 'epa_email': 'EPA Email',
                         'name': 'Name', 'address': 'Address', 'home_email': 'Home Email', 'store': 'Selected', 'phone': 'Phone #',
                         'no_e_card':'No e-card', 'comments': 'Comments'}
        # Name is actually Name and Address.  Fix it here.
        if 'Address' not in values:
            name, address = values['Name'].split(',', 1)
            values['Name'] = name
            values['Address'] = address
        return object_from_dict(Recipient, field_mapping,
                                {'id': int, 'epa_email': lambda x: x.lower().strip(), 'no_e_card': mark_to_bool}, values)

    def is_valid(self) -> bool:
        return self.valid.lower() == 'true'  # Anything else is False


@dataclass(frozen=True)
class Donation:
    donor: int
    recipient: int
    date: datetime.date

# The current state of the donation match program.
class State:
    def __init__(self) -> None:
        self.donors: dict[int, Donor] = {}
        self.recipients: dict[int, Recipient] = {}
        self.donations: list[Donation] = []
        self.new_this_session: list[Donation] = []
        self._recipient_emails: dict[str, str] = {}  # For finding duplicates.
        self._recipient_normalized_names: dict[str, tuple[str, int]] = {}  # Also for finding duplicates.

    def update_donors(self, new_donor_list: list[dict]) -> None:
        for donor_dict in new_donor_list:
            if not donor_dict['Donor #']:
                continue  # Ignore incomplete donors
            donor = Donor.from_dict(donor_dict)
            # "Memory" is assumed to be corrected, do not stomp with re-imported data.
            if donor.id in self.donors:
                continue
            self.donors[donor.id] = donor

    def update_recipients(self, new_recipient_list: list[dict]) -> None:
        for recipient_dict in new_recipient_list:
            if not recipient_dict['Recipient #']:
                continue  # Ignore incomplete recipients
            recipient = Recipient.from_dict(recipient_dict)
            # "Memory" is assumed to be the source of truth, do not stomp with re-imported data.
            if recipient.id in self.recipients:
                continue
            if recipient.epa_email in self._recipient_emails:
                raise ValueError(f"Duplicate email addresses used for {self._recipient_emails[recipient.epa_email]} and {recipient.name}")
            self._recipient_emails[recipient.epa_email] = recipient.name
            name = normalize_name(recipient.name)
            if name in self._recipient_normalized_names:
                existing_name, existing_id = self._recipient_normalized_names[name]
                # Only warn about this, as the matching is not perfect.
                print("Duplicate recipient found:")
                print(f" {recipient.name}, Recipient # {recipient.id}")
                print("might be")
                print(f" {existing_name}, Recipient # {existing_id}")
            else:
                self._recipient_normalized_names[name] = (recipient.name, recipient.id)
            self.recipients[recipient.id] = recipient
            # If we have donations recorded in this recipient list, add them to the database.
            # This should be unusual, the result of manual editing.
            for key in recipient_dict:
                if key.startswith('Donor ') and recipient_dict[key]:
                    donation = Donation(donor=int(recipient_dict[key]), recipient = recipient.id, date=NO_DATE_SUPPLIED)
                    print(f"Adding donation while updating recipients: {recipient.name} ({recipient.id}) from donor# {donation.donor}")
                    self.add_donation(donation)

    def add_donation(self, donation: Donation) -> None:
        # Don't allow duplicate donations.
        for d in self.donations:
            if d.recipient == donation.recipient and d.donor == donation.donor:
                if donation.date == NO_DATE_SUPPLIED:
                    pass  # Don't warn on hand edits that are already in the database.
                else:
                    print(f"Ignoring duplicate donation from {donation.donor} to {donation.recipient}")
                return
        self.donations.append(donation)

def load_state(fn):
    if os.path.exists(fn):
        assert False, "Not implemented"
    return State()

DONOR_SLOTS = ['Donor 1', 'Donor 2', 'Donor 3', 'Donor 4', 'Donor 5',
               'Donor 6', 'Donor 7', 'Donor 8', 'Donor 9', 'Donor 10']
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
        recipient['Full'] = True
        recipients[recipient['Recipient #']] = recipient
        for d in DONOR_SLOTS:
            if recipient[d]:
                recipient[d] = int(recipient[d])
                recipient['received'] += 1
                donors[recipient[d]].remaining -= 1
                assert donors[recipient[d]].remaining >= 0
            else:
                recipient['Full'] = False
    new_pledges = []

    for recipient in recipients_list:
        if recipient['Full']:
            continue
        if pledges < (len(DONOR_SLOTS) - recipient['received']):
            continue  # We can't do this one, or probably any.
        while not recipient['Full']:
            if not find_pledge(recipient, donors, recipients):
                remove_new_pledges(recipient)
                break

    optimize(donors, recipients)

    return donors, recipients

def find_pledge(recipient, donors, recipients):
    best_donor = None
    best_store_count = 0
    for donor in donors.values():
        # Requirements:
        # Has pledges remaining
        # Has not given to this recipient.
        #   Of those: pick the one with the most cards from this store.
        if donor['remaining'] > 0 and not has_given(recipient, donor):
            store_count = calculate_store_count(donor,
                                                recipient['Selected'],
                                                recipients)
            if best_donor is None:
                best_donor = donor
                best_store_count = store_count
            elif store_count > best_store_count:
                best_donor = donor
                best_store_count = store_count
    if best_donor is not None:
        pledge(best_donor, recipient)
        return True
    return False

def pledge(donor, recipient):
    for d in DONOR_SLOTS:
        if recipient[d] == '':
            recipient[d] = donor['Donor #']
            recipient['received'] += 1
            donor['remaining'] -= 1
            assert donor['remaining'] >= 0
            if recipient['received'] == len(DONOR_SLOTS):
                recipient['Full'] = True
            return
        assert recipient[d] != donor['Donor #']
    else:
        assert False

def has_given(recipient, donor):
    for d in DONOR_SLOTS:
        if recipient[d] == donor['Donor #']:
            return True
    return False

def calculate_store_count(donor, store, recipients):
    total = 0
    return total

def load_csv(filename):
    with open(filename, 'r', newline='') as csvfile:
        r = csv.DictReader(csvfile)

        return list(r)

def optimize(donors, recipients):
    # Try swapping donor/recipient pairs until we can't find
    # one that improves our score
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
    recipient1[donor_slot1], recipient2[donor_slot2] = \
        recipient2[donor_slot2], recipient1[donor_slot1]
    new_score = score(donors, recipients)
    if new_score > previous_score:
        print(new_score)
        return True
    # Swap back
    recipient1[donor_slot1], recipient2[donor_slot2] = \
        recipient2[donor_slot2], recipient1[donor_slot1]
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
        fields = ['Recipient #','Status','EPA Email','Name','Home Email',
                  'Phone #','Selected','Donor 1','Donor 2','Donor 3','Donor 4',
                  'Donor 5','Donor 6','Donor 7','Donor 8','Donor 9','Donor 10']
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
            these_recipients = \
                [r for r in recipients.values() if has_donor(r, donor)]
            recipient_list = ''.join(
                [recipient_template.format(**recipient)
                 for recipient in these_recipients])
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
    d, r = donation_match(data)

    if args.recip_out:
        write_recipient_table(args.recip_out, r)

    if args.donor_out:
        write_donors_report(args.donor_out, d, r)


if __name__ == '__main__':
    sys.exit(Main())
