"""Implementation of data storage for EPA
donation match program."""

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import dataclasses
import datetime
import os
from pathlib import Path
import re
import shutil
from typing import DefaultDict, Dict, Optional


NO_DATE_SUPPLIED = datetime.date(1980, 1, 1)
ASSOCIATION_ID = 1


def PartialKeyFind(values, partial_key):
    """Given a partial key, return the shortest key in values that contains
    that text."""
    if partial_key in values:
        return partial_key
    best_key = None
    for key in values:
        if (partial_key in key and
            (best_key is None or len(best_key) > len(key))):
            best_key = key
    return best_key
    
def LooseLookup(values, partial_key):
    """Given a partial key, return the value that matches the shortest
    key containing that text."""
    # If we have a exact match, that is the best we can do.
    best_key = PartialKeyFind(values, partial_key)
    if best_key is None:
        return None
    return values[best_key]


def object_from_dict(cls, field_mapping, type_mapping, values_raw):
    """Make some object of type cls, mapping fields from values into parameter names."""
    values = {k.strip(): values_raw[k] for k in values_raw}
    # First check that our object is ok and produce a good error message if not.
    for source_field in field_mapping.values():
        if PartialKeyFind(values, source_field) == None:
            raise KeyError(f"Could not find {source_field} in column names: {values.keys()}")
    parameters = {k: type_mapping.get(k, lambda x: x)(LooseLookup(values, field_mapping[k])) for k in field_mapping}
    return cls(**parameters)


def convert_fields(cls, values):
    """Make a dataclass object out of properly named strings"""
    for field in dataclasses.fields(cls):
        if field.type != str:
            # Special case booleans, as bool('False') == True
            if field.type == bool:
                values[field.name] = text_to_bool(values[field.name])
            if field.type == datetime.date:
                values[field.name] = datetime.date.fromisoformat(values[field.name])
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
        field_mapping = {'id': 'Respondent', 'valid': 'Validity', 'status': 'Employment Status', 'epa_email': 'EPA Email',
                         'name': 'Name', 'address': 'Address', 'home_email': 'Home Email', 'store': 'store for which you would',
                         'phone': 'Phone #', 'no_e_card': 'No printer or smartphone', 'comments': 'comments'}
        # Name is actually Name and Address.  Fix it here.
        if 'Address' not in values:
            # We always print Name, Address, so getting the splitting
            # right is nice-to-have.  But it is nice, to have, IMHO.
            if ',' in LooseLookup(values, 'Name and Address'):
                name, address = LooseLookup(values, 'Name and Address').split(',', 1)
                values['Name'] = name.strip()
                values['Address'] = address.strip()
            else:
                values['Address'] = ''
                values['Name'] = LooseLookup(values, 'Name and Address')
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


@dataclass
class UpdateDonorResult:
    success: bool
    new_count: int
    errors: list[str]
    warnings: list[str]


# The current state of the donation match program.
class State:
    def __init__(self) -> None:
        self.epaaa: Optional[Donor] = None
        self.donors: dict[int, Donor] = {}
        self.recipients: dict[int, Recipient] = {}
        self.donations: list[Donation] = []
        self.new_this_session: list[Donation] = []
        self._recipient_emails: dict[str, str] = {}  # For finding duplicates of epa_emails.
        self._recipient_normalized_names: dict[str, tuple[str, int]] = {}  # Also for finding duplicates.
        self._recipient_home_emails: dict[str, str] = {}  # For finding duplicates of home_emails.
        self._donations_to: DefaultDict[int, list[int]] = defaultdict(list)
        self._donations_from: DefaultDict[int, list[int]] = defaultdict(list)
        self._prev_donations_to: DefaultDict[int, int] = defaultdict(int)

    def update_donors(self, new_donor_list: list[dict]) -> UpdateDonorResult:
        ret = UpdateDonorResult(success=True, new_count=0, warnings=list(), errors=list())
        for donor_dict in new_donor_list:
            if not donor_dict['Donor #']:
                continue  # Ignore incomplete donors
            donor = Donor.from_dict(donor_dict)
            # "Memory" is assumed to be corrected, do not stomp with re-imported data.
            if donor.id in self.donors:
                continue
            if not donor.first and not donor.last:
                continue  # Ignore incomplete donors
            self.donors[donor.id] = donor
            ret.new_count += 1
            if donor.id == ASSOCIATION_ID:
                assert self.epaaa is None
                self.epaaa = donor
        # By the time we are done updating donors, even the first time, we should have
        # The EPAAA defined.
        if self.epaaa is None:
            ret.success = False
            ret.errors.append(f"No definition for EPAAA as a donor with ID {ASSOCIATION_ID}")
        return ret

    def load_donors(self, data) -> None:
        assert not self.donors, "Loading donors twice"
        for donor_dict in data:
            donor = Donor(**convert_fields(Donor, donor_dict))
            assert donor.id not in self.donors
            self.donors[donor.id] = donor
            if donor.id == ASSOCIATION_ID:
                assert not self.epaaa
                self.epaaa = donor

    def load_recipients(self, data) -> None:
        assert not self.recipients, "Loading recipients twice"
        for recipient_dict in data:
            recipient = Recipient(**convert_fields(Recipient, recipient_dict))
            print(recipient)
            assert recipient.id not in self.recipients
            self.recipients[recipient.id] = recipient
            assert recipient.epa_email not in self._recipient_emails
            assert recipient.home_email not in self._recipient_home_emails
            self._recipient_emails[recipient.epa_email] = recipient.name
            self._recipient_home_emails[recipient.home_email] = recipient.name
            self._recipient_normalized_names[normalize_name(recipient.name)] = \
                (recipient.name, recipient.id)

    def load_donations(self, data) -> None:
        assert not self.donations, "Loading donations twice"
        for donation_dict in data:
            donation = Donation(**convert_fields(Donation, donation_dict))
            self.add_donation(donation)

    def update_recipients(self, new_recipient_list: list[dict]) -> UpdateRecipientResult:
        ret = UpdateRecipientResult(success=True, new_count=0, new_to_validate=list(), errors=list(), warnings=list())
        for recipient_dict in new_recipient_list:
            if not recipient_dict['Respondent #']:
                continue  # Ignore incomplete recipients
            recipient = Recipient.from_dict(recipient_dict)
            print(recipient)
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
        if recipient.home_email in self._recipient_home_emails:
            result.errors.append("Duplicate home email addresses used for "
                                 f"{self._recipient_home_emails[recipient.home_email]} and {recipient.name}")
            result.success = False
            return
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
        self._prev_donations_to[donation.recipient] += 1

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

    def donors_for(self, recip_id: int) -> list[int]:
        return sorted(self._donations_to[recip_id])

    def donations_from(self, donor: Donor) -> int:
        return len(self._donations_from[donor.id])

    def remaining_pledges(self, donor: Donor) -> int:
        return donor.pledges - self.donations_from(donor)

    def epaaa_donations_to(self, recipient: Recipient) -> int:
        return len([donor for donor in self._donations_to[recipient.id] if donor == ASSOCIATION_ID])

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

    def has_given_id(self, recipient: int, donor: int) -> bool:
        return self.has_given(self.recipients[recipient], self.donors[donor])

    # TODO Should this be here or in donation_match?
    def remove_new_pledges(self, donor: Donor) -> None:
        for d in self.new_this_session:
            if d.donor == donor.id:
                self._donations_to[d.recipient].remove(d.donor)
                self._donations_from[d.donor].remove(d.recipient)
                self.donations.remove(d)
        self.new_this_session = [x for x in self.new_this_session if x.donor != donor.id]

    # TODO Move to donation_match.py
    def score(self) -> int:
        # Basics that are most important, but actually probably already maximized.
        total = 0
        for r in self.recipients.values():
            total += 100 * self.donations_to(r)
        for donor in self.donors.values():
            if donor.id == ASSOCIATION_ID:
                continue
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

    def validate(self):
        # Every recipient has an entry for email and normalized name
        #  It's ok for it not to point to THAT recipient.
        # Every donation has a valid donor and recipient.
        # Each donation donor/recipient pair is unique.
        # No donor has more than their desired donations.
        # No recipient has more than the proper number of donations.
        # Warn if any invalid recipient has donations.
        for r in self.recipients:
            assert self.recipients[r].epa_email in self._recipient_emails
            assert self.recipients[r].home_email in self._recipient_home_emails
            assert normalize_name(self.recipients[r].name) in self._recipient_normalized_names
        donation_set = set()
        for donation in self.donations:
            assert donation.recipient in self.recipients
            assert donation.donor in self.donors
            assert (donation.recipient, donation.donor) not in donation_set
            donation_set.add((donation.recipient, donation.donor))
            assert donation.donor in self._donations_to[donation.recipient]
            assert donation.recipient in self._donations_from[donation.donor]
        for donor in self.donors:
            count = 0
            for donation in self.donations:
                if donation.donor == donor:
                    count += 1
            assert count <= self.donors[donor].pledges
        for recipient in self.recipients:
            count = 0
            for donation in self.donations:
                if donation.recipient == recipient:
                    count += 1
            assert count <= 10   # This is dependent on numbers in donation_match
            if not self.recipients[recipient].is_valid and count > 0:
                print("WARNING: Invalid recipient has received donations")


def add_args(arg_parser):
    """Add command line arguments common to all users of data"""
    arg_parser.add_argument('--memory-dir', default=os.path.join(os.path.dirname(__file__), 'data'))


def load_csv(filename: str) -> list[dict]:
    with open(filename, 'r', newline='') as csvfile:
        r = csv.DictReader(csvfile)

        return list(r)


def load_state(args):
    if not os.path.isdir(args.memory_dir):
        os.mkdir(args.memory_dir)
    ret = State()
    recipient_filename = os.path.join(args.memory_dir, 'recipients.csv')
    if os.path.exists(recipient_filename):
        recipient_data = load_csv(recipient_filename)
        ret.load_recipients(recipient_data)
    donor_filename = os.path.join(args.memory_dir, 'donors.csv')
    if os.path.exists(donor_filename):
        donor_data = load_csv(donor_filename)
        ret.load_donors(donor_data)
    donation_filename = os.path.join(args.memory_dir, 'donations.csv')
    if os.path.exists(donation_filename):
        donation_data = load_csv(donation_filename)
        ret.load_donations(donation_data)
    return ret


def save_state(args, data: State):
    # Delete .tmp files
    # Write .tmp files
    # Transaction:
    #  Rename .csv to .bak
    #  Rename .tmp to .csv
    state_to_save = {
        Path(args.memory_dir, 'recipients.csv'): data.recipients.values(),
        Path(args.memory_dir, 'donors.csv'): data.donors.values(),
        Path(args.memory_dir, 'donations.csv'): data.donations
    }
    for fn in state_to_save.keys():
        fn.with_suffix('.tmp').unlink(True)

    for fn in state_to_save.keys():
        _write_csv_file(fn.with_suffix('.tmp'), state_to_save[fn])

    to_rollback = []
    delete_on_success = []
    try:
        for fn in state_to_save.keys():
            csv_fn = fn.with_suffix('.csv')
            if csv_fn.exists():
                bak_fn = csv_fn.with_suffix('.bak')
                csv_fn.rename(bak_fn)
                to_rollback.append((csv_fn, bak_fn))
                delete_on_success.append(bak_fn)
            tmp_fn = fn.with_suffix('.tmp')
            tmp_fn.rename(csv_fn)
            print(f"Wrote {csv_fn}")
            to_rollback.append((tmp_fn, csv_fn))
        # All successful!  No need to rollback.
        to_rollback = []
        for fn in delete_on_success:
            fn.unlink()
    finally:
        for rb in reversed(to_rollback):
            original, renamed = rb
            renamed.rename(original)  # Roll it back


def _write_csv_file(filename, things):
    if not things:
        filename.touch()
        return
    with open(filename, 'w', newline='') as outfile:
        wrote_headers = False
        w = csv.writer(outfile)
        for thing in things:
            if not wrote_headers:
                w.writerow([x.name for x in dataclasses.fields(thing)])
                wrote_headers = True
            w.writerow(dataclasses.asdict(thing).values())


def _backup_name(original_fn: Path) -> Path:
    """
    Find a good backup name for this file.
    Keep the extension.
    Number backups sequentially.
    Add 'old' to the name to make it clear.
    """
    name = original_fn.stem
    backup_number = 0
    while True:
        backup_number += 1
        candidate = original_fn.with_stem(f"old_{name}_{backup_number}")
        if not candidate.exists():
            return candidate


def _backup_if_needed(file_to_write: Path) -> None:
    """
    If the file we are about to write exists, backup
    the existing copy.
    """
    if file_to_write.exists():
        shutil.move(file_to_write, _backup_name(file_to_write))


def update_recipient_view(args, data: State) -> None:
    """Write an auditable report of all recipients"""
    path = Path(args.memory_dir, 'recipient_view.csv')
    _backup_if_needed(path)
    with open(path, 'w', newline='') as outfile:
        max_donations = 0
        for recip in data.valid_recipients():
            if data.donations_to(recip) > max_donations:
                max_donations = data.donations_to(recip)
        w = csv.writer(outfile)
        headings = [
            'Name',
            'Recipient #',
            'Status',
            'EPA Email',
            'Address',
            'Home Email',
            'Store',
            'Phone',
            'Previous Donations',
            'Total Donations']
        for i in range(max_donations):
            headings.append(f'Donor {i + 1}')
        w.writerow(headings)
        for recip in data.valid_recipients():
            has_donation = False
            row = [recip.name, recip.id, recip.status, recip.epa_email, recip.address,
                   recip.home_email, recip.store + ('*' if recip.no_e_card else ''), recip.phone,
                   data._prev_donations_to[recip.id], data.donations_to(recip)]
            for donor in data.donors_for(recip.id):
                row.append(str(donor))
                has_donation = True
            while len(row) < len(headings):
                row.append('')
            if has_donation:
                w.writerow(row)
    print(f"Wrote {path}")


def update_donor_view(args, data: State) -> None:
    """Create a report ready for mail merge of new donations."""
    path = Path(args.memory_dir, 'donation_view.csv')
    _backup_if_needed(path)

    by_donor: Dict[int, list[int]] = {}
    max_donations: int = 0
    for donation in data.new_this_session:
        if donation.donor == ASSOCIATION_ID:
            continue
        if donation.donor not in by_donor:
            by_donor[donation.donor] = []
        by_donor[donation.donor].append(donation.recipient)
        if len(by_donor[donation.donor]) > max_donations:
            max_donations = len(by_donor[donation.donor])

    headings = ['First', 'Last', 'Email', 'Pledge', 'Donor #']
    for i in range(max_donations):
        headings.append('Recipient ' + str(i + 1))
    with open(path, 'w', newline='') as outfile:
        w = csv.writer(outfile)
        w.writerow(headings)
        for donor in sorted(by_donor):
            columns = [data.donors[donor].first, data.donors[donor].last,
                       data.donors[donor].email, data.donors[donor].pledges,
                       data.donors[donor].id]
            for r in by_donor[donor]:
                recip = data.recipients[r]
                phys = '*' if recip.no_e_card else ''
                columns.append(
                    f'{recip.name}, {recip.address} {recip.home_email} {recip.phone} {recip.store}{phys}   ')
            while len(columns) < len(headings):
                columns.append('')
            w.writerow(columns)
    print(f"Wrote {path}")


def update_epaaa_view(args, data: State) -> None:
    """Create a report for EPA AA to handle sending out its donations."""
    path = Path(args.memory_dir, 'epaaa_view.csv')
    _backup_if_needed(path)

    donations = [x for x in data.new_this_session if x.donor == ASSOCIATION_ID]

    with open(path, 'w', newline='') as outfile:
        headings = ['Recipient #', 'Name', 'Address', 'Email', 'Phone', 'Store']
        w = csv.writer(outfile)
        w.writerow(headings)
        for d in donations:
            recip = data.recipients[d.recipient]
            columns = [str(recip.id), recip.name, recip.address, recip.home_email,
                       recip.phone, recip.store + ('*' if recip.no_e_card else '')]
            w.writerow(columns)
    print(f"Wrote {path}")
