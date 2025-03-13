"""mail_merge: Send emails to all donors"""

import argparse
import csv
from email.message import EmailMessage
from email.headerregistry import Address
import os
from pathlib import Path
import smtplib
import sys

import donation_data


def read_template() -> str:
    this_directory = Path(__file__).parent
    with open(Path(this_directory, 'email_template.html'), 'r', encoding='utf-8') as f:
        return f.read()


def send_email(destination: Address, subject_text: str,
               from_address: Address, template: str,
               data: dict, client: smtplib.SMTP):
    msg = EmailMessage()
    msg['Subject'] = subject_text
    msg['From'] = from_address
    msg['To'] = destination

    data['GreetingLine'] = 'Dear ' + data['First'] + ','
    data['RecipientRows'] = html_for_recipients(data)

    msg.set_content(plain_text_from_template(template, data))
    msg.add_alternative(html_from_template(template, data), subtype='html')

    client.send_message(msg)


def plain_text_from_template(template, data):
    html = html_from_template(template, data)
    # First, just strip out the <body>.
    body_start = html.find('<body')
    body_start = html.find('>', body_start) + 1
    body_end = html.find('</body>', body_start)
    body_text = html[body_start:body_end]
    ret = ''
    for element in parse_html(body_text):
        ret += to_plain_text(*element)
    return ret


def html_from_template(template, data):
    # Only substitute in <body>...</body>
    pos = template.find('<body') + 5
    ret = template[:pos]
    while True:
        replacement_start = template.find('{', pos)
        if replacement_start == -1:
            ret += template[pos:]
            break
        ret += template[pos:replacement_start]
        pos = template.find('}', replacement_start)+1
        key = template[replacement_start+1:pos-1].strip()
        ret += data[key]
    return ret


def html_for_recipients(data: dict) -> str:
    ret = ''
    for recipient_key in [
            'Recipient 1',
            'Recipient 2',
            'Recipient 3',
            'Recipient 4',
            'Recipient 5',
            'Recipient 6',
            'Recipient 7',
            'Recipient 8',
            'Recipient 9',
            'Recipient 10',
            ]:
        if data[recipient_key]:
            line = data[recipient_key]
            at_sign = line.find('@')
            email_boundary = at_sign
            while line[email_boundary] != ' ':
                email_boundary -= 1
            email_end = line.find(' ', email_boundary + 1)
            name_and_address = line[:email_boundary]
            email = line[email_boundary:email_end].strip()
            card = line[email_end:].strip()
            ret += '<tr>\n<td>' + name_and_address + '</td>'
            ret += '<td>' + email + '</td>'
            ret += '<td>' + card + '</td>\n</tr>\n'
    return ret


def parse_html(text: str):
    pos = 0
    while pos < len(text):
        elem_start = text.find('<', pos)
        if elem_start == -1:
            yield '', {}, text[pos:]
            return
        elem_end = text.find('>', elem_start)
        element_details = text[elem_start+1:elem_end].split(' ', )
        element_name = element_details[0]
        attributes = {}
        for x in element_details[1:]:
            assert '=' in x
            key, value = x.split('=', 1)
            attributes[key] = unquote(value)
        termination = text.find('</' + element_name + '>', elem_end)
        if termination == -1:
            termination = elem_end
        yield element_name, attributes, text[elem_end + 1:termination]
        pos = termination + 2 + len(element_name) + 1


class TableHeader:
    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text


class TableData:
    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text


class TableRow:
    def __init__(self, items):
        self.items = items


class ListData:
    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text


def to_plain_text(element_name: str, attributes: dict, contents: str) -> str | list:
    if element_name != '':
        text_contents: str | list = ''
        for e in parse_html(contents):
            inner = to_plain_text(*e)
            if type(inner) is str:
                text_contents += inner
            else:
                if type(text_contents) is str:
                    text_contents = []
                text_contents.append(inner)
        contents = text_contents
    else:
        return contents
    if element_name == 'small':
        return contents
    if element_name == 'p':
        return html_paragraph(attributes, contents)
    if element_name == 'a' or element_name == 'b' or element_name == 'u':
        return contents
    if element_name == 'th':
        return TableHeader(contents)
    if element_name == 'td':
        return TableData(contents)
    if element_name == 'tr':
        return TableRow(contents)
    if element_name == 'table':
        return html_table(attributes, contents)
    if element_name == 'li':
        return ListData(contents)
    if element_name == 'ol':
        return html_list(attributes, contents)
    if element_name == 'br':
        return '\n'
    print(element_name, attributes, contents)
    assert False


def unquote(text: str) -> str:
    if text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


LINE_LENGTH = 80


def html_paragraph(attributes: dict, contents: str) -> str:
    align = attributes.get('align', 'left')
    padding = '    '
    if attributes.get('class', '') == 'lefty':
        passing = ''
    if align == 'left':
        return padding + contents + '\n'
    elif align == 'center':
        return ' ' * ((LINE_LENGTH - len(contents)) // 2) + contents + '\n'
    elif align == 'right':
        return ' ' * (LINE_LENGTH - len(contents)) + contents + '\n'
    else:
        assert False


def html_table(attributes, contents):
    column_width = {}
    for row in contents:
        if isinstance(row, TableRow):
            for col_num, entry in enumerate(row.items):
                if col_num not in column_width or column_width[col_num] < len(str(entry)):
                    column_width[col_num] = len(str(entry))
    ret = ''
    for row in contents:
        if isinstance(row, TableRow):
            for col_num, entry in enumerate(row.items):
                ret += str(entry) + ' ' * (column_width[col_num] - len(str(entry))) + ' '
            ret += '\n'
    return ret


def html_list(attributes, contents):
    ret = ''
    count = 1
    for row in contents:
        if isinstance(row, ListData):
            ret += '\n'
            ret += '    '
            ret += str(count) + '. '
            count += 1
            ret += str(row)
    ret += '\n'
    return ret


def get_smtp_server(service: str) -> str:
    return {
        'aol.com': 'smtp.aol.com',
    }[service]


def Main():
    parser = argparse.ArgumentParser(
        prog='mail_merge',
        description="Email our donors")
    parser.add_argument('-e', '--email-user', default='epaalumni@aol.com')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--test-connection', action='store_true')
    parser.add_argument('-d', '--test-destination')
    parser.add_argument('--stop-early', action='store_true')
    donation_data.add_args(parser)
    args = parser.parse_args()
    password = os.environ['EPA_MAIL_MERGE_PASSWORD']

    user, service = args.email_user.split('@', 1)

    with smtplib.SMTP_SSL(get_smtp_server(service), 465) as client:
        if args.verbose:
            client.set_debuglevel(1)
        client.login(user, password)
        # End early if all we want to do is test the connection.
        if args.test_connection:
            return

        donor_report = donation_data.load_csv(Path(args.memory_dir, 'donation_view.csv'))

        email_template = read_template()
        subject_text = "Your EPAAA Donations"
        from_address = Address(user)

        for donor in donor_report:
            dest = donor['Email']
            if args.test_destination:
                dest = args.test_destination
            send_email(Address(dest), subject_text, from_address, email_template, donor, client)
            if args.stop_early:
                break


if __name__ == '__main__':
    sys.exit(Main())
