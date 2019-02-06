"""
Script to test performance of enroll students command.
"""
import os
import string
import subprocess
import sys
import random
import time


BASE_DIR = os.path.dirname(os.path.dirname(__file__))

def generate_random_emails(number):
    """
    Generate random emails
    """
    domains = ["labster.com", ]
    letters = string.ascii_uppercase + string.digits
    sizes = [5, 7, 9, 12, 15]

    for i in range(number):
        size = random.choice(sizes)
        name = 'test-' + ''.join(random.choice(letters) for char in range(size))
        email_str = name + '@' +random.choice(domains)

        yield email_str


if __name__ == "__main__":
    # check permission template email
    tmp_mako_path = '/tmp/mako_lms/'
    target_path = os.path.join(
        tmp_mako_path, random.choice(os.listdir(tmp_mako_path)), 'emails', 'enroll_email_enrolledmessage.txt.py'
    )

    if not os.access(target_path, os.R_OK):
        raise IOError("Permission denied: '%s'" % tmp_mako_path)

    file_name = (os.path.join(BASE_DIR, 'email_test.txt'))
    email_number = int(raw_input("Number of emails: "))
    course_id = str(raw_input("Course ID: "))

    with open(file_name, "w") as file:
        for email in generate_random_emails(email_number):
            file.write(email + "\n")
    cmd = [
        'python',
        BASE_DIR + 'manage.py',
        'lms',
        'enroll_students',
        file_name,
        '-c',
        course_id,
        '--settings=labster',
    ]
    start_time = time.time()
    subprocess.call(cmd)
    sys.stdout.write("Execution time: %s seconds, total: %s students \n" % (time.time() - start_time, email_number))
