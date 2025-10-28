"""
Test the functionality of individual parts of donation_match.
"""

import donation_data as dd

import copy
from dataclasses import dataclass, FrozenInstanceError
import datetime
import pathlib
import tempfile
import unittest


@dataclass(frozen=True)
class Foobar:
    name: str
    id: int
    value: float


class TestMiscFunctions(unittest.TestCase):
    def test_object_from_dict(self):
        foobar_fields = {'name': 'Name', 'id': 'A B C', 'value': 'Money'}
        foobar_types = {'id': int, 'value': float}
        mike = dd.object_from_dict(Foobar, foobar_fields, foobar_types, {'Name': 'Mike', 'A B C': '7', 'Money': '9'})
        self.assertEqual(mike.name, 'Mike')
        self.assertEqual(mike.id, 7)
        self.assertEqual(mike.value, 9.0)
        with self.assertRaises(KeyError):
            bad = dd.object_from_dict(Foobar, foobar_fields, foobar_types, {'Name': 'Bad', 'A B C': '3'})
        # Other fields don't cause trouble
        something = dd.object_from_dict(Foobar, foobar_fields, foobar_types, {'Name': 'Extra Guy',
                                                                              'A B C': '47', 'Money': '98.2',
                                                                              'Extraneous': 'ignored'})

    def test_text_to_bool(self):
        self.assertTrue(dd.text_to_bool('TRUE'))
        self.assertTrue(dd.text_to_bool('True'))
        self.assertTrue(dd.text_to_bool('true'))
        self.assertFalse(dd.text_to_bool('FALSE'))
        self.assertFalse(dd.text_to_bool('False'))
        self.assertFalse(dd.text_to_bool('false'))
        self.assertTrue(dd.mark_to_bool('X'))
        self.assertFalse(dd.mark_to_bool(''))
        with self.assertRaises(ValueError):
            dd.text_to_bool('Yes')
        with self.assertRaises(ValueError):
            dd.text_to_bool('No')
        with self.assertRaises(ValueError):
            dd.mark_to_bool('?')

    def test_normalize_names(self):
        test_cases = {
            'Mike Elkins': 'mike elkins',
            'Mike  ELKINS ': 'mike elkins',
            'Mr. Mike L. Elkins': 'mike elkins',
            "ms. farina peabody O'hara": 'farina ohara',
            'Gordo Zagnut-MarsBar, Jr': 'gordo zagnutmarsbar',
        }
        for name, expected in test_cases.items():
            self.assertEqual(dd.normalize_name(name), expected)

    def test_initial_int(self):
        test_cases = {
            '5': 5,
            '12': 12,
            ' 4': 4,
            ' 0 ': 0,
            '5x20': 5,
            '20 of $20': 20,
            '8,2,3': 8,
        }
        for text, expected in test_cases.items():
            self.assertEqual(dd.initial_int(text), expected)


class TestDonar(unittest.TestCase):
    def test_donor_parse(self):
        d1 = dd.Donor.from_dict({'Your First Name': 'Mike', 'Your Last Name': 'Elkins',
                                 'Personal Email Address': 'foo@example.com', 'number of pledges': '8',
                                 'comments': 'test', 'Respondent #': '25'})
        self.assertEqual(d1.first, 'Mike')
        self.assertEqual(d1.last, 'Elkins')
        self.assertEqual(d1.email, 'foo@example.com')
        self.assertEqual(d1.pledges, 8)
        self.assertEqual(d1.comments, 'test')
        self.assertEqual(d1.id, 25)
        with self.assertRaises(FrozenInstanceError):
            d1.id = 7


class TestRecipient(unittest.TestCase):
    def test_recipient_parse(self):
        r1 = dd.Recipient.from_dict({'Respondent #': '109', 'Validity': 'In process',
                                     'Employment Status': 'watching tv', 'EPA Email': 'aXz@Epa.Gov',
                                     'Name and Address': 'Howard The Duck, 400 Penslyvania Ave, Washington, DC',
                                     'Send physical cards': '',
                                     'Home Email': 'foo@bar.com', 'store for which you would': 'Petco',
                                     'Phone #': '867-5309', 'comments': 'quack'})
        self.assertEqual(r1.id, 109)
        self.assertFalse(r1.is_valid())
        self.assertEqual(r1.status, 'watching tv')
        self.assertEqual(r1.epa_email, 'axz@epa.gov')
        self.assertEqual(r1.name, 'Howard The Duck')
        self.assertEqual(r1.address, '400 Penslyvania Ave, Washington, DC')
        self.assertEqual(r1.home_email, 'foo@bar.com')
        self.assertEqual(r1.store, 'Petco')
        self.assertEqual(r1.phone, '867-5309')
        self.assertFalse(r1.no_e_card)
        self.assertEqual(r1.comments, 'quack')
        r2 = dd.Recipient.from_dict({'Respondent #': '110', 'Validity': 'True', 'Employment Status': 'eating candy',
                                     'EPA Email': 'ZXz@Epa.Gov', 'Name': 'Squirel Girl', 'Address': 'Stark Tower, NYC',
                                     'Send physical cards': 'X', 'Home Email': 'foo@bar.com',
                                     'store for which you would': 'Petco', 'Phone #': '867-5309',
                                     'comments': 'nuttin'})
        self.assertEqual(r2.id, 110)
        self.assertTrue(r2.is_valid())
        self.assertEqual(r2.status, 'eating candy')
        self.assertEqual(r2.epa_email, 'zxz@epa.gov')
        self.assertEqual(r2.name, 'Squirel Girl')
        self.assertEqual(r2.address, 'Stark Tower, NYC')
        self.assertEqual(r2.home_email, 'foo@bar.com')
        self.assertEqual(r2.store, 'Petco')
        self.assertEqual(r2.phone, '867-5309')
        self.assertTrue(r2.no_e_card)
        self.assertEqual(r2.comments, 'nuttin')

    def test_update_recipients(self):
        result = dd.UpdateRecipientResult(True, 0, list(), list(), list())
        next_id = 100

        def quick_recip(name: str, email: str):
            nonlocal next_id
            next_id += 1
            return dd.Recipient(id=next_id, valid='True', status='Current', epa_email=email,
                                name=name, address='123 baker st', home_email='',
                                store='Petco', phone='555-1234', no_e_card=False, comments='')
        s = dd.State()
        s.update_recipient(quick_recip('Adam Ant', 'foo@bar.gov'), result)
        s.update_recipient(quick_recip('Bob Barker', 'foo2@bar.gov'), result)
        s.update_recipient(quick_recip('Charlie Cheater', 'foo@bar.gov'), result)
        s.update_recipient(quick_recip('bob barker', 'foo3@bar.gov'), result)
        self.assertEqual(result.success, False)
        self.assertEqual(result.new_count, 3)
        self.assertEqual(result.errors, ['Duplicate email addresses used for Adam Ant and Charlie Cheater'])
        self.assertEqual(result.warnings, [
            'Duplicate recipient found:\n bob barker, Recipient # 104\nmight be\n Bob Barker, Recipient # 102'])


class Mock:
    pass


@dataclass
class MockThing:
    id: int
    first: str
    last: str

    def is_valid(this):
        return True


@dataclass
class MockDonation:
    donor: int
    recip: int


class TestDataSave(unittest.TestCase):
    def setUp(self):
        self.test_directory = tempfile.TemporaryDirectory()
        self.args = Mock()
        self.args.memory_dir = self.test_directory.name
        self.data = Mock()
        self.data.recipients = {100: MockThing(100, 'Mike', 'Elkins'),
                                101: MockThing(101, 'Chuck', 'Elkins')}
        self.data.donors = {1: MockThing(1, 'Aretha', 'Franklin'),
                            2: MockThing(2, 'Elvis', 'Presley')}
        self.data.donations = [MockDonation(1, 100), MockDonation(2, 101)]

    def tearDown(self):
        self.test_directory.cleanup()

    def test_save_state(self):
        # Create a new fixture
        # Write out some data.
        dd.save_state(self.args, self.data)
        self.check_data(self.data)

    def check_data(self, data):
        recips = dd.load_csv(pathlib.Path(self.args.memory_dir, 'recipients.csv'))
        self.assertEqual(len(recips), len(data.recipients))
        for r in recips:
            original = data.recipients[int(r['id'])]
            for k in r:
                self.assertEqual(r[k], str(getattr(original, k)))
        donors = dd.load_csv(pathlib.Path(self.args.memory_dir, 'donors.csv'))
        self.assertEqual(len(donors), len(data.donors))
        for d in donors:
            original = data.donors[int(d['id'])]
            for k in d:
                self.assertEqual(d[k], str(getattr(original, k)))
        donations = dd.load_csv(pathlib.Path(self.args.memory_dir, 'donations.csv'))
        self.assertEqual(len(donations), len(data.donations))
        for i in range(len(donations)):
            original = data.donations[i]
            for k in donations[i]:
                self.assertEqual(donations[i][k], str(getattr(original, k)))

    def test_multi_save(self):
        dd.save_state(self.args, self.data)
        self.check_data(self.data)
        self.data.recipients[102] = MockThing(102, 'Cheryl', 'Elkins')
        self.data.donors[2].last = 'Costello'
        dd.save_state(self.args, self.data)
        self.check_data(self.data)

    def test_save_failure(self):
        sub_cases = {
            'recipients.tmp': False,
            'donors.tmp': False,
            'donations.tmp': False,
            'recipients.csv': False,
            'donors.csv': False,
            'donations.csv': False,
            'recipients.bak': False,
            'donors.bak': False,
            'donations.bak': False,
        }
        original_data = self.data
        changed_data = copy.deepcopy(self.data)
        changed_data.recipients[102] = MockThing(102, 'Cheryl', 'Elkins')
        changed_data.donors[2].last = 'Costello'
        for subcase in sub_cases:
            print(f"\nSubcase {subcase}")
            with self.subTest(filename=subcase):
                fn = pathlib.Path(self.args.memory_dir, subcase)
                delete_at_end = False
                dd.save_state(self.args, original_data)
                self.check_data(original_data)
                if not fn.exists():
                    fn.touch()
                    delete_at_end = True
                with fn.open('r') as f:
                    with self.assertRaises((PermissionError, FileExistsError)):
                        dd.save_state(self.args, changed_data)
                    if sub_cases[subcase]:
                        self.check_data(changed_data)
                    else:
                        self.check_data(original_data)
                if delete_at_end:
                    fn.unlink()

    def test_donation_parse_standard(self):
        state = dd.State()
        state.recipients = self.data.recipients
        state.load_donations([{'donor': 1, 'recipient': 101, 'date': '2025-10-17'},
                              {'donor': 2, 'recipient': 101, 'date': '2025-10-17'}])
        self.assertEqual(len(state.donations), 2)
        self.assertEqual(state.donations[0].donor, 1)
        self.assertEqual(state.donations[0].recipient, 101)
        self.assertEqual(state.donations[0].date, datetime.date(2025, 10, 17))

        self.assertEqual(state.donations[1].donor, 2)
        self.assertEqual(state.donations[1].recipient, 101)
        self.assertEqual(state.donations[1].date, datetime.date(2025, 10, 17))

    def test_donation_parse_excel(self):
        """If we load and save in excel, the donation file
        gets its dates reformatted"""
        state = dd.State()
        state.recipients = self.data.recipients
        state.load_donations([{'donor': 1, 'recipient': 101, 'date': '10/17/2025'},
                              {'donor': 2, 'recipient': 101, 'date': '10/17/2025'}])
        self.assertEqual(len(state.donations), 2)
        self.assertEqual(state.donations[0].donor, 1)
        self.assertEqual(state.donations[0].recipient, 101)
        self.assertEqual(state.donations[0].date, datetime.date(2025, 10, 17))

        self.assertEqual(state.donations[1].donor, 2)
        self.assertEqual(state.donations[1].recipient, 101)
        self.assertEqual(state.donations[1].date, datetime.date(2025, 10, 17))


if __name__ == '__main__':
    unittest.main()
