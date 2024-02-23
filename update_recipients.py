"""update_recipients: Given a csv file list of all recipients,
add new ones to the program.  Part of donation_match."""

import argparse
import sys

import donation_data

def Main():
    parser = argparse.ArgumentParser(
        prog='update_recipients',
        description="Update our list of recipients")
    parser.add_argument('recipients')
    donation_data.add_args(parser)
    args = parser.parse_args()

    data = donation_data.load_state(args)

    data.update_recipients(donation_data.load_csv(args.recipients))

    donation_data.save_state(args, data)

if __name__ == '__main__':
    sys.exit(Main())
