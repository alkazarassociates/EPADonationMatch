"""
Test the functionality of individual parts of donation_match.
"""

import donation_match as dm
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
        foobar_types = {'id': int, 'value': float }
        mike = dm.object_from_dict(Foobar, foobar_fields, foobar_types, {'Name': 'Mike', 'A B C': '7', 'Money': '9'})
        self.assertEqual(mike.name, 'Mike')
        self.assertEqual(mike.id, 7)
        self.assertEqual(mike.value, 9.0)
        with self.assertRaises(KeyError):
            bad = dm.object_from_dict(Foobar, foobar_fields, foobar_types, {'Name': 'Bad', 'A B C': '3'})
        # Other fields don't cause trouble
        something = dm.object_from_dict(Foobar, foobar_fields, foobar_types, {'Name': 'Extra Guy', 'A B C': '47', 'Money': '98.2', 'Extraneous': 'ignored'})

    def test_text_to_bool(self):
        self.assertTrue(dm.text_to_bool('TRUE'))
        self.assertTrue(dm.text_to_bool('True'))
        self.assertTrue(dm.text_to_bool('true'))
        self.assertFalse(dm.text_to_bool('FALSE'))
        self.assertFalse(dm.text_to_bool('False'))
        self.assertFalse(dm.text_to_bool('false'))
        self.assertTrue(dm.mark_to_bool('X'))
        self.assertFalse(dm.mark_to_bool(''))
        with self.assertRaises(ValueError):
            dm.text_to_bool('Yes')
        with self.assertRaises(ValueError):
            dm.text_to_bool('No')
        with self.assertRaises(ValueError):
            dm.mark_to_bool('?')

    def test_normalize_names(self):
        test_cases = {
            'Mike Elkins': 'mike elkins',
            'Mike  ELKINS ': 'mike elkins',
            'Mr. Mike L. Elkins': 'mike elkins',
            "ms. farina peabody O'hara": 'farina ohara',
            'Gordo Zagnut-MarsBar, Jr': 'gordo zagnutmarsbar',
        }
        for name, expected in test_cases.items():
            self.assertEqual(dm.normalize_name(name), expected)

    def test_donor_parse(self):
        d1 = dm.Donor.from_dict({'First': 'Mike', 'Last': 'Elkins', 'Email': 'foo@example.com', 'Pledge units': '8', 'Comments': 'test', 'Donor #': '25'})
        self.assertEqual(d1.first, 'Mike')
        self.assertEqual(d1.last, 'Elkins')
        self.assertEqual(d1.email, 'foo@example.com')
        self.assertEqual(d1.pledges, 8)
        self.assertEqual(d1.comments, 'test')
        self.assertEqual(d1.id, 25)
        with self.assertRaises(FrozenInstanceError):
            d1.id = 7

    def test_recipient_parse(self):
        r1 = dm.Recipient.from_dict({'Recipient #': '109', 'Valid?': 'In process', 'Status': 'watching tv', 'EPA Email': 'aXz@Epa.Gov',
                                     'Name': 'Howard The Duck, 400 Penslyvania Ave, Washington, DC', 'No e-card': '', 'Home Email': 'foo@bar.com',
                                     'Selected': 'Petco', 'Phone #': '867-5309', 'Comments': 'quack'})
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
        r2 = dm.Recipient.from_dict({'Recipient #': '110', 'Valid?': 'True', 'Status': 'eating candy', 'EPA Email': 'ZXz@Epa.Gov',
                                     'Name': 'Squirel Girl', 'Address': 'Stark Tower, NYC', 'No e-card': 'X', 'Home Email': 'foo@bar.com',
                                     'Selected': 'Petco', 'Phone #': '867-5309', 'Comments': 'nuttin'})
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
        
if __name__ == '__main__':
    unittest.main()
