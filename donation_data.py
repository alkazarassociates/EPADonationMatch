"""Implementation of data storage for EPA
donation match program."""

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import dataclasses
import datetime
import os
import re
from typing import DefaultDict


NO_DATE_SUPPLIED = datetime.date(1980, 1, 1)


def object_from_dict(cls, field_mapping, type_mapping, values):
    """Make some object of type cls, mapping fields from values into parameter names."""
    # First check that our object is ok and produce a good error message if not.
    for source_field in field_mapping.values():
        if source_field not in values:
            raise KeyError(f"Could not find {source_field} in column names: {values.keys()}")
    parameters = {k: type_mapping.get(k, lambda x: x)(values[field_mapping[k]]) for k in field_mapping}
    return cls(**parameters)


def convert_fields(cls, values):
    """Make a dataclass object out of properly named strings"""
    for field in dataclasses.fields(cls):
        if field.type != str:
            # Special case booleans, as bool('False') == True
            if field.type == bool:
                values[field.name] = text_to_bool(values[field.name])
            else:
                values[field.name] = field.type(values[field.name])
    return values


def text_to_bool(text: str) -> bool:
    if text.lower() == 'true':
        return True
    if text.lower() == 'false':
        return False
    raise ValueError(f"Expected a TRUE or FALSE value, but got '{text}'")


def mark_to_bool(text: str) -> bool:
    """Is this cell in csv marked with an X?"""
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
    if words[0] in ['mr', 'mrs', 'miss', 'ms', 'mz']:
        words = words[1:]
    if words[-1] in ['junior', 'jr', 'iii', 'iv']:
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
                         'name': 'Name', 'address': 'Address', 'home_email': 'Home Email', 'store': 'Selected',
                         'phone': 'Phone #', 'no_e_card': 'No e-card', 'comments': 'Comments'}
        # Name is actually Name and Address.  Fix it here.
        if 'Address' not in values:
            name, address = values['Name'].split(',', 1)
            values['Name'] = name.strip()
            values['Address'] = address.strip()
        return object_from_dict(Recipient, field_mapping,
                                {'id': int, 'epa_email': lambda x: x.lower().strip(), 'no_e_card': mark_to_bool},
                                values)

    def is_valid(self) -> bool:
        return self.valid.lower() == 'true'  # Anything else is False


@dataclass(frozen=True)
class Donation:
    donor: int
    recipient: int
    date: datetime.date


@dataclass
class UpdateRecipientResult:
    success: bool
    new_count: int
    new_to_validate: list[int]
    errors: list[str]
    warnings: list[str]


# The current state of the donation match program.
class State:
    def __init__(self) -> None:
        self.donors: dict[int, Donor] = {}
        self.recipients: dict[int, Recipient] = {}
        self.donations: list[Donation] = []
        self.new_this_session: list[Donation] = []
        self._recipient_emails: dict[str, str] = {}  # For finding duplicates.
        self._recipient_normalized_names: dict[str, tuple[str, int]] = {}  # Also for finding duplicates.
        self._donations_to: DefaultDict[int, list[int]] = defaultdict(list)
        self._donations_from: DefaultDict[int, list[int]] = defaultdict(list)

    def update_donors(self, new_donor_list: list[dict]) -> None:
        for donor_dict in new_donor_list:
            if not donor_dict['Donor #']:
                continue  # Ignore incomplete donors
            donor = Donor.from_dict(donor_dict)
            # "Memory" is assumed to be corrected, do not stomp with re-imported data.
            if donor.id in self.donors:
                continue
            self.donors[donor.id] = donor

    def load_recipients(self, data):
        assert not self.recipients, "Loading recipients twice"
        for recipient_dict in data:
            recipient = Recipient(**convert_fields(Recipient, recipient_dict))
            assert recipient.id not in self.recipients
            self.recipients[recipient.id] = recipient
            assert recipient.epa_email not in self._recipient_emails
            self._recipient_emails[recipient.epa_email] = recipient.name
            self._recipient_normalized_names[normalize_name(recipient.name)] = \
                (recipient.name, recipient.id)

    def update_recipients(self, new_recipient_list: list[dict]) -> UpdateRecipientResult:
        ret = UpdateRecipientResult(success=True, new_count=0, new_to_validate=list(), errors=list(), warnings=list())
        for recipient_dict in new_recipient_list:
            if not recipient_dict['Recipient #']:
                continue  # Ignore incomplete recipients
            recipient = Recipient.from_dict(recipient_dict)
            self.update_recipient(recipient, ret)
            # If we have donations recorded in this recipient list, add them to the database.
            # This should be unusual, the result of manual editing.
            for key in recipient_dict:
                if key.startswith('Donor ') and recipient_dict[key]:
                    donation = Donation(donor=int(recipient_dict[key]), recipient=recipient.id, date=NO_DATE_SUPPLIED)
                    print(f"Adding donation while updating recipients: "
                          "{recipient.name} ({recipient.id}) from donor# {donation.donor}")
                    self.add_donation(donation)
        return ret

    def update_recipient(self, recipient: Recipient, result: UpdateRecipientResult) -> None:
        # "Memory" is assumed to be the source of truth, do not stomp with re-imported data.
        if recipient.id in self.recipients:
            return
        if recipient.epa_email in self._recipient_emails:
            result.errors.append(f"Duplicate email addresses used for {self._recipient_emails[recipient.epa_email]} "
                                 f"and {recipient.name}")
            result.success = False
            return
        self._recipient_emails[recipient.epa_email] = recipient.name
        name = normalize_name(recipient.name)
        if name in self._recipient_normalized_names:
            existing_name, existing_id = self._recipient_normalized_names[name]
            # Only warn about this, as the matching is not perfect.
            result.warnings.append(f"Duplicate recipient found:\n {recipient.name}, Recipient # {recipient.id}\n"
                                   f"might be\n {existing_name}, Recipient # {existing_id}")
        else:
            self._recipient_normalized_names[name] = (recipient.name, recipient.id)
        self.recipients[recipient.id] = recipient
        result.new_to_validate.append(recipient.id)
        result.new_count += 1

    # TODO Deal with better naming of add_donation and pledge
    def add_donation(self, donation: Donation) -> None:
        """Set up non-new donations.  Check for duplicates, don't mark as new."""
        assert self.recipients[donation.recipient].is_valid()
        # Don't allow duplicate donations.
        for d in self.donations:
            if d.recipient == donation.recipient and d.donor == donation.donor:
                if donation.date == NO_DATE_SUPPLIED:
                    pass  # Don't warn on hand edits that are already in the database.
                else:
                    print(f"Ignoring duplicate donation from {donation.donor} to {donation.recipient}")
                return
        self.donations.append(donation)
        self._donations_to[donation.recipient].append(donation.donor)
        self._donations_from[donation.donor].append(donation.recipient)

    def pledge(self, donor: Donor, recipient: Recipient) -> None:
        donation = Donation(donor=donor.id, recipient=recipient.id, date=datetime.date.today())
        self.donations.append(donation)
        self._donations_to[donation.recipient].append(donation.donor)
        self._donations_from[donation.donor].append(donation.recipient)
        self.new_this_session.append(donation)

    def valid_recipients(self) -> list[Recipient]:
        return [x for x in self.recipients.values() if x.is_valid()]

    def donations_to(self, recipient: Recipient) -> int:
        return len(self._donations_to[recipient.id])

    def donations_from(self, donor: Donor) -> int:
        return len(self._donations_from[donor.id])

    def remaining_pledges(self, donor: Donor) -> int:
        return donor.pledges - self.donations_from(donor)

    def calculate_store_count(self, donor: Donor, store: str) -> int:
        total = 0
        for d in self.donations:
            if d.donor == donor.id:
                if self.recipients[d.recipient].store == store:
                    total += 1
        return total

    def has_given(self, recipient: Recipient, donor: Donor) -> bool:
        for d in self.donations:
            if d.recipient == recipient.id and d.donor == donor.id:
                return True
        return False

    # TODO Should this be here or in donation_match?
    def remove_new_pledges(self, recipient: Recipient) -> None:
        for d in self.new_this_session:
            if d.recipient == recipient.id:
                self._donations_to[d.recipient].remove(d.donor)
                self._donations_from[d.donor].remove(d.recipient)
                self.donations.remove(d)
        self.new_this_session = [x for x in self.new_this_session if x.recipient != recipient.id]

    # TODO MOve to donation_match.py
    def try_to_swap(self):
        previous_score = self.score()
        new_index1 = random.randrange(len(self.new_this_session))
        donation1 = self.new_this_session[new_index1]
        new_index2 = random.randrange(len(self.new_this_session))
        if new_index1 == new_index2:
            return False
        donation2 = self.new_this_session[new_index2]
        if donation1.recipient == donation2.recipient:
            return False
        if donation1.donor == donation2.donor:
            return False
        index1 = self.donations.index(donation1)
        index2 = self.donations.index(donation2)
        self._swap_donation((index1, new_index1), (index2, new_index2))
        new_score = self.score()
        if new_score > previous_score:
            print(new_score)
            return True
        # Swap back
        self._swap_donation((index2, new_index2), (index1, new_index1))
        return False

    # TODO Move to donation_match.py
    def score(self) -> int:
        # Basics that are most important, but actually probably already maximized.
        total = 0
        for r in self.recipients.values():
            total += 100 * self.donations_to(r)
        for donor in self.donors.values():
            stores: Counter = Counter()
            for recipient_id in self._donations_from[donor.id]:
                stores[self.recipients[recipient_id].store] += 1
            # Add points for every time we are the most popular store, plus
            # less for second.  No points for third.
            stz = stores.most_common(2)
            if len(stz) > 0:
                total += stz[0][1] * 10
            if len(stz) > 1:
                total += stz[1][1]
        return total

    def write_recipient_table(self, filename: str) -> None:
        with open(filename, 'w', newline='') as csvfile:
            fields = ['Recipient #', 'Status', 'EPA Email', 'Name', 'Home Email',
                      'Phone #', 'Selected', 'Donor 1', 'Donor 2', 'Donor 3', 'Donor 4',
                      'Donor 5', 'Donor 6', 'Donor 7', 'Donor 8', 'Donor 9', 'Donor 10']
            w = csv.DictWriter(csvfile, fields, extrasaction='ignore')
            for r in self.recipients.values():
                to_write = {
                    'Recipient #': r.id, 'Status': r.status,
                    'EPA Email': r.epa_email, 'Name': r.name + ',' + r.address, 'Home Email': r.home_email,
                    'Selected': r.store
                }
                for count, donor_id in enumerate(self._donations_to[r.id]):
                    assert count <= 9
                    to_write[f'Donor {count+1}'] = donor_id
                w.writerow(to_write)

    def _swap_donation(self, d1: tuple[int, int], d2: tuple[int, int]) -> None:
        self._donations_to[self.donations[d1[0]].recipient].remove(self.donations[d1[0]].donor)
        self._donations_to[self.donations[d2[0]].recipient].remove(self.donations[d2[0]].donor)
        self._donations_from[self.donations[d1[0]].donor].remove(self.donations[d1[0]].recipient)
        self._donations_from[self.donations[d2[0]].donor].remove(self.donations[d2[0]].recipient)
        self._donations_to[self.donations[d1[0]].recipient].append(self.donations[d2[0]].donor)
        self._donations_to[self.donations[d2[0]].recipient].append(self.donations[d1[0]].donor)
        self._donations_from[self.donations[d1[0]].donor].append(self.donations[d2[0]].recipient)
        self._donations_from[self.donations[d2[0]].donor].append(self.donations[d1[0]].recipient)

        temp_donation: Donation = self.donations[d1[0]]
        self.donations[d1[0]] = Donation(donor=self.donations[d2[0]].donor,
                                         recipient=self.donations[d1[0]].recipient,
                                         date=self.donations[d1[0]].date)
        self.donations[d2[0]] = Donation(donor=temp_donation.donor,
                                         recipient=self.donations[d2[0]].recipient,
                                         date=self.donations[d2[0]].date)
        self.new_this_session[d1[1]] = self.donations[d1[0]]
        self.new_this_session[d2[1]] = self.donations[d2[0]]


def add_args(arg_parser):
    # No additional command line args needed yet.
    arg_parser.add_argument('--memory-dir', default=os.path.join(os.path.dirname(__file__), 'data'))


def load_csv(filename: str) -> list[dict]:
    if not os.path.exists(filename):
        return []
    with open(filename, 'r', newline='') as csvfile:
        r = csv.DictReader(csvfile)

        return list(r)


def load_state(args):
    if not os.path.isdir(args.memory_dir):
        os.mkdir(args.memory_dir)
    ret = State()
    recipient_data = load_csv(os.path.join(args.memory_dir, 'recipients.csv'))
    if recipient_data:
        ret.load_recipients(recipient_data)
    donar_data = load_csv(os.path.join(args.memory_dir, 'donors.csv'))
    if donar_data:
        ret.load_donors(donor_data)
    donation_data = load_csv(os.path.join(args.memory_dir, 'donations.csv'))
    if donation_data:
        ret.load_donations(donation_data)
    return ret


def save_state(args, data: State):
    _write_csv_file(args, 'recipients.csv', data.recipients.values())
    _write_csv_file(args, 'donors.csv', data.donors.values())
    _write_csv_file(args, 'donations.csv', data.donations)


def _write_csv_file(args, filename, things):
    if not things:
        return
    with open(os.path.join(args.memory_dir, filename), 'w', newline='') as outfile:
        wrote_headers = False
        w = csv.writer(outfile)
        for thing in things:
            if not wrote_headers:
                w.writerow([x.name for x in dataclasses.fields(thing)])
                wrote_headers = True
            w.writerow(dataclasses.asdict(thing).values())
