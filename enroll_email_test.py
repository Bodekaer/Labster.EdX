import os
import string
import sys
import subprocess
import random
import time

domains = ["labster.com", ]
letters = string.ascii_lowercase[:12]


def generate_random_emails(email_number):
    """
    Generate random emails
    """
    for i in range(email_number):
        name = ''.join(random.choice(letters) for i in range(10))
        email_str = name + '@' + random.choice(domains)

        yield email_str


if __name__ == "__main__":

    base_dir = os.path.dirname(__file__)
    file_name = (os.path.join(base_dir, 'email_test.txt'))

    number = int(raw_input("Number of emails: "))
    course_id = raw_input("Course ID: ")

    with open(file_name, "w") as file:
        for email in generate_random_emails(number):
            file.write(email + "\n")

    start_time = time.time()
    os.system(
        'sudo -u www-data /edx/bin/python.edxapp {base_dir}/manage.py lms enroll_students {file_name} -c "{course_id}" '
        '--settings=labster > {base_dir}/stdout_enroll_students.log 2> {base_dir}/stderr_enroll_students.log'.format(
            file_name=file_name, course_id=str(course_id), base_dir=base_dir
        )
    )

    sys.stdout.write("Execution time: %s seconds, total: %s students \n" % (time.time() - start_time, number))
