"""update_recipients: Given a csv file list of all recipients,
add new ones to the program.  Part of donation_match."""

import argparse
import sys

import donation_data


def report(result: donation_data.UpdateRecipientResult, data: donation_data.State) -> str:
    if not result.success:
        ret = "Errors detected--did not update recipients!"
        if result.errors:
            ret += "---Errors---"
            for e in result.errors:
                ret += "\n"
                ret += e
        if result.warnings:
            ret += "---Warnings---"
            for w in result.warnings:
                ret += "\n"
                ret += w
        return ret
    assert len(result.errors) == 0
    ret = f"Added {result.new_count} recipients, for a total of {len(data.recipients)}.\n"
    if result.warnings:
        ret += "\n"
        ret += "---Warnings---"
        for w in result.warnings:
            ret += "\n"
            ret += w
    return ret


def write_validation_report(args, result: donation_data.UpdateRecipientResult, data: donation_data.State) -> None:
    # TODO Implement
    pass


def Main():
    parser = argparse.ArgumentParser(
        prog='update_recipients',
        description="Update our list of recipients")
    parser.add_argument('recipients')
    donation_data.add_args(parser)
    args = parser.parse_args()

    data = donation_data.load_state(args)

    result = data.update_recipients(donation_data.load_csv(args.recipients))

    if result.success:
        donation_data.save_state(args, data)
        write_validation_report(args, result, data)

    print(report(result, data))


if __name__ == '__main__':
    sys.exit(Main())
