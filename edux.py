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
        yield (a['title'], a['href'])


def extract_announcements(fileobj):
    '''Extracts all announcements

    Returns list of pairs (timestmap, message)
    '''
    bs = BeautifulSoup(fileobj.read(), 'html.parser')
    announcements = bs.select(
        '#ctl00_ContentPlaceHolder1_grdOgloszenia_ctl00 tbody')[0]
    for announcement in announcements.select('tr'):
        (timestamp, message, ) = announcement.select('td')
        timestamp = datetime.strptime(timestamp.text, '%Y-%m-%d').date()
        message = re.sub(r'\s+', ' ', message.text)
        yield message


def main():
    p = '/Users/michal/Downloads/edux'

    with open(os.path.join(p, 'Premain.aspx.html')) as fileobj:
        extract_courses(fileobj)

    with open(os.path.join(p, 'Announcements.aspx.html')) as fileobj:
        extract_announcements(fileobj)


if __name__ == '__main__':
    main()
