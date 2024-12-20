"""update_donors: Given a csv file list of all donors,
add new ones to the program.  Part of donation_match."""

import argparse
import sys

import donation_data


def report(result: donation_data.UpdateDonorResult, data: donation_data.State) -> str:
    if not result.success:
        ret = "Errors detected--did not update donors!"
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
    ret = f"Added {result.new_count} donors, for a total of {len(data.donors)}.\n"
    if result.warnings:
        ret += "\n"
        ret += "---Warnings---"
        for w in result.warnings:
            ret += "\n"
            ret += w
    return ret


def write_validation_report(args, result: donation_data.UpdateDonorResult, data: donation_data.State) -> None:
    # TODO Implement
    pass


def Main():
    parser = argparse.ArgumentParser(
        prog='update_recipients',
        description="Update our list of donors")
    parser.add_argument('donors')
    donation_data.add_args(parser)
    args = parser.parse_args()

    data = donation_data.load_state(args)

    result = data.update_donors(donation_data.load_csv(args.donors))

    if result.success:
        donation_data.save_state(args, data)

    print(report(result, data))
    return 0 if result.success else 1


if __name__ == '__main__':
    sys.exit(Main())
