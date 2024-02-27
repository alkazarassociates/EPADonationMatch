"""
Test the functionality of individual parts of donation_match.
"""

import donation_data as dd
from dataclasses import dataclass, FrozenInstanceError
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


class TestDonar(unittest.TestCase):
    def test_donor_parse(self):
        d1 = dd.Donor.from_dict({'First': 'Mike', 'Last': 'Elkins', 'Email': 'foo@example.com', 'Pledge units': '8',
                                 'Comments': 'test', 'Donor #': '25'})
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
        r1 = dd.Recipient.from_dict({'Recipient #': '109', 'Valid?': 'In process', 'Status': 'watching tv',
                                     'EPA Email': 'aXz@Epa.Gov',
                                     'Name': 'Howard The Duck, 400 Penslyvania Ave, Washington, DC', 'No e-card': '',
                                     'Home Email': 'foo@bar.com', 'Selected': 'Petco', 'Phone #': '867-5309',
                                     'Comments': 'quack'})
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
        r2 = dd.Recipient.from_dict({'Recipient #': '110', 'Valid?': 'True', 'Status': 'eating candy',
                                     'EPA Email': 'ZXz@Epa.Gov', 'Name': 'Squirel Girl', 'Address': 'Stark Tower, NYC',
                                     'No e-card': 'X', 'Home Email': 'foo@bar.com', 'Selected': 'Petco',
                                     'Phone #': '867-5309', 'Comments': 'nuttin'})
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


if __name__ == '__main__':
    unittest.main()
