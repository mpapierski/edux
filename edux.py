import os
import re
from datetime import datetime

from bs4 import BeautifulSoup


def extract_courses(fileobj):
    '''Extracts all courses.

    Returns list of pairs (name, url)
    '''
    bs = BeautifulSoup(fileobj.read(), 'html.parser')
    courses = bs.select('#ctl00_ContentPlaceHolder1_grdKursy_ctl00 tbody')[0]
    for tr in courses.select('tr'):
        a = tr.select('a')[0]
        (course_id, ) = re.findall(
            r'^https://edux\.pjwstk\.edu\.pl/req\.aspx\?id=(\d+)$', a['href'])
        course_id = int(course_id)
        yield (course_id, a['title'], a['href'])


def extract_announcements(fileobj):
    '''Extracts all announcements

    Returns list of pairs (timestmap, message)
    '''
    bs = BeautifulSoup(fileobj.read(), 'html.parser')
    announcements = bs.select(
        '#ctl00_ContentPlaceHolder1_grdOgloszenia_ctl00 tbody')[0]

    result = []

    for announcement in announcements.select('tr'):
        (timestamp, message, ) = announcement.select('td')
        timestamp = datetime.strptime(timestamp.text, '%Y-%m-%d').date()
        message = re.sub(r'\s+', ' ', message.text)
        result.append((timestamp, message))
    return reversed(result)


def main():
    p = '/Users/michal/Downloads/edux'

    with open(os.path.join(p, 'Premain.aspx.html')) as fileobj:
        for (course_id, title, href) in extract_courses(fileobj):
            print (course_id, title, href)

    with open(os.path.join(p, 'Announcements.aspx.html')) as fileobj:
        for (timestamp, message) in extract_announcements(fileobj):
            print '---'
            print timestamp
            print message


if __name__ == '__main__':
    main()
